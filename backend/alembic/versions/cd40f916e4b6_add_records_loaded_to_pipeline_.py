"""add records_loaded to pipeline_executions

Revision ID: cd40f916e4b6
Revises: 85b0e57ada67
Create Date: 2026-08-08 17:51:54.152241

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd40f916e4b6'
down_revision: Union[str, None] = '85b0e57ada67'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('pipeline_executions', sa.Column('records_loaded', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('pipeline_executions', 'records_loaded')
