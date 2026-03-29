from __future__ import annotations

from datetime import UTC, datetime

from structlog import get_logger

from app.analysis.event_risk import EventRiskAnalyzer
from app.analysis.market_regime import MarketRegimeAnalyzer
from app.analysis.overreaction import OverreactionAnalyzer
from app.analysis.trends import TrendAnalyzer
from app.analysis.volatility import VolatilityAnalyzer
from app.cache.redis_client import RedisCache
from app.clients.gemini_client import GeminiClient
from app.clients.massive_client import MassiveClient
from app.clients.moomoo_client import MoomooClient
from app.config import get_settings
from app.db.repositories import ScanRepository
from app.db.session import get_db_session
from app.models.schemas import AnalysisBundle, RecommendationCard
from app.risk.portfolio_engine import PortfolioRiskEngine
from app.scanner.monitoring_scanner import MonitoringScanner
from app.services.alerts import AlertService
from app.synthesis.recommendation_engine import RecommendationEngine

logger = get_logger(__name__)


class Orchestrator:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.massive = MassiveClient()
        self.moomoo = MoomooClient()
        self.gemini = GeminiClient()
        self.cache = RedisCache()
        self.alerts = AlertService()
        self.watchlist = ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]

    def run_scan_cycle(self) -> list[RecommendationCard]:
        cards: list[RecommendationCard] = []
        started = datetime.now(UTC)
        with get_db_session() as db:
            repo = ScanRepository(db)
            scan_run = repo.create_scan_run(started_at=started, metadata_json={"interval": self.settings.scan_interval_minutes})

            scanner = MonitoringScanner(self.massive, self.cache, repo)
            overreaction = OverreactionAnalyzer(self.massive, self.gemini)
            volatility = VolatilityAnalyzer(self.massive)
            trends = TrendAnalyzer(self.massive)
            events = EventRiskAnalyzer(self.massive)
            regime = MarketRegimeAnalyzer(self.massive)
            risk_engine = PortfolioRiskEngine(self.moomoo, self.massive)
            recommender = RecommendationEngine(self.gemini)

            try:
                positions = self.moomoo.get_option_positions()
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
            except Exception as exc:
                repo.add_audit_log(
                    scan_run_id=scan_run.id,
                    stage="moomoo_ingestion",
                    level="ERROR",
                    message="failed to ingest positions",
                    payload_json={"error": str(exc)},
                )

            total_candidates = 0
            for symbol in self.watchlist:
                try:
                    candidates = scanner.scan_symbol(symbol)
                    total_candidates += len(candidates)
                except Exception as exc:
                    logger.exception("scan_symbol_failed", symbol=symbol)
                    repo.add_audit_log(
                        scan_run_id=scan_run.id,
                        stage="scan_symbol",
                        level="ERROR",
                        message="scan symbol failed",
                        payload_json={"symbol": symbol, "error": str(exc)},
                    )
                    continue

                for candidate in candidates:
                    over_score, over_text = overreaction.analyze(candidate.symbol)
                    hv_pct = volatility.analyze(candidate.symbol)
                    trend_score, trend_summary = trends.analyze(candidate.symbol)
                    event_flag, event_reason = events.analyze(candidate.symbol)
                    regime_score, regime_summary = regime.analyze(candidate.symbol)

                    analysis = AnalysisBundle(
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

                    risk = risk_engine.evaluate(
                        symbol=candidate.symbol,
                        candidate_delta=float(candidate.snapshot.extra.get("greeks", {}).get("delta", 0.0) or 0.0),
                        candidate_vega=float(candidate.snapshot.extra.get("greeks", {}).get("vega", 0.0) or 0.0),
                    )

                    recommendation = recommender.recommend(candidate, analysis, risk)
                    rejected = (recommendation.recommendation == "Avoid") or (not risk.approved)
                    rejection_reason = None if not rejected else risk.reason if not risk.approved else analysis.event_risk_reason

                    repo.save_recommendation(
                        {
                            "scan_run_id": scan_run.id,
                            "symbol": candidate.symbol,
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
                                "risk": risk.model_dump(),
                                "recommendation": recommendation.model_dump(),
                            },
                            "created_at": datetime.now(UTC),
                        }
                    )

                    card = RecommendationCard(
                        symbol=candidate.symbol,
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

        return cards
