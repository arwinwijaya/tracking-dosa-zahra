"""Conservative parsing of BRI statement rows using observed image column geometry."""
import re
from src.utils import amount,date_time
DATE=re.compile(r'(?<!\d)(\d{2})[/\-](\d{2})[/\-](\d{2})(?!\d)')
MONEY=re.compile(r'(?<![\d])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?(?![\d])')

def valid_date(s):
 m=DATE.search(str(s))
 if not m:return None
 d,mo,y=map(int,m.groups())
 if not 1<=d<=31 or not 1<=mo<=12:return None
 return m.group()

def parse_page(tokens,source_file,page):
 items=[]
 for box,text,conf in tokens:
  xs=[p[0] for p in box];ys=[p[1] for p in box]
  items.append(dict(x=sum(xs)/len(xs),y=sum(ys)/len(ys),text=str(text).strip(),conf=float(conf)))
 items.sort(key=lambda t:(t['y'],t['x']))
 # Cluster by vertical overlap, allowing separate wrapped reference lines.
 rows=[]
 for t in items:
  if rows and abs(t['y']-rows[-1]['y'])<=11:
   rows[-1]['items'].append(t);rows[-1]['y']=sum(x['y'] for x in rows[-1]['items'])/len(rows[-1]['items'])
  else:rows.append({'y':t['y'],'items':[t]})
 out=[]
 for row in rows:
  it=sorted(row['items'],key=lambda z:z['x'])
  dtok=next((t for t in it if t['x']<230 and valid_date(t['text'])),None)
  if not dtok:continue
  date=valid_date(dtok['text'])
  if row['y']<220:continue
  def column(a,b):return [t for t in it if a<=t['x']<b]
  desc=column(230,555);teller=column(555,685);debit=column(685,860);credit=column(860,1030);balance=column(1030,1250)
  def text(ts):return ' '.join(t['text'] for t in ts).strip()
  def money(ts):
   raw=text(ts)
   # OCR commonly reads the printed decimal point as a comma; only normalize the clear ,00 suffix.
   candidate=re.sub(r'(?<=\d),(?=00(?:\D|$))','.',raw)
   matches=list(MONEY.finditer(candidate))
   if not matches:return raw,None
   # Prefer a full grouped amount, or an explicit zero; do not infer from isolated OCR fragments.
   candidates=[m.group() for m in matches]
   full=[v for v in candidates if (',' in v or '.' in v) and amount(v) is not None]
   # A partly read numeral must never be accepted as a smaller complete amount.
   if not re.fullmatch(r'\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+\.\d{2}',candidate.strip()):return raw,None
   if len(full)==1:return raw,amount(full[0])
   return raw,None
  dr,dv=money(debit);cr,cv=money(credit);br,bv=money(balance)
  desc_raw=text(desc); teller_raw=text(teller)
  essential=[dtok]+debit+credit+balance
  confidence=sum(t['conf'] for t in essential)/len(essential) if essential else 0
  out.append(dict(_y=row['y'],tanggal_transaksi=date,uraian_transaksi=desc_raw,teller=teller_raw,debet_raw=dr,kredit_raw=cr,saldo_raw=br,debet=dv,kredit=cv,saldo=bv,source_file=source_file,source_page=page,confidence=confidence,review_required=(confidence<.50 or not desc_raw or dv is None or cv is None or bv is None),raw_text=' | '.join(t['text'] for t in it)))
 # append wrapped reference tokens below a row until the next transaction row
 ordered=sorted(out,key=lambda r:r['_y'])
 for idx,r in enumerate(ordered):
  next_y=ordered[idx+1]['_y'] if idx+1<len(ordered) else r['_y']+40
  extras=[]
  for row in rows:
   if r['_y']+3<row['y']<min(next_y,r['_y']+30):
    extras.extend(t['text'] for t in row['items'] if 230<=t['x']<555)
  if extras:r['uraian_transaksi']=(r['uraian_transaksi']+' '+' '.join(extras)).strip()
  del r['_y']
 return ordered
