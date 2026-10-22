"""bot_attempt_hourly / bot_attempt_daily / bot_attempt_sample: bounded bot-attempt history

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-22

Registration attempts rejected by the bot defenses (honeypot, form-token check,
URL-bearing names, disposable email domains), kept in three tiers so attack
trends stay visible while table sizes have a hard ceiling that does not depend
on attack volume - see services/bot_attempts.py for the retention and caps.
bot_attempt_sample_seq feeds the ring buffer's slot numbers.
"""
from alembic import op
import sqlalchemy as sa

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'bot_attempt_hourly',
        sa.Column('hour', sa.DateTime(timezone=True), primary_key=True),
        sa.Column('circle_slug', sa.String(50), primary_key=True),
        sa.Column('reason', sa.String(30), primary_key=True),
        sa.Column('count', sa.Integer, nullable=False, server_default='0'),
    )
    op.create_table(
        'bot_attempt_daily',
        sa.Column('day', sa.Date, primary_key=True),
        sa.Column('dimension', sa.String(20), primary_key=True),
        sa.Column('value', sa.String(100), primary_key=True),
        sa.Column('count', sa.Integer, nullable=False, server_default='0'),
    )
    op.create_table(
        'bot_attempt_sample',
        sa.Column('slot', sa.Integer, primary_key=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reason', sa.String(30), nullable=False),
        sa.Column('circle_slug', sa.String(50)),
        sa.Column('ip', sa.String(45)),
        sa.Column('user_agent', sa.String(100)),
        sa.Column('email', sa.String(100)),
        sa.Column('name', sa.String(100)),
    )
    op.execute('CREATE SEQUENCE bot_attempt_sample_seq')


def downgrade():
    op.execute('DROP SEQUENCE bot_attempt_sample_seq')
    op.drop_table('bot_attempt_sample')
    op.drop_table('bot_attempt_daily')
    op.drop_table('bot_attempt_hourly')
