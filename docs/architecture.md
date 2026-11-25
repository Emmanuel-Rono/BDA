# Architecture and API

## Processing flow

FastAPI accepts an invoice and packing slip, validates their file types and limits,
and preserves extracted text by page. The application hashes the document pair and
creates a durable processing record. Repeated uploads return the existing job.

Qwen extracts each document into a Pydantic schema. Fields include document and order
references, currency, totals and line items. Each written value carries its page and
source quote. Python verifies the quoted text and exact value against that page.
Missing values stay null. A failed grounding check receives one correction attempt
before the workflow records an error.

The Spree adapter retrieves the exact referenced order through the Admin API. Both
documents must name that same order. The adapter exposes selected order and line-item
fields without forwarding customer email, addresses or internal notes to the model.

Reconciliation aggregates quantities by SKU and calculates differences with Decimal.
It also checks invoice line arithmetic and subtotal arithmetic. The report retains
extracted fields, source pages, matched order facts and staff review decisions.

## Conversations and review

Browser follow-up questions use the selected report from server storage. The client
cannot replace report context or submit system-role messages. Model citations must
reference evidence available in that report.

Approval and rejection apply to internal reports. Review requests check the current
report version. Repeating the same decision and note returns the existing review;
conflicting requests are rejected. The application does not update orders, inventory,
payments or customer communications.

## Access and storage

The dashboard binds to loopback. A same-origin request from a local browser creates
a signed HttpOnly session cookie. Signatures are bound to the application and store,
expire after eight hours, and are checked for authenticated requests. Cookie-based
actions also require a matching origin. A server token supports programmatic clients.

SQLite stores jobs, outcomes, audit events and versioned reviews. Original documents
are saved under `data/uploads/` with content-hash filenames. Duplicate identity includes
the document pair, configured store and source mode. Failed duplicate jobs retain their
record; changing the document content creates a new job.

A short in-process lock protects duplicate claims; slow inference runs outside it.
Run one server worker. A restart marks interrupted jobs as failed.

## API routes

Except for process health and local session creation, routes require a browser
session or bearer token.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | Process health |
| GET | `/ready` | Check configured Spree and model availability |
| POST | `/v1/session` | Establish a local browser session |
| GET | `/v1/config` | Read workspace settings without credentials |
| POST | `/v1/jobs` | Extract and reconcile a document pair |
| POST | `/v1/chat` | Ask the model a question with optional report context |
| GET | `/v1/reports` | List recent reports |
| GET | `/v1/reports/{id}` | Read a stored report |
| POST | `/v1/reports/{id}/review` | Approve or reject an internal report |
| GET | `/v1/openapi.json` | Read the generated API schema |

Responses include an `X-Trace-ID` header. Controlled errors distinguish access,
parsing, extraction, source-evidence, reference, model and dependency failures.
Live API failures are reported directly; they do not switch to fixture records.

## Module responsibilities

| Module | Responsibility |
| --- | --- |
| `main.py` | Upload handling and workflow assembly |
| `documents.py` | File validation and page-level text extraction |
| `extraction.py` | Model extraction schemas and source validation |
| `reconcile.py` | SKU quantities, amount rules and discrepancy calculations |
| `spree.py` | Read-only order adapter and explicit test fixtures |
| `model.py` | Ollama requests and structured-output validation |
| `storage.py` | Persistent jobs, audit events and review transactions |
| `web.py` | Dashboard, sessions, conversations, reports and errors |
| `dashboard_auth.py` | Signed local sessions and origin checks |
| `settings.py` | Validated server configuration |
