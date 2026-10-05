from pathlib import Path
import re
from PIL import Image

EXT={'.jpg','.jpeg','.png','.webp','.tif','.tiff'}
def scan(root):
    rows=[]
    for p in Path(root).rglob('*'):
        if p.is_file() and p.suffix.lower() in EXT:
            try:
                with Image.open(p) as im: w,h=im.size
                status='pending'
            except Exception:
                w=h=None; status='failed: unreadable image'
            m=re.search(r'page[-_ ]?(\d+)',p.stem,re.I)
            rows.append(dict(filename=p.name,filepath=str(p.resolve()),width=w,height=h,file_size_bytes=p.stat().st_size,processing_status=status,sort_page=int(m.group(1)) if m else 999999))
    return sorted(rows,key=lambda r:(r['sort_page'],r['filename'].lower()))
