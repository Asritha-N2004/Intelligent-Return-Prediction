"""Reproducible synthetic data. Pre-order history is generated before the target."""
import json
import numpy as np
import pandas as pd
from .config import ROOT
CATEGORIES=['Apparel','Electronics','Footwear','Home','Beauty','Sports']
LOCATIONS={'Mumbai':(19.08,72.88),'Delhi':(28.61,77.21),'Bengaluru':(12.97,77.59),'Chennai':(13.08,80.27),'Hyderabad':(17.39,78.49),'Kolkata':(22.57,88.36)}
def generate(n=12000, seed=42):
    rng=np.random.default_rng(seed)
    customers=[]
    for i in range(1500):
        prior=int(rng.integers(1,80)); returns=int(rng.binomial(prior, rng.beta(2,9)))
        customers.append((f'CUS-{i:04}',rng.choice(list(LOCATIONS)),prior,returns))
    products=[(f'PRD-{i:04}',rng.choice(CATEGORIES),round(float(rng.lognormal(7.3,.65)),2),round(float(rng.uniform(2.2,5)),1)) for i in range(300)]
    rows=[]
    for i in range(n):
        cid,city,prior,returns=customers[int(rng.integers(len(customers)))]; pid,cat,price,rating=products[int(rng.integers(len(products)))]
        qty=int(rng.choice([1,2,3],p=[.8,.15,.05])); discount=int(rng.choice([0,5,10,20,30,50])); delay=int(rng.choice([0,1,2,3,5,8],p=[.62,.15,.1,.07,.04,.02]))
        rate=returns/prior
        logit=-2.7+2.8*rate+.23*delay+.6*(cat in ['Apparel','Footwear'])+.42*(4-rating)+.012*discount
        target=int(rng.random()<1/(1+np.exp(-logit)))
        date=pd.Timestamp('2025-01-01')+pd.Timedelta(days=int(rng.integers(660)))
        delivery=date+pd.Timedelta(days=3+delay)
        reason=str(rng.choice(['Size or fit','Damaged item','Not as described','Late delivery','Changed mind'])) if target else 'None'
        condition=str(rng.choice(['new','opened','damaged'])) if target else 'unknown'
        rows.append(dict(order_id=f'ORD-{i+1:05}',customer_id=cid,product_id=pid,product_category=cat,product_price=price,quantity=qty,order_date=str(date.date()),delivery_date=str(delivery.date()),payment_method=str(rng.choice(['Card','UPI','Cash on delivery'])),customer_location=city,product_rating=rating,product_review_score=rating,discount_percentage=discount,previous_orders=prior,previous_returns=returns,customer_return_rate=rate,delivery_delay=delay,product_condition=condition,return_reason=reason,return_requested=target,return_date=str((delivery+pd.Timedelta(days=int(rng.integers(1,25)))).date()) if target else None,refund_amount=round(price*qty*(1-discount/100),2) if target else 0,shipping_cost=round(float(rng.uniform(45,180)),2),warehouse_id=['WH-WEST','WH-NORTH','WH-SOUTH'][i%3],return_processing_time=int(rng.integers(1,8)) if target else 0,product_resale_value=round(price*(.9 if condition=='new' else .6),2) if target else 0))
    df=pd.DataFrame(rows)
    for folder in ['raw','processed','external','synthetic']: (ROOT/'data'/folder).mkdir(parents=True,exist_ok=True)
    df.to_csv(ROOT/'data/synthetic/transactions.csv',index=False)
    raw=df.copy()
    for col in ['product_rating','discount_percentage']:
        raw.loc[rng.choice(n,int(n*.015),replace=False),col]=np.nan
    raw=pd.concat([raw,raw.iloc[:100]],ignore_index=True)
    raw.to_csv(ROOT/'data/raw/transactions.csv',index=False)
    clean=preprocess(raw)
    clean.to_csv(ROOT/'data/processed/transactions.csv',index=False)
    (ROOT/'data/provenance.json').write_text(json.dumps({'source':'SYNTHETIC — not collected customer data','seed':seed,'unique_records':n,'raw_records':len(raw),'injected_duplicate_rows':100},indent=2),encoding='utf-8')
    return clean

def preprocess(df):
    required={'order_id','return_requested','previous_orders','previous_returns','product_price'}
    if not required.issubset(df.columns): raise ValueError('Missing fields: '+str(required-set(df.columns)))
    df=df.drop_duplicates('order_id').copy()
    if not df.return_requested.isin([0,1]).all(): raise ValueError('Invalid target')
    if (df.previous_returns>df.previous_orders).any() or (df.product_price<=0).any(): raise ValueError('Invalid prices or history')
    # Missing predictive values stay missing: imputation is fit inside each training fold.
    return df

def seed_database(df):
    from .db import Session,Customer,Product,Warehouse,Order,OrderItem,Return
    with Session.begin() as s:
        if s.query(Order).first(): return
        for _,r in df.drop_duplicates('customer_id').iterrows():
            s.add(Customer(id=r.customer_id,location=r.customer_location,previous_orders=int(r.previous_orders),previous_returns=int(r.previous_returns)))
        for _,r in df.drop_duplicates('product_id').iterrows():
            s.add(Product(id=r.product_id,category=r.product_category,price=float(r.product_price),rating=float(r.product_rating) if pd.notna(r.product_rating) else 3.5))
        for wid,city,cost,days in [('WH-WEST','Mumbai',48,2),('WH-NORTH','Delhi',42,3),('WH-SOUTH','Bengaluru',45,2)]:
            lat,lon=LOCATIONS[city]; s.add(Warehouse(id=wid,location=city,latitude=lat,longitude=lon,capacity=20000,used=0,processing_cost=cost,processing_days=days,capabilities=CATEGORIES))
        s.flush()
        records=json.loads(df.to_json(orient='records'))
        for r in records:
            s.add(Order(id=r['order_id'],customer_id=r['customer_id'],product_id=r['product_id'],order_date=r['order_date'],return_requested=bool(r['return_requested']),data=r))
        s.flush()
        for r in records:
            s.add(OrderItem(order_id=r['order_id'],product_id=r['product_id'],quantity=r['quantity'],unit_price=r['product_price']))
            if r['return_requested']: s.add(Return(order_id=r['order_id'],reason=r['return_reason'],refund_amount=r['refund_amount'],warehouse_id=r['warehouse_id']))
