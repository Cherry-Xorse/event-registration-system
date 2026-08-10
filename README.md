# Event Registration & Ticketing System

A serverless REST API built on AWS, replacing a manual Microsoft Forms + Excel workflow with a scalable, race-condition-safe event registration system.

**Live API:** `https://677qga8icb.execute-api.us-east-1.amazonaws.com/Prod/`

---

## Problem

The original process for managing event registrations relied on Microsoft Forms feeding into an Excel sheet — no real-time capacity tracking, no protection against overselling a limited-capacity event, and no way to programmatically query or cancel registrations. This project replaces that with a serverless REST API that handles registration, capacity enforcement, and cancellation automatically and safely, even under concurrent load.

---

## Architecture

```
Client
  │
  ▼
API Gateway (REST endpoints)
  │
  ▼
AWS Lambda (business logic, Python 3.12)
  │
  ▼
DynamoDB (Events, Registrations)
  │
  ├── CloudWatch (Logs, Alarms, Custom Metrics)
  ├── AWS Budgets (cost tracking)
  └── IAM (least-privilege, per-function roles)
```

**Services used:**
| Service | Purpose |
|---|---|
| AWS SAM | Infrastructure as Code — defines every resource in `template.yaml` |
| AWS Lambda | Business logic for each endpoint (Python 3.12) |
| Amazon API Gateway | REST API routing |
| Amazon DynamoDB | Storage for events and registrations |
| Amazon CloudWatch | Logs, alarms, and custom application metrics |
| AWS Budgets | Cost tracking, alerts at 80% of budget |
| AWS IAM | Per-function, least-privilege permissions |
| GitHub Actions | CI — automated testing on every push |

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/register` | Register for an event (body: `eventId`, `email`) |
| `GET` | `/events` | List all events |
| `GET` | `/registrations/{email}` | View a person's registrations |
| `DELETE` | `/registration/{id}` | Cancel a registration |

### Example: Register for an event
```bash
curl -X POST https://677qga8icb.execute-api.us-east-1.amazonaws.com/Prod/register \
  -H "Content-Type: application/json" \
  -d '{"eventId": "evt-001", "email": "you@example.com"}'
