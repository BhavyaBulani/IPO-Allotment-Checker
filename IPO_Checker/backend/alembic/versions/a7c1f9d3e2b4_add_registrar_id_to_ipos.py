"""Add registrar_id to ipos

Revision ID: a7c1f9d3e2b4
Revises: 93bad3ee7afa
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7c1f9d3e2b4'
down_revision: Union[str, Sequence[str], None] = '93bad3ee7afa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ipos', sa.Column('registrar_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_ipos_registrar_id',
        'ipos', 'registrars',
        ['registrar_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_ipos_registrar_id', 'ipos', type_='foreignkey')
    op.drop_column('ipos', 'registrar_id')
