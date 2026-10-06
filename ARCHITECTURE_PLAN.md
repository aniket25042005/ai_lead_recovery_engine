# Zizzet AI Lead Recovery Engine — Architecture & Implementation Plan

## 1. Executive Summary & Objective
The goal is to build an enterprise-grade, reliable, multi-tenant backend service using **FastAPI** that:
1. Ingests lead profile and multi-turn conversation logs (via synchronous REST API or async Webhooks).
2. Performs AI-driven recovery analysis (evaluating lead intent, priority score 0–100, stage, next best action, and follow-up message).
3. Strictly enforces **business rules & opt-out compliance** (e.g., if a customer says `STOP` or opts out, `do_not_contact=True` and no follow-up message is generated).
4. Guarantees **Tenant Isolation** (`tenant_id` validation across all queries and operations).
5. Ensures **Idempotency** for webhook events (preventing duplicate processing).
6. Executes webhook-triggered AI analysis asynchronously via a robust job queue with background processing.
7. Supports **LLM Provider Abstraction** (supporting Google Gemini, OpenAI, and a Mock/Deterministic provider for offline tests and evaluation).

---

## 2. System Architecture & Components

```
                +---------------------------------------+
                |         API Clients / Webhooks        |
                +---------------------------------------+
                                    |
                                    v
                +---------------------------------------+
                |           FastAPI Gateway             |
                |  - Multi-tenant Auth / Header / Body  |
                |  - Pydantic v2 Request Validation     |
                |  - Rate Limiting / Idempotency Check  |
                +---------------------------------------+
                       /                         \
    (Sync: POST /analyze)               (Async: POST /webhooks/leads)
                     /                             \
                    v                               v
    +-----------------------------+     +-------------------------------+
    |  LeadRecoveryService (Sync) |     |   Idempotent Event Store &    |
    |  - Opt-out Detector         |     |   Background Job Queue        |
    |  - Prompt Engine (v1)       |     |   (Worker / In-Memory / Redis)|
    |  - LLM Provider Interface   |     +-------------------------------+
    |  - Pydantic Schema Guard    |                     |
    +-----------------------------+                     v
                    |                   +-------------------------------+
                    |                   |      Async AI Worker          |
                    |                   |  - Exponential Backoff Retry  |
                    |                   |  - Process Lead & Convo       |
                    |                   +-------------------------------+
                    \                                  /
                     \                                /
                      v                              v
             +------------------------------------------------+
             |            Relational Database                 |
             |   - SQLAlchemy 2.0 (PostgreSQL & SQLite)       |
             |   - Tables: tenants, leads, conversations,     |
             |     analyses, webhook_events, job_runs         |
             +------------------------------------------------+
                                      |
                                      v
             +------------------------------------------------+
             |         Mock WhatsApp / Messaging API          |
             |   - Simulated message dispatcher               |
             +------------------------------------------------+
```

## 3. Database Schema & Data Models

We will use **PostgreSQL** as the primary relational database (leveraging **SQLAlchemy 2.0** with `psycopg2-binary`).
For seamless local development, testing, and CI, the database layer will allow setting `DATABASE_URL` via environment variables (with a convenient local SQLite fallback option for zero-friction testing when a live Postgres instance is not running).

### Database Configuration:
- Driver: `postgresql+psycopg2` (standard production-ready PostgreSQL driver)
- Default URL: `postgresql+psycopg2://postgres:postgres@localhost:5432/zizzet_recovery`
- Connection Pooling: Configured with pool pre-ping, pool size, and max overflow.

### Tables:
1. **`tenants`**:
   - `id`: VARCHAR (PK, e.g. `business_001`)
   - `name`: VARCHAR
   - `created_at`: TIMESTAMP

