"""Initial relational schema, including recommendation and audit records."""
from alembic import op
from backend.app.db import Base
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None
def upgrade():
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)
def downgrade():
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
