"""Add registrar_scan_health, so a registrar portal that stops being readable is visible.

The registrar dropdown scan is how an IPO becomes checkable, and how one that a
portal has dropped stops being checkable. Both directions depend on the scan
actually reading the portal: a scrape that raises, or returns zero options, is
treated as inconclusive and changes nothing. That is deliberate, but it means a
portal whose DOM changes silently freezes the dropdown in place — no error, no
alert, and `/health` stays green throughout.

This table records, per registrar, when its portal was last read successfully
and how many consecutive scans have failed. `/health/registrars` exposes it and
a run of failures is logged at ERROR. See ipo_sync/scan_health.py.

Revision ID: e91b6c2d5a70
Revises: d7f3a1c8b04e
"""

import sqlalchemy as sa
from alembic import op

revision = 'e91b6c2d5a70'
down_revision = 'd7f3a1c8b04e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'registrar_scan_health',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('registrar_name', sa.String(length=100), nullable=False),
        sa.Column('last_attempt_at', sa.DateTime(), nullable=True),
        sa.Column('last_success_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.String(length=500), nullable=True),
        sa.Column(
            'consecutive_failures', sa.Integer(), nullable=False, server_default=sa.text('0')
        ),
        sa.Column(
            'updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('registrar_name', name='uq_registrar_scan_health_name'),
    )


def downgrade() -> None:
    op.drop_table('registrar_scan_health')
