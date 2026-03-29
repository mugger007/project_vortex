"""Integration tests for FastAPI endpoints."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app


@pytest.fixture
def client():
    """Provide a test client for the FastAPI app."""
    return TestClient(app)


class TestAPIEndpoints:
    """Test FastAPI route handlers."""

    def test_healthcheck_endpoint(self, client):
        """Test GET /api/health returns status ok."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "ts" in data

    @patch("app.services.orchestrator.Orchestrator.run_scan_cycle")
    def test_scan_run_endpoint(self, mock_scan, client):
        """Test POST /api/scan/run triggers a scan and returns recommendations."""
        from app.models.schemas import RecommendationPayload, RecommendationCard
        from datetime import datetime, UTC

        mock_payload = RecommendationPayload(
            recommendation="Sell",
            confidence=75,
            explanation="Test recommendation",
            suggested_strike=500.0,
            suggested_delta=-0.3,
            estimated_theta=0.05,
            estimated_vega=0.1,
            scorecard=75,
        )
        mock_card = RecommendationCard(
            symbol="SPY",
            option_symbol="SPY240419C00500000",
            created_at=datetime.now(UTC),
            data=mock_payload,
            rejected=False,
        )
        mock_scan.return_value = [mock_card]

        response = client.post("/api/scan/run")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["items"]) == 1

    @patch("app.db.repositories.ScanRepository.list_recommendations")
    def test_recommendations_endpoint(self, mock_list, client):
        """Test GET /api/recommendations returns a list of recommendations."""
        from app.models.entities import Recommendation
        from datetime import datetime, UTC

        mock_rec = MagicMock(spec=Recommendation)
        mock_rec.id = 1
        mock_rec.symbol = "SPY"
        mock_rec.option_symbol = "SPY240419C00500000"
        mock_rec.recommendation = "Sell"
        mock_rec.confidence = 75
        mock_rec.scorecard = 75
        mock_rec.reason = "Test reason"
        mock_rec.created_at = datetime.now(UTC)
        mock_rec.rejected = False

        mock_list.return_value = [mock_rec]

        response = client.get("/api/recommendations?limit=50")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["items"][0]["symbol"] == "SPY"

    @patch("app.db.repositories.ScanRepository.list_recommendations")
    def test_recommendations_with_custom_limit(self, mock_list, client):
        """Test GET /api/recommendations with custom limit parameter."""
        mock_list.return_value = []

        response = client.get("/api/recommendations?limit=100")
        assert response.status_code == 200

        # Verify limit was passed to repository
        mock_list.assert_called_with(limit=100)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
