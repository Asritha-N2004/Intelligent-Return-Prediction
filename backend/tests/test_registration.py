import pytest
from backend.app import auth
from backend.app.db import Session,AuthUser,Audit

HEADERS={'X-ReturnWise-Request':'1','X-API-Key':''}
ACCOUNT={'name':'New Demo Member','email':'new.member@example.com','password':'A long test password 123'}

@pytest.fixture(autouse=True)
def clean_browser(client):
    client.cookies.clear()
    auth._attempts.clear()
    yield
    client.cookies.clear()
    auth._attempts.clear()

def test_register_persist_and_sign_in_again(client):
    result=client.post('/api/auth/register',json=ACCOUNT,headers=HEADERS)
    assert result.status_code==201,result.text
    assert result.json()['role']=='member'
    assert 'password' not in result.text
    assert 'httponly' in result.headers['set-cookie'].lower()
    assert client.get('/api/auth/me').json()['name']==ACCOUNT['name']
    assert client.get('/api/orders',headers={'X-API-Key':''}).status_code==200
    with Session() as s:
        user=s.get(AuthUser,ACCOUNT['email'])
        assert user.password_hash!=ACCOUNT['password']
        assert auth.verify_password(ACCOUNT['password'],user.password_hash)
        assert user.role=='member'
        record=s.query(Audit).filter_by(action='auth.register').order_by(Audit.id.desc()).first()
        assert record.payload=={'email':ACCOUNT['email']}
    assert client.post('/api/auth/logout',headers=HEADERS).status_code==204
    assert client.get('/api/auth/me').status_code==401
    login=client.post('/api/auth/login',json={'email':ACCOUNT['email'],'password':ACCOUNT['password']},headers=HEADERS)
    assert login.status_code==200
    assert login.json()['name']==ACCOUNT['name']

def test_duplicate_email_is_normalized_and_admin_reserved(client):
    body={**ACCOUNT,'email':'Case.Member@Example.com'}
    assert client.post('/api/auth/register',json=body,headers=HEADERS).status_code==201
    assert client.post('/api/auth/register',json={**body,'email':' case.member@example.com '},headers=HEADERS).status_code==409
    assert client.post('/api/auth/register',json={**body,'email':auth.ACCOUNT_EMAIL.upper()},headers=HEADERS).status_code==409

@pytest.mark.parametrize('changes',[
    {'password':'short'},
    {'email':'invalid-email'},
    {'name':'  '},
    {'role':'admin'},
])
def test_invalid_registration(client,changes):
    assert client.post('/api/auth/register',json={**ACCOUNT,**changes},headers=HEADERS).status_code==422

def test_browser_header_required(client):
    assert client.post('/api/auth/register',json=ACCOUNT).status_code==403

def test_registered_member_cannot_approve_or_retrain(client):
    body={**ACCOUNT,'email':'member.permissions@example.com'}
    assert client.post('/api/auth/register',json=body,headers=HEADERS).status_code==201
    assert client.post('/api/model/retrain',headers=HEADERS).status_code==403
    assert client.post('/api/decisions/99999/approve',json={'approved':True,'reviewer':'Member','note':'Test review'},headers=HEADERS).status_code==403

def test_inactive_user_cannot_reuse_session_or_login(client):
    body={**ACCOUNT,'email':'inactive.member@example.com'}
    assert client.post('/api/auth/register',json=body,headers=HEADERS).status_code==201
    with Session.begin() as s:s.get(AuthUser,body['email']).active=False
    assert client.get('/api/auth/me').status_code==401
    assert client.post('/api/auth/login',json={'email':body['email'],'password':body['password']},headers=HEADERS).status_code==401

def test_registration_throttled(client):
    body={**ACCOUNT,'email':auth.ACCOUNT_EMAIL}
    for _ in range(10):
        assert client.post('/api/auth/register',json=body,headers=HEADERS).status_code==409
    assert client.post('/api/auth/register',json=body,headers=HEADERS).status_code==429
