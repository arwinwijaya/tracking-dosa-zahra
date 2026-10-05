from pathlib import Path
import cv2, numpy as np

def process(src,dst):
    img=cv2.imread(str(src))
    if img is None: return False
    gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    gray=cv2.createCLAHE(2.0,(8,8)).apply(gray)
    gray=cv2.medianBlur(gray,3)
    coords=cv2.findNonZero(255-gray)
    if coords is not None:
        angle=cv2.minAreaRect(coords)[-1]
        if angle < -45: angle=90+angle
        if abs(angle)>=0.3:
            h,w=gray.shape[:2]
            M=cv2.getRotationMatrix2D((w/2,h/2),angle,1.0)
            gray=cv2.warpAffine(gray,M,(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
    Path(dst).parent.mkdir(parents=True,exist_ok=True)
    return cv2.imwrite(str(dst),gray)
