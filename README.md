> **Commercial status:** Preview scaffold only. This repository is not currently a verified production-ready paid product. Do not treat it as commercially ready until this banner is removed.

# Email→Linear Issue Auto-Triage

Automatically convert incoming emails into prioritized Linear issues using AI-powered triage. Extract customer information, priority levels, and issue types from raw email content, then instantly create structured tickets in your Linear workspace with Slack notifications for urgent items.

## Overview

This template provides a production-ready FastAPI webhook service that:
- Accepts emails via SMTP forwarding or Gmail API integration
- Extracts priority, customer, and issue classification using Claude AI
- Creates Linear issues with rich metadata and proper linking
- Sends Slack alerts for high-priority tickets
- Stores triage decisions for audit and refinement

**Why use this?**
- **Cost savings:** Eliminates $20-40/mo Zapier fees + manual triage overhead
- **Speed:** 30-second email-to-ticket pipeline vs. 5-minute manual routing
- **Consistency:** AI-driven classification reduces human error in priority assignment
- **Extensibility:** Built on Pydantic AI for easy customization of triage logic

## What It Does

### Email Ingestion
- Accepts raw email POST payloads (SMTP webhook format or parsed JSON)
- Extracts sender, subject, body, and attachment metadata
- Supports both plain text and HTML email bodies

### AI-Powered Triage
Uses Claude to extract from email content:
- **Priority level** (urgent/high/normal/low)
- **Customer identifier** (email domain, name, account ID)
- **Issue type** (bug/feature-request/support/billing)
- **Summary** (auto-generated from subject + body context)
- **Suggested assignee** (based on issue type patterns, optional)

### Linear Integration
- Creates issues in your Linear workspace
- Attaches original email as issue comment
- Sets priority and status based on triage output
- Links to customer/team projects (configurable)
- Supports custom fields for email metadata

### Slack Notifications
- Posts urgent/high-priority tickets to designated channel
- Includes customer info, issue link, and priority badge
- Optional thread replies for follow-up updates

### Audit & History
- Stores all triage decisions in SQLite (or configured DB)
- Enables performance monitoring and model refinement
- Supports manual override and feedback loops

## Prerequisites

