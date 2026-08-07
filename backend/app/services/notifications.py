import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import (
    DevicePushToken,
    NotificationChannel,
    NotificationJob,
    NotificationJobStatus,
    NotificationLog,
    User,
)

settings = get_settings()


@dataclass(frozen=True)
class DeliveryResult:
    provider_message_id: str
    detail: str


class EmailProvider(Protocol):
    def send(self, *, recipient: str, subject: str, body: str) -> DeliveryResult: ...


class PushProvider(Protocol):
    def send(self, *, token: str, title: str, body: str, data: dict) -> DeliveryResult: ...


class MockEmailProvider:
    def send(self, *, recipient: str, subject: str, body: str) -> DeliveryResult:
        return DeliveryResult(provider_message_id=f"mock-email-{int(datetime.now().timestamp())}", detail=f"Mock email to {recipient}: {subject}")


class SendGridEmailProvider:
    def send(self, *, recipient: str, subject: str, body: str) -> DeliveryResult:
        response = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {settings.sendgrid_api_key}"},
            json={
                "personalizations": [{"to": [{"email": recipient}]}],
                "from": {"email": settings.email_from},
                "subject": subject,
                "content": [{"type": "text/plain", "value": body}],
            },
            timeout=15,
        )
        response.raise_for_status()
        return DeliveryResult(provider_message_id=response.headers.get("x-message-id", "sendgrid"), detail="Sent by SendGrid")


class MockPushProvider:
    def send(self, *, token: str, title: str, body: str, data: dict) -> DeliveryResult:
        return DeliveryResult(provider_message_id=f"mock-push-{int(datetime.now().timestamp())}", detail=f"Mock push to {token[:12]}…: {title}")


class ExpoPushProvider:
    def send(self, *, token: str, title: str, body: str, data: dict) -> DeliveryResult:
        headers = {"Content-Type": "application/json"}
        if settings.expo_access_token:
            headers["Authorization"] = f"Bearer {settings.expo_access_token}"
        response = httpx.post(
            "https://exp.host/--/api/v2/push/send",
            headers=headers,
            json={"to": token, "title": title, "body": body, "data": data, "sound": "default"},
            timeout=15,
        )
        response.raise_for_status()
        result = response.json().get("data", {})
        if result.get("status") == "error":
            raise RuntimeError(result.get("message", "Expo push delivery failed"))
        return DeliveryResult(provider_message_id=result.get("id", "expo"), detail="Accepted by Expo Push Service")


def email_provider() -> EmailProvider:
    if settings.email_provider == "sendgrid" and settings.sendgrid_api_key:
        return SendGridEmailProvider()
    return MockEmailProvider()


def push_provider() -> PushProvider:
    if settings.push_provider == "expo":
        return ExpoPushProvider()
    return MockPushProvider()


def queue_notification(
    db: Session,
    *,
    user_id: str,
    channel: NotificationChannel,
    template_key: str,
    payload: dict,
    recipient: str | None = None,
    scheduled_for: datetime | None = None,
) -> NotificationJob:
    job = NotificationJob(
        user_id=user_id,
        channel=channel,
        template_key=template_key,
        recipient=recipient,
        payload_json=json.dumps(payload, default=str),
        scheduled_for=scheduled_for or datetime.now(timezone.utc),
        status=NotificationJobStatus.queued,
    )
    db.add(job)
    db.flush()
    return job


def render_template(template_key: str, payload: dict) -> tuple[str, str]:
    if template_key == "weekly_planning_reminder":
        return "Plan your week", "Add your upcoming activities and confirm a realistic spending plan."
    if template_key == "overspending_alert":
        amount = payload.get("amount", "0.00")
        currency = payload.get("currency", "")
        return "Budget alert", f"Your current plan is over budget by {currency} {amount}."
    return payload.get("title", "PocketPilot update"), payload.get("body", "You have a new financial planning update.")


def _deliver_job(db: Session, job: NotificationJob) -> None:
    job.status = NotificationJobStatus.processing
    job.attempts += 1
    payload = json.loads(job.payload_json)
    title, body = render_template(job.template_key, payload)
    try:
        if job.channel == NotificationChannel.email:
            user = db.get(User, job.user_id)
            recipient = job.recipient or (user.email if user else None)
            if not recipient:
                raise RuntimeError("No email recipient is available")
            result = email_provider().send(recipient=recipient, subject=title, body=body)
            db.add(NotificationLog(user_id=job.user_id, job_id=job.id, channel=job.channel, status="sent", provider_message_id=result.provider_message_id, detail=result.detail))
        elif job.channel == NotificationChannel.push:
            tokens = db.scalars(select(DevicePushToken).where(DevicePushToken.user_id == job.user_id, DevicePushToken.is_active.is_(True))).all()
            if not tokens:
                raise RuntimeError("No active push token is registered")
            for device in tokens:
                result = push_provider().send(token=device.token, title=title, body=body, data=payload)
                db.add(NotificationLog(user_id=job.user_id, job_id=job.id, channel=job.channel, status="sent", provider_message_id=result.provider_message_id, detail=result.detail))
        else:
            db.add(NotificationLog(user_id=job.user_id, job_id=job.id, channel=job.channel, status="sent", detail=body))
        job.status = NotificationJobStatus.sent
        job.sent_at = datetime.now(timezone.utc)
        job.last_error = None
    except Exception as exc:
        job.status = NotificationJobStatus.failed
        job.last_error = str(exc)[:2000]
        db.add(NotificationLog(user_id=job.user_id, job_id=job.id, channel=job.channel, status="failed", detail=job.last_error))


def run_due_notification_jobs(db: Session, *, limit: int = 100) -> int:
    now = datetime.now(timezone.utc)
    jobs = db.scalars(
        select(NotificationJob)
        .where(NotificationJob.status == NotificationJobStatus.queued, NotificationJob.scheduled_for <= now)
        .order_by(NotificationJob.scheduled_for)
        .limit(limit)
    ).all()
    for job in jobs:
        _deliver_job(db, job)
    db.commit()
    return len(jobs)