```

---

## Data Model

**Events table** — partition key: `eventId`
| Field | Type | Description |
|---|---|---|
| eventId | String | Unique event identifier |
| eventName | String | Display name |
| eventDate | String | ISO date |
| capacity | Number | Total capacity |
| remaining | Number | Spots remaining — drives availability status |

**Registrations table** — partition key: `registrationId`, GSI: `EmailIndex` (on `email`)
| Field | Type | Description |
|---|---|---|
| registrationId | String | Unique registration ID |
| eventId | String | Which event |
| email | String | Registrant's email |
| timestamp | String | ISO 8601 UTC timestamp |

Two separate tables were used rather than one, since events and registrations are distinct entities with different lifecycles — one event can have many registrations, and merging them would duplicate event data across every row.

---

## Key Design Decisions

**Atomic capacity checks.** The `/register` endpoint uses a DynamoDB `ConditionExpression` (`remaining > 0`) on the update that decrements capacity, rather than a read-then-write pattern. This guarantees that two people registering for the last spot at the same instant can never both succeed — DynamoDB evaluates the condition and performs the write as a single atomic operation, preventing overselling.

**GSI for email lookups.** `GET /registrations/{email}` needs to search by email rather than the table's primary key. Rather than scanning the entire table (slow, expensive, doesn't scale), a Global Secondary Index (`EmailIndex`) allows a direct, efficient query.

**Least-privilege IAM per function.** Each Lambda has its own auto-generated IAM role, scoped only to the specific DynamoDB tables (and specific actions) it actually needs. `ListEventsFunction` can only read `Events`; it has no access to `Registrations` or any other AWS resource. This limits the blast radius if any single function were ever compromised.

**No authentication on the API.** The API is intentionally public, matching its use case as a self-service registration form (replacing a public-facing Microsoft Form). See [Security Considerations](#security-considerations) below for what was considered instead.

---

## Monitoring & Observability

- **CloudWatch Logs** — structured JSON logging enabled for all 4 Lambda functions, with 14-day retention policies applied to control storage costs over time.
- **CloudWatch Alarm** — monitors `RegisterFunction`'s error rate using a math expression (`errors / invocations * 100`) and fires if it exceeds 5%.
- **Custom metric — `FailedRegistrations`** — a business-level metric (not just Lambda's built-in `Errors`) tracking how often registrations are rejected due to sold-out events, published via `cloudwatch:PutMetricData`.
- **AWS Budgets** — a monthly cost budget with an alert at 80% utilization, keeping spend within Free Tier expectations.

---

## Security Considerations

This API is intentionally public and unauthenticated, matching the project's use case: a self-service event registration form, similar to the Microsoft Forms it replaces. Several security patterns were considered:

- **API Gateway usage plans + API keys** — would throttle/meter usage per client; more relevant if this API were consumed by third-party integrators rather than end users filling out a form.
- **AWS WAF** — could block common attack patterns (rate-based abuse, bot traffic) in front of API Gateway. A reasonable next step for a production deployment, outside this capstone's free-tier scope.
- **Input validation and sanitization** — implemented directly in each Lambda: required-field checks, regex email validation, and DynamoDB `ConditionExpression`s used to enforce business rules server-side rather than trusting the client.
- **Least-privilege IAM** — see above.
- **CORS** — configured permissively (`*`) since this is a public form; a stricter origin allowlist would suit a deployment behind one known frontend domain.

The overall approach favors application-layer defenses (validation, atomic operations, scoped permissions) over network-layer restrictions, since the API is meant to be openly accessible by design.

---

## CI/CD

GitHub Actions runs on every push and pull request to `main` and `dev`:
1. Installs dependencies (`pytest`, `boto3`, `moto`)
2. Runs the full unit test suite (12 tests, using `moto` to mock AWS — no real credentials or costs involved)
3. Validates the SAM template (`sam validate --lint`)

Development follows a branch-based workflow: work happens on `dev`, then merges into `main` via reviewed pull requests.

---

## Testing

12 unit tests across all 4 Lambda functions, using `moto` to mock DynamoDB so tests run fast, free, and without touching real AWS:

```bash
pip install pytest boto3 moto --break-system-packages
python -m pytest tests/unit/ -v
```

Coverage includes the happy path for every endpoint, input validation failures, and — critically — the sold-out/race-condition rejection path for registration.

---

## Setup & Deployment

**Prerequisites:** AWS account, AWS CLI, AWS SAM CLI, Python 3.12, Docker Desktop (for local testing)

```bash
# Configure AWS credentials
aws configure

# Clone and enter the project
git clone https://github.com/Cherry-Xorse/event-registration-system.git
cd event-registration-system

# Build and deploy
sam build
sam deploy --guided
```

**Local testing** (requires Docker Desktop running):
```bash
sam local start-api --warm-containers LAZY
```

---

## Challenges Faced

- **DynamoDB `Decimal` serialization.** Python's `json.dumps()` can't natively serialize the `Decimal` type DynamoDB returns for numeric fields. Solved with a custom `JSONEncoder`.
- **Race conditions on capacity.** Solved using DynamoDB's `ConditionExpression` for atomic, race-safe updates rather than a vulnerable read-then-write pattern.
- **PowerShell vs. real curl.** Windows PowerShell aliases `curl` to `Invoke-WebRequest`, which doesn't support standard curl flags — resolved by calling `curl.exe` explicitly.
- **A live GitHub-wide Actions outage** (Aug 6, 2026) caused workflow runs to hang indefinitely in "Queued." Confirmed via githubstatus.com rather than assuming a config error, and continued other work until GitHub's infrastructure recovered.
- **A silent logic bug** — a missing `return` statement in email validation meant invalid emails passed through unnoticed since Python didn't raise an error, just discarded an unused dictionary. Caught during a deliberate least-privilege/validation review, a good reminder that code needs active auditing beyond "it didn't crash."
- **Invalid CloudFormation property** — `LoggingConfig` was mistakenly added under `Globals: Api` (only valid under `Globals: Function`), which silently didn't block `sam deploy` for several cycles until `sam build` was run directly and caught it.

---

## Author

Cherry Xorse Azanu — AWS Cloud Engineering Programme, Azubi Africa
