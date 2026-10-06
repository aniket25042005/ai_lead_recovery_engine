from fastapi.testclient import TestClient


def test_tenant_cannot_access_other_tenant_analysis(client: TestClient):
    # 1. Tenant A creates and analyzes a lead
    tenant_a_payload = {
        "tenant_id": "tenant_alpha",
        "lead_id": "lead_alpha_99",
        "customer": {"name": "Alpha Customer", "phone": "+1234567890"},
        "lead": {"source": "whatsapp", "status": "contacted"},
        "conversation": [
            {"role": "customer", "message": "Interested in private enterprise license."},
        ],
    }

    res_create = client.post("/api/v1/leads/analyze", json=tenant_a_payload)
    assert res_create.status_code == 200

    # 2. Tenant A can access its own analysis
    res_a = client.get(
        "/api/v1/leads/lead_alpha_99/analysis",
        headers={"X-Tenant-ID": "tenant_alpha"},
    )
    assert res_a.status_code == 200
    assert res_a.json()["lead_score"] is not None

    # 3. Tenant B attempts to access Tenant A's lead analysis -> MUST BE 404
    res_b = client.get(
        "/api/v1/leads/lead_alpha_99/analysis",
        headers={"X-Tenant-ID": "tenant_beta"},
    )
    assert res_b.status_code == 404
    assert "No analysis found for lead" in res_b.json()["detail"]


def test_tenant_cannot_trigger_follow_up_for_other_tenant_lead(client: TestClient):
    tenant_a_payload = {
        "tenant_id": "tenant_alpha",
        "lead_id": "lead_alpha_100",
        "customer": {"name": "Alpha Lead", "phone": "+1234567891"},
        "lead": {"source": "whatsapp", "status": "contacted"},
        "conversation": [
            {"role": "customer", "message": "Need pricing for 10 users."},
        ],
    }
    client.post("/api/v1/leads/analyze", json=tenant_a_payload)

    # Tenant B tries to trigger follow up
    res_b = client.post(
        "/api/v1/leads/lead_alpha_100/follow-up",
        headers={"X-Tenant-ID": "tenant_beta"},
    )
    assert res_b.status_code == 404


def test_mismatched_tenant_header_and_body_rejected(client: TestClient):
    payload = {
        "tenant_id": "tenant_alpha",
        "lead_id": "lead_alpha_101",
        "customer": {"name": "Test", "phone": "+1234567892"},
        "lead": {"source": "whatsapp", "status": "contacted"},
        "conversation": [{"role": "customer", "message": "Hello"}],
    }

    response = client.post(
        "/api/v1/leads/analyze",
        json=payload,
        headers={"X-Tenant-ID": "tenant_different"},
    )
    assert response.status_code == 400
    assert "Mismatched Tenant" in response.json()["detail"]
