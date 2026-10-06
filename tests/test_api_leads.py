from fastapi.testclient import TestClient


def test_analyze_lead_with_pdf_example_input(client: TestClient):
    """
    Tests POST /api/v1/leads/analyze with the exact example input from the screening task doc.
    """
    payload = {
        "tenant_id": "business_001",
        "lead_id": "lead_1024",
        "customer": {"name": "Arun Kumar", "phone": "+919876543210"},
        "lead": {
            "source": "whatsapp",
            "status": "contacted",
            "created_at": "2026-09-20",
            "last_contacted_at": "2026-09-25",
        },
        "conversation": [
            {"role": "customer", "message": "I am interested in your CRM."},
            {"role": "agent", "message": "How many users do you need?"},
            {"role": "customer", "message": "Around 25 users. What is the pricing?"},
        ],
    }

    response = client.post("/api/v1/leads/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Verify exact required fields
    required_fields = [
        "lead_score",
        "priority",
        "intent",
        "stage",
        "summary",
        "next_best_action",
        "follow_up_channel",
        "follow_up_message",
        "do_not_contact",
    ]
    for field in required_fields:
        assert field in data, f"Missing expected field: {field}"

    assert data["priority"] == "high"
    assert data["intent"] == "purchase"
    assert data["stage"] == "pricing_interest"
    assert data["do_not_contact"] is False
    assert data["lead_score"] == 86
    assert "Arun" in data["follow_up_message"]


def test_get_analysis_and_generate_follow_up(client: TestClient):
    # 1. Analyze first
    payload = {
        "tenant_id": "business_001",
        "lead_id": "lead_2048",
        "customer": {"name": "Meera Sen", "phone": "+919811223344"},
        "lead": {"source": "whatsapp", "status": "contacted"},
        "conversation": [
            {"role": "customer", "message": "Can someone demonstrate how the reports work tomorrow?"},
        ],
    }
    client.post("/api/v1/leads/analyze", json=payload)

    # 2. Get latest analysis
    get_res = client.get(
        "/api/v1/leads/lead_2048/analysis",
        headers={"X-Tenant-ID": "business_001"},
    )
    assert get_res.status_code == 200
    assert get_res.json()["priority"] == "high"

    # 3. Generate follow-up
    fu_res = client.post(
        "/api/v1/leads/lead_2048/follow-up",
        headers={"X-Tenant-ID": "business_001"},
        json={"custom_instructions": "Highlight our export to Excel feature"},
    )
    assert fu_res.status_code == 200
    fu_data = fu_res.json()
    assert fu_data["status"] == "ready"
    assert fu_data["dispatched_mock"] is True
    assert "Excel" in fu_data["follow_up_message"]


def test_analyze_validation_errors(client: TestClient):
    # Empty conversation
    invalid_payload = {
        "tenant_id": "business_001",
        "lead_id": "lead_9999",
        "conversation": [],
    }
    response = client.post("/api/v1/leads/analyze", json=invalid_payload)
    assert response.status_code == 422
    assert "Validation Error" in response.json()["error"]
