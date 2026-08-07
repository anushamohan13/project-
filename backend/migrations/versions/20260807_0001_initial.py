"""Initial Phase 1 schema.

Revision ID: 20260807_0001
Revises:
Create Date: 2026-08-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260807_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The authoritative model metadata remains in app.models.entities.
    # create_all is used only in development; production should run this migration.
    bind = op.get_bind()
    from app.core.database import Base
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    from app.core.database import Base
    from app import models  # noqa: F401
    Base.metadata.drop_all(bind=bind)
