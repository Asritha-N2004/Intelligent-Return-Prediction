import os
import uuid
from pathlib import Path
# Isolated persistent database; never mutate the user's demo database.
TEST_DIR=Path(__file__).resolve().parents[2]/'.test-runtime'/str(uuid.uuid4())
TEST_DIR.mkdir(parents=True,exist_ok=True)
os.environ['DATABASE_URL']='sqlite:///'+str(TEST_DIR/'test.db')
os.environ['API_KEY']='test-secret'
import pytest
from fastapi.testclient import TestClient
from backend.app.db import Base,engine
from backend.app.data import generate,seed_database
from backend.app.main import app
@pytest.fixture(scope='session')
def client():
    import pandas as pd
    from backend.app.config import ROOT
    Base.metadata.create_all(engine)
    seed_database(pd.read_csv(ROOT/'data/processed/transactions.csv'))
    with TestClient(app,headers={'X-API-Key':'test-secret'}) as c: yield c
    engine.dispose()
