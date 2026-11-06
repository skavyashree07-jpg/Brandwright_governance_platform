"""Persist evidence references attached to guideline clarification drafts.

The first standalone migration uses current SQLAlchemy metadata, so on a fresh
install this column may already exist. The guard also supports databases created
by the earlier 0001 revision before the evidence field was added.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_guideline_evidence"
down_revision = "0001_review_engine"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("review_engine_clarifications")}
    if "evidence" not in columns:
        op.add_column("review_engine_clarifications", sa.Column(
            "evidence", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("review_engine_clarifications")}
    if "evidence" in columns:
        op.drop_column("review_engine_clarifications", "evidence")
