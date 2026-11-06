"""Persist per-review AI service usage metadata without storing content."""
from alembic import op
from app.review.api_service.models import EngineAIUsage

revision = "0004_ai_usage_log"
down_revision = "0003_guideline_health_decisions"
branch_labels = None
depends_on = None

def upgrade():
    EngineAIUsage.__table__.create(bind=op.get_bind(), checkfirst=True)

def downgrade():
    EngineAIUsage.__table__.drop(bind=op.get_bind(), checkfirst=True)
