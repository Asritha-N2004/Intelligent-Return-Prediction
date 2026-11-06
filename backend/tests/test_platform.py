import pytest
from backend.app.db import Session,Warehouse,Decision,AgentLog
from backend.app.schemas import Inspection
from backend.app.services import disposition

def test_authentication(client):
    assert client.get('/api/orders',headers={'X-API-Key':'wrong'}).status_code==401
    assert client.get('/api/health').json()['model_ready']

@pytest.mark.parametrize('path',['/api/dashboard/overview','/api/dashboard/return-statistics','/api/dashboard/revenue-impact','/api/dashboard/return-trends','/api/customers','/api/customers/CUS-0000','/api/customers/CUS-0000/behavior','/api/orders','/api/orders/ORD-00001','/api/predictions','/api/agents/status','/api/agents/logs','/api/logistics/recommendations','/api/disposition/recommendations','/api/refunds','/api/analytics/returns','/api/analytics/products','/api/analytics/customers','/api/analytics/logistics','/api/model/performance','/api/model/feature-importance','/api/warehouses','/api/eda','/api/decisions'])
def test_read_endpoints(client,path):
    assert client.get(path).status_code==200

def test_predictions_persist_and_shap_adds_up(client):
    r=client.post('/api/predictions/return',json={'order_id':'ORD-00001'})
    assert r.status_code==200,r.text
    result=r.json(); assert 0<=result['return_probability']<=1
    assert abs(result['base_probability']+sum(f['contribution'] for f in result['factors'])-result['return_probability'])<1e-5
    assert client.get(f"/api/predictions/{result['id']}").json()['model_version']==result['model_version']

def test_optimization_capacity_and_infeasibility(client):
    good=client.post('/api/logistics/optimize',json={'order_id':'ORD-00001'}).json()
    assert good['status']=='recommended'; assert good['recommended']['total_cost']>0
    with Session.begin() as s:
        for w in s.query(Warehouse): w.used=w.capacity
    try:
        assert client.post('/api/logistics/optimize',json={'order_id':'ORD-00001'}).json()['status']=='infeasible'
    finally:
        with Session.begin() as s:
            for w in s.query(Warehouse): w.used=0

def test_inspection_gate_and_unsafe_goods():
    data={'product_price':1000,'quantity':1}
    assert disposition(data,None)['recommendation'] is None
    r=disposition(data,Inspection(order_id='ORD-00001',inspected=True,condition='unsafe',resale_value=1000))
    assert r['recommendation'] in ['Recycle','Dispose']

def test_refund_date_policy(client):
    d=client.get('/api/orders/ORD-00001').json()['delivery_date']
    good=client.post('/api/refunds/evaluate',json={'order_id':'ORD-00001','requested_date':d}).json()
    assert good['eligible']; assert not good['financial_transaction_initiated']
    assert not client.post('/api/refunds/evaluate',json={'order_id':'ORD-00001','requested_date':'2020-01-01'}).json()['eligible']

def test_workflow_audit_and_approval_gate(client):
    r=client.post('/api/agents/run',json={'order_id':'ORD-00001'})
    assert r.status_code==200,r.text
    report=r.json(); assert report['status']=='pending_approval'; assert len(report['outputs'])==9
    logs=client.get('/api/agents/'+report['execution_id']).json()['logs']; assert len(logs)==9
    body={'approved':True,'reviewer':'Test reviewer','note':'Reviewed evidence'}
    assert client.post(f"/api/decisions/{report['decision_id']}/approve",json=body).status_code==409
    r=client.post('/api/agents/run',json={'order_id':'ORD-00001','inspection':{'order_id':'ORD-00001','inspected':True,'condition':'new','resale_value':1000}})
    assert r.status_code==200,r.text
    did=r.json()['decision_id']
    assert client.post(f'/api/decisions/{did}/approve',json=body).json()['status']=='approved'
    assert client.post(f'/api/decisions/{did}/approve',json=body).status_code==409

def test_insights_use_database_facts(client):
    r=client.post('/api/ai/chat',json={'question':'What is the return rate?'}).json()
    assert r['facts']['total_orders']==client.get('/api/dashboard/overview').json()['total_orders']
    assert r['mode']=='deterministic'

def test_validation_and_pagination(client):
    assert client.post('/api/predictions/return',json={'order_id':'MISSING'}).status_code==404
    assert client.get('/api/orders?limit=10000').status_code==422
    assert client.post('/api/agents/run',json={'order_id':'ORD-00001','inspection':{'order_id':'ORD-00002'}}).status_code==422
    assert client.post('/api/logistics/optimize',json={'order_id':'ORD-00001','environmental_penalty':-1}).status_code==422
    a=client.get('/api/orders?limit=3&page=1').json(); b=client.get('/api/orders?limit=3&page=2').json()
    assert not set(x['order_id'] for x in a['items'])&set(x['order_id'] for x in b['items'])

def test_order_creation_and_duplicate_conflict(client):
    body={'order_id':'ORD-TEST','customer_id':'CUS-TEST','product_id':'PRD-TEST','product_category':'Apparel','product_price':1000,'order_date':'2026-11-01','delivery_date':'2026-11-03','customer_location':'Mumbai','previous_orders':5,'previous_returns':1}
    assert client.post('/api/orders',json=body).status_code==201
    assert client.get('/api/orders/ORD-TEST').json()['product_price']==1000
    assert client.post('/api/orders',json=body).status_code==409
    body['previous_returns']=8
    assert client.post('/api/orders',json=body).status_code==422
