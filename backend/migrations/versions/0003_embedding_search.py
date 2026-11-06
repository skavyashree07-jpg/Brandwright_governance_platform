"""Add term embeddings and vector search indexes."""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0003_embedding_search"
down_revision = "0002_review_configuration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("terms", sa.Column("embedding", Vector(1536), nullable=True))
    op.execute(
        "CREATE INDEX ix_rules_embedding_hnsw "
        "ON rules USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_facts_embedding_hnsw "
        "ON facts USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_terms_embedding_hnsw "
        "ON terms USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_terms_embedding_hnsw")
    op.execute("DROP INDEX ix_facts_embedding_hnsw")
    op.execute("DROP INDEX ix_rules_embedding_hnsw")
    op.drop_column("terms", "embedding")