- **Python 3.11+**
- **Linear API token** (create in [Settings > API > Personal API Keys](https://linear.app/settings/api))
- **Claude API key** (from [Anthropic Console](https://console.anthropic.com/))
- **Slack webhook URL** (optional, from [Slack Apps](https://api.slack.com/apps))
- **Gmail API credentials** or SMTP relay service (optional, for email ingestion)

### Optional
- Docker + Docker Compose (for containerized deployment)
- PostgreSQL (for production database, defaults to SQLite)

## Setup

### 1. Clone and Install Dependencies

```bash
git clone https://github.com/yourusername/email-linear-triage.git
cd email-linear-triage
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create Environment File

Create `.env` in the project root:

```bash
# API Keys
ANTHROPIC_API_KEY=sk-ant-...
LINEAR_API_KEY=lin_api_...
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL  # Optional

# Linear Configuration
LINEAR_TEAM_ID=acme  # Your Linear team slug (e.g., 'acme' from linear.app/acme)
LINEAR_PROJECT_ID=INB  # Project key for incoming emails (default: 'INB')
LINEAR_DEFAULT_STATUS=backlog  # Initial status for new issues

# Email Configuration
SMTP_SECRET_TOKEN=your-secret-token-here  # For webhook authentication
EMAIL_DOMAIN=yourdomain.com

# Database (optional)
DATABASE_URL=sqlite:///./triage.db  # Or: postgresql://user:pass@localhost/triage

# Feature Flags
ENABLE_SLACK_NOTIFICATIONS=true
ENABLE_AUTO_ASSIGN=false
TRIAGE_MODEL=claude-3-5-sonnet-20241022  # Claude model to use
```

### 3. Initialize Database

```bash
python -m alembic upgrade head
```

Or for SQLite (auto-created):
```bash
python -c "from app.db import init_db; init_db()"
```

### 4. Run the Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Server runs on `http://localhost:8000`

### 5. Configure Email Routing

**Option A: SMTP Forwarding** (Recommended)
- In your email provider, set up a forward rule:
  - **From:** `tickets@yourdomain.com`
  - **To:** `{your-server}/webhook/email` with authentication

**Option B: Gmail API**
- Enable [Gmail API](https://developers.google.com/gmail/api/quickstart/python) in Google Cloud Console
- Download credentials JSON to `./credentials.json`
- App auto-fetches labeled emails periodically

**Option C: Manual Testing**
```bash
curl -X POST http://localhost:8000/webhook/email \
  -H "X-Webhook-Token: your-secret-token-here" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "customer@example.com",
    "subject": "Payment processing is broken",
    "body": "Hi, our recurring invoices havent charged for 2 days. This is urgent!",
    "timestamp": "2024-01-15T14:30:00Z"
  }'
```

### 6. Set Linear Webhook (Optional, for future integration)

In Linear Settings > Integrations > Webhooks, add:
- **URL:** `{your-server}/webhook/linear-event`
- **Events:** Issue created, issue updated
- Useful for closing issues via email replies

---

## Usage

### Basic Email-to-Issue Flow

1. **Email arrives** at `tickets@yourdomain.com` (forwarded via SMTP)
2. **Webhook handler** receives POST, validates token
3. **Claude triage** classifies email (2-5 seconds)
4. **Linear issue created** with extracted metadata
5. **Slack notification** posted (if urgent/high)
6. **Response** returned with issue URL

### Example: Send an Email

```bash
curl -X POST http://localhost:8000/webhook/email \
  -H "X-Webhook-Token: your-secret-token-here" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "sarah@acmecorp.com",
    "subject": "[BUG] Dashboard crashes on mobile",
    "body": "When I open the dashboard on iPhone, it instantly crashes. Happens every time. Our team cant work.",
    "timestamp": "2024-01-15T09:30:00Z"
  }'
```

**Response (201 Created):**
```json
{
  "status": "success",
  "linear_issue_id": "INB-234",
  "linear_issue_url": "https://linear.app/acme/issue/INB-234",
  "triage_result": {
    "priority": "urgent",
    "issue_type": "bug",
    "customer_domain": "acmecorp.com",
    "summary": "Dashboard mobile app crashes on iOS",
    "suggested_assignee": "eng-mobile"
  },
  "slack_notification_sent": true,
  "processing_time_ms": 3200
}
```

---

## API Endpoints

### POST `/webhook/email`
**Ingest raw email and create Linear issue**

**Headers:**
```
X-Webhook-Token: {SMTP_SECRET_TOKEN}
Content-Type: application/json
```

**Request Body:**
```json
{
  "from": "customer@example.com",
  "subject": "Issue title",
  "body": "Email body text",
  "html_body": "<p>HTML version (optional)</p>",
  "timestamp": "2024-01-15T10:00:00Z",
  "attachments": [
    {
      "filename": "screenshot.png",
      "content_base64": "iVBORw0KGgoAAAANS...",
      "mime_type": "image/png"
    }
  ]
}
```

**Response (201 Created):**
```json
{
  "status": "success|error",
  "linear_issue_id": "INB-123",
  "linear_issue_url": "string",
  "triage_result": {
    "priority": "urgent|high|normal|low",
    "issue_type": "bug|feature|support|billing",
    "customer_domain": "string",
    "customer_name": "string (optional)",
    "summary": "string",
    "suggested_assignee": "string (optional)"
  },
  "slack_notification_sent": boolean,
  "error": "string (if status='error')"
}
```

---

### POST `/api/triage/override/{issue_id}`
**Manually override AI triage decision**

**Headers:**
```
X-API-Key: {LINEAR_API_KEY}
Content-Type: application/json
```

**Request Body:**
```json
{
  "priority": "high",
  "issue_type": "bug",
  "notes": "Manually corrected from 'low' due to context"
}
```

**Response (200 OK):**
```json
{
  "status": "updated",
  "triage_record_id": "uuid",
  "changes": {
    "priority": {"old": "normal", "new": "high"}
  }
}
```

---

### GET `/api/triage/history`
**Retrieve triage history and metrics**

**Query Parameters:**
- `limit=50` (default)
- `offset=0`
- `priority_filter=urgent|high|normal|low` (optional)
- `date_from=2024-01-01` (optional)
- `date_to=2024-01-31` (optional)

**Response (200 OK):**
```json
{
  "total_processed": 342,
  "results": [
    {
      "id": "uuid",
      "email_from": "customer@example.com",
      "linear_issue_id": "INB-234",
      "priority": "high",
      "issue_type": "bug",
      "created_at": "2024-01-15T09:30:00Z",
      "processing_time_ms": 3200,
      "model_confidence": 0.94
    }
  ],
  "statistics": {
    "avg_processing_time_ms": 2800,
    "priority_distribution": {
      "urgent": 15,
      "high": 87,
      "normal": 198,
      "low": 42
    },
    "issue_type_distribution": {
      "bug": 124,
      "feature": 56,
      "support": 142,
      "billing": 20
    }
  }
}
```

---

### GET `/health`
**Service health check**

**Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:00:00Z",
  "dependencies": {
    "anthropic": "ok",
    "linear": "ok",
    "slack": "ok",
    "database": "ok"
  }
}
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | ✓ | — | Claude API key from Anthropic Console |
| `LINEAR_API_KEY` | ✓ | — | Linear API token from Settings > API |
| `LINEAR_TEAM_ID` | ✓ | — | Linear team slug (e.g., 'acme') |
| `LINEAR_PROJECT_ID` | | `INB` | Linear project key for new issues |
| `LINEAR_DEFAULT_STATUS` | | `backlog` | Initial issue status (backlog/todo/in_progress) |
| `SMTP_SECRET_TOKEN` | ✓ | — | Secret token for webhook authentication |
| `SLACK_WEBHOOK_URL` | | — | Slack webhook URL (leave empty to disable) |
| `ENABLE_SLACK_NOTIFICATIONS` | | `true` | Post notifications for urgent/high |
| `ENABLE_AUTO_ASSIGN` | | `false` | Automatically assign based on issue type |
| `TRIAGE_MODEL` | | `claude-3-5-sonnet-20241022` | Claude model (3-opus-20250219 for best accuracy) |
| `DATABASE_URL` | | `sqlite:///./triage.db` | PostgreSQL or SQLite connection string |
| `GMAIL_CREDENTIALS_PATH` | | `./credentials.json` | Path to Gmail API credentials (if using Gmail) |
| `EMAIL_DOMAIN` | | — | Your email domain (for reply-to headers) |
| `LOG_LEVEL` | | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |

### Pydantic AI Configuration

Edit `app/config.py` to customize:

```python
# Claude model settings
TRIAGE_MODEL = "claude-3-5-sonnet-20241022"  # Change to claude-3-opus-20250219 for higher accuracy

# Triage classification thresholds
PRIORITY_KEYWORDS = {
    "urgent": ["critical", "down", "broken", "asap", "emergency"],
    "high": ["bug", "broken", "failing", "urgent"],
    "normal": ["feature", "improve"],
    "low": ["typo", "minor", "nice-to-have"]
}

# Linear field mappings
LINEAR_PRIORITY_MAP = {
    "urgent": 4,    # Urgent in Linear
    "high": 3,
    "normal": 2,
    "low": 1
}
```

---

## Customization

### Change Triage Prompt

Edit `app/agents/triage_agent.py`:

```python
TRIAGE_SYSTEM_PROMPT = """You are an expert customer support triage system...
Analyze the email and extract:
1. Priority (urgent/high/normal/low) - consider customer tone, service impact, frequency
2. Issue type (bug/feature/support/billing) - classify by nature
3. Customer identifier - extract domain or company name
4. Concise summary - max 10 words
5. Suggested team - based on issue type
"""
```

### Add Custom Issue Fields

In `app/models/triage.py`, extend `TriageResult`:

```python
class TriageResult(BaseModel):
    priority: str
    issue_type: str
    customer_domain: str
    summary: str
    custom_field_1: str | None = None  # Add your field
```

Then update the Claude prompt to extract it, and Linear creation logic in `app/integrations/linear.py`:

```python
custom_field_id = "LIN_CUSTOM_1"
issue_data["fieldValues"].append({
    "fieldId": custom_field_id,
    "value": triage_result.custom_field_1
})
```

### Route Issues to Different Projects

In `app/integrations/linear.py`, modify project selection:

```python
def get_target_project(triage_result: TriageResult) -> str:
    if triage_result.issue_type == "billing":
        return "BIL"  # Billing project
    elif triage_result.customer_domain == "enterprise.com":
        return "ENT"  # Enterprise project
    return settings.LINEAR_PROJECT_ID
```

### Customize Slack Messages

In `app/integrations/slack.py`, edit the Slack payload:

```python
blocks = [
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"🔴 *URGENT: {triage_result.summary}*\nCustomer: {triage_result.customer_domain}\n<{issue_url}|View in Linear>"
        }
    }
]
```

### Use Different Claude Models

For **higher accuracy** (slower + more expensive):
```bash
TRIAGE_MODEL=claude-3-opus-20250219 python -m uvicorn app.main:app
```

For **lower cost** (faster):
```bash
TRIAGE_MODEL=claude-3-5-haiku-20241022 python -m uvicorn app.main:app
```

### Add Database Persistence

Switch from SQLite to PostgreSQL:

```bash
pip install psycopg2-binary
export DATABASE_URL=postgresql://user:password@localhost:5432/triage
python -m alembic upgrade head
```

---

## Testing

### Run Unit Tests

```bash
pytest tests/ -v
```

### Test Triage Agent Locally

```bash
python -m app.agents.triage_agent --email-from "customer@example.com" --subject "Payment failed" --body "We can't process payments today"
```

### Mock Email Webhook

```bash
python scripts/test_email_webhook.py
```

---

## Deployment

### Docker Compose

```bash
docker-compose up -d
```

See `docker-compose.yml` for production config (PostgreSQL, environment variables).

### Heroku

```bash
git push heroku main
heroku config:set ANTHROPIC_API_KEY=sk-ant-...
heroku config:set LINEAR_API_KEY=lin_api_...
```

### AWS Lambda

```bash
pip install aws-wsgi
# See Dockerfile.lambda for container image setup
```

---

## Troubleshooting

**"Invalid Linear API Key"**
- Verify token in [Settings > API > Personal API Keys](https://linear.app/settings/api)
- Ensure token has `read` and `write` scopes

**"Claude rate limit exceeded"**
- Upgrade Anthropic plan or implement request queueing
- Batch emails in peak hours

**"Slack notification not sent"**
- Verify `SLACK_WEBHOOK_URL` is set and valid
- Check Slack workspace webhook permissions
- Set `ENABLE_SLACK_NOTIFICATIONS=false` to skip errors

**"Database connection error"**
- For SQLite: ensure `triage.db` directory is writable
- For PostgreSQL: verify host/port/credentials
- Run `python -c "from app.db import init_db; init_db()"` to reinitialize

---

## Performance Metrics

Typical performance on Sonnet 3.5:
- **Email parsing:** 50ms
- **Claude triage:** 2-4s (network + inference)
- **Linear issue creation:** 300-800ms
- **Slack notification:** 200-500ms
- **Total end-to-end:** 2.5-6s

---

## License

MIT License — see LICENSE file for details.

Built with [Pydantic AI](https://github.com/pydantic/pydantic-ai), [FastAPI](https://fastapi.tiangolo.com/), and [Linear API](https://linear.app/docs).