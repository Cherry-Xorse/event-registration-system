# Event Registration & Ticketing System

A serverless REST API and web app built on AWS, replacing a manual Microsoft Forms + Excel workflow with a scalable, race-condition-safe event registration system.

**Live API:** `https://677qga8icb.execute-api.us-east-1.amazonaws.com/Prod/`
**Live frontend:** `http://cherry-event-registration-frontend.s3-website-us-east-1.amazonaws.com`

---

## Problem

The original process for managing event registrations relied on Microsoft Forms feeding into an Excel sheet — no real-time capacity tracking, no protection against overselling a limited-capacity event, and no way to programmatically query or cancel registrations. This project replaces that with a serverless REST API — and a real web frontend on top of it — that handles registration, capacity enforcement, and cancellation automatically and safely, even under concurrent load.

---

## Architecture

```
Browser (S3-hosted frontend)
  │
  ▼
API Gateway (REST endpoints)
  │
  ▼
AWS Lambda (business logic, Python 3.12 × 5)
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
| AWS Lambda | Business logic for each endpoint (Python 3.12, 5 functions) |
| Amazon API Gateway | REST API routing |
| Amazon DynamoDB | Storage for events and registrations |
| Amazon S3 | Static hosting for the frontend |
| Amazon CloudWatch | Logs, alarms, and custom application metrics |
| AWS Budgets | Cost tracking, alerts at 80% of budget |
| AWS IAM | Per-function, least-privilege permissions |
| GitHub Actions | CI/CD — automated testing and automated deployment on every push to `main` |

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/events` | List all events |
| `POST` | `/events` | Create a new event (body: `eventName`, `eventDate`, `capacity`) |
| `POST` | `/register` | Register for an event (body: `eventId`, `email`) |
| `GET` | `/registrations/{email}` | View a person's registrations |
| `DELETE` | `/registration/{id}` | Cancel a registration |

`POST /events` was added beyond the original spec's 4 required endpoints — without it, events could only be seeded manually via the AWS CLI, which meant the system wasn't actually usable end-to-end through the app itself.

### Example: Register for an event
```bash
curl -X POST https://677qga8icb.execute-api.us-east-1.amazonaws.com/Prod/register \
  -H "Content-Type: application/json" \
  -d '{"eventId": "evt-001", "email": "you@example.com"}'
```

### Example: Create an event
```bash
curl -X POST https://677qga8icb.execute-api.us-east-1.amazonaws.com/Prod/events \
  -H "Content-Type: application/json" \
  -d '{"eventName": "Cloud Solutions Summit", "eventDate": "2026-06-28", "capacity": 30}'
```

---

## Frontend

A static HTML/CSS/JS frontend ("STUB"), hosted on S3, calling the live API directly from the browser — no build step, no framework, CORS enabled on the API for cross-origin requests.

**Design:** styled around a movie-ticket / boarding-pass visual motif — die-cut circle notches, a dashed perforation line, a rotated "Admit One" stub — since the system is literally a ticketing system. Event cards show live status (Available / Limited / Sold Out) computed from real `remaining` vs `capacity` data.

**Functionality:** all 5 endpoints are wired in — browse events, register, look up registrations by email, cancel a registration, and add a new event, entirely through the UI.

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

**Least-privilege IAM per function.** Each of the 5 Lambdas has its own auto-generated IAM role, scoped only to the specific DynamoDB tables (and specific actions) it actually needs — verified by reading the generated policy JSON directly in the IAM console, not assumed. `ListEventsFunction` can only read `Events`; it has no access to `Registrations` or any other AWS resource. This limits the blast radius if any single function were ever compromised.

**No authentication on the API.** The API is intentionally public, matching its use case as a self-service registration form (replacing a public-facing Microsoft Form). See [Security Considerations](#security-considerations) below for what was considered instead.

---

## Monitoring & Observability

- **CloudWatch Logs** — structured JSON logging enabled for all 5 Lambda functions, with 14-day retention policies applied to control storage costs over time.
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
- **CORS** — configured permissively (`*`) since this is a public form and the frontend is hosted on a different origin (S3) than the API; a stricter origin allowlist would suit a production deployment behind one known domain.

The overall approach favors application-layer defenses (validation, atomic operations, scoped permissions) over network-layer restrictions, since the API is meant to be openly accessible by design.

---

## CI/CD

GitHub Actions runs two jobs:

**`test`** — on every push and pull request to `main` and `dev`:
1. Installs dependencies (`pytest`, `boto3`, `moto`)
2. Runs the full unit test suite (12 tests, using `moto` to mock AWS — no real credentials or costs involved)
3. Validates the SAM template (`sam validate --lint`)

**`deploy`** — only on a push directly to `main`, and only if `test` passes first (`needs: test`):
1. Runs `sam build` and `sam deploy` to update the live backend
2. Uploads `index.html` to the S3 frontend bucket

This means a merge to `main` is a genuinely complete pipeline — tested and deployed automatically, with zero manual `sam deploy` or `aws s3 cp` commands required. This wasn't the initial design: the pipeline originally only ran tests, and manual deployment continued out of habit until a frontend update didn't appear on the live site, which led to adding the `deploy` job (see Challenges Faced).

Development follows a branch-based workflow: work happens on `dev`, then merges into `main` via reviewed pull requests.

---

## Testing

12 unit tests across all 4 core Lambda functions (register, list events, get registrations, cancel registration), using `moto` to mock DynamoDB so tests run fast, free, and without touching real AWS:

```bash
pip install pytest boto3 moto --break-system-packages
python -m pytest tests/unit/ -v
```

Coverage includes the happy path for every endpoint, input validation failures, and — critically — the sold-out/race-condition rejection path for registration.

---

## Setup & Deployment

**Prerequisites:** AWS account, AWS CLI, AWS SAM CLI, Python 3.12, Docker Desktop (for local testing only)

```bash
# Configure AWS credentials
aws configure

# Clone and enter the project
git clone https://github.com/Cherry-Xorse/event-registration-system.git
cd event-registration-system

# Build and deploy the backend
sam build
sam deploy --guided

# Deploy the frontend
aws s3 cp index.html s3://cherry-event-registration-frontend/index.html
```

In practice, deployment now happens automatically via CI/CD on every merge to `main` — see the CI/CD section above.

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
- **CI without CD.** For most of the build, the pipeline only ran tests — every deploy, backend and frontend, was still manual. Noticed when a frontend change didn't appear on the live site after pushing to GitHub. Fixed by adding a gated `deploy` job that only runs after tests pass and only on `main`.

---

## Author

Cherry Xorse Azanu — AWS Cloud Engineering Programme, Azubi Africa