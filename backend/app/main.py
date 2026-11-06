import json
import logging
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import date
from fastapi import FastAPI,Depends,HTTPException,Query,Header,Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from .config import ROOT,API_KEY,ORIGINS
from .db import *
from .schemas import *
from . import services as svc
from .ml import predict,bundle,train
from .agents import AGENTS,run_workflow
logging.basicConfig(level=logging.INFO)
logger=logging.getLogger('returnwise')
train_lock=threading.Lock()
@asynccontextmanager
async def lifespan(app):
    # Never generate data or retrain at startup. Bootstrap/migrations are explicit.
    yield

from .auth import router as auth_router,current_identity,require_browser_header

def authenticate(request:Request,x_api_key:str|None=Header(default=None)):
    if request.url.path in ['/api/health','/api/auth/login','/api/auth/register','/api/auth/me','/api/auth/logout']: return
    if API_KEY and x_api_key and secrets.compare_digest(x_api_key,API_KEY): return
    identity=current_identity(request)
    if not identity: raise HTTPException(401,'Sign in to continue')
    if request.method not in ['GET','HEAD','OPTIONS']: require_browser_header(request)
    if identity['role']!='admin' and request.method=='POST' and (request.url.path=='/api/model/retrain' or request.url.path.endswith('/approve')):
        raise HTTPException(403,'An administrator must review this action')
    request.state.identity=identity
app=FastAPI(title='ReturnWise AI',version='1.0.0',docs_url='/api/docs',lifespan=lifespan,dependencies=[Depends(authenticate)])
app.include_router(auth_router)
app.add_middleware(CORSMiddleware,allow_origins=ORIGINS,allow_methods=['GET','POST'],allow_headers=['Content-Type','X-API-Key','X-ReturnWise-Request'])
(ROOT/'reports').mkdir(exist_ok=True)
# Reports contain synthetic aggregate data only. Operational APIs use authentication dependency.
app.mount('/reports',StaticFiles(directory=ROOT/'reports'),name='reports')
@app.exception_handler(IntegrityError)
async def conflict(req,exc): return JSONResponse(status_code=409,content={'detail':'Record conflicts with existing data'})
@app.exception_handler(RuntimeError)
async def unavailable(req,exc):
    logger.exception('Service unavailable')
    return JSONResponse(status_code=503,content={'detail':'Service unavailable; check bootstrap and server logs'})
@app.exception_handler(Exception)
async def unexpected(req,exc):
    logger.exception('Unhandled request failure')
    return JSONResponse(status_code=500,content={'detail':'Unexpected server error'})
def session():
    with Session() as s: yield s

def utc_iso(value):
    from datetime import timezone
    return value.replace(tzinfo=timezone.utc).isoformat() if value.tzinfo is None else value.isoformat()

def stored(row):
    return {'id':row.id,'order_id':row.order_id,'created_at':utc_iso(row.created_at),**row.payload}

def save(s,cls,oid,payload):
    row=cls(order_id=oid,payload=payload); s.add(row); s.add(Audit(action=cls.__tablename__+'.create',payload={'order_id':oid})); s.commit(); return stored(row)

def records(s,cls,page,limit):
    return {'items':[stored(r) for r in s.query(cls).order_by(cls.id.desc()).offset((page-1)*limit).limit(limit)],'total':s.query(func.count(cls.id)).scalar(),'page':page,'limit':limit}
@app.get('/api/health')
def health(s=Depends(session)):
    s.execute(__import__('sqlalchemy').text('SELECT 1'))
    return {'status':'ok','model_ready':(ROOT/'artifacts/model.joblib').exists(),'data_source':'synthetic','authentication_enabled':True}
@app.get('/api/dashboard/overview')
def dashboard(s=Depends(session)): return svc.overview(s)
@app.get('/api/dashboard/return-statistics')
@app.get('/api/analytics/returns')
def analytics(s=Depends(session)): return svc.analytics(s)
@app.get('/api/analytics/products')
def product_analytics(page:int=Query(1,ge=1),limit:int=Query(25,ge=1,le=200),s=Depends(session)):
    groups=s.query(Order.product_id,func.count(Order.id),func.sum(__import__('sqlalchemy').cast(Order.return_requested,Integer))).group_by(Order.product_id).order_by(Order.product_id)
    total=groups.count()
    return {'items':[{'product_id':pid,'orders':n,'returns':int(r or 0),'return_rate':float(r or 0)/n} for pid,n,r in groups.offset((page-1)*limit).limit(limit)],'total':total,'page':page}
