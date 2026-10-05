"""Parse manual.txt (Markdown table) into a DataFrame compatible with the downstream pipeline."""
import re
import pandas as pd
from pathlib import Path

def load_manual_txt(path: Path) -> pd.DataFrame:
    text = path.read_text(encoding='utf-8')
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) < 6:
            continue
        # skip header and separator
        if cells[0].lower().startswith('tanggal'):
            continue
        if set(cells[0]) <= set('-: '):
            continue
        datecell = cells[0]
        m = re.match(r'(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2}:\d{2})', datecell)
        if not m:
            continue
        tanggal, waktu = m.group(1), m.group(2)
        uraian = cells[1].strip()
        teller = cells[2].strip()
        debet_raw = cells[3].strip().replace('*', '').replace(' ', '')
        kredit_raw = cells[4].strip().replace('*', '').replace(' ', '')
        saldo_raw = cells[5].strip().replace('*', '').replace(' ', '')

        def parse_amt(s: str):
            s = s.replace(',', '')
            if '.' in s:
                whole, cents = s.split('.')
                return int(whole) if cents == '00' else None
            if s.isdigit():
                return int(s)
            return None

        rows.append(dict(
            tanggal_transaksi=tanggal,
            waktu=waktu,
            uraian_transaksi=uraian,
            teller=teller,
            debet_raw=debet_raw,
            kredit_raw=kredit_raw,
            saldo_raw=saldo_raw,
            debet=parse_amt(debet_raw),
            kredit=parse_amt(kredit_raw),
            saldo=parse_amt(saldo_raw),
        ))
    df = pd.DataFrame(rows)
    # Assign source metadata (manual transcription replaces OCR source)
    df['source_file'] = 'manual.txt'
    df['source_page'] = 0
    df['row_on_page'] = range(1, len(df) + 1)
    df['raw_text'] = df.apply(lambda r: ' | '.join([r['tanggal_transaksi'], r['waktu'], r['uraian_transaksi'], r['teller'], r['debet_raw'], r['kredit_raw'], r['saldo_raw']]), axis=1)
    df['confidence'] = 1.0
    df['review_required'] = False
    # Preserve the source order, including ties on timestamp. Sorting equal-time
    # rows by amount reverses principal/fee or interest/tax and fabricates gaps.
    if df.empty:
        raise ValueError('No transaction table rows found in manual.txt')
    times = pd.to_datetime(df['tanggal_transaksi'] + ' ' + df['waktu'], format='%d/%m/%y %H:%M:%S', errors='raise')
    if not times.is_monotonic_increasing:
        raise ValueError('Manual table is not chronological; verify source order before reconciliation')
    return df

def validate_running_balance(df: pd.DataFrame) -> list:
    """Return list of (index, expected, actual, diff) where balance check fails."""
    mismatches = []
    prev = None
    for i, r in df.iterrows():
        if prev is not None:
            expected = prev - r['debet'] + r['kredit']
            if expected != r['saldo']:
                mismatches.append((i, prev, r['debet'], r['kredit'], expected, r['saldo'], r['saldo'] - expected))
        prev = r['saldo']
    return mismatches

if __name__ == '__main__':
    df = load_manual_txt(Path('manual.txt'))
    print(f'Loaded {len(df)} rows')
    mismatches = validate_running_balance(df)
    print(f'Balance mismatches: {len(mismatches)}')
    if mismatches:
        for m in mismatches[:5]:
            print(m)
    print(f'Total debit: {df.debet.sum():,}')
    print(f'Total credit: {df.kredit.sum():,}')
    print(f'First saldo: {df.saldo.iloc[0]:,}')
    print(f'Last saldo: {df.saldo.iloc[-1]:,}')