"""
Visual analysis for concert footage.

Detects faces (YuNet ONNX) and persons (HOG) at SAMPLE_FPS samples per second over
a time range of the source video. Outputs normalized bounding boxes per sample.

Usage:
    python visual_analyze.py <source.mp4> <start_seconds> <end_seconds> [--out persons.json]
    python visual_analyze.py <source.mp4> 155 214 --reference --out ref.json

With --reference: samples ONE frame at the midpoint and runs full-resolution
face detection. Use this for category 3 (fixed-stage multi-musician) where you
only need the positions once.
"""
import argparse
import json
import os
import sys
import urllib.request

import cv2
import numpy as np


YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SAMPLE_FPS = 2  # samples per second


def ensure_yunet(dest):
    if not os.path.exists(dest):
        print(f"Downloading YuNet model to {dest}...", file=sys.stderr)
        urllib.request.urlretrieve(YUNET_URL, dest)
    return dest


def detect_faces(yunet, frame, max_side=1280):
    """YuNet face detection. frame is BGR. Returns list of normalized boxes."""
    H, W = frame.shape[:2]
    if max(W, H) > max_side:
        scale = max_side / max(W, H)
        small = cv2.resize(frame, (int(W * scale), int(H * scale)))
    else:
        small = frame
    sh, sw = small.shape[:2]
    yunet.setInputSize((sw, sh))
    _, faces = yunet.detect(small)
    out = []
    if faces is not None:
        for f in faces:
            x, y, w, h = f[:4]
            x1 = float(x / sw); y1 = float(y / sh)
            x2 = float((x + w) / sw); y2 = float((y + h) / sh)
            if (x2 - x1) * (y2 - y1) < 1e-5:
                continue
            out.append({
                "type": "face",
                "conf": round(float(f[-1]), 3),
                "x1": round(x1, 4), "y1": round(y1, 4),
                "x2": round(x2, 4), "y2": round(y2, 4),
                "cx": round((x1 + x2) / 2, 4),
                "cy": round((y1 + y2) / 2, 4),
                "w": round(x2 - x1, 4),
                "h": round(y2 - y1, 4),
            })
    return out


def detect_persons(hog, frame, target_w=960, min_weight=0.4):
    """HOG person detection. Returns normalized boxes."""
    H, W = frame.shape[:2]
    scale = target_w / W
    small = cv2.resize(frame, (target_w, int(H * scale)))
    sh, sw = small.shape[:2]
    rects, weights = hog.detectMultiScale(
        small, winStride=(8, 8), padding=(8, 8), scale=1.05,
    )
    out = []
    for (x, y, w, h), wt in zip(rects, weights):
        if wt < min_weight:
            continue
        x1, y1 = x / sw, y / sh
        x2, y2 = (x + w) / sw, (y + h) / sh
        out.append({
            "type": "person",
            "conf": round(float(wt), 3),
            "x1": round(float(x1), 4), "y1": round(float(y1), 4),
            "x2": round(float(x2), 4), "y2": round(float(y2), 4),
            "cx": round(float((x1 + x2) / 2), 4),
            "cy": round(float((y1 + y2) / 2), 4),
            "w": round(float(x2 - x1), 4),
            "h": round(float(y2 - y1), 4),
        })
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("source")
    ap.add_argument("start", type=float)
    ap.add_argument("end", type=float)
    ap.add_argument("--out", default="visual_timeline.json")
    ap.add_argument("--reference", action="store_true",
                    help="Only analyze a single reference frame (midpoint)")
    ap.add_argument("--yunet", default="yunet.onnx", help="Path to YuNet ONNX model")
    args = ap.parse_args()

    ensure_yunet(args.yunet)
    yunet = cv2.FaceDetectorYN.create(args.yunet, "", (1280, 720),
                                        score_threshold=0.5, nms_threshold=0.3, top_k=10)
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    cap = cv2.VideoCapture(args.source)
    fps = cap.get(cv2.CAP_PROP_FPS)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    start_frame = int(args.start * fps)
    end_frame = int(args.end * fps)

    samples = []

    if args.reference:
        mid_frame = (start_frame + end_frame) // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
        ret, frame = cap.read()
        if not ret:
            print("Couldn't read reference frame", file=sys.stderr)
            sys.exit(1)
        samples.append({
            "t": mid_frame / fps,
            "faces": detect_faces(yunet, frame),
            "persons": detect_persons(hog, frame),
        })
    else:
        step = max(1, int(fps / SAMPLE_FPS))
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        hog_skip = 0
        idx = start_frame
        while idx < end_frame:
            ret, frame = cap.read()
            if not ret: break
            if (idx - start_frame) % step == 0:
                t_out = (idx - start_frame) / fps
                faces = detect_faces(yunet, frame)
                # HOG is slow, run every other sample
                persons = detect_persons(hog, frame) if hog_skip % 2 == 0 else []
                samples.append({
                    "t": round(t_out, 2),
                    "faces": faces,
                    "persons": persons,
                })
                hog_skip += 1
            idx += 1

    cap.release()

    result = {
        "video_w": W, "video_h": H,
        "fps": fps,
        "sample_fps": SAMPLE_FPS if not args.reference else 0,
        "reference_only": args.reference,
        "samples": samples,
        "meta": {
            "source": os.path.abspath(args.source),
            "trim_start": args.start,
            "trim_end": args.end,
        },
    }
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote {args.out}: {len(samples)} samples, "
          f"{sum(len(s['faces']) for s in samples)} faces, "
          f"{sum(len(s['persons']) for s in samples)} persons")


if __name__ == "__main__":
    main()
