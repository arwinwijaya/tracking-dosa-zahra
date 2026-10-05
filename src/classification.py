import re
import pandas as pd

def classify(df):
    df=df.copy()
    fields=[]
    for _,r in df.iterrows():
        s=(str(r.get('uraian_transaksi') or '')+' '+str(r.get('teller') or '')).upper()
        debit=r.get('debet'); credit=r.get('kredit')
        direction='OUT' if pd.notna(debit) and debit>0 else ('IN' if pd.notna(credit) and credit>0 else 'UNKNOWN')
        cat='Unknown'; channel='Unknown'; sub=''; merchant='UNKNOWN'; dest='UNKNOWN'; bank='UNKNOWN'; account=''
        if 'BFST' in s or 'BI FAST' in s or 'BI-FAST' in s: cat='BI-FAST';channel='Online Banking'
        elif 'TARIK TUNAI' in s or 'TARK TUNAI' in s: cat='ATM Withdrawal';channel='ATM'
        elif 'FEE ATM' in s: cat='Bank Fee';channel='ATM';sub='Monthly fee'
        elif 'WBNKTR' in s or 'TRANSFER' in s or 'TRF' in s: cat='Transfer';channel='Online Banking'
        elif 'QRIS' in s: cat='QRIS';channel='QRIS'
        elif 'PRCH' in s or 'PRTT' in s: cat='Debit Card';channel='Debit Card'
        elif 'INTEREST' in s: cat='Interest'; direction='IN'
        elif 'TAX' in s: cat='Bank Fee';sub='Tax'
        elif 'ADMIN' in s: cat='Administration Fee'
        elif 'DANA' in s: cat='E-Wallet';channel='Online' # platform != verified counterparty
        # BRI internal reference structures often contain account identifiers but no recipient name.
        # Opaque reference numbers are NOT independently verified destination accounts.
        # Preserve them only in the raw OCR evidence, never label them as a recipient.
        # Incoming transfer names are sender evidence; they are not outgoing destinations.
        if direction=='IN' and cat=='Unknown': cat='Credit/Deposit'
        fields.append((direction,cat,sub,channel,dest,account,bank,merchant,0.9 if cat!='Unknown' else 0.3))
    cols=['transaction_direction','transaction_category','transaction_subcategory','channel','destination_name','destination_account','destination_bank','merchant','classification_confidence']
    for i,c in enumerate(cols): df[c]=[x[i] for x in fields]
    df['destination_normalized']=df.destination_name.where(df.destination_name!='UNKNOWN','UNKNOWN')
    df['reference_number']=''
    return df
