""Initial migration schema creation""

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    op.create_table(
        'organisations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )
    
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('organisation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organisations.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'guideline_docs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organisation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organisations.id'), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organisation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organisations.id'), nullable=False),
        sa.Column('guideline_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('guideline_docs.id'), nullable=True),
        sa.Column('clause_number', sa.String(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('channels', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True),
        sa.Column('sensitivity', sa.String(), nullable=True),
        sa.Column('embedding', pgvector.sqlalchemy.vector.Vector(1536), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'facts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organisation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organisations.id'), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('owner', sa.String(), nullable=True),
        sa.Column('source_url', sa.String(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('embedding', pgvector.sqlalchemy.vector.Vector(1536), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'terms',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organisation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organisations.id'), nullable=False),
        sa.Column('preferred', sa.String(), nullable=False),
        sa.Column('banned', sa.String(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'assets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organisation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organisations.id'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('file_url', sa.String(), nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'content_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organisation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organisations.id'), nullable=False),
        sa.Column('creator_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('current_version_no', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'content_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('content_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('content_items.id'), nullable=False),
        sa.Column('version_no', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('intent', sa.String(), nullable=False),
        sa.Column('channel', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'findings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('content_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('content_versions.id'), nullable=False),
        sa.Column('span_start', sa.Integer(), nullable=True),
        sa.Column('span_end', sa.Integer(), nullable=True),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('check_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('source_type', sa.String(), nullable=True),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('suggestion_text', sa.Text(), nullable=True),
        sa.Column('intent_preserved', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'finding_decisions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('finding_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('findings.id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'comments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('content_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('content_items.id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('span_start', sa.Integer(), nullable=True),
        sa.Column('span_end', sa.Integer(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organisation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organisations.id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'ai_usage_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organisation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organisations.id'), nullable=False),
        sa.Column('service', sa.String(), nullable=False),
        sa.Column('purpose', sa.String(), nullable=False),
        sa.Column('redacted_bool', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'fact_usage',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('content_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('content_versions.id'), nullable=False),
        sa.Column('fact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('facts.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organisation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organisations.id'), nullable=False),
        sa.Column('alert_type', sa.String(), nullable=False),
        sa.Column('ref_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'rule_clarifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('rule_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('rules.id'), nullable=False),
        sa.Column('drafted_text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

def downgrade() -> None:
    op.drop_table('rule_clarifications')
    op.drop_table('alerts')
    op.drop_table('fact_usage')
    op.drop_table('ai_usage_log')
    op.drop_table('audit_log')
    op.drop_table('comments')
    op.drop_table('finding_decisions')
    op.drop_table('findings')
    op.drop_table('content_versions')
    op.drop_table('content_items')
    op.drop_table('assets')
    op.drop_table('terms')
    op.drop_table('facts')
    op.drop_table('rules')
    op.drop_table('guideline_docs')
    op.drop_table('users')
    op.drop_table('organisations')
