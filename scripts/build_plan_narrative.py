"""
Category 1 (Narrative) keyframe builder.

Reads audio_analysis.json and visual_timeline.json, produces keyframes.json with
heavy Gaussian smoothing + subsampling. Supports manual overrides via a Python file.

Usage:
    python build_plan_narrative.py --audio audio.json --visual visual.json \\
        [--override overrides.py] --out keyframes.json

The overrides file should define a cx_override(t_src) function that returns
(cx, zoom) or None. See examples/chez_gegene_overrides.py for a working example.
"""
import argparse
import importlib.util
import json
import math
import sys

import numpy as np
from scipy.ndimage import gaussian_filter1d


def gap_aware_fill(subjects, gap_drift_time=2.0, drift_duration=4.0):
    """Fill missing cx/cy with drift-to-center for long gaps."""
    for i, s in enumerate(subjects):
        if s["cx"] is not None:
            s["cx_interp"] = s["cx"]
            s["cy_interp"] = s["cy"]
            s["has_subject"] = True
            continue
        before = after = None
        for j in range(i - 1, -1, -1):
            if subjects[j]["cx"] is not None:
                before = subjects[j]; break
        for j in range(i + 1, len(subjects)):
            if subjects[j]["cx"] is not None:
                after = subjects[j]; break
        if before and after:
            gap = after["t"] - before["t"]
            if gap < 3.0:
                f = (s["t"] - before["t"]) / max(0.01, gap)
                s["cx_interp"] = before["cx"] + (after["cx"] - before["cx"]) * f
                s["cy_interp"] = before["cy"] + (after["cy"] - before["cy"]) * f
            else:
                t_from = s["t"] - before["t"]
                t_to = after["t"] - s["t"]
                if t_from < t_to:
                    ax, ay = before["cx"], before["cy"]
                    factor = min(1.0, max(0, t_from - gap_drift_time) / drift_duration)
                else:
                    ax, ay = after["cx"], after["cy"]
                    factor = min(1.0, max(0, t_to - gap_drift_time) / drift_duration)
                s["cx_interp"] = ax + (0.5 - ax) * factor
                s["cy_interp"] = ay + (0.5 - ay) * factor
        elif before:
            t_from = s["t"] - before["t"]
            factor = min(1.0, max(0, t_from - gap_drift_time) / drift_duration)
            s["cx_interp"] = before["cx"] + (0.5 - before["cx"]) * factor
            s["cy_interp"] = before["cy"] + (0.5 - before["cy"]) * factor
        elif after:
            t_to = after["t"] - s["t"]
            factor = min(1.0, max(0, t_to - gap_drift_time) / drift_duration)
            s["cx_interp"] = 0.5 + (after["cx"] - 0.5) * (1 - factor)
            s["cy_interp"] = 0.5 + (after["cy"] - 0.5) * (1 - factor)
        else:
            s["cx_interp"] = 0.5
            s["cy_interp"] = 0.5
        s["has_subject"] = False