@app.get('/api/dashboard/return-trends')
def trends(s=Depends(session)): return svc.analytics(s)['trends']
@app.get('/api/dashboard/revenue-impact')
def revenue(s=Depends(session)): return svc.overview(s)
@app.get('/api/customers')
@app.get('/api/analytics/customers')
def customers(page:int=Query(1,ge=1),limit:int=Query(25,ge=1,le=200),search:str='',s=Depends(session)):
    q=s.query(Customer)
    if search: q=q.filter(Customer.id.contains(search,autoescape=True))
    return {'items':[{'id':c.id,'location':c.location,'previous_orders':c.previous_orders,'previous_returns':c.previous_returns,'return_rate':c.previous_returns/max(c.previous_orders,1)} for c in q.order_by(Customer.id).offset((page-1)*limit).limit(limit)],'total':q.count(),'page':page}
@app.get('/api/customers/{cid}')
@app.get('/api/customers/{cid}/behavior')
def customer(cid:str,s=Depends(session)):
    c=s.get(Customer,cid)
    if not c: raise HTTPException(404,'Customer not found')
    orders=s.query(Order).filter_by(customer_id=cid).order_by(Order.order_date.desc()).limit(50).all()
    return {'id':cid,'location':c.location,'behavior':svc.behavior({'previous_orders':c.previous_orders,'previous_returns':c.previous_returns}),'orders':[o.data for o in orders]}
@app.get('/api/orders')
def orders(page:int=Query(1,ge=1),limit:int=Query(25,ge=1,le=200),search:str='',returned:bool|None=None,s=Depends(session)):
    q=s.query(Order)
    if search: q=q.filter(Order.id.contains(search,autoescape=True))
    if returned is not None: q=q.filter(Order.return_requested==returned)
    return {'items':[o.data for o in q.order_by(Order.id).offset((page-1)*limit).limit(limit)],'total':q.count(),'page':page,'limit':limit}
@app.get('/api/orders/{oid}')
def order(oid:str,s=Depends(session)): return svc.order_data(s,oid)
@app.post('/api/orders',status_code=201)
def create_order(body:OrderCreate,s=Depends(session)):
    data=body.model_dump(mode='json'); data.update(return_requested=0,return_reason='None',customer_return_rate=body.previous_returns/max(body.previous_orders,1))
    c=s.get(Customer,body.customer_id)
    if c and (c.location!=body.customer_location or c.previous_orders!=body.previous_orders or c.previous_returns!=body.previous_returns): raise HTTPException(409,'Existing customer history/location differs')
    if not c: s.add(Customer(id=body.customer_id,location=body.customer_location,previous_orders=body.previous_orders,previous_returns=body.previous_returns))
    p=s.get(Product,body.product_id)
    if p and p.category!=body.product_category: raise HTTPException(409,'Product category differs')
    if not p: s.add(Product(id=body.product_id,category=body.product_category,price=body.product_price,rating=body.product_rating))
    s.flush(); s.add(Order(id=body.order_id,customer_id=body.customer_id,product_id=body.product_id,order_date=str(body.order_date),return_requested=False,data=data)); s.flush()
    s.add(OrderItem(order_id=body.order_id,product_id=body.product_id,quantity=body.quantity,unit_price=body.product_price)); s.add(Audit(action='order.create',payload={'order_id':body.order_id})); s.commit(); return data
@app.post('/api/predictions/return')
def prediction(body:OrderRef,s=Depends(session)): return save(s,Prediction,body.order_id,predict(svc.order_data(s,body.order_id)))
@app.get('/api/predictions')
def predictions(page:int=Query(1,ge=1),limit:int=Query(25,ge=1,le=200),s=Depends(session)): return records(s,Prediction,page,limit)
@app.get('/api/predictions/{pid}')
def prediction_detail(pid:int,s=Depends(session)):
    r=s.get(Prediction,pid)
    if not r: raise HTTPException(404,'Prediction not found')
    return stored(r)
@app.post('/api/agents/run')
def agents_run(body:WorkflowRequest): return run_workflow(body)
@app.get('/api/agents/status')
def agents_status(s=Depends(session)):
    result=[]
    for key,name,desc in AGENTS:
        latest=s.query(AgentLog).filter_by(agent=key).order_by(AgentLog.id.desc()).first()
        result.append({'key':key,'name':name,'description':desc,'status':latest.status if latest else 'idle','last_execution':utc_iso(latest.created_at) if latest else None,'duration_ms':latest.duration_ms if latest else None,'latest_output':latest.payload if latest else None})
    return result
