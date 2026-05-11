"""
Chunked frame renderer for category 1 (narrative) and category 2 (static).

Reads keyframes.json (produced by build_plan_narrative.py or build_plan_static.py),
renders a frame range with CubicSpline interpolation, pipes to FFmpeg as raw BGR,
encodes to MKV (libx264 ultrafast).

Usage:
    python render_chunk.py --keyframes keyframes.json \\
        --start-frame 0 --end-frame 500 --out chunk1.mkv

For category 1/2 with smooth motion, you typically render in 500-frame chunks
to fit within sandbox timeouts. After all chunks are rendered, concatenate them
with FFmpeg `concat` demuxer and mux the audio.
"""
import argparse
import json
import os
import subprocess
import sys
import time

import cv2
import numpy as np
from scipy.interpolate import CubicSpline


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--keyframes", required=True)
    ap.add_argument("--start-frame", type=int, required=True)
    ap.add_argument("--end-frame", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--source", default=None,
                    help="Override source video path (defaults to keyframes.json's source)")
    args = ap.parse_args()

    with open(args.keyframes) as f:
        plan = json.load(f)
    SRC = args.source or plan["source"]
    VW, VH = plan["video_w"], plan["video_h"]
    OUT_W, OUT_H = plan["out_w"], plan["out_h"]
    TARGET_AR = OUT_W / OUT_H
    trim_start_t = plan.get("trim_start", 0)

    keyframes = plan["keyframes"]
    ts = np.array([k["t"] for k in keyframes])
    cxs = np.array([k["cx"] for k in keyframes])
    cys = np.array([k["cy"] for k in keyframes])
    zs  = np.array([k["zoom"] for k in keyframes])

    cx_sp = CubicSpline(ts, cxs, bc_type="natural")
    cy_sp = CubicSpline(ts, cys, bc_type="natural")
    z_sp  = CubicSpline(ts, zs,  bc_type="natural")

    def interp(t):
        t = max(ts[0], min(ts[-1], t))
        return float(cx_sp(t)), float(cy_sp(t)), float(z_sp(t))

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
    trim_start_frame = int(round(trim_start_t * fps))
    n = 0
    while idx < args.end_frame:
        ret, frame = cap.read()
        if not ret: break
        # Map source frame → output time (keyframes.t is in OUTPUT time, 0 = trim start)
        t_out = (idx - trim_start_frame) / fps
        cx, cy, zoom = interp(t_out)
        crop = make_crop(frame, cx, cy, zoom)
        try:
            ff.stdin.write(crop.tobytes())
        except BrokenPipeError:
            print(f"Broken pipe at frame {n}", file=sys.stderr)
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
