"""rename templates to orchestrations

Revision ID: 96711a0d8040
Revises: aa0aa2c8765a
Create Date: 2026-06-18 22:41:53.533504

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96711a0d8040'
down_revision: Union[str, None] = 'aa0aa2c8765a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """将应用模板相关表和字段重命名为应用编排。"""
    # 重命名表
    op.rename_table('app_templates', 'app_orchestrations')

    # 重命名 app_instances 中相关字段，并更新外键引用
    with op.batch_alter_table('app_instances', schema=None) as batch_op:
        batch_op.alter_column(
            'template_id',
            new_column_name='orchestration_id',
            existing_type=sa.INTEGER(),
            nullable=True,
        )
        batch_op.alter_column(
            'template_version',
            new_column_name='orchestration_version',
            existing_type=sa.VARCHAR(length=20),
        )
        batch_op.create_foreign_key(
            'fk_app_instances_orchestration_id',
            'app_orchestrations',
            ['orchestration_id'],
            ['id'],
        )


def downgrade() -> None:
    """回滚应用编排重命名。"""
    with op.batch_alter_table('app_instances', schema=None) as batch_op:
        batch_op.drop_constraint('fk_app_instances_orchestration_id', type_='foreignkey')
        batch_op.alter_column(
            'orchestration_version',
            new_column_name='template_version',
            existing_type=sa.VARCHAR(length=20),
        )
        batch_op.alter_column(
            'orchestration_id',
            new_column_name='template_id',
            existing_type=sa.INTEGER(),
            nullable=True,
        )

    op.rename_table('app_orchestrations', 'app_templates')
