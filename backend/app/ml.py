import json
import uuid
import threading
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import train_test_split, StratifiedKFold, GridSearchCV
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, IsolationForest
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, average_precision_score, confusion_matrix, classification_report, roc_curve, precision_recall_curve
from sklearn.inspection import permutation_importance
from .config import ROOT, THRESHOLDS
NUM=['product_price','quantity','product_rating','discount_percentage','previous_orders','previous_returns','customer_return_rate','delivery_delay','order_value','customer_risk_score','delivery_performance','purchase_frequency']
CAT=['product_category','payment_method','customer_location','price_category']
# Return reason, condition, refund, resale value and all post-return outcomes are excluded.
def features(df):
    df=df.copy()
    df['customer_return_rate']=df.previous_returns/df.previous_orders.clip(lower=1)
    df['order_value']=df.product_price*df.quantity*(1-df.discount_percentage/100)
    df['customer_risk_score']=(df.previous_returns+1)/(df.previous_orders+5)
    df['delivery_performance']=1/(1+df.delivery_delay)
    df['purchase_frequency']=np.log1p(df.previous_orders)
    df['price_category']=pd.cut(df.product_price,[0,500,2000,10000,np.inf],labels=['budget','standard','premium','luxury']).astype(str)
    return df[NUM+CAT]

def preprocessing():
    return ColumnTransformer([('num',Pipeline([('impute',SimpleImputer(strategy='median')),('scale',StandardScaler())]),NUM),('cat',Pipeline([('impute',SimpleImputer(strategy='most_frequent')),('encode',OneHotEncoder(handle_unknown='ignore',sparse_output=False))]),CAT)])
_lock=threading.RLock()
_bundle=None

