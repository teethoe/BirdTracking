import cv2
import numpy as np
from utils.general import kernel
from utils.calibrate import find_corners, get_mask, remap, obj_pts


class Camera:
    def __init__(self, path, skip=0):
        self.cap = cv2.VideoCapture(path)
        self.skip = skip
        self.h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.skip)
        self.flash = -1
        self.first_flash()
        self.objpts = []
        self.imgpts = []
        self.mpts = []
        self.mpts_ = []
        self.k = None
        self.dist = None

    def first_flash(self, kernel_size=5):
        print('Detecting camera flash...')
        count = 0
        while self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                count += 1
                frame = cv2.resize(frame, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_CUBIC)

                low = np.array([0, 0, 255])
                high = np.array([0, 0, 255])
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv, low, high)
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel(kernel_size))

                contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                if len(contours) >= 1:
                    self.flash = count + self.skip
                    break
            else:
                print('not ret')
                self.cap.release()
                break

    def add_chessboard_pts(self, corners, size):
        if corners is not None and size is not None:
            self.objpts.append(obj_pts(*size))
            self.imgpts.append(corners)

    def add_matched_pts(self, corners):
        self.mpts.append(corners)
        self.mpts_.append(corners.squeeze)

    def calibrate(self):
        _, self.k, self.dist, _, _ = cv2.calibrateCamera(
            self.objpts, self.imgpts, (self.w, self.h),
            None, None)

    def undistort(self, im):
        return cv2.undistort(im, self.k, self.dist)

    def undistort_pts(self, pts):
        return cv2.undistortImagePoints(pts, self.k, self.dist)


class Stereo:
    def __init__(self, vidL, vidR, skip=1500, stride=30, timeout=5400, size=(4, 7)):
        self.camL = Camera(vidL, skip)
        self.camR = Camera(vidR, skip)
        self.size = size
        self.R = None
        self.T = None
        self.E = None
        self.F = None
        self.calibrated = False
        self.offsetL = 0
        self.offsetR = 0
        self.objpts = []
        self.sync(stride=stride, timeout=timeout)

    def sync(self, stride, timeout):
        if self.camL.flash >= 0 and self.camR.flash >= 0:
            print('Calibrating cameras...')
            self.offsetL = self.camL.flash
            self.offsetR = self.camR.flash
            self.camL.cap.set(cv2.CAP_PROP_POS_FRAMES, self.offsetL)
            self.camR.cap.set(cv2.CAP_PROP_POS_FRAMES, self.offsetR)
            count = 0
            while count < timeout and self.camL.cap.isOpened() and self.camR.cap.isOpened():
                for i in range(stride):
                    _ = self.camL.cap.grab()
                    _ = self.camR.cap.grab()
                self.offsetL += stride
                self.offsetR += stride
                count += stride
                retL, frameL = self.camL.cap.retrieve()
                retR, frameR = self.camR.cap.retrieve()
                if retL and retR:
                    self.find_chessboard(frameL, frameR)
                else:
                    break
            self.camL.calibrate()
            self.camR.calibrate()
            print('Syncing cameras...')
            self.calibrate()
        else:
            print('Camera sync failed.')
        self.camL.cap.release()
        self.camR.cap.release()

    def find_chessboard(self, frameL, frameR, show=False):
        cnrL, sizeL = find_corners(get_mask(frameL), self.size)
        cnrR, sizeR = find_corners(get_mask(frameR), self.size)
        self.camL.add_chessboard_pts(cnrL, sizeL)
        self.camR.add_chessboard_pts(cnrR, sizeR)
        if show:
            cv2.drawChessboardCorners(frameL, sizeL, cnrL, cnrL is not None)
            cv2.drawChessboardCorners(frameR, sizeR, cnrR, cnrR is not None)
            cv2.imshow('chessboard',
                       cv2.resize(cv2.vconcat([frameL, frameR]), None, fx=0.5, fy=0.5, interpolation=cv2.INTER_CUBIC))
            cv2.waitKey(1)
        if cnrL is not None and cnrR is not None:
            if sizeL != sizeR:
                cnrR = remap(cnrR, sizeR)
            self.camL.add_matched_pts(cnrL)
            self.camR.add_matched_pts(cnrR)
            self.objpts.append(obj_pts(*sizeL))

    def calibrate_(self):
        print('Calibrating cameras...')
        self.E, mask = cv2.findEssentialMat(
            self.camL.undistort_pts(np.concatenate(self.camL.mpts_)),
            self.camR.undistort_pts(np.concatenate(self.camR.mpts_)),
            self.camL.k)

    def calibrate(self):
        self.calibrated, self.camL.k, self.camL.dist, self.camR.k, self.camR.dist, self.R, self.T, self.E, self.F \
            = cv2.stereoCalibrate(
            self.objpts, self.camL.mpts, self.camR.mpts,
            self.camL.k, self.camL.dist,
            self.camR.k, self.camR.dist,
            (self.camL.w, self.camL.h),
            self.R, self.T, self.E, self.F)


if __name__ == '__main__':
    import yaml
    from pathlib import Path

    ROOT = Path(__file__).parent.parent
    STRIDE = 30
    vidL = str(ROOT / 'data/vid/fps120/K203_K238/GOPRO2/GH010039.MP4')
    vidR = str(ROOT / 'data/vid/fps120/K203_K238/GOPRO1/GH010045.MP4')

    # sync videos and calibrate cameras
    stereo = Stereo(vidL, vidR, stride=STRIDE)
    with open(ROOT / 'data/mtx.yaml', 'w') as f:
        data = {'kL': stereo.camL.k.flatten().tolist(),
                'distL': stereo.camL.dist.flatten().tolist(),
                'kR': stereo.camR.k.flatten().tolist(),
                'distR': stereo.camR.dist.flatten().tolist(),
                'R': stereo.R.flatten().tolist(),
                'T': stereo.T.tolist(),
                'E': stereo.E.flatten().tolist(),
                'F': stereo.F.flatten().tolist()}
        f.write(yaml.dump(data, sort_keys=False))
