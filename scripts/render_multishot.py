"""
Multi-shot renderer for category 3 (multi-musician fixed stage).

Reads an EDL JSON (produced/edited from build_edl_multishot.py), renders a frame
range with HARD CUTS between shots and optional cross-dissolves at specified times.

Usage:
    python render_multishot.py --edl edl.json \\
        --start-frame 0 --end-frame 500 --out chunk1.mkv

The EDL JSON structure:
{
  "video_w": 2560, "video_h": 1440,
  "out_w": 1080, "out_h": 1920,
  "trim_start": 155.0, "trim_end": 214.0,
  "source": "/path/to/video.mp4",
  "shots": [
    {"t_start": 0.0, "t_end": 5.4, "cx": 0.61, "cy": 0.50,
     "zoom_start": 1.00, "zoom_end": 1.00, "notes": "..."},
    ...
  ],
  "dissolves": [
    [47.12, 47.52],  // start, end of a 0.4s cross-dissolve window
    ...
  ]
}
"""
import argparse
import json
import os
import subprocess
import sys
import time

import cv2
import numpy as np


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--edl", required=True)
    ap.add_argument("--start-frame", type=int, required=True)
    ap.add_argument("--end-frame", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--source", default=None)
    args = ap.parse_args()

    with open(args.edl) as f:
        edl = json.load(f)
    SRC = args.source or edl["source"]
    VW, VH = edl.get("video_w"), edl.get("video_h")
    OUT_W, OUT_H = edl["out_w"], edl["out_h"]
    TARGET_AR = OUT_W / OUT_H
    trim_start_t = edl.get("trim_start", 0)
    shots = edl["shots"]
    dissolves = edl.get("dissolves", [])

    # Auto-detect VW/VH if missing
    if not VW or not VH:
        cap0 = cv2.VideoCapture(SRC)
        VW = int(cap0.get(cv2.CAP_PROP_FRAME_WIDTH))
        VH = int(cap0.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap0.release()

    def shot_params(t):
        for sh in shots:
            if sh["t_start"] <= t < sh["t_end"]:
                f = smoothstep((t - sh["t_start"]) / max(0.01, sh["t_end"] - sh["t_start"]))
                z = sh["zoom_start"] + (sh["zoom_end"] - sh["zoom_start"]) * f
                return sh["cx"], sh["cy"], z
        last = shots[-1]
        return last["cx"], last["cy"], last["zoom_end"]

    def in_dissolve(t):
        for ds, de in dissolves:
            if ds <= t < de:
                alpha = smoothstep((t - ds) / (de - ds))
                cut_t = (ds + de) / 2
                # find adjacent shot pair around cut_t
                shot_a = shot_b = None
                for i, sh in enumerate(shots):
                    if abs(sh["t_end"] - cut_t) < 0.5 and i + 1 < len(shots):
                        shot_a = sh
                        shot_b = shots[i + 1]
                        break
                if shot_a is None:
                    return None
                a = (shot_a["cx"], shot_a["cy"], shot_a["zoom_end"])
                b = (shot_b["cx"], shot_b["cy"], shot_b["zoom_start"])
                return alpha, a, b
        return None

    def make_crop(frame, cx, cy, zoom):
        zoom = max(1.0, zoom)
        cw = (VH * TARGET_AR) / zoom
        ch = VH / zoom
        x1 = max(0, min(VW - cw, cx * VW - cw / 2))
        y1 = max(0, min(VH - ch, cy * VH - ch / 2))
        xi, yi = int(round(x1)), int(round(y1))
        crop = frame[yi:yi + int(round(ch)), xi:xi + int(round(cw))]
        if crop.shape[0] != OUT_H or crop.shape[1] != OUT_W:
            crop = cv2.resize(crop, (OUT_W, OUT_H), interpolation=cv2.INTER_LINEAR)
        return crop

    cap = cv2.VideoCapture(SRC)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.set(cv2.CAP_PROP_POS_FRAMES, args.start_frame)
    trim_start_frame = int(round(trim_start_t * fps))

    ff = subprocess.Popen([
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{OUT_W}x{OUT_H}", "-framerate", str(fps),
        "-i", "pipe:0",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
        "-pix_fmt", "yuv420p", "-an", "-f", "matroska", args.out,
    ], stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    t0 = time.time()
    idx = args.start_frame
    n = 0
    while idx < args.end_frame:
        ret, frame = cap.read()
        if not ret: break
        t_out = (idx - trim_start_frame) / fps
        dis = in_dissolve(t_out)
        if dis:
            alpha, (cxa, cya, za), (cxb, cyb, zb) = dis
            ca = make_crop(frame, cxa, cya, za)
            cb = make_crop(frame, cxb, cyb, zb)
            crop = cv2.addWeighted(ca, 1.0 - alpha, cb, alpha, 0)
        else:
            cx, cy, zoom = shot_params(t_out)
            crop = make_crop(frame, cx, cy, zoom)
        try:
            ff.stdin.write(crop.tobytes())
        except BrokenPipeError:
            break
        idx += 1
        n += 1

    cap.release()
    ff.stdin.close()
    ff.wait()
    err = ff.stderr.read().decode()
    if err: print(f"ffmpeg stderr: {err}", file=sys.stderr)
    print(f"Rendered {n} frames in {time.time()-t0:.1f}s → {args.out}")


if __name__ == "__main__":
    main()
