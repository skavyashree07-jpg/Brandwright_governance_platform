"""Create isolated AI review engine tables."""
from alembic import op
from app.review.api_service.database import Base
from app.review.api_service import models  # noqa: F401

revision = "0001_review_engine"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

def downgrade():
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
