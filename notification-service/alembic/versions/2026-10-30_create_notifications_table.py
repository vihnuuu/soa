"""create_notifications_table

Revision ID: 2ee0ef5922b3
Revises: 
Create Date: 2026-10-30 22:37:39.281317

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ee0ef5922b3'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('notification',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('loan_id', sa.UUID(), nullable=False),
        sa.Column('recipient', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'SENT', 'FAILED', name='notification_status_enum'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('notification_pkey'))
    )
    op.create_index(op.f('notification_loan_id_idx'), 'notification', ['loan_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('notification_loan_id_idx'), table_name='notification')
    op.drop_table('notification')
    sa.Enum(name='notification_status_enum').drop(op.get_bind(), checkfirst=True)