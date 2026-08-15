"""add pipeline schedules table and execution trigger fields

Revision ID: d9e87f654321
Revises: 1e6727a743f1
Create Date: 2026-08-15 23:56:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9e87f654321'
down_revision: Union[str, None] = 'e3780ce9affd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table('pipeline_schedules'):
        op.create_table(
            'pipeline_schedules',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('organization_id', sa.Integer(), nullable=False),
            sa.Column('pipeline_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('cron_expression', sa.String(), nullable=False),
            sa.Column('timezone', sa.String(), nullable=False, server_default='UTC'),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['pipeline_id'], ['pipelines.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_pipeline_schedules_enabled'), 'pipeline_schedules', ['enabled'], unique=False)
        op.create_index(op.f('ix_pipeline_schedules_id'), 'pipeline_schedules', ['id'], unique=False)
        op.create_index(op.f('ix_pipeline_schedules_next_run_at'), 'pipeline_schedules', ['next_run_at'], unique=False)
        op.create_index(op.f('ix_pipeline_schedules_organization_id'), 'pipeline_schedules', ['organization_id'], unique=False)
        op.create_index(op.f('ix_pipeline_schedules_pipeline_id'), 'pipeline_schedules', ['pipeline_id'], unique=False)

    exec_cols = {c['name'] for c in inspector.get_columns('pipeline_executions')}
    if 'trigger_type' not in exec_cols:
        op.add_column('pipeline_executions', sa.Column('trigger_type', sa.String(), server_default='MANUAL', nullable=False))

    if 'schedule_id' not in exec_cols:
        op.add_column('pipeline_executions', sa.Column('schedule_id', sa.Integer(), nullable=True))
        op.create_foreign_key('fk_pipeline_executions_schedule_id', 'pipeline_executions', 'pipeline_schedules', ['schedule_id'], ['id'], ondelete='SET NULL')
        op.create_index(op.f('ix_pipeline_executions_schedule_id'), 'pipeline_executions', ['schedule_id'], unique=False)



def downgrade() -> None:
    op.drop_constraint('fk_pipeline_executions_schedule_id', 'pipeline_executions', type_='foreignkey')
    op.drop_index(op.f('ix_pipeline_executions_schedule_id'), table_name='pipeline_executions')
    op.drop_column('pipeline_executions', 'schedule_id')
    op.drop_column('pipeline_executions', 'trigger_type')

    op.drop_index(op.f('ix_pipeline_schedules_pipeline_id'), table_name='pipeline_schedules')
    op.drop_index(op.f('ix_pipeline_schedules_organization_id'), table_name='pipeline_schedules')
    op.drop_index(op.f('ix_pipeline_schedules_next_run_at'), table_name='pipeline_schedules')
    op.drop_index(op.f('ix_pipeline_schedules_id'), table_name='pipeline_schedules')
    op.drop_index(op.f('ix_pipeline_schedules_enabled'), table_name='pipeline_schedules')
    op.execute("DROP TABLE IF EXISTS pipeline_schedules CASCADE")
