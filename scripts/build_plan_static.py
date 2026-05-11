"""
Category 2 (Static single musician) Ken Burns keyframe builder.

Generates a small set of hand-tuned keyframes for a gentle slow zoom + face-follow
on a fixed-position musician. Adjust the KEYFRAMES list for your specific case.

Usage:
    python build_plan_static.py --source video.mp4 --start 0 --end 30 \\
        --cx 0.5 --out keyframes.json

The default behavior is a gentle zoom 1.0 → 1.10 → 1.05 over the duration with
cy drifting from 0.50 → 0.42 → 0.50 to keep the upper body framed.
"""
import argparse
import json


def build_default_keyframes(duration, cx=0.5):
    """5-7 anchors for a gentle Ken Burns over the duration."""
    d = duration
    return [
        {"t": 0.0,        "cx": cx, "cy": 0.50, "zoom": 1.00},
        {"t": d * 0.20,   "cx": cx, "cy": 0.47, "zoom": 1.04},
        {"t": d * 0.40,   "cx": cx, "cy": 0.43, "zoom": 1.09},
        {"t": d * 0.55,   "cx": cx, "cy": 0.42, "zoom": 1.11},
        {"t": d * 0.80,   "cx": cx, "cy": 0.45, "zoom": 1.08},
        {"t": d * 0.95,   "cx": cx, "cy": 0.49, "zoom": 1.03},
        {"t": d,          "cx": cx, "cy": 0.50, "zoom": 1.00},
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", required=True)
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--cx", type=float, default=0.5, help="Horizontal position of the musician")
    ap.add_argument("--out-w", type=int, default=1080)
    ap.add_argument("--out-h", type=int, default=1920)
    ap.add_argument("--out", default="keyframes.json")
    args = ap.parse_args()

    duration = args.end - args.start

    # Need source dimensions
    import cv2
    cap = cv2.VideoCapture(args.source)
    VW = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    VH = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    kfs = build_default_keyframes(duration, cx=args.cx)
    out = {
        "video_w": VW, "video_h": VH,
        "out_w": args.out_w, "out_h": args.out_h,
        "trim_start": args.start, "trim_end": args.end,
        "source": args.source,
        "keyframes": kfs,
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {args.out}: {len(kfs)} keyframes")
    for k in kfs:
        print(f"  t={k['t']:6.2f}  cx={k['cx']:.2f}  cy={k['cy']:.2f}  zoom={k['zoom']:.2f}")


if __name__ == "__main__":
    main()
