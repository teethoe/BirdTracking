import yaml
import cv2
import numpy as np
from pathlib import Path

from utils.structs import CLS_DICT


ROOT = Path(__file__).parent.parent
cfg_path = ROOT / 'data/blender/config.yaml'
with open(cfg_path, 'r') as f:
    HEAD_CFG = yaml.safe_load(f)


def solvePnP(bird, K, dist=None):
    head_pts = np.array([HEAD_CFG[k] for k, v in bird.feats.items() if v is not None], dtype=np.float32)
    feat_pts = np.array([v for k, v in bird.feats.items() if v is not None], dtype=np.float32)
    if head_pts.shape[0] >= 4:
        return cv2.solvePnPRansac(head_pts, feat_pts, K, dist, reprojectionError=4.)
        # return True, cv2.solvePnPRefineLM(head_pts, feat_pts, K, dist, None, None), None
    return False, None, None, None


def triangulate(birdL, birdR, stereo):
    visible = [k for k in CLS_DICT.keys() if birdL.feats[k] is not None and birdR.feats[k] is not None]
    if len(visible) == 0:
        return 0, None, None
    head_pts = np.array([HEAD_CFG[k] for k in visible])
    feat_ptsL = np.array([birdL.feats[k] for k in visible]).T
    feat_ptsR = np.array([birdR.feats[k] for k in visible]).T
    feat_pts = cv2.triangulatePoints(stereo.camL.P, stereo.camR.P, feat_ptsL, feat_ptsR)
    return cv2.estimateAffine3D(head_pts, cv2.convertPointsFromHomogeneous(feat_pts.T))
