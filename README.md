# Zizzet AI Lead Recovery Engine

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%20%2F%20SQLAlchemy%202.0-336791.svg)](https://www.postgresql.org/)
[![Tests](https://img.shields.io/badge/Tests-16%20Passed%20(100%25)-brightgreen.svg)]()

An enterprise-grade, multi-tenant AI backend service designed to identify inactive or high-intent leads, analyze multi-turn conversation histories with an LLM, and recommend prescriptive next-best actions and personalized recovery follow-up messages.

---

## 📑 Table of Contents
- [1. Architecture & Design](#1-architecture--design)
- [2. Features & Technical Highlights](#2-features--technical-highlights)
- [3. Evaluation Cases Verification (Cases A–E)](#3-evaluation-cases-verification-cases-ae)
- [4. Environment Variables](#4-environment-variables)
- [5. Setup & Installation](#5-setup--installation)
  - [Local Development Setup](#local-development-setup)
  - [Docker & Docker Compose Setup](#docker--docker-compose-setup)
- [6. API Reference & Usage Guide](#6-api-reference--usage-guide)
  - [1. POST /api/v1/leads/analyze](#1-post-apiv1leadsanalyze)
  - [2. GET /api/v1/leads/{lead_id}/analysis](#2-get-apiv1leadslead_idanalysis)
  - [3. POST /api/v1/leads/{lead_id}/follow-up](#3-post-apiv1leadslead_idfollow-up)
  - [4. POST /api/v1/webhooks/leads](#4-post-apiv1webhooksleads)
- [7. AI Approach & LLM Abstraction](#7-ai-approach--llm-abstraction)
- [8. Multi-Tenancy & Idempotency](#8-multi-tenancy--idempotency)
- [9. Testing](#9-testing)
- [10. Assumptions & Limitations](#10-assumptions--limitations)

---

## 1. Architecture & Design

```
                     +---------------------------------------+
                     |         API Clients / Webhooks        |
                     +---------------------------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |           FastAPI Gateway             |
                     |  - Multi-tenant Dependency Scoping    |
                     |  - Pydantic v2 Schema Validation      |
                     |  - Global Exception Handling & CORS   |
                     +---------------------------------------+
                            /                         \
         (Sync: POST /analyze)               (Async: POST /webhooks/leads)
                          /                             \
                         v                               v
         +-----------------------------+     +-------------------------------+
         |  LeadRecoveryService (Sync) |     |    Idempotent Event Store     |
         |  - Opt-out Pre-guardrail    |     |    (SHA-256 / Event Keys)     |
         |  - Prompt Engine (v1.0)     |     +-------------------------------+
         |  - LLM Provider Abstraction |                     |
         |  - Pydantic Output Guard    |                     v
         +-----------------------------+     +-------------------------------+
                         |                   |       Async Worker Queue      |
                         |                   |  - Exponential Backoff Retry  |
                         |                   |  - Background AI Processing   |
                         |                   +-------------------------------+
                         \                                  /
                          \                                /
                           v                              v
                  +------------------------------------------------+
                  |         PostgreSQL (SQLAlchemy 2.0)            |
                  |   - Tables: tenants, leads, conversations,     |
                  |     lead_analyses, webhook_events              |
                  |   - Composite Indexes: (tenant_id, lead_id)    |
                  +------------------------------------------------+
                                           |
                                           v
                  +------------------------------------------------+
                  |         Mock WhatsApp Messaging Provider       |
                  |   - Simulated message dispatcher               |
                  +------------------------------------------------+
```

---

## 2. Features & Technical Highlights

- **Python + FastAPI Backend**: High-performance, modular routing with lifespan database management and automated OpenAPI/Swagger documentation.
- **PostgreSQL Database Design**: Structured relational schema built with **SQLAlchemy 2.0**, composite indexes `(tenant_id, id)` and `(tenant_id, lead_id)` for high throughput and zero tenant leakage.
- **LLM Provider Abstraction**: Pluggable provider interface supporting:
  - **Google Gemini** (`google-genai` SDK with structured JSON mode)
  - **OpenAI** (`gpt-4o-mini` with json_object mode)
  - **Mock LLM Provider** (Deterministic, high-fidelity offline mode for testing all evaluation cases without API cost or external network dependencies)
- **Retry with Exponential Backoff**: LLM API calls are wrapped using `tenacity` with exponential backoff (`min=2s`, `max=8s`).
- **Strict Opt-Out & Compliance Guardrails**: If a customer says `STOP`, `unsubscribe`, or requests to cease communication, `do_not_contact=True` is strictly set, and no follow-up message is generated.
- **Multi-Tenant Security**: Strict isolation enforced across all database queries and endpoints. Tenant A cannot view or trigger follow-ups for Tenant B's leads (returns `404 Not Found`).
- **Webhook Idempotency**: Duplicate webhook payloads (using provided `X-Idempotency-Key`, `event_id`, or deterministic SHA-256 payload hash) are intercepted, returning existing results without duplicate job execution.
- **Mock WhatsApp Messaging Provider**: Clean abstraction dispatching simulated WhatsApp messages, tracking message IDs, delivery statuses, and audit timestamps.

---

## 3. Evaluation Cases Verification (Cases A–E)

All 5 evaluation cases specified in the screening task are verified and covered by automated tests in `tests/test_evaluation_cases.py`:

| Case | Scenario | Expected Behavior | Automated Test Status |
|---|---|---|---|
| **Case A** | 50 employees + asks for pricing | `priority: "high"`, `intent: "purchase"`, `stage: "pricing_interest"` | ✅ `PASSED` |
| **Case B** | Only asks what the product does | `priority: "low"`, `intent: "inquiry"`, `stage: "discovery"` | ✅ `PASSED` |
| **Case C** | Requests a demo/call tomorrow | `next_best_action`: Schedule demo/call | ✅ `PASSED` |
| **Case D** | Customer says: `"STOP. Don't message me again."` | `do_not_contact: true`, `follow_up_message: None` | ✅ `PASSED` |
| **Case E** | Same webhook event submitted twice | Exactly one processing execution; idempotent response | ✅ `PASSED` |

---

## 4. Environment Variables

Create your `.env` file based on `.env.example`:

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg2://postgres:postgres@localhost:5432/zizzet_recovery` |
| `SQLITE_FALLBACK_URL` | Fallback SQLite URL if PostgreSQL is offline | `sqlite:///./zizzet_recovery.db` |
| `FALLBACK_TO_SQLITE_ON_DB_ERROR` | Auto-fallback to SQLite for zero-friction local tests | `true` |
| `LLM_PROVIDER` | Active LLM provider (`mock`, `gemini`, or `openai`) | `mock` |
| `GEMINI_API_KEY` | Google Gemini API key | `""` |
| `GEMINI_MODEL` | Gemini model name | `gemini-2.5-flash` |
| `OPENAI_API_KEY` | OpenAI API key | `""` |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4o-mini` |
| `LLM_MAX_RETRIES` | Max retry attempts with exponential backoff | `3` |
| `PROMPT_VERSION` | Version identifier for prompt tracking | `v1.0` |
| `LOG_LEVEL` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |

---

## 5. Setup & Installation

### Local Development Setup

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd "zizzet project"
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # On Windows PowerShell
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # On Linux/macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   ```

5. **Start the application**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   Interactive Swagger documentation will be available at: **http://localhost:8000/docs**

---

### Docker & Docker Compose Setup

Launch both the PostgreSQL database and the FastAPI application with a single command:

```bash
docker compose up --build -d
```

- API Server: `http://localhost:8000`
- PostgreSQL Port: `5432`
- Healthcheck Endpoint: `http://localhost:8000/health`

---

## 6. API Reference & Usage Guide

### 1. `POST /api/v1/leads/analyze`
Synchronously analyzes a lead profile and conversation history.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/leads/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "business_001",
    "lead_id": "lead_1024",
    "customer": {
      "name": "Arun Kumar",
      "phone": "+919876543210"
    },
    "lead": {
      "source": "whatsapp",
      "status": "contacted",
      "created_at": "2026-09-20",
      "last_contacted_at": "2026-09-25"
    },
    "conversation": [
      { "role": "customer", "message": "I am interested in your CRM." },
      { "role": "agent", "message": "How many users do you need?" },
      { "role": "customer", "message": "Around 25 users. What is the pricing?" }
    ]
  }'
```

**Response (200 OK):**
```json
{
  "lead_score": 86,
  "priority": "high",
  "intent": "purchase",
  "stage": "pricing_interest",
  "summary": "Customer is evaluating CRM pricing for a 25-member team.",
  "next_best_action": "Send pricing and schedule a demo",
  "follow_up_channel": "whatsapp",
  "follow_up_message": "Hi Arun Kumar! Just following up on your CRM requirement for your team. Here is our pricing breakdown, and I'd love to walk you through a quick demo.",
  "do_not_contact": false
}
```

---

### 2. `GET /api/v1/leads/{lead_id}/analysis`
Retrieves the latest recovery recommendation for a lead. Enforces tenant isolation via header.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/leads/lead_1024/analysis" \
  -H "X-Tenant-ID: business_001"
```

**Response (200 OK):**
```json
{
  "lead_score": 86,
  "priority": "high",
  "intent": "purchase",
  "stage": "pricing_interest",
  "summary": "Customer is evaluating CRM pricing for a 25-member team.",
  "next_best_action": "Send pricing and schedule a demo",
  "follow_up_channel": "whatsapp",
  "follow_up_message": "Hi Arun Kumar! Just following up...",
  "do_not_contact": false
}
```

---

### 3. `POST /api/v1/leads/{lead_id}/follow-up`
Generates and dispatches a personalized follow-up message via mock WhatsApp. Blocks action if customer opted out.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/leads/lead_1024/follow-up" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: business_001" \
  -d '{
    "custom_instructions": "Mention our 10% discount for annual plans"
  }'
```

**Response (200 OK):**
```json
{
  "tenant_id": "business_001",
  "lead_id": "lead_1024",
  "follow_up_channel": "whatsapp",
  "follow_up_message": "Hi Arun Kumar! Just following up on your CRM requirement for your team... Note: Mention our 10% discount for annual plans",
  "do_not_contact": false,
  "status": "ready",
  "dispatched_mock": true
}
```

---

### 4. `POST /api/v1/webhooks/leads`
Receives asynchronous lead events, stores the event, enforces idempotency, and enqueues background processing.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/webhooks/leads" \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: evt_lead_1024_01" \
  -d '{
    "tenant_id": "business_001",
    "lead_id": "lead_1024",
    "customer": { "name": "Arun Kumar", "phone": "+919876543210" },
    "lead": { "source": "whatsapp", "status": "contacted" },
    "conversation": [
      { "role": "customer", "message": "Can we schedule a demo call tomorrow?" }
    ]
  }'
```

**Response (202 Accepted on first call):**
```json
{
  "status": "accepted",
  "job_id": "4b684cb3-00f7-4a0b-9df0-e170c0fb9b07",
  "idempotency_key": "evt_lead_1024_01",
  "message": "Lead webhook event accepted for asynchronous background processing.",
  "result": null
}
```

**Response (200 OK on duplicate call — Case E):**
```json
{
  "status": "already_processed",
  "job_id": "4b684cb3-00f7-4a0b-9df0-e170c0fb9b07",
  "idempotency_key": "evt_lead_1024_01",
  "message": "Duplicate event detected. Event status is 'completed'. No new job queued.",
  "result": { ... }
}
```

---

## 7. AI Approach & LLM Abstraction

1. **System Prompt & Versioning**: Versioned system instructions (`v1.0`) define strict CRM domain reasoning and schema constraints.
2. **Schema Validation**: Output is validated against Pydantic v2 `LeadRecoveryOutput` with bounds (`lead_score: 0–100`, strict priority enum).
3. **Opt-Out Pre & Post Guardrails**: Both deterministic regex rules (`detect_opt_out`) and system prompt instructions guarantee that customer opt-outs (STOP, unsubscribe) automatically trigger `do_not_contact=True` and clear follow-up messages.
4. **Retry Logic**: Configured with `tenacity` exponential backoff to handle rate limits and transient cloud service errors.

---

## 8. Multi-Tenancy & Idempotency

- **Tenant Isolation**:
  - Every table includes `tenant_id` foreign keys and composite indexes.
  - Queries explicitly filter by `(tenant_id, lead_id)`.
  - Attempts by Tenant B to query Tenant A's lead data return `404 Not Found`, preventing data leakage.
- **Idempotency Architecture**:
  - Webhooks enforce a unique constraint on `(tenant_id, idempotency_key)` in the `webhook_events` table.
  - If a webhook with the same key or payload hash arrives, the existing event status and result are returned without re-executing background AI workers.

---

## 9. Testing

The project includes 16 automated tests covering API endpoints, validation errors, the 5 evaluation scenarios, LLM provider error handling, and multi-tenant isolation.

To run the automated test suite:
```bash
pytest -v
```

Output:
```
tests/test_api_leads.py::test_analyze_lead_with_pdf_example_input PASSED
tests/test_api_leads.py::test_get_analysis_and_generate_follow_up PASSED
tests/test_api_leads.py::test_analyze_validation_errors PASSED
tests/test_evaluation_cases.py::test_case_a_50_employees_asks_pricing PASSED
tests/test_evaluation_cases.py::test_case_b_only_asks_what_product_does PASSED
tests/test_evaluation_cases.py::test_case_c_requests_demo_or_call_tomorrow PASSED
tests/test_evaluation_cases.py::test_case_d_customer_says_stop PASSED
tests/test_evaluation_cases.py::test_case_e_same_webhook_event_submitted_twice PASSED
tests/test_llm_providers.py::test_mock_llm_provider_behavior PASSED
tests/test_llm_providers.py::test_gemini_provider_malformed_response_handling PASSED
tests/test_llm_providers.py::test_openai_provider_malformed_response_handling PASSED
tests/test_llm_providers.py::test_llm_factory_selection PASSED
tests/test_tenant_isolation.py::test_tenant_cannot_access_other_tenant_analysis PASSED
tests/test_tenant_isolation.py::test_tenant_cannot_trigger_follow_up_for_other_tenant_lead PASSED
tests/test_tenant_isolation.py::test_mismatched_tenant_header_and_body_rejected PASSED
tests/test_webhooks.py::test_webhook_processing_flow PASSED

======================= 16 passed in 0.34s =======================
```

---

## 10. Assumptions & Limitations

1. **Messaging Provider**: WhatsApp messaging is simulated using a mock dispatcher that logs dispatches and returns delivery receipts, matching task instructions.
2. **Background Queue**: Implemented using FastAPI's asynchronous background tasks backed by persistent database job tracking and idempotency records. For massive distributed workloads, a Redis/ARQ broker can be plugged in seamlessly.
3. **Conversation Format**: Expects chronological message sequences with `role` (`customer`, `agent`, or `system`).
