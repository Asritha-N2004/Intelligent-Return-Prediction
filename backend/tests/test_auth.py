from datetime import datetime,timedelta,timezone
from backend.app.db import Session,AuthSession
from backend.app.auth import COOKIE,token_hash
HEADERS={'X-ReturnWise-Request':'1','X-API-Key':''}
CREDENTIALS={'email':'demo@returnwise.ai','password':'ReturnWise@123'}

def test_login_session_logout(client):
    client.cookies.clear()
    assert client.get('/api/orders',headers={'X-API-Key':''}).status_code==401
    assert client.get('/api/auth/me').status_code==401
    assert client.post('/api/auth/login',json=CREDENTIALS).status_code==403
    wrong=client.post('/api/auth/login',json={**CREDENTIALS,'password':'wrong'},headers=HEADERS)
    assert wrong.status_code==401
    r=client.post('/api/auth/login',json=CREDENTIALS,headers=HEADERS)
    assert r.status_code==200
    cookie=r.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie
    assert client.get('/api/auth/me').json()['email']==CREDENTIALS['email']
    assert client.get('/api/dashboard/overview',headers={'X-API-Key':''}).status_code==200
    assert client.post('/api/predictions/return',json={'order_id':'ORD-00001'},headers={'X-API-Key':''}).status_code==403
    raw=client.cookies.get(COOKIE)
    with Session() as s:
        assert s.get(AuthSession,token_hash(raw)) is not None
        assert s.get(AuthSession,raw) is None
    assert client.post('/api/auth/logout',headers=HEADERS).status_code==204
    assert client.get('/api/auth/me').status_code==401
    assert client.get('/api/orders',headers={'X-API-Key':''}).status_code==401

def test_expired_and_forged_sessions(client):
    r=client.post('/api/auth/login',json=CREDENTIALS,headers=HEADERS)
    assert r.status_code==200
    raw=client.cookies.get(COOKIE)
    with Session.begin() as s:s.get(AuthSession,token_hash(raw)).expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
    assert client.get('/api/auth/me').status_code==401
    client.cookies.clear();client.cookies.set(COOKIE,'fabricated-session')
    assert client.get('/api/orders',headers={'X-API-Key':''}).status_code==401
    client.cookies.clear()
