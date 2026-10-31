"""create_loans_and_outbox

Revision ID: f1b07edc2bd8
Revises: 
Create Date: 2026-10-30 22:37:27.880237

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f1b07edc2bd8'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('loan',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('book_id', sa.UUID(), nullable=False),
        sa.Column('borrower_name', sa.String(length=128), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'ACTIVE', 'CANCELLED', 'RETURNED', name='loan_status_enum'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('loan_pkey'))
    )
    op.create_index(op.f('loan_book_id_idx'), 'loan', ['book_id'], unique=False)

    op.create_table('outbox_message',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.Enum('NEW', 'PROCESSED', 'FAILED', name='outbox_status_enum'), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('outbox_message_pkey'))
    )
    op.create_index(op.f('outbox_message_status_idx'), 'outbox_message', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('outbox_message_status_idx'), table_name='outbox_message')
    op.drop_table('outbox_message')
    sa.Enum(name='outbox_status_enum').drop(op.get_bind(), checkfirst=True)

    op.drop_index(op.f('loan_book_id_idx'), table_name='loan')
    op.drop_table('loan')
    sa.Enum(name='loan_status_enum').drop(op.get_bind(), checkfirst=True)