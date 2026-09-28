"""circle_admins table - per-circle admin scoping

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-30

"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'circle_admins',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('email', sa.String(254), nullable=False),
        sa.Column('circle_slug', sa.String(50), sa.ForeignKey('circles.slug'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('email', 'circle_slug', name='uq_circle_admins_email_circle'),
    )
    op.create_index('ix_circle_admins_circle_slug', 'circle_admins', ['circle_slug'])
    op.create_index('ix_circle_admins_email', 'circle_admins', ['email'])


def downgrade():
    op.drop_table('circle_admins')
