import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from .config import ROOT

def generate_report(df):
    out=ROOT/'reports'; out.mkdir(exist_ok=True)
    raw=pd.read_csv(ROOT/'data/raw/transactions.csv')
    groups={}
    copy=df.copy()
    copy['customer_segment']=pd.cut(copy.customer_return_rate,[-.01,.15,.35,1],labels=['Low historical returns','Moderate historical returns','Frequent historical returns'])
    for col in ['product_category','customer_segment','payment_method','customer_location','return_reason','product_rating','delivery_delay']:
        groups[col]=json.loads(copy.groupby(col,observed=True).return_requested.agg(['count','sum','mean']).reset_index().to_json(orient='records'))
    numeric=copy.select_dtypes('number')
    q1=numeric.quantile(.25); q3=numeric.quantile(.75); iqr=q3-q1
    report={'data_source':'SYNTHETIC','rows':len(df),'raw_rows':len(raw),'duplicates':int(raw.duplicated('order_id').sum()),'missing_values':raw.isna().sum().to_dict(),'return_rate':float(df.return_requested.mean()),'groups':groups,'outliers_iqr':((numeric<q1-1.5*iqr)|(numeric>q3+1.5*iqr)).sum().to_dict()}
    for col in ['product_category','payment_method','customer_location','delivery_delay','product_rating']:
        fig,ax=plt.subplots(figsize=(9,4)); copy.groupby(col).return_requested.mean().plot.bar(ax=ax,color='#635bff'); ax.set_ylabel('Observed synthetic return rate'); ax.set_title(col.replace('_',' ').title()); fig.tight_layout(); fig.savefig(out/f'{col}.png',dpi=140); plt.close(fig)
    fig,ax=plt.subplots(figsize=(14,10)); sns.heatmap(numeric.corr(),cmap='coolwarm',center=0,ax=ax); fig.tight_layout(); fig.savefig(out/'correlation.png',dpi=120); plt.close(fig)
    for col in ['product_price','customer_return_rate']:
        fig,ax=plt.subplots(figsize=(8,4)); sns.histplot(data=copy,x=col,hue='return_requested',bins=30,ax=ax); fig.tight_layout(); fig.savefig(out/f'{col}.png',dpi=120); plt.close(fig)
    (out/'eda.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (out/'eda_report.md').write_text(f"# Synthetic transaction EDA\n\n{len(df):,} unique orders; observed return rate {df.return_requested.mean():.2%}.\n\nRaw duplicates: {report['duplicates']}. Missing predictive values remain missing until fold-local imputation.\n\nSee eda.json for grouped statistics and outlier counts. Correlations include outcome variables for descriptive exploration only; these fields are excluded from the predictive model.\n",encoding='utf-8')
    return report
