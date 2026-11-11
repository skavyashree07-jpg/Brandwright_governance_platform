"""Add organisation-owned brands and optional brand scopes."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_brand_management"
down_revision = "0004_review_progress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(length=120), nullable=True),
        sa.Column("website_url", sa.String(length=2048), nullable=True),
        sa.Column("logo_file_key", sa.Text(), nullable=True),
        sa.Column("primary_colour", sa.String(length=7), nullable=True),
        sa.Column("secondary_colour", sa.String(length=7), nullable=True),
        sa.Column("voice", sa.String(length=120), nullable=True),
        sa.Column("target_audience", sa.Text(), nullable=True),
        sa.Column("mission", sa.Text(), nullable=True),
        sa.Column("vision", sa.Text(), nullable=True),
        sa.Column("guidelines", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_brands_organisation_status", "brands", ["organisation_id", "status"])
    op.create_index(
        "uq_brands_organisation_name_lower",
        "brands",
        ["organisation_id", sa.text("lower(name)")],
        unique=True,
    )

    for table in ("guideline_docs", "rules", "facts", "terms", "assets", "content_items"):
        op.add_column(
            table,
            sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            f"fk_{table}_brand_id_brands",
            table,
            "brands",
            ["brand_id"],
            ["id"],
        )
        op.create_index(f"ix_{table}_brand_id", table, ["brand_id"])


def downgrade() -> None:
    for table in ("content_items", "assets", "terms", "facts", "rules", "guideline_docs"):
        op.drop_index(f"ix_{table}_brand_id", table_name=table)
        op.drop_constraint(f"fk_{table}_brand_id_brands", table, type_="foreignkey")
        op.drop_column(table, "brand_id")
    op.drop_index("ix_brands_organisation_status", table_name="brands")
    op.drop_index("uq_brands_organisation_name_lower", table_name="brands")
    op.drop_table("brands")
