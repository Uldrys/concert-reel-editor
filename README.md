# concert-reel-editor

A Claude Skill for editing single-song concert footage into 9:16 vertical Reels/Shorts. Built on FFmpeg + OpenCV + librosa with cubic-spline motion and beat-aware multi-shot cutting.

## What it does

You give Claude (via a Claude-powered tool: Claude Code, Cowork, or the Claude Agent SDK) a raw concert video file, a trim range (e.g. `2:35 - 3:34`), and a category hint, and it produces a polished vertical Reel with:

- Smart cropping that follows musicians (no manual keyframing)
- Smooth motion (CubicSpline interpolation, heavy Gaussian smoothing — no jitter)
- Beat-aware cuts on musical downbeats (multi-musician category)
- Fade in/out video + audio
- Optional concert-info end card with logo

The skill is designed for amateur fixed-camera concert footage — the kind of phone or DSLR recording you take from your seat at the venue.

## Three categories

The skill picks one of three workflows based on the source:

1. **Narrative** — musicians move through space (e.g. walking through a vineyard). Continuous follow shot, no cuts.
2. **Static single** — one musician, fixed position. Gentle Ken Burns effect.
3. **Multi-musician** — band on a fixed stage. Multiple cuts on downbeats, single shots and 2-shots interleaved.

Each has its own reference doc in `references/`.

## Repository layout

```
concert-reel-editor/
├── SKILL.md                    Main skill instructions (read by Claude)
├── README.md                   This file
├── LICENSE                     MIT
├── .gitignore                  Excludes depot/, sortie/, *.mp4, etc.
├── scripts/                    Python helpers, called by the skill
│   ├── audio_analyze.py        Beat/vocal/energy detection
│   ├── visual_analyze.py       Face/person detection (YuNet + HOG)
│   ├── build_plan_narrative.py Cat 1 keyframe builder
│   ├── build_plan_static.py    Cat 2 Ken Burns builder
│   ├── build_edl_multishot.py  Cat 3 EDL builder
│   ├── render_chunk.py         Chunked frame renderer
│   ├── render_multishot.py     Multi-shot renderer with cross-dissolves
│   └── make_endcard.py         End-card image generator
├── references/                 Per-category guidance (loaded as needed)
│   ├── category-1-narrative.md
│   ├── category-2-static.md
│   └── category-3-multishot.md
├── examples/                   Concrete examples from real cases
│   ├── chez_gegene_keyframes.json
│   ├── montmartre_plan.py
│   └── peggy_edl.py
├── depot/                      [gitignored] Drop source videos here
└── sortie/                     [gitignored] Final outputs land here
```

## Installation

### Claude Code

```bash
git clone https://github.com/<your-username>/concert-reel-editor.git ~/.claude/skills/concert-reel-editor
```

Then in your conversation: tell Claude `please use the concert-reel-editor skill` for the relevant request.

### Cowork

Settings → Plugins / Skills → install from URL or paste the GitHub URL of the repo.

### Claude Agent SDK / Anthropic API

Read the file structure, load `SKILL.md` as a system prompt component, and expose the scripts. See [Anthropic Skills docs](https://docs.claude.com).

## Dependencies (runtime)

Two ways to set up the toolchain. **Docker is the recommended path** — one command, no host pollution, reproducible.

### Option A — Docker (recommended)

```bash
docker build -t concert-reel-editor .
./scripts/cre python3 scripts/audio_analyze.py depot/song.mp4 0 30 \
    --out work/song/audio.json
```

`scripts/cre` is a thin wrapper that runs any command inside the image, mounts the current directory at `/work`, and uses your host UID/GID so output files aren't owned by root. Run `./scripts/cre bash` for an interactive shell. The image bundles ffmpeg (with libx264 + AAC), Python 3.11, librosa, scipy, opencv-python-headless, pillow, soundfile, numpy, and DejaVu fonts.

### Option B — Native install

If you'd rather run on your host directly:

- Python 3.10+
- `ffmpeg` + `ffprobe` on PATH (with libx264, AAC, libass)
- `pip install opencv-python-headless librosa scipy pillow soundfile`

For face detection, the scripts auto-download the YuNet ONNX model on first run (~232 KB) — works the same under Docker or native (the model is cached in the mounted working directory).

## Quick start (manual run, no Claude)

You can run the pipeline by hand without Claude, treating the scripts as standalone CLI tools. See each script's docstring. Roughly:

1. Drop source in `depot/your-song.mp4`
2. Run `python scripts/audio_analyze.py depot/your-song.mp4 155 214 > audio.json`
3. Pick a category template from `examples/` and adapt it
4. Run `python scripts/render_chunk.py <start_frame> <end_frame> chunk1.mkv`
5. Concat + mux with ffmpeg

But honestly, the value of the skill is that Claude handles the orchestration, picks reasonable defaults, and iterates with you on the framing. The scripts are the load-bearing components — the skill is the brain.

## Origin

Built iteratively by Simon ([@simon2uldry](https://github.com/?)) and Claude (Anthropic) while editing concert footage of his father's band, SIBB. The 3 categories emerged from real videos:

- **Cat 1**: "Chez Gégène 2" — duo accordion+singer walking through a vineyard
- **Cat 2**: "Montmartre" — solo accordionist against a wall
- **Cat 3**: "Peggy" — 4-piece band on a cave-bar stage

The skill is now generic and can be applied to any concert footage fitting these patterns.

## License

MIT — see [LICENSE](LICENSE).
