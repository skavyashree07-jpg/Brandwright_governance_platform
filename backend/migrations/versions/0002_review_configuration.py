"""Add deterministic rule configuration and edited decision text."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_review_configuration"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rules", sa.Column("type", sa.String(), nullable=True))
    op.add_column(
        "rules",
        sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column("finding_decisions", sa.Column("edited_text", sa.Text(), nullable=True))
    op.add_column("content_versions", sa.Column("source_file_key", sa.Text(), nullable=True))
    op.add_column("content_versions", sa.Column("review_job_id", sa.String(length=36), nullable=True))
    op.add_column("content_versions", sa.Column("review_error", sa.Text(), nullable=True))
    op.add_column("alerts", sa.Column("prior_status", sa.String(), nullable=True))
    op.add_column(
        "ai_usage_log",
        sa.Column("content_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_usage_log_content_version",
        "ai_usage_log",
        "content_versions",
        ["content_version_id"],
        ["id"],
    )
    op.add_column("ai_usage_log", sa.Column("external", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("ai_usage_log", sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("finding_decisions", "edited_text")
    op.drop_column("content_versions", "review_error")
    op.drop_column("content_versions", "review_job_id")
    op.drop_column("content_versions", "source_file_key")
    op.drop_column("alerts", "prior_status")
    op.drop_column("ai_usage_log", "blocked")
    op.drop_column("ai_usage_log", "external")
    op.drop_constraint("fk_ai_usage_log_content_version", "ai_usage_log", type_="foreignkey")
    op.drop_column("ai_usage_log", "content_version_id")
    op.drop_column("rules", "config")
    op.drop_column("rules", "type")
