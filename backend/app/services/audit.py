import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import AuditLog


SENSITIVE_KEYS = {"password", "token", "refresh_token", "access_token", "api_key", "secret"}


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if key.lower() in SENSITIVE_KEYS else _sanitize(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def record_audit(
    db: Session,
    *,
    user_id: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    detail: dict | None = None,
) -> AuditLog:
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail_json=json.dumps(_sanitize(detail or {}), default=str, sort_keys=True),
    )
    db.add(log)
    return log