2. **`leads`**:
   - `id`: VARCHAR (PK, e.g. `lead_1024`)
   - `tenant_id`: VARCHAR (FK `tenants.id`, indexed)
   - `customer_name`: VARCHAR
   - `customer_phone`: VARCHAR
   - `source`: VARCHAR (e.g. `whatsapp`, `web`)
   - `status`: VARCHAR (e.g. `contacted`, `converted`, `lost`)
   - `created_at`: TIMESTAMP
   - `last_contacted_at`: TIMESTAMP
   - `do_not_contact`: BOOLEAN (default False)
   - *Composite Index*: `(tenant_id, id)` for strict tenant filtering.

3. **`conversations`**:
   - `id`: UUID (PK)
   - `tenant_id`: VARCHAR (FK `tenants.id`)
   - `lead_id`: VARCHAR (FK `leads.id`)
   - `role`: VARCHAR (`customer`, `agent`, `system`)
   - `message`: TEXT
   - `created_at`: TIMESTAMP

4. **`lead_analyses`**:
   - `id`: UUID (PK)
   - `tenant_id`: VARCHAR (FK)
   - `lead_id`: VARCHAR (FK)
   - `lead_score`: INTEGER (0-100)
   - `priority`: VARCHAR (`high`, `medium`, `low`)
   - `intent`: VARCHAR (`purchase`, `inquiry`, `support`, `churn_risk`, `opt_out`, etc.)
   - `stage`: VARCHAR (`pricing_interest`, `discovery`, `evaluation`, `objection`, `lost`, etc.)
   - `summary`: TEXT
   - `next_best_action`: TEXT
   - `follow_up_channel`: VARCHAR (`whatsapp`, `email`, `call`, `none`)
   - `follow_up_message`: TEXT (nullable if `do_not_contact` is true)
   - `do_not_contact`: BOOLEAN
   - `raw_llm_response`: JSON/TEXT
   - `created_at`: TIMESTAMP

5. **`webhook_events` (Idempotency Store)**:
   - `id`: UUID (PK)
   - `tenant_id`: VARCHAR
   - `idempotency_key`: VARCHAR (UNIQUE per tenant, e.g. hash of event or provided idempotency key)
   - `event_type`: VARCHAR
   - `payload`: JSON
   - `status`: VARCHAR (`received`, `processing`, `completed`, `failed`)
   - `created_at`: TIMESTAMP
   - `completed_at`: TIMESTAMP nullable

---

## 4. API Endpoints Specification

### 1. `POST /api/v1/leads/analyze`
- **Headers**: `X-Tenant-ID` (optional override or validated against body `tenant_id`)
- **Body**:
  ```json
  {
    "tenant_id": "business_001",
    "lead_id": "lead_1024",
    "customer": { "name": "Arun Kumar", "phone": "+919876543210" },
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
  }
  ```
- **Response**: Exact expected schema from screening doc:
  ```json
  {
    "lead_score": 86,
    "priority": "high",
    "intent": "purchase",
    "stage": "pricing_interest",
    "summary": "Customer is evaluating a CRM for a 25-member team.",
    "next_best_action": "Send pricing and schedule a demo",
    "follow_up_channel": "whatsapp",
    "follow_up_message": "Hi Arun! Just following up on your CRM requirement...",
    "do_not_contact": false
  }
  ```

### 2. `GET /api/v1/leads/{lead_id}/analysis`
- **Headers**: `X-Tenant-ID: business_001`
- **Behavior**: Retrieves the latest analysis for the lead, enforcing that `tenant_id` matches. If lead exists under another tenant, returns `404 Not Found` (never leaks data across tenants).

### 3. `POST /api/v1/leads/{lead_id}/follow-up`
- **Headers**: `X-Tenant-ID: business_001`
- **Body**: `{ "custom_instructions": "Offer a 10% discount" }` (optional)
- **Behavior**: Generates or retrieves the customized follow-up message and simulates dispatch via Mock WhatsApp messaging provider. Blocks follow-up if `do_not_contact=true`.

