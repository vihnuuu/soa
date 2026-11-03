"""create_books_table

Revision ID: ea4a4f97200e
Revises: 
Create Date: 2026-10-30 22:29:52.467983

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea4a4f97200e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('book',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('author', sa.String(length=255), nullable=False),
    sa.Column('owner_id', sa.UUID(), nullable=False),
    sa.Column('is_available', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('book_pkey'))
    )
    op.create_index(op.f('book_owner_id_idx'), 'book', ['owner_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('book_owner_id_idx'), table_name='book')
    op.drop_table('book')