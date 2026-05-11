"""
Audio analysis for concert footage editing.

Extracts the trim range from the source video, then analyzes the audio for:
- Tempo (BPM)
- Beat positions
- Onset positions (strong musical accents)
- Per-window vocal energy (separated via REPET-like NN-filter)
- Per-window instrumental energy

Outputs a JSON document used by the plan builders.

Usage:
    python audio_analyze.py <source.mp4> <start_seconds> <end_seconds> [--out audio_analysis.json]

Example:
    python audio_analyze.py depot/peggy.mp4 155 214 --out work/audio.json
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import librosa
import numpy as np


WINDOW_SEC = 0.5  # aggregation window in seconds


def extract_audio(src, start, duration, sr=22050):
    """Extract a mono WAV of [start, start+duration] from the source."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-ss", str(start), "-t", str(duration),
         "-i", src, "-vn", "-ac", "1", "-ar", str(sr), tmp],
        check=True,
    )
    return tmp


def analyze(audio_path, hop_length=512):
    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    duration = len(y) / sr

    # Beats
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length)
    tempo_val = float(tempo) if np.isscalar(tempo) else float(np.asarray(tempo).item())

    # Onsets
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    onsets = librosa.onset.onset_detect(
        onset_envelope=onset_env, sr=sr, hop_length=hop_length,
        units="time", backtrack=False,
    )

    # Vocal separation via REPET-style nearest-neighbor filter
    S_full, phase = librosa.magphase(librosa.stft(y, hop_length=hop_length))
    S_filter = librosa.decompose.nn_filter(
        S_full, aggregate=np.median, metric="cosine",
        width=int(librosa.time_to_frames(2, sr=sr)),
    )
    S_filter = np.minimum(S_full, S_filter)
    mask_v = librosa.util.softmask(S_full - S_filter, 10 * S_filter, power=2)
    mask_i = librosa.util.softmask(S_filter, 2 * (S_full - S_filter), power=2)
    S_vocal = mask_v * S_full
    S_inst = mask_i * S_full

    vocal_e = S_vocal.mean(axis=0)
    inst_e = S_inst.mean(axis=0)
    times = librosa.frames_to_time(np.arange(len(vocal_e)), sr=sr, hop_length=hop_length)

    # Aggregate per WINDOW_SEC
    windows = []
    n_w = int(np.ceil(duration / WINDOW_SEC))
    for i in range(n_w):
        t_s = i * WINDOW_SEC
        t_e = min((i + 1) * WINDOW_SEC, duration)
        fs = np.searchsorted(times, t_s)
        fe = max(fs + 1, np.searchsorted(times, t_e))
        fe = min(fe, len(times))
        ve = float(vocal_e[fs:fe].mean()) if fe > fs else 0
        ie = float(inst_e[fs:fe].mean()) if fe > fs else 0
        windows.append({"t": round(t_s, 2), "vocal_e": ve, "inst_e": ie})

    # Normalize
    v_max = max(w["vocal_e"] for w in windows) or 1
    i_max = max(w["inst_e"] for w in windows) or 1
    for w in windows:
        w["vocal_n"] = round(w["vocal_e"] / v_max, 3)
        w["inst_n"] = round(w["inst_e"] / i_max, 3)
        w["vocal_e"] = round(w["vocal_e"], 4)
        w["inst_e"] = round(w["inst_e"], 4)

    return {
        "duration": duration,
        "tempo": tempo_val,
        "beats": [round(float(b), 3) for b in beat_times],
        "onsets": [round(float(o), 3) for o in onsets],
        "windows": windows,
        "window_sec": WINDOW_SEC,
    }


def downbeats(beats, meter=4):
    """Heuristically extract downbeats by taking every Nth beat. Use meter=3 for waltz/java."""
    if not beats:
        return []
    return beats[::meter]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("source", help="Source video file")
    ap.add_argument("start", type=float, help="Trim start in seconds")
    ap.add_argument("end", type=float, help="Trim end in seconds")
    ap.add_argument("--out", default="audio_analysis.json", help="Output JSON path")
    ap.add_argument("--meter", type=int, default=4, help="Time signature numerator (4 for 4/4, 3 for 3/4)")
    args = ap.parse_args()

    duration = args.end - args.start
    if duration <= 0:
        print("End must be after start", file=sys.stderr)
        sys.exit(1)

    print(f"Extracting audio from {args.source} ({args.start:.1f}s + {duration:.1f}s)...", flush=True)
    audio_path = extract_audio(args.source, args.start, duration)
    try:
        print("Analyzing...", flush=True)
        result = analyze(audio_path)
        result["downbeats"] = downbeats(result["beats"], meter=args.meter)
        result["meta"] = {
            "source": os.path.abspath(args.source),
            "trim_start": args.start,
            "trim_end": args.end,
            "meter": args.meter,
        }
        with open(args.out, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Wrote {args.out}", flush=True)
        print(f"  Duration: {result['duration']:.2f}s")
        print(f"  Tempo: {result['tempo']:.1f} BPM")
        print(f"  Beats: {len(result['beats'])} ({len(result['downbeats'])} downbeats)")
        print(f"  Onsets: {len(result['onsets'])}")
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


if __name__ == "__main__":
    main()
