import os
import sys
from pathlib import Path
ROOT = Path(os.path.abspath(__file__)).parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from yolov8.predict import Predictor, detect_features
from yolov8.track import Tracker

from utils.box import pad_boxes
from utils.camera import Stereo
from utils.structs import Bird, Birds
from utils.reconstruct import triangulate
from utils.sim import *


RESIZE = .5  # resize display window
STRIDE = 30
PADDING = 20

tracker = Tracker(ROOT / 'yolov8/weights/head.pt')
predictor_head = Predictor(ROOT / 'yolov8/weights/head.pt')

vidL = ROOT / 'data/vid/fps120/K203_K238/GOPRO2/GH010039.MP4'
vidR = ROOT / 'data/vid/fps120/K203_K238/GOPRO1/GH010045.MP4'

cfg_path = ROOT / 'data/configs/cam.yaml'

# sync videos and calibrate cameras
# stereo = Stereo(vidL=vidL, vidR=vidR, stride=STRIDE)
stereo = Stereo(path=cfg_path)
capL = cv2.VideoCapture(str(vidL))
capR = cv2.VideoCapture(str(vidR))
# skip chessboard calibration frames
capL.set(cv2.CAP_PROP_POS_FRAMES, stereo.offsetL+1800)
capR.set(cv2.CAP_PROP_POS_FRAMES, stereo.offsetR+1800)

sim = Sim()

birdsL = Birds()
birdsR = Birds()
prev_frames = None
T = np.eye(4)
prev_T = np.eye(4)
sim.update(T)
while capL.isOpened() and capR.isOpened():
    for i in range(STRIDE):
        _ = capL.grab()
        _ = capR.grab()
    stereo.offsetL += STRIDE
    stereo.offsetR += STRIDE
    retL, frameL = capL.retrieve()
    retR, frameR = capR.retrieve()
    if retL and retR:
        headL = pad_boxes(tracker.tracks(frameL)[0].boxes.cpu().numpy(), frameL.shape, PADDING)
        headR = pad_boxes(tracker.tracks(frameR)[0].boxes.cpu().numpy(), frameR.shape, PADDING)
        featL = detect_features(frameL, headL)
        featR = detect_features(frameR, headR)
        birdsL.update([Bird(head, feat) for head, feat in zip(headL, featL)], frameL)
        birdsR.update([Bird(head, feat) for head, feat in zip(headR, featR)], frameR)

        birdL = birdsL['m'] if birdsL['m'] is not None else birdsL['f']
        birdR = birdsR['m'] if birdsR['m'] is not None else birdsR['f']
        if birdL is not None and birdR is not None:
            tri, transform, _ = triangulate(birdL, birdR, stereo)
            if tri:
                print(transform)
                R = transform[:3, :3]
                T[:3, :3] = prev_T[:3, :3].T @ R
                # T[:3, 3] = t.T - prev_T[:3, 3]
                prev_T[:3, :3] = R
                # prev_T[:3, 3] = t.T
                sim.update(T)
        display = cv2.hconcat([cv2.resize(birdsL.plot(), None, fx=RESIZE, fy=RESIZE, interpolation=cv2.INTER_CUBIC),
                               cv2.resize(birdsR.plot(), None, fx=RESIZE, fy=RESIZE, interpolation=cv2.INTER_CUBIC)])
        cv2.imshow('display', display)
        key = cv2.waitKey(1)
        if key == ord('q'):
            break
        elif key == ord('s'):
            cv2.waitKey(0)
        prev_frames = {'l': frameL, 'r': frameR}
    else:
        break

capL.release()
capR.release()
cv2.destroyAllWindows()
sim.close()
