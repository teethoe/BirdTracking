from ultralytics import YOLO

import os
import sys
from pathlib import Path
ROOT = Path(os.path.abspath(__file__)).parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
YOLO_ROOT = ROOT / 'yolov8'
if str(YOLO_ROOT) not in sys.path:
    sys.path.append(str(YOLO_ROOT))

from yolov8.utils import parser, parse_opt


class Predictor:
    """
    Detect bird head features using our pre-trained model.
    """
    def __init__(self, model_path=YOLO_ROOT / 'weights/pose.pt'):
        self.model = YOLO(model_path)

    def predict(self, **kwargs):
        self.model.predict(**kwargs)

    def predictions(self, source, save=False, verbose=False, iou=0.5, **kwargs):
        return self.model.predict(source, save=save, verbose=verbose, iou=iou, **kwargs)


feat_model = Predictor(YOLO_ROOT / 'weights/liner.pt')
def detect_features(im, boxes, **kwargs):
    feats = []
    for xyxy in boxes.xyxy:
        x0, y0, x1, y1 = list(map(round, xyxy))
        feats.append(feat_model.predictions(im[y0:y1, x0:x1], **kwargs)[0].boxes.cpu().numpy())
    return feats


def run(
        weights=YOLO_ROOT / 'weights/pose.pt',  # model path or triton URL
        source=ROOT / 'data/img',  # file/dir/URL/glob/screen/0(webcam)
        conf=0.25,  # confidence threshold
        iou=0.7,  # NMS IOU threshold
        imgsz=640,  # inference size
        half=False,  # use FP16 half-precision inference
        device='',  # cuda device, i.e. 0 or 0,1,2,3 or cpu
        max_det=300,  # maximum detections per image
        vid_stride=1,  # video frame-rate stride
        visualize=False,  # visualize features
        augment=False,  # augmented inference
        agnostic_nms=False,  # class-agnostic NMS
        classes=None,  # filter by class: --class 0, or --class 0 2 3
        show=False,  # show results
        no_save=False,  # do not save results to file
        save_txt=False,  # save results to *.txt
        save_conf=False,  # save confidences in --save-txt labels
        save_crop=False,  # save cropped prediction boxes
        show_labels=True,  # show labels
        show_conf=True,  # show confidences
        show_boxes=True,  # show boxes
        line_width=3  # bounding box thickness (pixels)
):
    model = Predictor(weights)
    model.predict(
        source=source,
        conf=conf,
        iou=iou,
        imgsz=imgsz,
        half=half,
        device=device,
        max_det=max_det,
        vid_stride=vid_stride,
        visualize=visualize,
        augment=augment,
        agnostic_nms=agnostic_nms,
        classes=classes,
        show=show,
        save=not no_save,
        save_txt=save_txt,
        save_conf=save_conf,
        save_crop=save_crop,
        show_labels=show_labels,
        show_conf=show_conf,
        show_boxes=show_boxes,
        line_width=line_width
    )


def main(opt):
    run(**vars(opt))


if __name__ == '__main__':
    opt = parse_opt(parser)
    main(opt)
