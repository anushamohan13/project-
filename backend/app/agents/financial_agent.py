from sqlalchemy.orm import Session

from app.agents.orchestrator import process_message
from app.models.entities import User


def respond_to_financial_question(db: Session, user: User, message: str) -> dict:
    return process_message(db, user=user, message=message)
