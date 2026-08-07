"""Phase 2 OAuth, CRUD, transaction, notifications, widget, and AI orchestration schema.

Revision ID: 20260807_0002
Revises: 20260807_0001
Create Date: 2026-08-07
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260807_0002"
down_revision: str | None = "20260807_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _add_column(table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(table_name):
        op.add_column(table_name, column)


def upgrade() -> None:
    # Additive migration supports databases created by the Phase 1 release.
    _add_column("users", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    _add_column("user_profiles", sa.Column("ai_memory_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    _add_column("activities", sa.Column("actual_cost", sa.Numeric(18, 2), nullable=True))
    _add_column("activities", sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()))
    _add_column("wishlist_items", sa.Column("notes", sa.Text(), nullable=True))

    _add_column("budget_plans", sa.Column("source", sa.String(30), nullable=False, server_default="manual"))
    _add_column("budget_plans", sa.Column("source_proposal_id", sa.String(36), nullable=True))
    _add_column("budget_plans", sa.Column("previous_plan_id", sa.String(36), nullable=True))

    _add_column("widget_snapshots", sa.Column("plan_id", sa.String(36), nullable=True))
    _add_column("widget_snapshots", sa.Column("plan_version", sa.Integer(), nullable=False, server_default="0"))
    _add_column("widget_snapshots", sa.Column("snapshot_json", sa.Text(), nullable=True))

    proposal_columns = {
        "conversation_id": sa.Column("conversation_id", sa.String(36), nullable=True),
        "base_plan_id": sa.Column("base_plan_id", sa.String(36), nullable=True),
        "base_plan_version": sa.Column("base_plan_version", sa.Integer(), nullable=True),
        "before_plan_json": sa.Column("before_plan_json", sa.Text(), nullable=False, server_default="{}"),
        "proposed_plan_json": sa.Column("proposed_plan_json", sa.Text(), nullable=False, server_default="{}"),
        "calculation_json": sa.Column("calculation_json", sa.Text(), nullable=False, server_default="{}"),
        "applied_plan_id": sa.Column("applied_plan_id", sa.String(36), nullable=True),
        "reversal_plan_id": sa.Column("reversal_plan_id", sa.String(36), nullable=True),
        "expires_at": sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        "confirmed_at": sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        "applied_at": sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        "reversed_at": sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
    }
    for column in proposal_columns.values():
        _add_column("financial_change_proposals", column)

    # Create every new Phase 2 table and index that does not already exist.
    from app.core.database import Base
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # Budget plans are immutable records. Downgrade removes only Phase 2 additions;
    # application data should be backed up before running this operation.
    removable_columns = {
        "users": ["updated_at"],
        "user_profiles": ["ai_memory_enabled"],
        "activities": ["actual_cost", "completed"],
        "wishlist_items": ["notes"],
        "budget_plans": ["source", "source_proposal_id", "previous_plan_id"],
        "widget_snapshots": ["plan_id", "plan_version", "snapshot_json"],
        "financial_change_proposals": [
            "conversation_id",
            "base_plan_id",
            "base_plan_version",
            "before_plan_json",
            "proposed_plan_json",
            "calculation_json",
            "applied_plan_id",
            "reversal_plan_id",
            "expires_at",
            "confirmed_at",
            "applied_at",
            "reversed_at",
        ],
    }
    # Remove foreign-key columns before dropping their referenced Phase 2 tables.
    for table_name, column_names in removable_columns.items():
        current = _columns(table_name)
        existing_columns = [name for name in column_names if name in current]
        if existing_columns:
            with op.batch_alter_table(table_name) as batch_op:
                for column_name in existing_columns:
                    batch_op.drop_column(column_name)

    phase2_tables = [
        "audit_logs",
        "confirmed_cost_memories",
        "ai_recommendations",
        "currency_rates",
        "ai_usage_records",
        "user_ai_memories",
        "chat_tool_results",
        "chat_tool_calls",
        "chat_messages",
        "chat_conversations",
        "notification_logs",
        "notification_jobs",
        "device_push_tokens",
        "notification_preferences",
        "wishlist_contributions",
        "savings_goals",
        "transactions",
        "recurring_expenses",
        "custom_categories",
        "refresh_tokens",
    ]
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())
    for table_name in phase2_tables:
        if table_name in existing:
            op.drop_table(table_name)