### 4. `POST /api/v1/webhooks/leads`
- **Headers**: `X-Tenant-ID: business_001`, `X-Idempotency-Key: <optional-key>`
- **Body**: Webhook event payload containing lead & conversation data.
- **Behavior**:
  - Validates event and idempotency key (or computes SHA-256 hash of payload).
  - Checks if event is already processed or in-progress. If already completed, returns existing cached result with `200 OK` (idempotent response) and does NOT re-queue.
  - If new, records event in `webhook_events`, enqueues background processing task, and returns `202 Accepted` with `job_id` and tracking status.

---

## 5. Core Business & AI Logic Requirements

### A. Opt-out & Compliance Rule (Critical Requirement)
- If the customer messages include `"STOP"`, `"unsubscribe"`, `"don't message me again"`, `"leave me alone"`, or explicit opt-out phrases:
  - System sets `do_not_contact = True`
  - Priority = `"low"`
  - Stage = `"opted_out"` or `"lost"`
  - `follow_up_message = None` (or empty string)
  - `next_best_action = "Mark as opted-out and do not contact"`
  - Both pre-LLM regex/rule guardrail and LLM prompt instructions ensure strict adherence.

### B. LLM Provider Abstraction
Create an extensible interface `BaseLLMProvider`:
- `GeminiProvider` (Google GenAI / google-genai SDK)
- `OpenAIProvider` (OpenAI / compatible endpoints)
- `MockLLMProvider` (High-fidelity rule-based / deterministic analyzer for 100% reproducible tests without external API dependencies or incurring costs).
Provider selection configurable via `.env` (`LLM_PROVIDER=gemini` or `openai` or `mock`).

### C. Retry with Exponential Backoff
- Wrap LLM calls with `tenacity` retry handler (exponential backoff for rate limits and transient network errors).

### D. Structured Output Validation
- Pydantic v2 `LeadRecoveryOutput` schema with field constraints:
  - `lead_score`: integer `ge=0, le=100`
  - `priority`: Literal["high", "medium", "low"]
  - `intent`: str
  - `stage`: str
  - `summary`: str
  - `next_best_action`: str
  - `follow_up_channel`: Literal["whatsapp", "email", "sms", "call", "none"]
  - `follow_up_message`: Optional[str]
  - `do_not_contact`: bool

---

## 6. Verification Against the 5 Evaluation Cases in the PDF

| Case | Scenario | Expected Outcome to Test |
|---|---|---|
| **Case A** | 50 employees + asks for pricing | `priority: "high"`, `intent: "purchase"`, `stage: "pricing_interest"` |
| **Case B** | Only asks what the product does | `priority: "low"`, general inquiry |
| **Case C** | Requests a demo/call tomorrow | `next_best_action`: Schedule demo/call |
| **Case D** | "STOP. Don't message me again." | `do_not_contact: true`, `follow_up_message: null` |
| **Case E** | Same webhook event submitted twice | Exactly one processing execution; idempotent return |

---

## 7. Submission Artifacts & Deliverables

1. **Clean Codebase**:
   - `app/`
     - `api/v1/endpoints/`: `leads.py`, `webhooks.py`
     - `core/`: `config.py`, `logging.py`, `security.py`
     - `db/`: `session.py`, `models.py`
     - `schemas/`: Pydantic request/response schemas
     - `services/`: `lead_service.py`, `llm/` (providers), `queue/` (worker/queue), `messenger/` (mock WhatsApp)
   - `main.py`
2. **Configuration**:
   - `requirements.txt`
   - `.env.example`
   - `Dockerfile` & `docker-compose.yml`
3. **Automated Test Suite**:
   - `tests/test_api_leads.py`: Tests `analyze`, `analysis`, `follow_up`, multi-tenancy isolation
   - `tests/test_webhooks.py`: Tests async webhook handling and idempotency (Case E)
   - `tests/test_evaluation_cases.py`: Direct tests covering Cases A, B, C, D, E from screening doc
4. **Comprehensive Documentation (`README.md`)**:
   - Architecture diagram, quick start guide, API reference, AI design decisions, edge case handling.
