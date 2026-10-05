"""Conservative Indonesian amount/date helpers. Amounts are integer rupiah."""
import re
from datetime import datetime


def amount(raw):
    if raw is None:
        return None
    s = str(raw).strip().replace(' ', '')
    # Printed statements here use 1,250,000.00; accept Indonesian 1.250.000,00 too.
    if re.fullmatch(r'\d{1,3}(?:,\d{3})+\.\d{2}', s) or re.fullmatch(r'\d+\.\d{2}', s):
        whole, cents = s.rsplit('.', 1)
        if cents == '00': return int(whole.replace(',', ''))
        return None
    if re.fullmatch(r'\d{1,3}(?:\.\d{3})+,\d{2}', s) or re.fullmatch(r'\d+,\d{2}', s):
        whole, cents = s.rsplit(',', 1)
        if cents == '00': return int(whole.replace('.', ''))
        return None
    # Ungrouped amounts can be truncated OCR fragments; do not call them rupiah.
    return None


def date_time(raw):
    if not raw: return None
    s = str(raw).replace(';', ':').replace(',', ':').replace('.', ':')
    m = re.search(r'(\d{2})[/\-](\d{2})[/\-](\d{2})\s+(\d{2})[:](\d{2})[:](\d{2})', s)
    if not m: return None
    try: return datetime.strptime(' '.join(('/'.join(m.group(i) for i in (1,2,3)), ':'.join(m.group(i) for i in (4,5,6)))), '%d/%m/%y %H:%M:%S')
    except ValueError: return None


def money(v):
    return f"Rp {v:,.0f}" if v is not None else 'tidak terbaca'


def mask(s):
    # References often embed account-like digit runs inside letters (e.g. WBNKTRF...T...).
    return re.sub(r'(?<!\d)\d{7,}(?!\d)', lambda m: '*' * (len(m.group()) - 4) + m.group()[-4:], str(s or ''))
