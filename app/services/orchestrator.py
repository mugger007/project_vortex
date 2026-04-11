"""End-to-end orchestration of scanning, analysis, synthesis, and persistence."""

from __future__ import annotations

from datetime import UTC, datetime

from structlog import get_logger

from app.analysis.event_risk import EventRiskAnalyzer
from app.analysis.market_regime import MarketRegimeAnalyzer
from app.analysis.overreaction import OverreactionAnalyzer
from app.analysis.trends import TrendAnalyzer
from app.analysis.volatility import VolatilityAnalyzer
from app.clients.finnhub_client import FinnhubClient
from app.clients.gemini_client import GeminiClient
from app.clients.massive_client import MassiveClient
from app.clients.moomoo_client import MoomooClient
from app.clients.yfinance_client import YFinanceClient
from app.config import get_settings
from app.db.repositories import ScanRepository
from app.db.session import get_db_session
from app.models.schemas import AnalysisBundle, RecommendationCard
# from app.risk.portfolio_engine import PortfolioRiskEngine
from app.scanner.monitoring_scanner import MonitoringScanner
from app.services.alerts import AlertService
from app.synthesis.recommendation_engine import RecommendationEngine

logger = get_logger(__name__)


class Orchestrator:
    def __init__(self) -> None:
        """Create the end-to-end scan orchestrator and its provider clients."""
        self.settings = get_settings()
        self.massive = MassiveClient()
        self.moomoo = MoomooClient()
        self.yfinance = YFinanceClient()
        self.finnhub = None
        if self.settings.finnhub_api_key:
            try:
                self.finnhub = FinnhubClient()
                logger.info("orchestrator_finnhub_client_initialized")
            except (ImportError, ValueError) as exc:
                logger.warning("orchestrator_finnhub_client_unavailable", error=str(exc))
        self.gemini = GeminiClient()
        self.alerts = AlertService()
        self.watchlist = getattr(self.settings, "watchlist", ["SNOW"])

    def _to_moomoo_symbol(self, symbol: str) -> str:
        """Normalize a bare ticker into the Moomoo-prefixed symbol format."""
        # Moomoo expects market-prefixed symbols like US.SNOW.
        return symbol if "." in symbol else f"US.{symbol}"

    def _to_analysis_symbol(self, symbol: str) -> str:
        """Normalize a provider-prefixed symbol into a bare analysis ticker."""
        # Massive/analyzers expect bare symbols like SNOW.
        return symbol.split(".", 1)[1] if "." in symbol else symbol

    def run_scan_cycle(self) -> list[RecommendationCard]:
        """Run the full scan, analysis, synthesis, and persistence workflow."""
        cards: list[RecommendationCard] = []
        started = datetime.now(UTC)
        logger.info("orchestrator_scan_cycle_started", started_at=started.isoformat(), watchlist_size=len(self.watchlist))
        with get_db_session() as db:
            repo = ScanRepository(db)
            scan_run = repo.create_scan_run(started_at=started, metadata_json={"interval": self.settings.scan_interval_minutes})

            scanner = MonitoringScanner(self.moomoo, self.massive, repo)
            overreaction = OverreactionAnalyzer(self.yfinance, self.finnhub, self.gemini)
            volatility = VolatilityAnalyzer(self.massive)
            trends = TrendAnalyzer(self.massive)
            events = EventRiskAnalyzer(self.massive)
            regime = MarketRegimeAnalyzer()
            # Risk engine temporarily disabled.
            # risk_engine = PortfolioRiskEngine(self.moomoo, self.massive)
            recommender = RecommendationEngine(self.gemini)

            try:
                positions = self.moomoo.get_option_positions()
                logger.info("orchestrator_positions_loaded", positions_count=len(positions))
                repo.clear_position_snapshots()
                for p in positions:
                    repo.save_position_snapshot(
                        {
                            "account_id": "default",
                            "symbol": str(p.get("symbol", "")),
                            "option_symbol": str(p.get("symbol", "")),
                            "quantity": float(p.get("qty", p.get("quantity", 0.0)) or 0.0),
                            "delta": float(p.get("delta", 0.0) or 0.0),
                            "vega": float(p.get("vega", 0.0) or 0.0),
                            "market_value": float(p.get("market_val", p.get("market_value", 0.0)) or 0.0),
                            "raw_json": p,
                            "created_at": datetime.now(UTC),
                        }
                    )
                logger.info("orchestrator_positions_saved", positions_count=len(positions))
            except Exception as exc:
                logger.exception("orchestrator_positions_ingestion_failed")
                repo.add_audit_log(
                    scan_run_id=scan_run.id,
                    stage="moomoo_ingestion",
                    level="ERROR",
                    message="failed to ingest positions",
                    payload_json={"error": str(exc)},
                )

            total_candidates = 0
            all_candidates = []
            for symbol in self.watchlist:
                moomoo_symbol = self._to_moomoo_symbol(symbol)
                try:
                    candidates = scanner.scan_symbol(moomoo_symbol)
                    total_candidates += len(candidates)
                    logger.info(
                        "orchestrator_symbol_scanned",
                        symbol=symbol,
                        moomoo_symbol=moomoo_symbol,
                        candidates=len(candidates),
                    )
                except Exception as exc:
                    logger.exception("scan_symbol_failed", symbol=symbol, moomoo_symbol=moomoo_symbol)
                    repo.add_audit_log(
                        scan_run_id=scan_run.id,
                        stage="scan_symbol",
                        level="ERROR",
                        message="scan symbol failed",
                        payload_json={"symbol": symbol, "moomoo_symbol": moomoo_symbol, "error": str(exc)},
                    )
                    continue

                if not candidates:
                    logger.info("orchestrator_no_candidates", symbol=symbol, moomoo_symbol=moomoo_symbol)
                    continue

                all_candidates.extend(candidates)

            analysis_cache = {}
            recommendation_cache = {}
            symbol_metrics_cache = {}
            regime_score = 0.0
            regime_summary = ""
            if all_candidates:
                regime_score, regime_summary = regime.analyze()

            for candidate in all_candidates:
                analysis_symbol = self._to_analysis_symbol(candidate.symbol)
                cache_key = (analysis_symbol, candidate.option_type)
                if cache_key in analysis_cache:
                    continue

                if analysis_symbol in symbol_metrics_cache:
                    hv_pct, trend_score, trend_summary, event_flag, event_reason = symbol_metrics_cache[analysis_symbol]
                else:
                    hv_pct = volatility.analyze(analysis_symbol)
                    trend_score, trend_summary = trends.analyze(analysis_symbol)
                    event_flag, event_reason = events.analyze(analysis_symbol)
                    symbol_metrics_cache[analysis_symbol] = (
                        hv_pct,
                        trend_score,
                        trend_summary,
                        event_flag,
                        event_reason,
                    )

                over_score, over_text = overreaction.analyze(analysis_symbol, candidate.option_type)

                analysis_cache[cache_key] = AnalysisBundle(
                    overreaction_score=over_score,
                    overreaction_explanation=over_text,
                    hv_percentile=hv_pct,
                    trend_score=trend_score,
                    trend_summary=trend_summary,
                    event_risk_flag=event_flag,
                    event_risk_reason=event_reason,
                    regime_score=regime_score,
                    regime_summary=regime_summary,
                )

            for candidate in all_candidates:
                candidate_symbol = self._to_analysis_symbol(candidate.symbol)
                analysis_cache_key = (candidate_symbol, candidate.option_type)
                recommendation_cache_key = candidate.option_symbol
                analysis = analysis_cache[analysis_cache_key]

                # Portfolio risk evaluation temporarily disabled.
                risk = None

                if recommendation_cache_key in recommendation_cache:
                    recommendation = recommendation_cache[recommendation_cache_key]
                else:
                    recommendation = recommender.recommend(candidate, analysis, risk)
                    recommendation_cache[recommendation_cache_key] = recommendation

                rejected = recommendation.recommendation == "Avoid"
                rejection_reason = None if not rejected else analysis.event_risk_reason
                logger.info(
                    "orchestrator_recommendation_generated",
                    symbol=candidate_symbol,
                    option_type=candidate.option_type,
                    moomoo_symbol=candidate.symbol,
                    option_symbol=candidate.option_symbol,
                    recommendation=recommendation.recommendation,
                    confidence=recommendation.confidence,
                    scorecard=recommendation.scorecard,
                    rejected=rejected,
                )

                repo.save_recommendation(
                    {
                        "scan_run_id": scan_run.id,
                        "symbol": candidate_symbol,
                        "option_symbol": candidate.option_symbol,
                        "recommendation": recommendation.recommendation,
                        "confidence": recommendation.confidence,
                        "scorecard": recommendation.scorecard,
                        "reason": recommendation.explanation,
                        "suggested_strike": recommendation.suggested_strike,
                        "suggested_delta": recommendation.suggested_delta,
                        "estimated_theta": recommendation.estimated_theta,
                        "estimated_vega": recommendation.estimated_vega,
                        "rejected": rejected,
                        "full_payload_json": {
                            "candidate": candidate.model_dump(),
                            "analysis": analysis.model_dump(),
                            "risk": (risk.model_dump() if risk is not None else {"disabled": True}),
                            "recommendation": recommendation.model_dump(),
                        },
                        "created_at": datetime.now(UTC),
                    }
                )

                card = RecommendationCard(
                    symbol=candidate_symbol,
                    option_symbol=candidate.option_symbol,
                    created_at=datetime.now(UTC),
                    data=recommendation,
                    rejected=rejected,
                    rejection_reason=rejection_reason,
                )
                cards.append(card)
                repo.add_audit_log(
                    scan_run_id=scan_run.id,
                    stage="recommendation",
                    message="recommendation generated",
                    payload_json=card.model_dump(),
                )
                self.alerts.notify_high_confidence(card)

            repo.complete_scan_run(
                scan_run.id,
                finished_at=datetime.now(UTC),
                status="success",
                metadata_json={
                    "watchlist_size": len(self.watchlist),
                    "filtered_candidates": total_candidates,
                    "recommendations": len(cards),
                },
            )
            logger.info(
                "orchestrator_scan_cycle_completed",
                scan_run_id=scan_run.id,
                watchlist_size=len(self.watchlist),
                filtered_candidates=total_candidates,
                recommendations=len(cards),
            )

        return cards

