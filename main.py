"""
Email→Linear Issue Auto-Triage
FastAPI webhook that ingests emails, extracts priority/customer/issue type via Claude,
and auto-creates Linear issues with metadata. Includes Slack notifications for urgent tickets.
"""

import json
import logging
from typing import Optional
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from dotenv import load_dotenv
import os

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmailTriageResult(BaseModel):
    """Structured output from Claude for email triage."""
    priority: str = Field(
        ...,
        description="Priority level: critical, high, medium, or low"
    )
    customer_email: str = Field(
        ...,
        description="Extracted customer email address"
    )
    customer_name: Optional[str] = Field(
        None,
        description="Extracted customer name if available"
    )
    issue_type: str = Field(
        ...,
        description="Issue category: bug, feature_request, support, billing"
    )
    title: str = Field(
        ...,
        description="Suggested issue title (max 100 chars)"
    )
    summary: str = Field(
        ...,
        description="Issue summary (max 500 chars)"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Suggested Linear issue labels"
    )


class EmailWebhookPayload(BaseModel):
    """Expected payload from email webhook."""
    from_email: str
    from_name: Optional[str] = None
    subject: str
    body: str
    received_at: Optional[str] = None


class LinearIssueResponse(BaseModel):
    """Response from Linear API when creating issue."""
    id: str
    identifier: str
    url: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Email→Linear Auto-Triage service starting")
    logger.info(f"Linear API Key: {'configured' if os.getenv('LINEAR_API_KEY') else 'missing'}")
    logger.info(f"Anthropic API Key: {'configured' if os.getenv('ANTHROPIC_API_KEY') else 'missing'}")
    yield
    logger.info("🛑 Service shutting down")


app = FastAPI(
    title="Email→Linear Auto-Triage",
    description="Auto-triage customer emails into Linear issues",
    version="1.0.0",
    lifespan=lifespan
)

triage_agent = Agent(
    model=OpenAIModel("gpt-4.1"),
    result_type=EmailTriageResult,
    system_prompt="""You are an expert customer support triage specialist. 
    Analyze incoming emails and extract structured data to auto-create Linear issues.
    Be conservative with priority: only mark critical for true P0/emergency issues.
    Extract customer email and name when present in email headers or signature."""
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "email-linear-triage"}


@app.post("/webhook/email")
async def webhook_email(payload: EmailWebhookPayload):
    """
    Webhook endpoint to receive emails and auto-triage them.
    """
    try:
        email_context = f"""
Email from: {payload.from_email}
From name: {payload.from_name or 'Unknown'}
Subject: {payload.subject}
Body: {payload.body}
"""
        
        logger.info(f"Triaging email from {payload.from_email}")
        
        triage_result = await triage_agent.run(
            f"Triage this email and extract structured issue data:\n{email_context}"
        )
        
        logger.info(f"Triage result: priority={triage_result.data.priority}, "
                   f"issue_type={triage_result.data.issue_type}")
        
        linear_issue = await _create_linear_issue(
            triage_result.data,
            payload.from_email,
            payload.subject
        )
        
        if triage_result.data.priority == "critical":
            await _notify_slack(
                triage_result.data,
                linear_issue,
                payload.from_email
            )
        
        return {
            "status": "success",
            "linear_issue": {
                "id": linear_issue.id,
                "identifier": linear_issue.identifier,
                "url": linear_issue.url
            },
            "triage": {
                "priority": triage_result.data.priority,
                "issue_type": triage_result.data.issue_type
            }
        }
    
    except Exception as e:
        logger.error(f"Error processing email: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Triage failed: {str(e)}")


async def _create_linear_issue(
    triage: EmailTriageResult,
    customer_email: str,
    original_subject: str
) -> LinearIssueResponse:
    """Create issue in Linear via GraphQL API."""
    linear_api_key = os.getenv("LINEAR_API_KEY")
    if not linear_api_key:
        raise ValueError("LINEAR_API_KEY not configured")
    
    team_id = os.getenv("LINEAR_TEAM_ID", "TEAM")
    priority_map = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    
    mutation = """
    mutation CreateIssue($input: IssueCreateInput!) {
        issueCreate(input: $input) {
            issue {
                id
                identifier
                url
            }
        }
    }
    """
    
    variables = {
        "input": {
            "teamId": team_id,
            "title": triage.title,
            "description": f"{triage.summary}\n\n**Customer:** {triage.customer_name or 'Unknown'} ({triage.customer_email})\n**Original Subject:** {original_subject}",
            "priority": priority_map.get(triage.priority, 2),
            "labelIds": triage.tags,
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.linear.app/graphql",
            json={"query": mutation, "variables": variables},
            headers={
                "Authorization": f"Bearer {linear_api_key}",
                "Content-Type": "application/json"
            },
            timeout=10.0
        )
        response.raise_for_status()
        
        data = response.json()
        if "errors" in data:
            raise ValueError(f"Linear API error: {data['errors']}")
        
        issue_data = data["data"]["issueCreate"]["issue"]
        return LinearIssueResponse(**issue_data)


async def _notify_slack(
    triage: EmailTriageResult,
    linear_issue: LinearIssueResponse,
    customer_email: str
):
    """Send Slack notification for critical issues."""
    slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not slack_webhook:
        logger.warning("SLACK_WEBHOOK_URL not configured, skipping notification")
        return
    
    message = {
        "text": "🚨 Critical Email Triage Alert",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Critical Issue Detected*\n{triage.title}\n<{linear_issue.url}|View in Linear>"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Customer:*\n{customer_email}"},
                    {"type": "mrkdwn", "text": f"*Type:*\n{triage.issue_type}"},
                    {"type": "mrkdwn", "text": f"*Issue ID:*\n{linear_issue.identifier}"}
                ]
            }
        ]
    }
    
    async with httpx.AsyncClient() as client:
        try:
            await client.post(slack_webhook, json=message, timeout=5.0)
        except Exception as e:
            logger.warning(f"Failed to send Slack notification: {e}")


def main():
    """Entry point for production deployment."""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="info"
    )


if __name__ == "__main__":
    main()