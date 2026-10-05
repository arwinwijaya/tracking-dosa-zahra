"""Process the seven JPEG bank statement pages in this directory, locally."""
import json, logging
from pathlib import Path
import pandas as pd
from src import config,inventory,preprocess,ocr_extract,parse_table,deduplication,reconciliation,classification,fraud_analysis,export_excel,report_md

def main():
    config.OUTPUT.mkdir(exist_ok=True);config.PROCESSED.mkdir(exist_ok=True);config.OCR.mkdir(exist_ok=True)
    logging.basicConfig(filename=str(config.OUTPUT/'extraction_log.txt'),filemode='w',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    # Existing root images are the source; the source/*.pdf and merged PDF duplicate these pages.
    files=[r for r in inventory.scan(config.ROOT) if Path(r['filepath']).parent==config.ROOT and r['filename'].startswith('ilovepdf_merged_page-')]
    raw=[]
    for entry in files:
        src=Path(entry['filepath']);dst=config.PROCESSED/src.name; js=config.OCR/(src.stem+'.json')
        try:
            if not preprocess.process(src,dst):raise RuntimeError('preprocess returned false')
            # For these already legible scans, preprocessing damaged small printed digits;
            # OCR the untouched original while retaining the processed copy for audit.
            tokens=ocr_extract.run(src,js)
            page=entry['sort_page'];records=parse_table.parse_page(tokens,str(src.resolve()),page)
            for j,r in enumerate(records,1):r['row_on_page']=j
            raw.extend(records);entry['processing_status']=f'processed: {len(records)} OCR rows'
            logging.info('page %s: %s rows, %s OCR detections',page,len(records),len(tokens))
            print(f'Page {page}: {len(records)} transaction candidates, {len(tokens)} tokens',flush=True)
        except Exception as exc:
            entry['processing_status']=f'failed: {type(exc).__name__}: {exc}';logging.exception('page %s failed',src)
            print(f'FAILED page {src}: {exc}',flush=True)
    pd.DataFrame(files).to_csv(config.OUTPUT/'source_inventory.csv',index=False)
    if not raw: raise RuntimeError('No transactions extracted; no workbook will be generated.')
    pd.DataFrame(raw).to_json(config.OUTPUT/'raw_transactions.json',orient='records',indent=2,force_ascii=False)
    df=pd.DataFrame(raw)
    df=deduplication.mark(df);df=reconciliation.reconcile(df);df=classification.classify(df);df=fraud_analysis.assess(df)
    df.to_csv(config.OUTPUT/'transactions_audit.csv',index=False,encoding='utf-8-sig')
    export_excel.export(df,files,config.EXCEL);report_md.report(df,files,config.REPORT)
    match=(df.reconciliation_status=='MATCH').sum(); mismatch=(df.reconciliation_status=='MISMATCH').sum(); can=(df.reconciliation_status=='CANNOT_VALIDATE').sum()
    from src.statement_totals import TOTALS
    month_totals={}
    for month,tot in TOTALS.items():
        mask=df.tanggal_transaksi.map(lambda v: pd.to_datetime(v,format='%d/%m/%y',errors='coerce').strftime('%Y-%m') if pd.notna(pd.to_datetime(v,format='%d/%m/%y',errors='coerce')) else None)==month
        month_totals[month]={'statement_opening_balance':tot['opening_balance'],'statement_total_debit':tot['total_debit'],'ocr_readable_debit':int(df.loc[mask,'debet'].sum()),'unallocated_debit_difference':int(tot['total_debit']-df.loc[mask,'debet'].sum()),'statement_total_credit':tot['total_credit'],'ocr_readable_credit':int(df.loc[mask,'kredit'].sum()),'unallocated_credit_difference':int(tot['total_credit']-df.loc[mask,'kredit'].sum()),'statement_closing_balance':tot['closing_balance']}
    qc={'statement_totals_by_month':month_totals,'images_discovered':len(files),'images_processed':sum(r['processing_status'].startswith('processed') for r in files),'images_failed':sum(r['processing_status'].startswith('failed') for r in files),'transactions_extracted':len(df),'duplicate_candidates':int((df.duplicate_status=='SUSPECTED_DUPLICATE').sum()),'reconciliation_matches':int(match),'reconciliation_mismatches':int(mismatch),'cannot_validate':int(can),'reconciliation_match_rate':round(match/(match+mismatch)*100,2) if match+mismatch else None,'ocr_review_required':int(df.review_required.sum()),'ocr_review_rate':round(df.review_required.mean()*100,2),'suspicious_transactions':int(df.risk_level.isin(['HIGH','CRITICAL']).sum()),'total_debit_readable':int(df.debet.sum()),'total_credit_readable':int(df.kredit.sum()),'potentially_suspicious_outgoing_readable':int(df.loc[df.risk_level.isin(['HIGH','CRITICAL']),'debet'].sum())}
    (config.OUTPUT/'quality_control.json').write_text(json.dumps(qc,indent=2),encoding='utf-8');print(json.dumps(qc,indent=2),flush=True)
    print('Outputs:',config.EXCEL,config.REPORT,sep='\n')
if __name__=='__main__':main()