def train(df):
    from xgboost import XGBClassifier
    X=features(df); y=df.return_requested.astype(int)
    Xdev,Xtest,ydev,ytest=train_test_split(X,y,test_size=.2,stratify=y,random_state=42)
    Xtrain,Xval,ytrain,yval=train_test_split(Xdev,ydev,test_size=.25,stratify=ydev,random_state=43)
    models={
        'Logistic Regression':(LogisticRegression(max_iter=600,class_weight='balanced'),{'model__C':[.1,1]}),
        'Random Forest':(RandomForestClassifier(n_estimators=100,class_weight='balanced',random_state=42,n_jobs=2),{'model__max_depth':[6,12]}),
        'Gradient Boosting':(GradientBoostingClassifier(n_estimators=80,random_state=42),{'model__max_depth':[2,3]}),
        'XGBoost':(XGBClassifier(n_estimators=100,max_depth=3,eval_metric='logloss',random_state=42,n_jobs=2,scale_pos_weight=float((ytrain==0).sum()/(ytrain==1).sum())),{'model__learning_rate':[.04,.1]})}
    comparison=[]; fitted={}
    cv=StratifiedKFold(n_splits=3,shuffle=True,random_state=42)
    for name,(model,grid) in models.items():
        search=GridSearchCV(Pipeline([('preprocess',preprocessing()),('model',model)]),grid,scoring='average_precision',cv=cv,n_jobs=1)
        search.fit(Xtrain,ytrain); pipe=search.best_estimator_; fitted[name]=pipe
        pv=pipe.predict_proba(Xval)[:,1]
        comparison.append({'model':name,'cv_pr_auc':float(search.best_score_),'validation_pr_auc':float(average_precision_score(yval,pv)),'validation_roc_auc':float(roc_auc_score(yval,pv)),'parameters':search.best_params_})
    best=max(comparison,key=lambda x:x['validation_pr_auc'])['model']
    pipe=fitted[best]; pipe.fit(Xdev,ydev)
    prob=pipe.predict_proba(Xtest)[:,1]; pred=(prob>=.5).astype(int)
    fpr,tpr,_=roc_curve(ytest,prob); precision,recall,_=precision_recall_curve(ytest,prob)
    metrics={'accuracy':accuracy_score(ytest,pred),'precision':precision_score(ytest,pred,zero_division=0),'recall':recall_score(ytest,pred,zero_division=0),'f1':f1_score(ytest,pred,zero_division=0),'roc_auc':roc_auc_score(ytest,prob),'pr_auc':average_precision_score(ytest,prob),'confusion_matrix':confusion_matrix(ytest,pred).tolist(),'classification_report':classification_report(ytest,pred,output_dict=True,zero_division=0)}
    importance=permutation_importance(pipe,Xtest.iloc[:500],ytest.iloc[:500],scoring='average_precision',n_repeats=3,random_state=42,n_jobs=1)
    imp=sorted([{'feature':f,'importance':float(v)} for f,v in zip(X.columns,importance.importances_mean)],key=lambda x:-x['importance'])
    anomaly=Pipeline([('preprocess',preprocessing()),('model',IsolationForest(n_estimators=100,contamination=.04,random_state=42,n_jobs=2))]).fit(Xdev)
    version=str(uuid.uuid4())
    report={'version':version,'selected_model':best,'selection_metric':'validation PR-AUC','data_source':'synthetic','split':{'training':len(Xtrain),'validation':len(Xval),'test':len(Xtest)},'comparison':comparison,'test_metrics':metrics,'feature_importance':imp,'roc_curve':[{'fpr':float(a),'tpr':float(b)} for a,b in zip(fpr[::max(1,len(fpr)//120)],tpr[::max(1,len(tpr)//120)])],'precision_recall_curve':[{'recall':float(a),'precision':float(b)} for a,b in zip(recall[::max(1,len(recall)//120)],precision[::max(1,len(precision)//120)])]}
    bundle={'pipeline':pipe,'anomaly':anomaly,'background':Xdev.iloc[:60],'report':report}
    (ROOT/'artifacts').mkdir(exist_ok=True)
    # One atomic pointer replacement prevents readers seeing partially written artifacts.
    joblib.dump(bundle,ROOT/'artifacts/model.tmp.joblib')
    with _lock:
        (ROOT/'artifacts/model.tmp.joblib').replace(ROOT/'artifacts/model.joblib')
        global _bundle
        _bundle=bundle
    (ROOT/'reports/model_performance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report

def bundle():
    global _bundle
    with _lock:
        if _bundle is None:
            if not (ROOT/'artifacts/model.joblib').exists(): raise RuntimeError('Model unavailable. Run python -m scripts.bootstrap first.')
            _bundle=joblib.load(ROOT/'artifacts/model.joblib')
        return _bundle

def predict(data, explain=True):
    b=bundle(); X=features(pd.DataFrame([data])); prob=float(b['pipeline'].predict_proba(X)[0,1])
    factors=[]; method='SHAP permutation, probability scale'
    if explain:
        import shap
        pre=b['pipeline'].named_steps['preprocess']
        transformed=pre.transform(X)
        background=pre.transform(b['background'])
        names=pre.get_feature_names_out()
        explainer=shap.Explainer(lambda a:b['pipeline'].named_steps['model'].predict_proba(a)[:,1],shap.maskers.Independent(background),algorithm='permutation',seed=42)
        values=explainer(transformed,max_evals=2*len(names)+1)
        factors=sorted([{'feature':f.replace('num__','').replace('cat__',''),'contribution':float(v)} for f,v in zip(names,values.values[0])],key=lambda a:-abs(a['contribution']))
        base=float(values.base_values[0])
    else: base=None
    risk=['Low','Medium','High','Critical'][sum(prob>t for t in THRESHOLDS)]
    return {'order_id':data['order_id'],'return_probability':prob,'risk_category':risk,'prediction_confidence':max(prob,1-prob),'confidence_note':'Model class probability; not a calibrated certainty estimate.','model_version':b['report']['version'],'factors':factors,'explanation_method':method,'base_probability':base,'data_source':'synthetic-trained model','explanation':f"Estimated return probability is {prob:.1%}. This prediction is not a confirmed return."}
