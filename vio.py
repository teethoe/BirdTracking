import yaml
import cv2
import numpy as np

from yolov8.predict import Predictor, detect_features
from yolov8.track import Tracker

from utils.general import RAD2DEG
from utils.camera import Stereo
from utils.structs import Bird, Birds
from utils.sim import *
from utils.odometry import estimate_vio, find_matches


STRIDE = 30

tracker = Tracker('yolov8/weights/head.pt')
predictor_head = Predictor('yolov8/weights/head.pt')

vid = 'data/vid/fps120/K203_K238_1_GH040045.mp4'

cfg_path = 'data/calibration/cam.yaml'

h, w = (720, 1280)
writer = cv2.VideoWriter('data/out/vio.mp4', cv2.VideoWriter_fourcc(*'MPEG'), 4, (w, int(h*1.5)))

with open(cfg_path, 'r') as f:
    cfg = yaml.safe_load(f)
    K = np.asarray(cfg['KR']).reshape(3, 3)
    dist = np.asarray(cfg['distR'])

cap = cv2.VideoCapture(vid)
birds = Birds()
prev_frame = None
frame_no = 0
sim.flip()
T = np.eye(4)
sim.update(T)
print(sim.screen.shape)
while cap.isOpened():
    for i in range(STRIDE):
        if cap.isOpened():
            _ = cap.grab()
        else:
            break
    ret, frame = cap.retrieve()
    if ret:
        head = tracker.tracks(frame)[0].boxes.cpu().numpy()
        feat = detect_features(frame, head)
        birds.update([Bird(head, feat) for head, feat in zip(head, feat)], frame)
        bird = birds['m'] if birds['m'] is not None else birds['f']
        prev_bird = birds.caches['m'][-1] if birds.caches['m'][-1] is not None else birds.caches['f'][-1]
        if bird is not None and prev_frame is not None:
            prev_mask = prev_bird.mask(prev_frame.shape[:2])
            curr_mask = bird.mask(frame.shape[:2])
            vio, R, t, _ = estimate_vio(prev_frame, frame, prev_mask, curr_mask, K, dist, method='sift')
            if vio:
                T[:3, :3] = R.T
                # T[:3, 3] = -t.T
                # r, _ = cv2.Rodrigues(R*transforms[frame_no][:3, :3])
                # error = np.linalg.norm(r)
                # print(r, error)
                print('vo:', *np.rint(cv2.Rodrigues(R.T)[0] * RAD2DEG))
                print('')
                sim.update(T)
            kp1, kp2, matches = find_matches(prev_frame, frame, prev_mask, curr_mask, method='sift')
            orb = cv2.drawMatches(prev_frame, kp1, frame, kp2, matches, None, flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
        # cv2.imshow('frame', cv2.resize(birds.plot(frame), None, fx=0.4, fy=0.4, interpolation=cv2.INTER_CUBIC))

        # out = cv2.vconcat([cv2.resize(birds.plot(frame), (w, h), interpolation=cv2.INTER_CUBIC),
        #                    cv2.resize(sim.screen, (w, h), interpolation=cv2.INTER_CUBIC)])
            out = cv2.vconcat([cv2.resize(orb, (w, int(h/2)), interpolation=cv2.INTER_CUBIC),
                               cv2.resize(sim.screen, (w, h), interpolation=cv2.INTER_CUBIC)])
        else:
            out = cv2.vconcat([cv2.resize(cv2.hconcat([frame, frame]), (w, int(h / 2)), interpolation=cv2.INTER_CUBIC),
                               cv2.resize(sim.screen, (w, h), interpolation=cv2.INTER_CUBIC)])
        cv2.imshow('out', out)
        writer.write(out)

        prev_frame = frame
        frame_no += 1
        if cv2.waitKey(1) == ord('q'):
            break
    else:
        break

cap.release()
writer.release()
cv2.destroyAllWindows()
sim.close()