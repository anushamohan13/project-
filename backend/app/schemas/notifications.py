from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.entities import NotificationChannel, NotificationJobStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class NotificationPreferenceUpdate(BaseModel):
    email_enabled: bool = True
    push_enabled: bool = True
    weekly_reminder_enabled: bool = True
    reminder_weekday: int = Field(default=6, ge=0, le=6)
    reminder_hour: int = Field(default=18, ge=0, le=23)
    reminder_minute: int = Field(default=0, ge=0, le=59)
    timezone: str = Field(default="Asia/Singapore", min_length=3, max_length=100)


class NotificationPreferenceResponse(NotificationPreferenceUpdate, ORMModel):
    id: str


class PushTokenCreate(BaseModel):
    token: str = Field(min_length=10, max_length=500)
    platform: str = Field(pattern=r"^(ios|android)$")


class PushTokenResponse(PushTokenCreate, ORMModel):
    id: str
    is_active: bool
    created_at: datetime


class NotificationJobCreate(BaseModel):
    channel: NotificationChannel
    template_key: str = Field(min_length=1, max_length=80)
    recipient: str | None = Field(default=None, max_length=500)
    payload: dict = Field(default_factory=dict)
    scheduled_for: datetime | None = None


class NotificationJobResponse(ORMModel):
    id: str
    channel: NotificationChannel
    template_key: str
    recipient: str | None
    status: NotificationJobStatus
    scheduled_for: datetime
    attempts: int
    last_error: str | None
    created_at: datetime
    sent_at: datetime | None
