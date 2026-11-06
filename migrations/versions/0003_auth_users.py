"""Persist self-service accounts without changing existing admin sessions."""
from alembic import op
import sqlalchemy as sa
revision='0003'
down_revision='0002'
branch_labels=None
depends_on=None
def upgrade():
    if not sa.inspect(op.get_bind()).has_table('auth_users'):
        op.create_table('auth_users',
            sa.Column('email',sa.String(254),primary_key=True),
            sa.Column('name',sa.String(100),nullable=False),
            sa.Column('password_hash',sa.String(256),nullable=False),
            sa.Column('role',sa.String(20),nullable=False),
            sa.Column('active',sa.Boolean(),nullable=False),
            sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
def downgrade():
    op.drop_table('auth_users')
