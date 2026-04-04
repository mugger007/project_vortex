from __future__ import annotations

from app.analysis.market_regime import MarketRegimeAnalyzer


def test_market_regime_mid_vol_bull(monkeypatch) -> None:
    analyzer = MarketRegimeAnalyzer()

    def fake_intraday(symbol: str) -> tuple[float, float]:
        if symbol == "^VIX":
            return 20.0, -1.0
        return 6000.0, 1.2

    monkeypatch.setattr(analyzer, "_get_index_intraday_metrics", fake_intraday)
    monkeypatch.setattr(analyzer, "_get_index_prev_close_change_pct", lambda s: 0.5)

    score, summary = analyzer.analyze()

    assert score == 65.0
    assert "Regime=mid-vol/bull" in summary
    assert "VIX=" in summary
    assert "SPX%=" in summary


def test_market_regime_high_vol_bear(monkeypatch) -> None:
    analyzer = MarketRegimeAnalyzer()

    def fake_intraday(symbol: str) -> tuple[float, float]:
        if symbol == "^VIX":
            return 31.0, 2.0
        return 5900.0, -0.7

    monkeypatch.setattr(analyzer, "_get_index_intraday_metrics", fake_intraday)
    monkeypatch.setattr(analyzer, "_get_index_prev_close_change_pct", lambda s: -0.3)

    score, summary = analyzer.analyze()

    assert score == 15.0
    assert "Regime=high-vol/bear" in summary


def test_market_regime_no_vix_data_defaults_neutral(monkeypatch) -> None:
    analyzer = MarketRegimeAnalyzer()

    def fake_intraday(symbol: str) -> tuple[float, float]:
        if symbol == "^VIX":
            return 0.0, 0.0
        return 6000.0, 0.0

    monkeypatch.setattr(analyzer, "_get_index_intraday_metrics", fake_intraday)
    monkeypatch.setattr(analyzer, "_get_index_prev_close_change_pct", lambda s: 0.0)

    score, summary = analyzer.analyze()

    assert score == 55.0
    assert "Regime=mid-vol/neutral" in summary
