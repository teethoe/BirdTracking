import cv2
import numpy as np
import math

import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))

from utils.general import kernel


def contour_valid(im, contour, area_thresh=0.0025, centre_thresh=0.2):
    h, w = im.shape[:2]
    area = cv2.contourArea(contour) > math.prod(im.shape[:2]) * area_thresh
    M = cv2.moments(contour)
    cX = int(M["m10"] / M["m00"])
    cY = int(M["m01"] / M["m00"])
    centre = w*centre_thresh < cX < w*(1-centre_thresh) and h*area_thresh < cY < h*(1-area_thresh)
    return area and centre


def get_mask(im):
    grey = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    _, thw = cv2.threshold(grey, 200, 255, cv2.THRESH_BINARY)
    _, thb = cv2.threshold(grey, 50, 255, cv2.THRESH_BINARY_INV)
    combined = cv2.bitwise_or(thw, thb)
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel(5))
    combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel(5))
    contours, hierarchy = cv2.findContours(combined, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    cnts = [contour for contour in contours if contour_valid(im, contour)]
    cnts = sorted(cnts, key=lambda x: cv2.contourArea(x), reverse=True)

    mask = np.zeros(im.shape[:2], np.uint8)
    cv2.drawContours(mask, cnts[:1], 0, 255, -1)
    chessboard = cv2.bitwise_and(grey, grey, mask=mask)
    _, binary_mask = cv2.threshold(chessboard, 150, 255, cv2.THRESH_BINARY)
    binary_mask -= 255
    return binary_mask


def harris_corners(img):
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    dst = cv2.cornerHarris(grey, 2, 15, 0.07)
    dst_norm = np.empty(dst.shape, dtype=np.float32)
    cv2.normalize(dst, dst_norm, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
    dst_norm_scaled = cv2.convertScaleAbs(dst_norm)
    v = np.percentile(dst_norm_scaled, 99)
    img[dst_norm_scaled > v] = (0, 0, 255)
    return img


def draw_corners(img, size=(4, 7)):
    mask = get_mask(img)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.01)
    flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK + cv2.CALIB_CB_NORMALIZE_IMAGE
    ret, corners = cv2.findChessboardCorners(mask, size, flags)
    if ret:
        cnrs = cv2.cornerSubPix(mask, corners, (11, 11), (-1, -1), criteria)
        cv2.drawChessboardCorners(img, size, cnrs, ret)
    return img


def find_corners(im, size=(4, 7)):
    flags = (cv2.CALIB_CB_ADAPTIVE_THRESH
             + cv2.CALIB_CB_FAST_CHECK
             + cv2.CALIB_CB_NORMALIZE_IMAGE
             + cv2.CALIB_USE_INTRINSIC_GUESS)
    ret, corners = cv2.findChessboardCorners(im, size, flags)
    if not ret:
        size = size[::-1]
        ret, corners = cv2.findChessboardCorners(im, size, flags)
    if ret:
        return corners, size
    return None, None


def remap(pts, size):
    h, w = size
    return np.asarray([pts[(i%h)*w+(w-1-i//h)] for i in range(h*w)])


def obj_pts(c, r):
    o = np.zeros((math.prod((c, r)), 3), np.float32)
    o[:, :2] = np.mgrid[0:c, 0:r].T.reshape(-1, 2)
    return o


if __name__ == '__main__':
    im = cv2.imread(str(ROOT / 'data/calibration/fps10/chessboard.jpg'))
    # im = cv2.imread(str(ROOT / 'data/calibration/K203_K238/chessboard/l/3411.jpg'))
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    shape = (4, 7)

    # termination criteria
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    # prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
    objp = np.zeros((shape[0]*shape[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:shape[0], 0:shape[1]].T.reshape(-1, 2)

    # Arrays to store object points and image points from all the images.
    objpts = []  # 3d point in real world space
    imgpts = []  # 2d points in image plane.

    # Find the chess board corners
    ret, corners = cv2.findChessboardCorners(gray, shape, None)
    if ret:
        objpts.append(objp)

        corners = cv2.cornerSubPix(gray, corners, (11,11), (-1,-1), criteria)
        imgpts.append(corners)

        # Draw and display the corners
        cv2.drawChessboardCorners(im, shape, corners, ret)
        cv2.imshow('corners', im)
        cv2.waitKey(0)
        cv2.imwrite(str(ROOT / 'data/out/chessboard_corners.jpg'), im)

    cv2.destroyAllWindows()
