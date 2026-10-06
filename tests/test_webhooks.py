from fastapi.testclient import TestClient
from app.services.queue_service import QueueService


def test_webhook_processing_flow(client: TestClient):
    payload = {
        "event_id": "evt_hook_test_1",
        "tenant_id": "tenant_hook_01",
        "lead_id": "lead_hook_01",
        "customer": {"name": "Test User", "phone": "+919999988888"},
        "lead": {"source": "whatsapp", "status": "contacted"},
        "conversation": [
            {"role": "customer", "message": "Need to understand pricing for 50 users."},
        ],
    }

    response = client.post("/api/v1/webhooks/leads", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    job_id = data["job_id"]

    # Execute background worker task
    QueueService.process_webhook_task(job_id)

    # Now verify the analysis was recorded and can be fetched via GET endpoint
    get_res = client.get(
        f"/api/v1/leads/{payload['lead_id']}/analysis",
        headers={"X-Tenant-ID": payload["tenant_id"]},
    )
    assert get_res.status_code == 200
    res_data = get_res.json()
    assert res_data["priority"] == "high"
    assert res_data["intent"] == "purchase"
