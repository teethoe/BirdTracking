import yaml
import cv2
import numpy as np

import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))

from yolov8.predict import Predictor
from utils.odometry import find_matches, estimate_vio
from utils.sim import *
from utils.colour import head_mask


model_head = Predictor(ROOT / 'yolov8/weights/head.pt')
vid_path = ROOT / 'data/vid/fps120/K203_K238_1_GH040045.mp4'
mtx_path = ROOT / 'data/calibration/cam.yaml'

backgroundModel = np.zeros((1, 65), np.float64)
foregroundModel = np.zeros((1, 65), np.float64)

with open(mtx_path, 'r') as f:
    mtx = yaml.safe_load(f)
    k = np.asarray(mtx['kR']).reshape(3, 3)
    dist = np.asarray(mtx['distR'])
print(k)
print(dist)

cap = cv2.VideoCapture(str(vid_path))
prev_frame = None
prev_mask = None
count = 1
T = np.eye(4)

while cap.isOpened():
    ret, frame = cap.read()
    if ret:
        boxes = model_head.predictions(source=frame)[0].boxes
        if boxes:
            x0, y0, x1, y1 = list(map(int, list(boxes.xyxy[0].cpu().numpy())))
            mask = np.zeros(frame.shape[:2], np.uint8)
            mask[y0:y1, x0:x1] = 1
            mask &= head_mask(frame, 20)
            if prev_frame is not None:
                kp1, kp2, matches = find_matches(prev_frame, frame, prev_mask, mask)
                out = cv2.drawMatches(prev_frame, kp1, frame, kp2, matches, None, flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
                cv2.imshow('matches', cv2.resize(out, None, fx=0.4, fy=0.4, interpolation=cv2.INTER_CUBIC))
                R, t = estimate_vio(prev_frame, frame, prev_mask, mask, k)[2:4]
                T[:3, :3] = R
                T[:3, 3] = t.T
                cv2.imshow('frame', cv2.bitwise_and(frame, frame, mask=mask))
            sim.update(T)
            prev_frame = frame.copy()
            prev_mask = mask.copy()
        if cv2.waitKey(1) == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()
sim.close()
