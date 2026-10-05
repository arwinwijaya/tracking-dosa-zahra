from pathlib import Path
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import CellIsRule
from openpyxl.chart import BarChart,Reference,LineChart

SHEETS=['Executive Summary','All Transactions','Suspicious Transactions','Money Destination','Category Analysis','Monthly Summary','Daily Summary','Counterparty Analysis','Suspicious Clusters','Reconciliation','OCR Review','Possible Duplicates','Source Files','Scam Investigation']
MONEY={'debet','kredit','saldo','expected_saldo','actual_saldo','saldo_difference','total_debit','total_credit','average_transaction','minimum_transaction','maximum_transaction','total_sent','total_received','net_flow','largest_outgoing','opening_balance','closing_balance','total_outgoing','cluster_outgoing'}
def export(df,inventory,out_path):
    out_path=Path(out_path);out_path.parent.mkdir(parents=True,exist_ok=True)
    df=df.copy(); dt=pd.to_datetime(df['tanggal_transaksi'],format='%d/%m/%y',errors='coerce')
    outgoing=df[df.transaction_direction=='OUT'].copy()
    dest=outgoing.groupby('destination_normalized',dropna=False).agg(transaction_count=('debet','count'),total_debit=('debet','sum'),average_transaction=('debet','mean'),minimum_transaction=('debet','min'),maximum_transaction=('debet','max'),first_transaction=('tanggal_transaksi','min'),last_transaction=('tanggal_transaksi','max')).reset_index().sort_values('total_debit',ascending=False)
    cats=outgoing.groupby('transaction_category').agg(total_debit=('debet','sum'),transaction_count=('debet','count'),average_transaction=('debet','mean')).reset_index()
    denom=outgoing.debet.sum();cats['percentage_total_outgoing']=cats.total_debit/denom if denom else 0
    monthly=df.assign(_month=dt.dt.to_period('M').astype(str)).groupby('_month').agg(total_debit=('debet','sum'),total_credit=('kredit','sum'),transaction_count=('debet','size')).reset_index().rename(columns={'_month':'month'});monthly['net_cash_flow']=monthly.total_credit-monthly.total_debit
    daily=df.assign(_day=dt.dt.date).groupby('_day').agg(total_debit=('debet','sum'),total_credit=('kredit','sum'),transaction_count=('debet','size')).reset_index().rename(columns={'_day':'date'})
    largest=outgoing.groupby('_day').debet.max() if '_day' in outgoing else None
    # Attach summaries
    cp=outgoing.groupby(['destination_name','destination_account','destination_bank']).agg(first_seen=('tanggal_transaksi','min'),last_seen=('tanggal_transaksi','max'),transaction_count=('debet','count'),total_sent=('debet','sum')).reset_index();cp['total_received']=0;cp['net_flow']=cp.total_sent
    clusters=outgoing.groupby('transaction_cluster_id').agg(cluster_start=('tanggal_transaksi','min'),cluster_end=('tanggal_transaksi','max'),number_of_transactions=('debet','count'),cluster_outgoing=('debet','sum')).reset_index()
    suspicious=df[df.risk_level.isin(['HIGH','CRITICAL'])].copy()
    from src.statement_totals import TOTALS
    summary=[('Statement period',f"{dt.min()} — {dt.max()}" if dt.notna().any() else 'Uncertain'),('Total transactions',len(df)),('Total debit (OCR readable)',df.debet.sum()),('Total credit (OCR readable)',df.kredit.sum()),('Opening balance (OCR first row; NOT statement opening)',df.saldo.iloc[0] if len(df) else None),('Closing balance (OCR last row)',df.saldo.iloc[-1] if len(df) else None),('High/Critical transactions',len(suspicious)),('Potentially suspicious outgoing',suspicious.debet.sum()),('Highest outgoing transaction',outgoing.debet.max() if len(outgoing) else None),('Largest destination',dest.iloc[0].destination_normalized if len(dest) else 'UNKNOWN'),('Most frequent destination',dest.sort_values('transaction_count',ascending=False).iloc[0].destination_normalized if len(dest) else 'UNKNOWN'),('OCR/reconciliation rows requiring review',int(df.review_required.sum())),('Reconciliation mismatches',int((df.reconciliation_status=='MISMATCH').sum()))]
    for month,tot in TOTALS.items():summary.extend([(f'{month} statement printed debit',tot['total_debit']),(f'{month} statement printed credit',tot['total_credit']),(f'{month} OCR debit difference',tot['total_debit']-int(df.loc[dt.dt.to_period('M').astype(str)==month,'debet'].sum())),(f'{month} OCR credit difference',tot['total_credit']-int(df.loc[dt.dt.to_period('M').astype(str)==month,'kredit'].sum()))])
    ex=pd.DataFrame(summary,columns=['Metric','Value'])
    # A shareable workbook masks long digit sequences in free text; local OCR JSON/CSV retain originals.
    trans=df.copy()
    from src.utils import mask
    for col in ('uraian_transaksi','raw_text','source_file','debet_raw','kredit_raw','saldo_raw','teller','destination_account','reference_number'):
        if col in trans:trans[col]=trans[col].map(lambda v:mask(v) if pd.notna(v) else v)
    recon=trans[['tanggal_transaksi','uraian_transaksi','debet','kredit','saldo','expected_saldo','actual_saldo','saldo_difference','reconciliation_status','source_file','source_page','raw_text']]
    reviews=trans[trans.review_required];dups=trans[trans.duplicate_status=='SUSPECTED_DUPLICATE']
    suspicious=trans[trans.risk_level.isin(['HIGH','CRITICAL'])].copy()
    scam=suspicious.sort_values('tanggal_transaksi').copy(); scam['No']=range(1,len(scam)+1)
    scam=scam[['No','tanggal_transaksi','uraian_transaksi','transaction_category','destination_name','destination_account','destination_bank','debet','expected_saldo','saldo','risk_level','risk_reason','source_file']]
    sheets={'Executive Summary':ex,'All Transactions':trans,'Suspicious Transactions':suspicious,'Money Destination':dest,'Category Analysis':cats,'Monthly Summary':monthly,'Daily Summary':daily,'Counterparty Analysis':cp,'Suspicious Clusters':clusters,'Reconciliation':recon,'OCR Review':reviews,'Possible Duplicates':dups,'Source Files':pd.DataFrame(inventory).map(lambda v:mask(v) if isinstance(v,str) else v),'Scam Investigation':scam}
    for key in ('Money Destination','Counterparty Analysis'):
        for col in sheets[key].select_dtypes(include='object').columns:
            sheets[key][col]=sheets[key][col].map(lambda v:mask(v) if pd.notna(v) else v)
    with pd.ExcelWriter(out_path,engine='openpyxl') as writer:
        for name,data in sheets.items(): data.to_excel(writer,sheet_name=name,index=False)
    from openpyxl import load_workbook
    wb=load_workbook(out_path)
    for ws in wb.worksheets:
        ws.freeze_panes='A2'
        if ws.max_row and ws.max_column: ws.auto_filter.ref=ws.dimensions
        for cell in ws[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='17365D')
        for col in ws.columns:
            letter=get_column_letter(col[0].column); width=min(55,max(12,max((len(str(c.value)) for c in col if c.value is not None),default=0)+2));ws.column_dimensions[letter].width=width
        for j,c in enumerate(ws[1],1):
            if str(c.value).lower() in MONEY:
                for cells in ws.iter_rows(min_row=2,min_col=j,max_col=j): cells[0].number_format='"Rp "#,##0;[Red]("Rp "#,##0)'
        headers={c.value:c.column for c in ws[1]}
        if 'risk_level' in headers:
            j=headers['risk_level'];
            for row in range(2,ws.max_row+1):
                if ws.cell(row,j).value in ('HIGH','CRITICAL'):
                    for cell in ws[row]:cell.fill=PatternFill('solid',fgColor='F4CCCC')
        if 'reconciliation_status' in headers:
            j=headers['reconciliation_status'];
            for row in range(2,ws.max_row+1):
                if ws.cell(row,j).value=='MISMATCH':
                    for cell in ws[row]:cell.fill=PatternFill('solid',fgColor='FCE4D6')
        if 'review_required' in headers:
            j=headers['review_required'];
            for row in range(2,ws.max_row+1):
                if ws.cell(row,j).value is True:
                    for cell in ws[row]:cell.fill=PatternFill('solid',fgColor='FFF2CC')
    ws=wb['Executive Summary']
    if len(monthly):
        start=ws.max_row+2
        ws.cell(start,1,'Monthly Debit/Credit');monthly.to_excel if False else None
        for j,h in enumerate(monthly.columns,1):ws.cell(start+1,j,h)
        for i,row in enumerate(monthly.itertuples(index=False,name=None),start+2):
            for j,v in enumerate(row,1):ws.cell(i,j,str(v) if pd.isna(v) else v)
        chart=BarChart();chart.title='Debit vs Credit by Month';chart.y_axis.title='IDR';chart.x_axis.title='Month'
        chart.add_data(Reference(ws,min_col=2,max_col=3,min_row=start+1,max_row=start+1+len(monthly)),titles_from_data=True);chart.set_categories(Reference(ws,min_col=1,min_row=start+2,max_row=start+1+len(monthly)));ws.add_chart(chart,'D2')
    wb.save(out_path)
