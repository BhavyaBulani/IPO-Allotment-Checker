"""Add ipos.name_key and a unique index over it, de-duplicating existing rows.

`ipos.name` had no uniqueness constraint, and three separate name-normalizing
implementations disagreed about what "the same IPO name" means — the manual
upload path in particular did not strip "SME", so "Ashutosh Fibre" and
"ASHUTOSH FIBRE LIMITED SME" produced different keys and became two rows for one
company. `name_key` stores the shared key so the database can reject a
duplicate instead of a human noticing one later.

Existing duplicates must be resolved before the unique index can be created.
`apply_name_key_backfill` hides the losing row (validated=False, status Closed)
and gives it a synthetic non-colliding key. Rows are never deleted, because
`allotment_results.ipo_id` references `ipos.id` and a delete would destroy real
check history.

Revision ID: d7f3a1c8b04e
Revises: c4e8b1a9f2d7
"""

import sqlalchemy as sa
from alembic import op

revision = 'd7f3a1c8b04e'
down_revision = 'c4e8b1a9f2d7'
branch_labels = None
depends_on = None

INDEX_NAME = 'uq_ipos_name_key'


def upgrade() -> None:
    op.add_column('ipos', sa.Column('name_key', sa.String(length=255), nullable=True))

    # Backfill and de-duplicate before the unique index goes on, so the index
    # creation cannot fail on pre-existing duplicates. Run on the migration's
    # own connection so this all commits or rolls back together.
    from ipo_sync.name_key_backfill import apply_name_key_backfill

    apply_name_key_backfill(op.get_bind())

    # Nullable on purpose: normalize_ipo_name() returns "" for an unusable name,
    # stored as NULL, and both MySQL and SQLite allow repeated NULLs in a unique
    # index — so a handful of junk names never block each other.
    op.create_index(INDEX_NAME, 'ipos', ['name_key'], unique=True)


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name='ipos')
    op.drop_column('ipos', 'name_key')
