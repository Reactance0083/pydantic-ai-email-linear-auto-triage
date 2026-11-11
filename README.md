# Email to Linear Triage Reference

A FastAPI implementation reference for classifying email-shaped JSON and creating a Linear issue, with a Slack notification path for critical items.

**[Portfolio](https://github.com/Reactance0083)** · **Status: experimental integration**

## Actual public implementation

`POST /webhook/email` accepts `from_email`, optional `from_name`, `subject`, `body`, and optional `received_at`. A PydanticAI agent using an OpenAI model produces structured priority, customer details, category, title, summary, and tags.

The handler calls Linear's GraphQL API and, for a critical classification, an optional Slack incoming webhook. `GET /health` reports service health.

The source does not contain Gmail polling, SMTP ingestion, or an email-provider adapter. Those would have to supply the JSON input separately. Some original comments/log labels refer to Claude, but the implemented model path uses OpenAI.

## Local setup

```bash
python -m venv .venv
# Activate the environment for your shell.
python -m pip install -r requirements.txt
# Configure OPENAI_API_KEY, LINEAR_API_KEY, and LINEAR_TEAM_ID.
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Set `SLACK_WEBHOOK_URL` only for a designated test channel if testing critical notifications. The application source is `main.py`. Live requests can create external issues and messages.

## Review before deployment

The Linear priority mapping, label-name-to-ID handling, API authentication format, and current PydanticAI compatibility require correction or verification. The endpoint also needs authentication, duplicate handling, input/data controls, and a durable failure/retry path before public exposure.

This project demonstrates integration structure and typed output design. It is not presented as a production-verified service.

Developed with AI assistance. Documentation reviewed against source on November 10, 2026.
