"""add_celery_execution_fields

Revision ID: e3780ce9affd
Revises: 1e6727a743f1
Create Date: 2026-08-15 16:47:01.032384

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3780ce9affd'
down_revision: Union[str, None] = '1e6727a743f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    
    # Safely add current_stage
    conn.execute(sa.text(
        "ALTER TABLE pipeline_executions ADD COLUMN IF NOT EXISTS current_stage VARCHAR NOT NULL DEFAULT 'PENDING'"
    ))
    
    # Safely add celery_task_id
    conn.execute(sa.text(
        "ALTER TABLE pipeline_executions ADD COLUMN IF NOT EXISTS celery_task_id VARCHAR"
    ))
    
    # Safely add retry_count
    conn.execute(sa.text(
        "ALTER TABLE pipeline_executions ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0"
    ))


def downgrade() -> None:
    op.drop_column('pipeline_executions', 'retry_count')
    op.drop_column('pipeline_executions', 'celery_task_id')
    op.drop_column('pipeline_executions', 'current_stage')
