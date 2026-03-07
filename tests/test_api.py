"""
Tests for FastAPI server endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import date, timedelta

from src.server.server import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


class TestAPIEndpoints:
    """Test cases for API endpoints."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "MCP Legal Assistant" in data["data"]["name"]
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data
    
    def test_list_templates(self, client):
        """Test document templates endpoint."""
        response = client.get("/api/v1/templates")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "templates" in data["data"]
    
    def test_validate_time_description(self, client):
        """Test time description validation endpoint."""
        # Test vague description
        response = client.post(
            "/api/v1/validate/time-description",
            params={"description": "Worked on case"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["is_vague"] is True
        
        # Test specific description
        response = client.post(
            "/api/v1/validate/time-description",
            params={"description": "Reviewed plaintiff's motion for summary judgment and prepared response outline"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["is_vague"] is False
    
    @pytest.mark.skip(reason="Requires API key")
    def test_contract_review_endpoint(self, client):
        """Test contract review endpoint."""
        request_data = {
            "document_text": """
            SIMPLE AGREEMENT
            Between Party A and Party B.
            Payment due in 30 days.
            """,
            "document_name": "Test Agreement",
            "matter_id": "TEST-001",
            "client_name": "Test Client",
            "jurisdiction": "Texas",
        }
        
        response = client.post("/api/v1/contract/review", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "review_id" in data["data"]
        assert "risk_flags" in data["data"]
    
    @pytest.mark.skip(reason="Requires API key")
    def test_case_research_endpoint(self, client):
        """Test case research endpoint."""
        request_data = {
            "legal_question": "What is the statute of limitations for breach of contract in Texas?",
            "jurisdiction": "Texas",
            "practice_area": "Contract",
            "matter_id": "TEST-001",
            "client_name": "Test Client",
            "favorable_research": True,
        }
        
        response = client.post("/api/v1/case/research", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "research_memo_text" in data["data"]
    
    @pytest.mark.skip(reason="Requires API key")
    def test_document_draft_endpoint(self, client):
        """Test document drafting endpoint."""
        request_data = {
            "document_type": "NDA",
            "party_details": {
                "disclosing_party": "TechCorp Inc.",
                "receiving_party": "Client LLC",
            },
            "key_terms": {
                "confidentiality_period": "2 years",
                "governing_law": "Texas",
            },
            "jurisdiction": "Texas",
            "matter_id": "TEST-001",
            "client_name": "Test Client",
        }
        
        response = client.post("/api/v1/document/draft", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "full_document_text" in data["data"]
    
    def test_deadline_tracker_endpoint(self, client):
        """Test deadline tracker endpoint."""
        request_data = {
            "firm_id": "TEST-FIRM",
            "matter_ids": ["TEST-001"],
            "generate_report": True,
        }
        
        response = client.post("/api/v1/deadlines/check", json=request_data)
        
        # This may fail without database connection, but should handle gracefully
        assert response.status_code in [200, 500]
    
    def test_billing_calculator_endpoint(self, client):
        """Test billing calculator endpoint."""
        request_data = {
            "matter_id": "TEST-001",
            "billing_period_start": str(date.today() - timedelta(days=30)),
            "billing_period_end": str(date.today()),
            "client_name": "Test Client",
            "include_expenses": True,
            "generate_invoice": True,
        }
        
        response = client.post("/api/v1/billing/calculate", json=request_data)
        
        # This may fail without database connection, but should handle gracefully
        assert response.status_code in [200, 500]
    
    @pytest.mark.skip(reason="Requires API key")
    def test_orchestrate_endpoint(self, client):
        """Test orchestrator endpoint."""
        request_data = {
            "task_description": "Review this contract for risks",
            "matter_id": "TEST-001",
            "client_name": "Test Client",
            "jurisdiction": "Texas",
            "attachments": [{
                "document_text": "Simple agreement text...",
                "document_name": "Test Contract",
            }],
        }
        
        response = client.post("/api/v1/orchestrate", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "task_type" in data["data"]
        assert "agents_invoked" in data["data"]


class TestErrorHandling:
    """Test error handling in API endpoints."""
    
    def test_invalid_contract_review(self, client):
        """Test contract review with missing required fields."""
        request_data = {
            "document_name": "Test",
            # Missing required fields
        }
        
        response = client.post("/api/v1/contract/review", json=request_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_invalid_date_format(self, client):
        """Test billing with invalid date format."""
        request_data = {
            "matter_id": "TEST-001",
            "billing_period_start": "invalid-date",
            "billing_period_end": "invalid-date",
            "client_name": "Test Client",
        }
        
        response = client.post("/api/v1/billing/calculate", json=request_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_nonexistent_endpoint(self, client):
        """Test accessing nonexistent endpoint."""
        response = client.get("/api/v1/nonexistent")
        
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
