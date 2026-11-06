import argparse
import pandas as pd
from backend.app.config import ROOT
from backend.app.data import generate, seed_database
from backend.app.db import Base,engine,Session,ModelVersion
from backend.app.ml import train
from backend.app.eda import generate_report

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--rows',type=int,default=12000); parser.add_argument('--skip-training',action='store_true'); args=parser.parse_args()
    if args.rows<10000: parser.error('At least 10000 rows are required')
    print('Generating reproducible synthetic transactions...',flush=True)
    df=generate(args.rows)
    Base.metadata.create_all(engine)
    seed_database(df)
    print('Generating EDA...',flush=True); generate_report(df)
    if not args.skip_training:
        print('Training and comparing four models...',flush=True)
        report=train(df)
        with Session.begin() as s: s.add(ModelVersion(version=report['version'],metrics=report))
        print('Selected:', report['selected_model'], 'Test PR-AUC:',round(report['test_metrics']['pr_auc'],4),flush=True)
    print('Ready. Synthetic data only.',flush=True)
if __name__=='__main__': main()