@app.get('/api/agents/logs')
def agent_logs(page:int=Query(1,ge=1),limit:int=Query(25,ge=1,le=200),s=Depends(session)):
    rows=s.query(AgentLog).order_by(AgentLog.id.desc()).offset((page-1)*limit).limit(limit).all()
    return {'items':[{**stored(r),'agent':r.agent,'status':r.status,'duration_ms':r.duration_ms,'execution_id':r.execution_id} for r in rows],'total':s.query(AgentLog).count()}
@app.get('/api/agents/{execution_id}')
def execution(execution_id:str,s=Depends(session)):
    rows=s.query(AgentLog).filter_by(execution_id=execution_id).order_by(AgentLog.id).all()
    decisions=s.query(Decision).all(); report=next((stored(d) for d in reversed(decisions) if d.payload.get('execution_id')==execution_id),None)
    if not rows and not report: raise HTTPException(404,'Execution not found')
    return {'logs':[{**stored(r),'agent':r.agent,'status':r.status,'duration_ms':r.duration_ms} for r in rows],'report':report}
@app.get('/api/decisions')
def decisions(page:int=Query(1,ge=1),limit:int=Query(25,ge=1,le=200),s=Depends(session)): return records(s,Decision,page,limit)
@app.post('/api/decisions/{did}/approve')
def approve(did:int,body:Approval,s=Depends(session)):
    row=s.get(Decision,did)
    if not row: raise HTTPException(404,'Decision not found')
    if row.payload.get('status')!='pending_approval': raise HTTPException(409,'Decision is not awaiting approval')
    disp=row.payload.get('outputs',{}).get('disposition',{})
    if body.approved and disp.get('status')=='awaiting_inspection': raise HTTPException(409,'Complete inspection and rerun workflow before approval')
    row.payload={**row.payload,'status':'approved' if body.approved else 'rejected','review':body.model_dump(),'reviewed_at':now().isoformat()}
    s.add(Audit(action='decision.review',payload={'decision_id':did,**body.model_dump()})); s.commit(); return stored(row)
@app.post('/api/logistics/optimize')
def logistics(body:LogisticsRequest,s=Depends(session)): return save(s,Logistics,body.order_id,svc.optimize(s,svc.order_data(s,body.order_id),body.environmental_penalty,body.deadline_days,body.transport_capacity))
@app.get('/api/logistics/recommendations')
@app.get('/api/analytics/logistics')
def logistics_records(page:int=Query(1,ge=1),limit:int=Query(25,ge=1,le=200),s=Depends(session)): return records(s,Logistics,page,limit)
@app.get('/api/warehouses')
def warehouses(s=Depends(session)): return [{'id':w.id,'location':w.location,'capacity':w.capacity,'used':w.used,'processing_cost':w.processing_cost,'processing_days':w.processing_days,'capabilities':w.capabilities} for w in s.query(Warehouse).all()]
@app.post('/api/disposition/recommend')
def disposition(body:Inspection,s=Depends(session)): return save(s,Disposition,body.order_id,svc.disposition(svc.order_data(s,body.order_id),body))
@app.get('/api/disposition/recommendations')
def dispositions(page:int=Query(1,ge=1),limit:int=Query(25,ge=1,le=200),s=Depends(session)): return records(s,Disposition,page,limit)
@app.post('/api/refunds/evaluate')
def refund(body:RefundRequest,s=Depends(session)): return save(s,Refund,body.order_id,svc.refund(svc.order_data(s,body.order_id),body.requested_date,body.proof_of_purchase))
@app.get('/api/refunds')
def refunds(page:int=Query(1,ge=1),limit:int=Query(25,ge=1,le=200),s=Depends(session)): return records(s,Refund,page,limit)
@app.get('/api/model/performance')
def performance(): return bundle()['report']
@app.get('/api/model/feature-importance')
def importance(): return bundle()['report']['feature_importance']
@app.post('/api/model/retrain')
def retrain(s=Depends(session)):
    if not train_lock.acquire(blocking=False): raise HTTPException(409,'Training already running')
    try:
        import pandas as pd
        report=train(pd.read_csv(ROOT/'data/processed/transactions.csv'))
        s.add(ModelVersion(version=report['version'],metrics=report)); s.add(Audit(action='model.retrain',payload={'version':report['version']})); s.commit(); return report
    finally: train_lock.release()
@app.post('/api/ai/insights')
@app.post('/api/ai/chat')
def ai(body:ChatRequest,s=Depends(session)): return svc.insights(s,body.question)
@app.get('/api/eda')
def eda():
    path=ROOT/'reports/eda.json'
    if not path.exists(): raise HTTPException(503,'Run bootstrap first')
    return json.loads(path.read_text(encoding='utf-8'))
