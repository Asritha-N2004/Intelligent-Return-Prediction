"""Render entry point: migrate, optionally seed the demo, then start the API."""
import json
import os
from contextlib import contextmanager
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from backend.app.config import ROOT
from backend.app.db import engine, Session, ModelVersion

def validate_runtime():
    if os.getenv('APP_ENV') == 'production':
        if not os.getenv('LOGIN_EMAIL') or not os.getenv('LOGIN_PASSWORD_HASH'):
            raise RuntimeError('Configure LOGIN_EMAIL and LOGIN_PASSWORD_HASH in Render before starting.')
    for path in ('artifacts/model.joblib', 'reports/model_performance.json'):
        if not (ROOT / path).is_file():
            raise RuntimeError(f'Missing {path}; run bootstrap during the Docker build.')

@contextmanager
def initialization_lock():
    # Serialize migrations/seeding across overlapping Render deployment starts.
    if engine.dialect.name == 'postgresql':
        with engine.connect() as connection:
            connection.execute(text('SELECT pg_advisory_lock(732194020)'))
            try:
                yield
            finally:
                connection.execute(text('SELECT pg_advisory_unlock(732194020)'))
    else:
        yield

def prepare_database():
    with initialization_lock():
        config = Config(str(ROOT / 'alembic.ini'))
        config.set_main_option('script_location', str(ROOT / 'migrations'))
        command.upgrade(config, 'head')
        if os.getenv('SEED_DEMO_DATA', 'false').lower() == 'true':
            import pandas as pd
            from backend.app.data import seed_database
            seed_database(pd.read_csv(ROOT / 'data/processed/transactions.csv'))
        report = json.loads((ROOT / 'reports/model_performance.json').read_text(encoding='utf-8'))
        with Session.begin() as session:
            if not session.scalar(select(ModelVersion).where(ModelVersion.version == report['version'])):
                session.add(ModelVersion(version=report['version'], metrics=report))
    print('Database migrations and configured initialization completed.', flush=True)

def main():
    validate_runtime()
    prepare_database()
    import sys
    os.execv(sys.executable, [sys.executable, '-m', 'uvicorn', 'backend.app.main:app',
                             '--host', '0.0.0.0', '--port', os.getenv('PORT', '8000')])

if __name__ == '__main__':
    main()
