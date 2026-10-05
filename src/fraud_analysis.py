"""Indicator scores are screening flags, never assertions of fraud."""
import pandas as pd

def assess(df):
    df=df.copy(); df['risk_score']=0;df['risk_level']='LOW';df['risk_reason']=''
    df['transaction_cluster_id']=''; seen=set()
    valid=df.loc[df['debet'].notna() & (df['debet']>0),'debet']
    median=float(valid.median()) if len(valid) else 0
    last_dt=None; cluster=0
    for i,r in df.iterrows():
        dt=pd.to_datetime(r['tanggal_transaksi'],format='%d/%m/%y',errors='coerce')
        if pd.isna(dt) or last_dt is None or dt-last_dt>pd.Timedelta(hours=24) or dt-last_dt<pd.Timedelta(0): cluster+=1
        df.at[i,'transaction_cluster_id']=f'C{cluster:03d}';last_dt=dt
        debit=r['debet']; dest=r['destination_normalized']; score=0; reasons=[]
        if debit is None or pd.isna(debit) or debit<=0: continue
        if median and debit>=max(1_000_000,median*5):score+=25;reasons.append('Nilai >=5 kali median debit')
        if debit>=5_000_000:score+=20;reasons.append('Nominal besar (>= Rp 5 juta)')
        if dest!='UNKNOWN' and dest not in seen:score+=15;reasons.append('Tujuan baru pada data tersedia')
        if i>0 and df.at[i,'transaction_cluster_id']==df.at[i-1,'transaction_cluster_id'] and debit>=1_000_000:score+=15;reasons.append('Debit dalam kelompok waktu berdekatan')
        before=df.iloc[i-1]['saldo'] if i else None
        if before is not None and not pd.isna(before) and before>0 and debit/before>=.5:score+=25;reasons.append('Menghabiskan >=50% saldo sebelum transaksi')
        if r['review_required'] or r['reconciliation_status']=='MISMATCH':reasons.append('Data OCR/saldo perlu verifikasi; skor bukan bukti')
        score=min(score,100);df.at[i,'risk_score']=score
        df.at[i,'risk_level']='CRITICAL' if score>=75 else 'HIGH' if score>=50 else 'MEDIUM' if score>=25 else 'LOW'
        df.at[i,'risk_reason']='; '.join(reasons) or 'Tidak terdeteksi indikator dari data yang tersedia'
        if dest!='UNKNOWN': seen.add(dest)
    return df
