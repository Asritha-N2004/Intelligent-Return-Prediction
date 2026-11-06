from alembic import context
from backend.app.db import Base, engine
target_metadata = Base.metadata
if context.is_offline_mode():
    from backend.app.config import DATABASE_URL
    context.configure(url=DATABASE_URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction(): context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction(): context.run_migrations()
