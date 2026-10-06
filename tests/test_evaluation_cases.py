from fastapi.testclient import TestClient
from app.services.queue_service import QueueService


def test_case_a_50_employees_asks_pricing(client: TestClient):
    """
    Case A: 50 employees + asks for pricing
    Expected: High priority / purchase intent / pricing_interest
    """
    payload = {
        "tenant_id": "tenant_eval_a",
        "lead_id": "lead_eval_a",
        "customer": {"name": "Suresh Patel", "phone": "+919876543211"},
        "lead": {"source": "whatsapp", "status": "contacted"},
        "conversation": [
            {"role": "customer", "message": "Hi, we have 50 employees and need a solution."},
            {"role": "agent", "message": "Great! We can accommodate your team."},
            {"role": "customer", "message": "What is the pricing for 50 users?"},
        ],
    }

    response = client.post("/api/v1/leads/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["priority"] == "high"
    assert data["intent"] == "purchase"
    assert data["stage"] == "pricing_interest"
    assert data["lead_score"] >= 80
    assert data["do_not_contact"] is False
    assert data["follow_up_message"] is not None


def test_case_b_only_asks_what_product_does(client: TestClient):
    """
    Case B: Only asks what the product does
    Expected: Low priority / general inquiry
    """
    payload = {
        "tenant_id": "tenant_eval_b",
        "lead_id": "lead_eval_b",
        "customer": {"name": "Priya Sharma", "phone": "+919876543212"},
        "lead": {"source": "website", "status": "new"},
        "conversation": [
            {"role": "customer", "message": "What does the product do?"},
        ],
    }

    response = client.post("/api/v1/leads/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["priority"] == "low"
    assert data["intent"] == "inquiry"
    assert data["do_not_contact"] is False
    assert data["lead_score"] < 50


def test_case_c_requests_demo_or_call_tomorrow(client: TestClient):
    """
    Case C: Requests a demo/call tomorrow
    Expected: Demo/call as next action
    """
    payload = {
        "tenant_id": "tenant_eval_c",
        "lead_id": "lead_eval_c",
        "customer": {"name": "Rahul Verma", "phone": "+919876543213"},
        "lead": {"source": "whatsapp", "status": "contacted"},
        "conversation": [
            {"role": "customer", "message": "Can we schedule a demo call tomorrow?"},
        ],
    }

    response = client.post("/api/v1/leads/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "demo" in data["next_best_action"].lower() or "call" in data["next_best_action"].lower()
    assert data["priority"] == "high"
    assert data["do_not_contact"] is False


def test_case_d_customer_says_stop(client: TestClient):
    """
    Case D: Customer says: "STOP. Don't message me again."
    Expected: do_not_contact=true; no follow-up
    """
    payload = {
        "tenant_id": "tenant_eval_d",
        "lead_id": "lead_eval_d",
        "customer": {"name": "Amit Saxena", "phone": "+919876543214"},
        "lead": {"source": "whatsapp", "status": "contacted"},
        "conversation": [
            {"role": "agent", "message": "Hi Amit, checking in regarding our services."},
            {"role": "customer", "message": "STOP. Don't message me again."},
        ],
    }

    response = client.post("/api/v1/leads/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["do_not_contact"] is True
    assert data["follow_up_message"] is None
    assert data["follow_up_channel"] in ("none", "none")

    # Also test follow-up endpoint directly to ensure it is blocked
    follow_up_res = client.post(
        f"/api/v1/leads/{payload['lead_id']}/follow-up",
        headers={"X-Tenant-ID": payload["tenant_id"]},
    )
    assert follow_up_res.status_code == 200
    fu_data = follow_up_res.json()
    assert fu_data["status"] == "blocked_opt_out"
    assert fu_data["do_not_contact"] is True
    assert fu_data["follow_up_message"] is None
    assert fu_data["dispatched_mock"] is False


def test_case_e_same_webhook_event_submitted_twice(client: TestClient):
    """
    Case E: Same webhook event submitted twice
    Expected: One job / one processing result (Idempotency)
    """
    webhook_payload = {
        "event_id": "webhook_evt_unique_101",
        "tenant_id": "tenant_eval_e",
        "lead_id": "lead_eval_e",
        "customer": {"name": "Kavita Reddy", "phone": "+919876543215"},
        "lead": {"source": "whatsapp", "status": "contacted"},
        "conversation": [
            {"role": "customer", "message": "I want to purchase the CRM for 20 users."},
        ],
    }

    # 1. First submission
    resp1 = client.post(
        "/api/v1/webhooks/leads",
        json=webhook_payload,
        headers={"X-Idempotency-Key": "key_e_101"},
    )
    assert resp1.status_code == 202
    data1 = resp1.json()
    assert data1["status"] == "accepted"
    job_id_1 = data1["job_id"]

    # Process background task synchronously for test verification
    QueueService.process_webhook_task(job_id_1)

    # 2. Duplicate submission with same payload & idempotency key
    resp2 = client.post(
        "/api/v1/webhooks/leads",
        json=webhook_payload,
        headers={"X-Idempotency-Key": "key_e_101"},
    )
    # Must return 200 or 202 without creating a new job
    assert resp2.status_code in (200, 202)
    data2 = resp2.json()
    assert data2["status"] in ("already_processed", "already_processing")
    assert data2["job_id"] == job_id_1
    assert "Duplicate" in data2["message"]
