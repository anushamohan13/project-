import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.entities import (
    DevicePushToken,
    NotificationChannel,
    NotificationJob,
    NotificationJobStatus,
    NotificationLog,
    NotificationPreference,
    User,
)
from app.schemas.notifications import (
    NotificationJobCreate,
    NotificationJobResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    PushTokenCreate,
    PushTokenResponse,
)
from app.services.audit import record_audit
from app.services.notifications import queue_notification, run_due_notification_jobs

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _job_owned(db: Session, user_id: str, job_id: str) -> NotificationJob:
    item = db.scalar(select(NotificationJob).where(NotificationJob.id == job_id, NotificationJob.user_id == user_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Notification job not found")
    return item


@router.get("/preferences", response_model=NotificationPreferenceResponse)
def get_preferences(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user.id))
    if item is None:
        timezone_name = user.profile.timezone if user.profile else "Asia/Singapore"
        item = NotificationPreference(user_id=user.id, timezone=timezone_name)
        db.add(item)
        db.commit()
        db.refresh(item)
    return item


@router.put("/preferences", response_model=NotificationPreferenceResponse)
def update_preferences(payload: NotificationPreferenceUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user.id))
    if item is None:
        item = NotificationPreference(user_id=user.id)
        db.add(item)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    record_audit(db, user_id=user.id, action="notification_preferences.updated", entity_type="NotificationPreference", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return item


@router.get("/push-tokens", response_model=list[PushTokenResponse])
def list_push_tokens(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(DevicePushToken).where(DevicePushToken.user_id == user.id).order_by(DevicePushToken.created_at.desc())).all()


@router.post("/push-tokens", response_model=PushTokenResponse, status_code=201)
def create_push_token(payload: PushTokenCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.scalar(select(DevicePushToken).where(DevicePushToken.user_id == user.id, DevicePushToken.token == payload.token))
    if existing:
        existing.platform = payload.platform
        existing.is_active = True
        item = existing
    else:
        item = DevicePushToken(user_id=user.id, **payload.model_dump())
        db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/push-tokens/{token_id}", response_model=PushTokenResponse)
def update_push_token(token_id: str, payload: PushTokenCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(DevicePushToken).where(DevicePushToken.id == token_id, DevicePushToken.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Push token not found")
    item.token = payload.token
    item.platform = payload.platform
    item.is_active = True
    db.commit()
    db.refresh(item)
    return item


@router.delete("/push-tokens/{token_id}", status_code=204)
def delete_push_token(token_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(DevicePushToken).where(DevicePushToken.id == token_id, DevicePushToken.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Push token not found")
    db.delete(item)
    db.commit()


@router.get("/jobs", response_model=list[NotificationJobResponse])
def list_jobs(
    job_status: NotificationJobStatus | None = Query(default=None, alias="status"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(NotificationJob).where(NotificationJob.user_id == user.id)
    if job_status:
        query = query.where(NotificationJob.status == job_status)
    return db.scalars(query.order_by(NotificationJob.created_at.desc())).all()


@router.post("/jobs", response_model=NotificationJobResponse, status_code=201)
def create_job(payload: NotificationJobCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    recipient = payload.recipient
    if payload.channel == NotificationChannel.email and recipient is None:
        recipient = user.email
    item = queue_notification(
        db,
        user_id=user.id,
        channel=payload.channel,
        template_key=payload.template_key,
        payload=payload.payload,
        recipient=recipient,
        scheduled_for=payload.scheduled_for,
    )
    record_audit(db, user_id=user.id, action="notification_job.created", entity_type="NotificationJob", entity_id=item.id)
    db.commit()
    db.refresh(item)
    return item


@router.get("/jobs/{job_id}", response_model=NotificationJobResponse)
def get_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _job_owned(db, user.id, job_id)


@router.put("/jobs/{job_id}", response_model=NotificationJobResponse)
def update_job(job_id: str, payload: NotificationJobCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _job_owned(db, user.id, job_id)
    if item.status not in {NotificationJobStatus.queued, NotificationJobStatus.failed}:
        raise HTTPException(status_code=409, detail="Only queued or failed jobs can be edited")
    item.channel = payload.channel
    item.template_key = payload.template_key
    item.recipient = payload.recipient or (user.email if payload.channel == NotificationChannel.email else None)
    item.payload_json = json.dumps(payload.payload, default=str)
    item.scheduled_for = payload.scheduled_for or datetime.now(timezone.utc)
    item.status = NotificationJobStatus.queued
    item.last_error = None
    db.commit()
    db.refresh(item)
    return item


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _job_owned(db, user.id, job_id)
    if item.status == NotificationJobStatus.processing:
        raise HTTPException(status_code=409, detail="A processing job cannot be deleted")
    db.delete(item)
    db.commit()


@router.post("/jobs/{job_id}/cancel", response_model=NotificationJobResponse)
def cancel_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _job_owned(db, user.id, job_id)
    if item.status not in {NotificationJobStatus.queued, NotificationJobStatus.failed}:
        raise HTTPException(status_code=409, detail="Only queued or failed jobs can be cancelled")
    item.status = NotificationJobStatus.cancelled
    db.commit()
    db.refresh(item)
    return item


@router.post("/queue-weekly-reminder", response_model=list[NotificationJobResponse], status_code=201)
def queue_weekly_reminder(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    preferences = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user.id))
    if preferences is None:
        preferences = NotificationPreference(user_id=user.id, timezone=user.profile.timezone if user.profile else "Asia/Singapore")
        db.add(preferences)
        db.flush()
    jobs = []
    payload = {"title": "Plan your week", "body": "Add activities and confirm your weekly spending plan."}
    if preferences.email_enabled:
        jobs.append(queue_notification(db, user_id=user.id, channel=NotificationChannel.email, template_key="weekly_planning_reminder", payload=payload, recipient=user.email))
    if preferences.push_enabled:
        jobs.append(queue_notification(db, user_id=user.id, channel=NotificationChannel.push, template_key="weekly_planning_reminder", payload=payload))
    jobs.append(queue_notification(db, user_id=user.id, channel=NotificationChannel.in_app, template_key="weekly_planning_reminder", payload=payload))
    db.commit()
    for item in jobs:
        db.refresh(item)
    return jobs


@router.post("/run-due", response_model=dict)
def run_due_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Development/test helper. Production invokes the scheduler worker.
    processed = run_due_notification_jobs(db)
    return {"processed": processed}


@router.get("/logs", response_model=list[dict])
def list_notification_logs(
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = db.scalars(select(NotificationLog).where(NotificationLog.user_id == user.id).order_by(NotificationLog.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": item.id,
            "job_id": item.job_id,
            "channel": item.channel.value,
            "status": item.status,
            "provider_message_id": item.provider_message_id,
            "detail": item.detail,
            "created_at": item.created_at.isoformat(),
        }
        for item in items
    ]
