import time
import uuid
from datetime import date
from typing import TypedDict,Any
from langgraph.graph import StateGraph,START,END
from .db import Session,AgentLog,Decision,Prediction,RiskProfile,Anomaly,Logistics,Disposition,Refund,Audit
from .ml import predict
from . import services as svc
AGENTS=[('prediction','Return Prediction','ML probability and local SHAP attribution'),('behavior','Customer Behavior','Prior purchase and return history'),('reason','Return Reason Analysis','Feedback categorization'),('anomaly','Fraud & Anomaly Detection','Isolation Forest indicators for review'),('coordinator','Decision Coordinator','Combine evidence and identify conflicts'),('logistics','Reverse Logistics','Capacity-constrained cost optimization'),('disposition','Product Disposition','Inspection-based recovery recommendation'),('refund','Refund & Resolution','Policy eligibility, no transactions'),('intelligence','Business Intelligence','Summaries grounded in database aggregates')]
class State(TypedDict,total=False):
    execution_id:str
    order_id:str
    data:dict
    request:Any
    outputs:dict
    status:str
    review_requirement:str

def run_workflow(request):
    execution=str(uuid.uuid4())
    with Session() as s: data=svc.order_data(s,request.order_id)
    graph=StateGraph(State)
    def wrap(name,fn,record=None):
        def node(state):
            start=time.perf_counter()
            try:
                with Session.begin() as s:
                    output=fn(state,s)
                    if record: s.add(record(order_id=state['order_id'],payload=output))
                    s.add(AgentLog(execution_id=execution,agent=name,status='completed',duration_ms=(time.perf_counter()-start)*1000,order_id=state['order_id'],payload=output))
                return {'outputs':{**state.get('outputs',{}),name:output}}
            except Exception as exc:
                with Session.begin() as s: s.add(AgentLog(execution_id=execution,agent=name,status='failed',duration_ms=(time.perf_counter()-start)*1000,order_id=state['order_id'],payload={'error':type(exc).__name__}))
                raise
        return node
    graph.add_node('prediction',wrap('prediction',lambda st,s:predict(st['data']),Prediction))
    graph.add_node('behavior',wrap('behavior',lambda st,s:svc.behavior(st['data']),RiskProfile))
    graph.add_node('reason',wrap('reason',lambda st,s:svc.reason(st['data'])))
    graph.add_node('anomaly',wrap('anomaly',lambda st,s:svc.anomaly(st['data']),Anomaly))
    graph.add_node('coordinator',wrap('coordinator',lambda st,s:{'manual_review':st['outputs']['anomaly']['manual_review'],'recommendation':'Collect inspection, evaluate costs and eligibility; all sensitive recommendations require human review.'}))
    graph.add_node('logistics',wrap('logistics',lambda st,s:svc.optimize(s,st['data']),Logistics))
    graph.add_node('disposition',wrap('disposition',lambda st,s:svc.disposition(st['data'],request.inspection),Disposition))
    graph.add_node('refund',wrap('refund',lambda st,s:svc.refund(st['data'],request.requested_date or date.today()),Refund))
    graph.add_node('intelligence',wrap('intelligence',lambda st,s:svc.insights(s)))
    def persist(state):
        report={'execution_id':execution,'status':'pending_approval','outputs':state['outputs'],'requires_approval':True,'review_requirement':state['review_requirement'],'explanation':'Recommendations only; no payments, capacity reservations or product movements executed.'}
        with Session.begin() as s:
            row=Decision(order_id=request.order_id,payload=report); s.add(row); s.flush()
            s.add(Audit(action='workflow_completed',payload={'execution_id':execution,'decision_id':row.id}))
            report={**report,'decision_id':row.id}; row.payload=report
        return {'status':'pending_approval','outputs':{**state['outputs'],'final_report':report}}
    graph.add_node('persist',persist)
    graph.add_node('inspection_hold',lambda state:{'review_requirement':'Complete inspection and rerun before approval'})
    graph.add_node('review_ready',lambda state:{'review_requirement':'Human review required before any operational action'})
    graph.add_edge(START,'prediction')
    chain=['prediction','behavior','reason','anomaly','coordinator','logistics','disposition','refund','intelligence']
    for a,b in zip(chain,chain[1:]): graph.add_edge(a,b)
    graph.add_conditional_edges('intelligence',lambda state:'inspection_hold' if state['outputs']['disposition']['status']=='awaiting_inspection' else 'review_ready')
    graph.add_edge('inspection_hold','persist')
    graph.add_edge('review_ready','persist')
    graph.add_edge('persist',END)
    try:
        result=graph.compile().invoke({'execution_id':execution,'order_id':request.order_id,'data':data,'request':request,'outputs':{}},config={'recursion_limit':20})
        return result['outputs']['final_report']
    except Exception:
        with Session.begin() as s:
            s.add(Decision(order_id=request.order_id,payload={'execution_id':execution,'status':'failed','requires_approval':False}))
            s.add(Audit(action='workflow_failed',payload={'execution_id':execution}))
        raise
