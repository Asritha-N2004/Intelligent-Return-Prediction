import pytest
from sqlalchemy import func, select
from backend.app.config import normalize_database_url
from backend.app.db import Session, Order, ModelVersion
from scripts.start_backend import prepare_database, validate_runtime

@pytest.mark.parametrize('value,expected',[
    ('postgres://user:pass@db/name','postgresql+psycopg://user:pass@db/name'),
    ('postgresql://user:pass@db/name','postgresql+psycopg://user:pass@db/name'),
    ('postgresql+psycopg://user:pass@db/name','postgresql+psycopg://user:pass@db/name'),
    ('sqlite:///local.db','sqlite:///local.db'),
])
def test_render_database_uri(value,expected):
    assert normalize_database_url(value)==expected

def test_startup_requires_production_login(monkeypatch):
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.delenv('LOGIN_PASSWORD_HASH',raising=False)
    with pytest.raises(RuntimeError,match='LOGIN_EMAIL'):
        validate_runtime()

def test_repeated_deploy_start_preserves_orders_and_model_version(client,monkeypatch):
    monkeypatch.setenv('SEED_DEMO_DATA','true')
    with Session() as session: before=session.scalar(select(func.count(Order.id)))
    prepare_database()
    with Session() as session: versions=session.scalar(select(func.count(ModelVersion.id)))
    prepare_database()
    with Session() as session:
        assert session.scalar(select(func.count(Order.id)))==before
        assert session.scalar(select(func.count(ModelVersion.id)))==versions