def derive_zoom(subjects, audio_windows):
    for s in subjects:
        if s["has_subject"]:
            pw = s["primary_w"]
            if pw > 0.07: base_zoom = 1.0
            elif pw > 0.04: base_zoom = 1.1
            elif pw > 0.02: base_zoom = 1.15
            else: base_zoom = 1.05
        else:
            base_zoom = 1.0
        a = audio_windows.get(round(s["t"], 1))
        if a:
            intensity = a["vocal_n"] * 0.6 + a["inst_n"] * 0.4
            s["zoom"] = base_zoom + intensity * 0.05
        else:
            s["zoom"] = base_zoom


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--audio", required=True, help="audio_analysis.json")
    ap.add_argument("--visual", required=True, help="visual_timeline.json")
    ap.add_argument("--override", default=None, help="Optional Python override file with cx_override(t_src) -> (cx, zoom) or None")
    ap.add_argument("--out", default="keyframes.json")
    ap.add_argument("--out-w", type=int, default=1080)
    ap.add_argument("--out-h", type=int, default=1920)
    ap.add_argument("--smooth-sigma", type=float, default=8.0,
                    help="Gaussian sigma in samples (each = 0.5s by default)")
    ap.add_argument("--subsample-interval", type=float, default=1.5,
                    help="Keep one keyframe per N seconds after smoothing")
    args = ap.parse_args()

    with open(args.audio) as f:
        audio = json.load(f)
    with open(args.visual) as f:
        visual = json.load(f)

    VW, VH = visual["video_w"], visual["video_h"]
    TARGET_AR = args.out_w / args.out_h

    # Build subject array per sample
    subjects = []
    for r in visual["samples"]:
        t = r["t"]
        candidates = []
        for f in r["faces"]:
            candidates.append({
                "cx": f["cx"], "cy": min(0.6, f["cy"] + 0.15),
                "w": f["w"], "size": f["w"] * f["h"],
            })
        for p in r["persons"]:
            candidates.append({
                "cx": p["cx"], "cy": p["y1"] + (p["y2"] - p["y1"]) * 0.4,
                "w": p["w"], "size": p["w"] * p["h"],
            })
        if candidates:
            primary = max(candidates, key=lambda c: c["size"])
            mean_cx = sum(c["cx"] * c["size"] for c in candidates) / sum(c["size"] for c in candidates)
            subjects.append({"t": t, "cx": mean_cx, "cy": primary["cy"],
                              "max_size": primary["size"], "primary_w": primary["w"]})
        else:
            subjects.append({"t": t, "cx": None, "cy": None, "max_size": 0, "primary_w": 0})

    audio_by_t = {round(w["t"], 1): w for w in audio["windows"]}

    gap_aware_fill(subjects)
    derive_zoom(subjects, audio_by_t)

    # Apply user override (pre-smoothing — smoothing flows through it naturally)
    override_fn = None
    if args.override:
        spec = importlib.util.spec_from_file_location("ov", args.override)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        override_fn = getattr(mod, "cx_override", None)

    if override_fn:
        for s in subjects:
            ov = override_fn(s["t"])
            if ov is not None:
                s["cx_interp"], s["zoom"] = ov
                s["cy_interp"] = 0.5

    cxs = np.array([s["cx_interp"] for s in subjects])
    cys = np.array([s["cy_interp"] for s in subjects])
    zooms = np.array([s["zoom"] for s in subjects])

    cxs_s = gaussian_filter1d(cxs, sigma=args.smooth_sigma, mode="reflect")
    cys_s = gaussian_filter1d(cys, sigma=args.smooth_sigma * 0.8, mode="reflect")
    zs_s  = gaussian_filter1d(zooms, sigma=args.smooth_sigma * 0.8, mode="reflect")

    # Re-overlay override on its core to keep it sharp
    if override_fn:
        for i, s in enumerate(subjects):
            ov = override_fn(s["t"])
            if ov is not None:
                cxs_s[i], zs_s[i] = ov
                cys_s[i] = 0.5
        cxs_s = gaussian_filter1d(cxs_s, sigma=3.0, mode="reflect")
        cys_s = gaussian_filter1d(cys_s, sigma=3.0, mode="reflect")

    # Clamp
    for i in range(len(subjects)):
        cw_norm = (VH * TARGET_AR) / VW / max(1.0, zs_s[i])
        cxs_s[i] = max(cw_norm / 2, min(1 - cw_norm / 2, cxs_s[i]))
        ch_norm = 1.0 / max(1.0, zs_s[i])
        cys_s[i] = max(ch_norm / 2, min(1 - ch_norm / 2, cys_s[i]))

    # Subsample
    ts_all = np.array([s["t"] for s in subjects])
    keep_idx = []
    last = -1e9
    for i, t in enumerate(ts_all):
        if t - last >= args.subsample_interval or i == 0 or i == len(ts_all) - 1:
            keep_idx.append(i); last = t
    if 0 not in keep_idx: keep_idx.insert(0, 0)
    if len(ts_all) - 1 not in keep_idx: keep_idx.append(len(ts_all) - 1)

    keyframes = []
    for i in keep_idx:
        keyframes.append({
            "t": round(subjects[i]["t"], 3),
            "cx": round(float(cxs_s[i]), 4),
            "cy": round(float(cys_s[i]), 4),
            "zoom": round(float(zs_s[i]), 3),
        })

    with open(args.out, "w") as f:
        json.dump({
            "video_w": VW, "video_h": VH,
            "out_w": args.out_w, "out_h": args.out_h,
            "trim_start": audio["meta"]["trim_start"],
            "trim_end": audio["meta"]["trim_end"],
            "source": audio["meta"]["source"],
            "keyframes": keyframes,
        }, f, indent=2)
    print(f"Wrote {args.out}: {len(keyframes)} keyframes")


if __name__ == "__main__":
    main()
