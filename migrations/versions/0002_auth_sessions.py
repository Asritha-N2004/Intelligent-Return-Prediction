"""Persist opaque authenticated browser sessions."""
from alembic import op
import sqlalchemy as sa
revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None
def upgrade():
    # Initial installations may already include this table via bootstrap.
    if not sa.inspect(op.get_bind()).has_table('auth_sessions'):
        op.create_table('auth_sessions',sa.Column('id',sa.String(64),primary_key=True),sa.Column('email',sa.String(254),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
        op.create_index('ix_auth_sessions_expires_at','auth_sessions',['expires_at'])
def downgrade():
    op.drop_table('auth_sessions')
