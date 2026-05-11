"""
Category 3 (Multi-musician) EDL skeleton builder.

This script is more of a helper than an automatic tool — the EDL really needs
human input on who's at what cx in the source. It snaps cuts to detected
downbeats so the rhythm is right, but the framing positions and per-shot
intentions are domain-specific to each video.

Usage:
    # Generate a template EDL based on detected downbeats and musician positions
    python build_edl_multishot.py --audio audio.json --visual ref.json \\
        --musicians "guitar=0.21,bass=0.36,accord=0.53,singer=0.69" \\
        --out edl.json

The output is a JSON EDL with shots placed every ~8 downbeats. You should edit
the JSON to:
- Adjust which musician/2-shot is featured per slot
- Add zoom motion within shots
- Mark cross-dissolves if desired (max 2 in a 60s reel)

See examples/peggy_edl.py for a hand-crafted EDL after this skeleton.
"""
import argparse
import json


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--audio", required=True, help="audio_analysis.json")
    ap.add_argument("--musicians", required=True,
                    help="name=cx pairs separated by commas, e.g. 'guitar=0.21,bass=0.36'")
    ap.add_argument("--shot-beats", type=int, default=8,
                    help="Beats per shot (8 = 2 measures at 4/4)")
    ap.add_argument("--out", default="edl.json")
    ap.add_argument("--out-w", type=int, default=1080)
    ap.add_argument("--out-h", type=int, default=1920)
    args = ap.parse_args()

    with open(args.audio) as f:
        audio = json.load(f)

    # Parse musicians
    musicians = {}
    for pair in args.musicians.split(","):
        name, cx = pair.split("=")
        musicians[name.strip()] = float(cx)

    # Get downbeat-aligned cut times
    beats = audio["beats"]
    duration = audio["duration"]
    cut_times = beats[::args.shot_beats]
    if cut_times[-1] < duration - 1:
        cut_times.append(duration)

    # Build skeleton shots: rotate through musicians
    names = list(musicians.keys())
    shots = []
    for i in range(len(cut_times) - 1):
        t_start = cut_times[i]
        t_end = cut_times[i + 1]
        # Default: pick the i-th musician cyclically; user will edit
        primary = names[i % len(names)]
        shots.append({
            "shot_id": i + 1,
            "t_start": round(t_start, 2),
            "t_end": round(t_end, 2),
            "focus": primary,
            "cx": musicians[primary],
            "cy": 0.50,
            "zoom_start": 1.10,
            "zoom_end": 1.10,
            "notes": "TODO: review framing and motion",
        })

    edl = {
        "out_w": args.out_w, "out_h": args.out_h,
        "musicians": musicians,
        "tempo": audio["tempo"],
        "trim_start": audio["meta"]["trim_start"],
        "trim_end": audio["meta"]["trim_end"],
        "source": audio["meta"]["source"],
        "shots": shots,
        "dissolves": [],  # add [(t_start, t_end), ...] for 0.4s cross-dissolves
    }
    with open(args.out, "w") as f:
        json.dump(edl, f, indent=2)
    print(f"Wrote {args.out}: {len(shots)} skeleton shots")
    print("EDIT THIS FILE before rendering. Adjust focus/cx/cy/zoom per shot.")


if __name__ == "__main__":
    main()
