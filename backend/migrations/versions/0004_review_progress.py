"""Persist review job lifecycle and replayable progress events."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_review_progress"
down_revision = "0003_embedding_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content_versions", sa.Column("review_job_status", sa.String(), nullable=True))
    op.add_column("content_versions", sa.Column("review_stage", sa.String(), nullable=True))
    op.add_column("content_versions", sa.Column("source_alt_text", sa.Text(), nullable=True))
    op.create_table(
        "review_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["content_version_id"], ["content_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_review_events_version_id",
        "review_events",
        ["content_version_id", "id"],
    )
    op.create_index(
        "ix_review_events_org_id",
        "review_events",
        ["organisation_id", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_review_events_org_id", table_name="review_events")
    op.drop_index("ix_review_events_version_id", table_name="review_events")
    op.drop_table("review_events")
    op.drop_column("content_versions", "source_alt_text")
    op.drop_column("content_versions", "review_stage")
    op.drop_column("content_versions", "review_job_status")
