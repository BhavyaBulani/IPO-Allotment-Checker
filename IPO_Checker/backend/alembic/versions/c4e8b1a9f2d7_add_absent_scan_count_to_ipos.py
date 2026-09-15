"""Add absent_scan_count to ipos

Tracks how many consecutive registrar-dropdown scans have conclusively found
an IPO missing from its registrar's allotment portal. The sync uses it to hide
IPOs that a registrar has removed (validated=False, status -> Closed) without
deleting the row, so saved allotment results survive.

Revision ID: c4e8b1a9f2d7
Revises: f1a2b3c4d5e6
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4e8b1a9f2d7'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'ipos',
        sa.Column(
            'absent_scan_count',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('0'),
        ),
    )


def downgrade() -> None:
    op.drop_column('ipos', 'absent_scan_count')
