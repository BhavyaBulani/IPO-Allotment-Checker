"""Add bigshare_flows table

Revision ID: f1a2b3c4d5e6
Revises: a7c1f9d3e2b4
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'a7c1f9d3e2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'bigshare_flows',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('ipo_name', sa.String(length=200), nullable=False),
        sa.Column('company_value', sa.String(length=200), nullable=False),
        sa.Column('selection_type', sa.String(length=20), nullable=False),
        sa.Column('pan', sa.String(length=10), nullable=False),
        sa.Column('captcha_token', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_activity', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'idx_bigshare_flows_last_activity',
        'bigshare_flows',
        ['last_activity'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_bigshare_flows_last_activity', table_name='bigshare_flows')
    op.drop_table('bigshare_flows')
