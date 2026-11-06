"""Persist human decisions used by Guideline Health."""
from alembic import op
from app.review.api_service.models import EngineFindingDecision

revision = "0003_guideline_health_decisions"
down_revision = "0002_guideline_evidence"
branch_labels = None
depends_on = None

def upgrade():
    EngineFindingDecision.__table__.create(bind=op.get_bind(), checkfirst=True)

def downgrade():
    EngineFindingDecision.__table__.drop(bind=op.get_bind(), checkfirst=True)
