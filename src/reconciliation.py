"""Reconcile in original document order; never use missing amounts as zero."""
from datetime import datetime

def reconcile(df):
    df=df.copy().sort_values(['source_page','row_on_page']).reset_index(drop=True)
    import pandas as pd
    df['expected_saldo']=None; df['actual_saldo']=df['saldo']; df['saldo_difference']=None
    df['reconciliation_status']='CANNOT_VALIDATE'
    from src.statement_totals import TOTALS
    prev=None; prev_month=None
    for i,r in df.iterrows():
        dt=pd.to_datetime(r['tanggal_transaksi'],format='%d/%m/%y',errors='coerce')
        month=dt.strftime('%Y-%m') if pd.notna(dt) else None
        if month!=prev_month:
            prev=TOTALS.get(month,{}).get('opening_balance')
            prev_month=month
        if prev is not None and all(pd.notna(v) for v in (prev,r['debet'],r['kredit'],r['saldo'])):
            expected=int(prev)-int(r['debet'])+int(r['kredit'])
            df.at[i,'expected_saldo']=expected
            df.at[i,'saldo_difference']=int(r['saldo'])-expected
            df.at[i,'reconciliation_status']='MATCH' if expected==int(r['saldo']) else 'MISMATCH'
        prev=r['saldo'] if pd.notna(r['saldo']) else None
    df.loc[df['reconciliation_status']!='MATCH','review_required']=True
    return df
