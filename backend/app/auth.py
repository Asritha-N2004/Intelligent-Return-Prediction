"""Database-backed accounts and HTTP-only opaque sessions."""
import hashlib
import hmac
import os
import secrets
import threading
import time
from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,HTTPException,Request,Response
from pydantic import BaseModel,Field,field_validator,ConfigDict
from sqlalchemy.exc import IntegrityError
from .db import Session,AuthSession,AuthUser,Audit
PRODUCTION=os.getenv('APP_ENV','development')=='production'
ACCOUNT_EMAIL=os.getenv('LOGIN_EMAIL','demo@returnwise.ai').strip().lower()
PASSWORD_HASH=os.getenv('LOGIN_PASSWORD_HASH','')
COOKIE='returnwise_session'
SECURE=PRODUCTION or os.getenv('SESSION_COOKIE_SECURE','false').lower()=='true'
TTL=8*60*60
_attempts={}
_lock=threading.Lock()
router=APIRouter(prefix='/api/auth',tags=['Authentication'])

def hash_password(password,salt=None):
    salt=salt or secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),600000).hex()
    return f'pbkdf2_sha256$600000${salt}${digest}'

def verify_password(password,encoded):
    try:
        algorithm,iterations,salt,expected=encoded.split('$')
        if algorithm!='pbkdf2_sha256' or not 200000<=int(iterations)<=2000000:return False
        actual=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),int(iterations)).hex()
        return hmac.compare_digest(actual,expected)
    except (ValueError,TypeError):return False

def valid_password(password):
    encoded=PASSWORD_HASH
    if not encoded:
        if PRODUCTION:return False
        encoded=hash_password('ReturnWise@123','returnwise-local-demo-only')
    return verify_password(password,encoded)

def token_hash(token):return hashlib.sha256(token.encode()).hexdigest()

def current_identity(request):
    token=request.cookies.get(COOKIE)
    if not token:return None
    with Session() as s:
        row=s.get(AuthSession,token_hash(token))
        if not row:return None
        expiry=row.expires_at
        if expiry.tzinfo is None:expiry=expiry.replace(tzinfo=timezone.utc)
        if expiry<=datetime.now(timezone.utc):
            s.delete(row);s.commit();return None
        if row.email==ACCOUNT_EMAIL:
            name,role='Operations team','admin'
        else:
            user=s.get(AuthUser,row.email)
            if not user or not user.active:return None
            name,role=user.name,user.role
        return {'email':row.email,'name':name,'role':role,'expires_at':expiry.isoformat()}

def require_browser_header(request):
    if request.headers.get('X-ReturnWise-Request')!='1':raise HTTPException(403,'Invalid browser request')

def rate_limit(request,scope,maximum=5):
    ip=request.client.host if request.client else 'unknown'
    key=(scope,ip);now=time.monotonic()
    with _lock:
        for old in list(_attempts):
            if now-_attempts[old][0]>900:del _attempts[old]
        started,count=_attempts.get(key,(now,0))
        if count>=maximum:raise HTTPException(429,'Too many attempts. Try again in 15 minutes.')
        _attempts[key]=(started,count+1)
    return key

def issue_session(s,email,name,role,request,response,action='auth.login'):
    token=secrets.token_urlsafe(32);expiry=datetime.now(timezone.utc)+timedelta(seconds=TTL)
    old=request.cookies.get(COOKIE)
    if old:
        existing=s.get(AuthSession,token_hash(old))
        if existing:s.delete(existing)
    s.add(AuthSession(id=token_hash(token),email=email,expires_at=expiry))
    s.add(Audit(action=action,payload={'email':email}))
    response.set_cookie(COOKIE,token,max_age=TTL,httponly=True,secure=SECURE,samesite='strict',path='/')
    response.headers['Cache-Control']='no-store'
    return {'email':email,'name':name,'role':role,'expires_at':expiry.isoformat()}

class Login(BaseModel):
    model_config=ConfigDict(extra='forbid')
    email:str=Field(min_length=3,max_length=254,pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    password:str=Field(min_length=1,max_length=256)
    @field_validator('email',mode='before')
    @classmethod
    def normalize_email(cls,value):return value.strip().lower() if isinstance(value,str) else value

class Registration(Login):
    name:str=Field(min_length=2,max_length=100)
    password:str=Field(min_length=12,max_length=256)
    @field_validator('name')
    @classmethod
    def normalize_name(cls,value):
        value=value.strip()
        if len(value)<2:raise ValueError('Enter your name (at least two characters)')
        return value

@router.post('/register',status_code=201)
def register(body:Registration,request:Request,response:Response):
    require_browser_header(request)
    rate_limit(request,'register',10)
    if body.email==ACCOUNT_EMAIL:raise HTTPException(409,'An account with this email already exists. Sign in instead.')
    encoded=hash_password(body.password)
    try:
        with Session.begin() as s:
            if s.get(AuthUser,body.email):raise HTTPException(409,'An account with this email already exists. Sign in instead.')
            s.add(AuthUser(email=body.email,name=body.name,password_hash=encoded,role='member',active=True))
            return issue_session(s,body.email,body.name,'member',request,response,'auth.register')
    except IntegrityError:
        raise HTTPException(409,'An account with this email already exists. Sign in instead.')

@router.post('/login')
def login(body:Login,request:Request,response:Response):
    require_browser_header(request)
    key=rate_limit(request,'login')
    with Session.begin() as s:
        if body.email==ACCOUNT_EMAIL:
            if PRODUCTION and not PASSWORD_HASH:raise HTTPException(503,'Login credentials have not been configured')
            correct=valid_password(body.password);name,role='Operations team','admin'
        else:
            user=s.get(AuthUser,body.email)
            if user:
                correct=verify_password(body.password,user.password_hash) and user.active
                name,role=user.name,user.role
            else:
                valid_password(body.password)
                correct=False;name,role='','member'
        if not correct:raise HTTPException(401,'Incorrect email or password')
        result=issue_session(s,body.email,name,role,request,response)
    with _lock:_attempts.pop(key,None)
    return result

@router.get('/me')
def me(request:Request,response:Response):
    response.headers['Cache-Control']='no-store'
    identity=current_identity(request)
    if not identity:raise HTTPException(401,'Sign in to continue')
    return identity

@router.post('/logout',status_code=204)
def logout(request:Request,response:Response):
    require_browser_header(request)
    token=request.cookies.get(COOKIE)
    with Session.begin() as s:
        row=s.get(AuthSession,token_hash(token)) if token else None
        if row:
            s.add(Audit(action='auth.logout',payload={'email':row.email}));s.delete(row)
    response.delete_cookie(COOKIE,path='/',httponly=True,secure=SECURE,samesite='strict')
    response.headers['Cache-Control']='no-store'
