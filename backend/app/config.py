import os
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
def normalize_database_url(value: str) -> str:
    # Render supplies a standard Postgres URI; this project uses psycopg 3.
    for prefix in ('postgres://', 'postgresql://'):
        if value.startswith(prefix):
            return 'postgresql+psycopg://' + value[len(prefix):]
    return value

DATABASE_URL = normalize_database_url(os.getenv('DATABASE_URL', 'sqlite:///' + str(ROOT / 'returnwise.db')))
API_KEY = os.getenv('API_KEY', '')
ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(',')
THRESHOLDS = [float(x) for x in os.getenv('RISK_THRESHOLDS', '0.3,0.6,0.8').split(',')]
if len(THRESHOLDS) != 3 or not 0 < THRESHOLDS[0] < THRESHOLDS[1] < THRESHOLDS[2] < 1:
    raise ValueError('RISK_THRESHOLDS must contain three increasing values between 0 and 1')
RETURN_WINDOW = int(os.getenv('RETURN_WINDOW_DAYS', '30'))
