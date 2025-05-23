import open3d as o3d
import numpy as np
import cv2
import yaml

import os
import sys
from pathlib import Path
ROOT = Path(os.path.abspath(__file__)).parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from utils.box import Box
from utils.colour import bgr_mask
from utils.configs import CLS_DICT, COLOUR_DICT
from utils.general import cnt_centroid, DEG2RAD
from utils.sorter import process_labels


class Sim:
    def __init__(self, path=ROOT / 'data/blender/full_model.obj', cfg=ROOT / 'data/blender/configs/cam.yaml'):
        self.mesh = o3d.io.read_triangle_mesh(str(path), enable_post_processing=True)
        self.mesh.compute_vertex_normals()
        self.vis = o3d.visualization.Visualizer()
        self.vis.create_window()
        self.vis.add_geometry(self.mesh)
        with open(cfg, 'r') as f:
            cfg = yaml.safe_load(f)
            ext = np.array(cfg['ext']).reshape(3, 4)
            R = ext[:3, :3]
            t = ext[:3, 3]
        self.vis.get_view_control().set_front(-R.T@t)
        self.vis.get_view_control().set_lookat([0, 0, 0])
        self.vis.get_view_control().set_up([0, 1, 0])
        self.vis.update_renderer()
        self.T = np.eye(4)

    def run(self):
        self.vis.run()

    def update(self, T):
        self.mesh.transform(T)
        self.vis.update_geometry(self.mesh)
        self.vis.poll_events()
        self.vis.update_renderer()

    def flip(self):
        rad = 180 * DEG2RAD
        self.T[0, 0] = np.cos(rad)
        self.T[0, 2] = np.sin(rad)
        self.T[2, 0] = -np.sin(rad)
        self.T[2, 2] = np.cos(rad)
        self.update(self.T)

    @property
    def screen(self):
        return np.uint8(np.asarray(self.vis.capture_screen_float_buffer(False)) * 255)[46:-46]

    def close(self):
        self.vis.destroy_window()

    def set_camera(self, ext):
        R = ext[:3, :3]
        t = ext[:3, 3]
        self.vis.get_view_control().set_front(-R.T @ t)
        self.vis.get_view_control().set_lookat([0, 0, 0])
        self.vis.get_view_control().set_up([0, 1, 0])
        self.vis.update_renderer()


def extract_feature(im, colour, n, cls):
    out = []
    mask = bgr_mask(im, colour)
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) >= 1:
        centroids = [cnt_centroid(cnt) for cnt in contours if cv2.contourArea(cnt) > 0]
        centroids = process_labels(centroids, n, dist=10)
        for i in range(min(n, len(centroids))):
            centroid = centroids[i]
            xywh = np.array([[*centroid, 0., 0.]])
            xywhn = np.array([[*centroid*im.shape[1::-1], 0., 0.]])
            feat = Box(cls, conf=1., xywh=xywh, xywhn=xywhn)
            out.append(feat)
    return out


def extract_features(im):
    bill = extract_feature(im, COLOUR_DICT['bill'], 1, CLS_DICT['bill'])
    eyes = extract_feature(im, COLOUR_DICT['eyes'], 2, CLS_DICT['left_eye'])
    tear_marks = extract_feature(im, COLOUR_DICT['tear_marks'], 2, CLS_DICT['left_tear'])
    bill_liners = extract_feature(im, COLOUR_DICT['bill_liners'], 2, CLS_DICT['left_liner'])
    return [*bill, *eyes, *tear_marks, *bill_liners]


if __name__ == '__main__':
    import numpy as np

    sim = Sim()
    T = np.eye(4)
    # rad = 0 * np.pi / 180
    # T[0, 0] = np.cos(rad)
    # T[0, 2] = np.sin(rad)
    # T[2, 0] = -np.sin(rad)
    # T[2, 2] = np.cos(rad)
    sim.update(T)
    o3d.visualization.draw_geometries([o3d.geometry.TriangleMesh.create_coordinate_frame(), sim.mesh])
