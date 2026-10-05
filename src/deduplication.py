import hashlib

def mark(df):
    df=df.copy()
    keys=['tanggal_transaksi','uraian_transaksi','debet','kredit','saldo']
    def key(r): return hashlib.sha256('|'.join(str(r.get(k,'')) for k in keys).encode()).hexdigest()[:16]
    df['duplicate_group']=df.apply(key,axis=1)
    counts=df['duplicate_group'].value_counts()
    df['duplicate_status']=df['duplicate_group'].map(lambda k:'SUSPECTED_DUPLICATE' if counts[k]>1 else 'UNIQUE')
    return df
