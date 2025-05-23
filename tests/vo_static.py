import yaml
import cv2
import numpy as np

import os
import sys
from pathlib import Path
ROOT = Path(os.path.abspath(__file__)).parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from lightglue import LightGlue, SuperPoint, match_pair, viz2d
from lightglue.utils import load_image, numpy_image_to_torch

from utils.general import RAD2DEG
from utils.odometry import estimate_vo, estimate_vo_pts, find_matches


BLENDER_ROOT = ROOT / 'data/blender'
NAME = 'vanilla'

renders_dir = BLENDER_ROOT / 'renders'
vid_path = renders_dir / f'vid/{NAME}_f.mp4'
input_dir = renders_dir / NAME
cfg_path = input_dir / 'cam.yaml'
trans_path = input_dir / 'transforms.txt'


with open(cfg_path, 'r') as f:
    cfg = yaml.safe_load(f)
    K = np.asarray(cfg['K']).reshape(3, 3)
    dist = None

with open(trans_path, 'r') as f:
    lines = f.readlines()
    transforms = [np.array(list(map(float, line.strip().split()[1:]))).reshape((4, 4)) for line in lines]


index = 2
im1 = cv2.imread(os.path.join(input_dir, f'{index:03}.png'))
im2 = cv2.imread(os.path.join(input_dir, f'{index+1:03}.png'))

extractor = SuperPoint(max_num_keypoints=2048).eval().cuda()  # load the extractor
matcher = LightGlue(features='superpoint').eval().cuda()  # load the matcher

image0 = numpy_image_to_torch(im1).cuda()
image1 = numpy_image_to_torch(im2).cuda()

feats0, feats1, matches01 = match_pair(extractor, matcher, image0, image1)
kpts0, kpts1, matches = feats0["keypoints"], feats1["keypoints"], matches01["matches"]
m_kpts0, m_kpts1 = kpts0[matches[..., 0]], kpts1[matches[..., 1]]
src_pts, dst_pts = m_kpts0.cpu().numpy(), m_kpts1.cpu().numpy()
vo, R, t, _ = estimate_vo_pts(src_pts, dst_pts, K, dist)
if vo:
    print('vo:', *np.rint(cv2.Rodrigues(R.T)[0]*RAD2DEG))
    print('gt:', *np.rint(cv2.Rodrigues(transforms[index][:3, :3])[0]*RAD2DEG))

axes = viz2d.plot_images([image0, image1])
kpc0, kpc1 = viz2d.cm_prune(matches01["prune0"]), viz2d.cm_prune(matches01["prune1"])
viz2d.plot_images([image0, image1])
viz2d.plot_matches(m_kpts0, m_kpts1, color="lime", lw=0.2)
viz2d.plot_keypoints([kpts0, kpts1], colors=[kpc0, kpc1], ps=10)
viz2d.save_plot(f'data/out/lightglue_{index}.jpg')
