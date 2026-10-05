import json, os
from pathlib import Path
os.environ.setdefault('KMP_DUPLICATE_LIB_OK','TRUE')
import easyocr
import cv2

reader=easyocr.Reader(['en','id'],gpu=False,verbose=False)
# Page-specific table rectangles exclude address/footer text and improve small type recognition.
TABLE_REGIONS={1:(640,1400),2:(225,1450),3:(218,615),4:(638,1450),5:(230,455),6:(640,1430),7:(210,265)}

def run(img_path,json_path):
    page=int(Path(img_path).stem.rsplit('-',1)[-1])
    y0,y1=TABLE_REGIONS[page]
    im=cv2.imread(str(img_path))
    if im is None: raise RuntimeError('Cannot open source image')
    crop=cv2.resize(im[y0:y1,:],None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC)
    res=reader.readtext(crop,detail=1,paragraph=False)
    # EasyOCR may return numpy int32/float32 values, not JSON serializable.
    safe=[]
    for box,text,conf in res:
        safe.append([[[round(float(p[0])/2,2),round(float(p[1])/2+y0,2)] for p in box],str(text),float(conf)])
    Path(json_path).parent.mkdir(parents=True,exist_ok=True)
    Path(json_path).write_text(json.dumps(safe,ensure_ascii=False,indent=2),encoding='utf-8')
    return safe