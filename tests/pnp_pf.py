import pycolmap
from scipy.spatial.transform import Rotation as R

import os
import sys
from pathlib import Path
ROOT = Path(os.path.abspath(__file__)).parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from yolov8.predict import Predictor, detect_features

from utils.box import pad_boxes
from utils.calibrate import calibrate
from utils.filter import ParticleFilter
from utils.general import RAD2DEG
from utils.reconstruct import get_head_feat_pts, reproj_error
from utils.sim import *
from utils.structs import Bird, Birds


RESIZE = 0.5  # resize display window
STRIDE = 1
FPS = 120
SPEED = .5
PADDING = 30
FLIP = False
TEST = int(sys.argv[1]) if len(sys.argv) > 1 else 2

predictor = Predictor(ROOT / 'yolov8/weights/head.pt')

data_dir = ROOT / 'data'
test_dir = data_dir / 'test'
out_dir = data_dir / 'out/pnp'
os.makedirs(out_dir, exist_ok=True)

vid_path = test_dir / f'bird/test_{TEST}.mp4'
calib_path = test_dir / f'calib/test_{TEST}.mp4'

blender_cfg = data_dir / 'blender/configs/cam.yaml'

h, w = (720, 1280)
writer = cv2.VideoWriter(str(out_dir / f'pnp_pf_{TEST}.mp4'), cv2.VideoWriter_fourcc(*'mp4v'), FPS//STRIDE*SPEED, (w, h * 2))

K, dist, mre_calib = calibrate(calib_path, flip=FLIP)
dist = dist.squeeze()

with open(blender_cfg, 'r') as f:
    cfg = yaml.safe_load(f)
    ext = np.array(cfg['ext']).reshape(3, 4)
    cam_rmat = ext[:3, :3]
    cam_rvec = cv2.Rodrigues(cam_rmat)[0]
    cam_tvec = ext[:3, 3]

cap = cv2.VideoCapture(str(vid_path))
cam = pycolmap.Camera(
    model='OPENCV',
    width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
    height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    params=(K[0, 0], K[1, 1],  # fx, fy
            K[0, 2], K[1, 2],  # cx, cy
            *dist[:4]),  # dist: k1, k2, p1, p2
    )

birds = Birds()
frame_count = 0
re_sum = 0

sim = Sim()
T = np.eye(4)
prev_T = np.eye(4)
proj_T = np.eye(4)
sim.update(T)

pf = ParticleFilter()
continuous = False
while cap.isOpened():
    for i in range(STRIDE):
        if cap.isOpened():
            _ = cap.grab()
        else:
            break
    ret, frame = cap.retrieve()
    if ret:
        if FLIP:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        head = pad_boxes(predictor.predictions(frame)[0].boxes.cpu().numpy(), frame.shape, PADDING)
        feat = detect_features(frame, head)
        birds.update([Bird(head, feat) for head, feat in zip(head, feat)][:1], frame)
        bird = birds['m'] if birds['m'] is not None else birds['f']
        if bird is not None:
            head_pts, feat_pts = get_head_feat_pts(bird)
            if head_pts.shape[0] >= 4:
                pnp = pycolmap.estimate_and_refine_absolute_pose(feat_pts, head_pts, cam)
                if pnp is not None:
                    rig = pnp['cam_from_world']  # Rigid3d
                    rmat = rig.rotation.matrix()
                    rmat = cam_rmat @ rmat  # camera to world
                    tvec = rig.translation + cam_tvec

                    # particle filter
                    obs = np.array([*R.from_matrix(rmat).as_euler('xyz'), *tvec])
                    pf.transition()
                    pf.observe(obs, continuous)
                    pf.resample()
                    estimate = pf.estimate()
                    r = estimate[:3]
                    tvec = estimate[3:]

                    # error projection
                    proj_T[:3, :3] = R.from_euler('xyz', r).as_matrix()
                    proj_T[:3, 3] = tvec

                    # colmap to o3d notation
                    r[0] *= -1
                    rmat = R.from_euler('xyz', r).as_matrix()
                    tvec[0] *= -1

                    # camera pose to head pose
                    rmat = rmat.T
                    tvec = -tvec

                    T[:3, :3] = rmat @ prev_T[:3, :3].T
                    # T[:3, 3] = tvec - prev_T[:3, 3]
                    print('es:', *np.rint(R.from_matrix(T[:3, :3]).as_euler('xyz', degrees=True)))
                    print('esT:', *np.rint(-r * RAD2DEG))

                    error = reproj_error(feat_pts, head_pts, proj_T, -cam_rvec, -cam_tvec, K, dist)
                    print('error:', error)
                    print('')

                    re_sum += error
                    frame_count += 1

                    prev_T[:3, :3] = rmat
                    prev_T[:3, 3] = tvec.T
                    sim.update(T)
                    continuous = True
                else:
                    continious = False
            else:
                continious = False
        else:
            continious = False
        cv2.imshow('frame', cv2.resize(birds.plot(), None, fx=RESIZE, fy=RESIZE, interpolation=cv2.INTER_CUBIC))

        out = cv2.vconcat([cv2.resize(birds.plot(), (w, h), interpolation=cv2.INTER_CUBIC),
                           cv2.resize(sim.screen, (w, h), interpolation=cv2.INTER_CUBIC)])
        cv2.imshow('out', cv2.resize(out, None, fx=RESIZE, fy=RESIZE, interpolation=cv2.INTER_CUBIC))

        writer.write(out)

        if cv2.waitKey(1) == ord('q'):
            break
    else:
        break

cap.release()
writer.release()
cv2.destroyAllWindows()
sim.close()

print('Test', TEST)
print(f'Calibration MRE: {round(mre_calib, 3)}')
print(f'Pose MRE:', round(re_sum / frame_count, 3))
