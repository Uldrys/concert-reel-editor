---
name: concert-reel-editor
description: Edit a single song video from a live concert into a vertical Reel/Short suitable for Instagram, TikTok or YouTube Shorts. Use this skill whenever the user wants to turn raw concert footage (musician solo, narrative-style band shot, or multi-musician fixed-stage shot) into a polished short-form video. Triggers include phrases like "make a Reel from this concert video", "turn this song into a Short", "vertical edit of this band performance", "clip this song with smart cropping", "concert highlight reel". Also use when the user references a video file by name and a time range and asks for a 9:16 output, or mentions Reels/TikTok/Shorts in a live-music context. The skill handles smart cropping with smooth motion, beat-aware multi-shot cutting, end cards with concert info, and the FFmpeg/OpenCV plumbing — Claude doesn't need to invent a pipeline from scratch.
---

# Concert Reel Editor

Turn raw 16:9 concert footage of a single song into a polished 9:16 vertical Reel (~30-90 seconds) with intelligent framing, gentle motion, and a final end card when needed. Built for live music videos where the source is wide-angle and you want to follow the action without sloppy hand-edits.

## When to invoke this skill

Trigger whenever the user wants to turn raw concert footage of a single song into a vertical short-form video. Don't worry about whether the source is "good enough" — the skill assumes the source is a fixed-camera or near-fixed-camera live recording, which covers most amateur concert capture.

If the source is professional multi-angle footage with existing cuts, this skill is the wrong tool — that needs a different workflow.

## The decision tree (pick your category)

The first thing to do is determine which of three categories the video falls into. Ask the user if it's not obvious from the source. The three categories drive completely different technical strategies:

**Category 1 — Narrative / movement-through-space**
The musicians physically move through the frame during the song. Example: walking through a vineyard while playing, approaching the camera then walking away, processing through a corridor. There is NO cutting. The output is a single continuous shot that follows the action with smooth panning and gentle zooming.
→ Read `references/category-1-narrative.md`.

**Category 2 — Single musician, near-static**
One musician, fixed position, the camera doesn't move much in the source. Example: solo accordionist standing in front of a wall. The output keeps the musician centered with a gentle Ken Burns effect (slow zoom + tiny vertical pan to follow the face). Optional concert-info end card on black.
→ Read `references/category-2-static.md`.

**Category 3 — Multi-musician fixed stage**
Several musicians on a stage, each at a fixed position, no significant movement. Example: 3-5 piece band in a club or cave venue. The output is a multi-shot edit with hard cuts on musical downbeats, single shots and 2-shots interleaved with brief zoom-in/zoom-out motivated by emotional moments. Optional cross-dissolves at major transitions only.
→ Read `references/category-3-multishot.md`.

If unsure, ask the user. Don't auto-assume.

## Toolchain

All scripts assume ffmpeg + Python deps (librosa, opencv-python-headless, scipy, pillow, soundfile, numpy) are available. The repo ships a `Dockerfile` plus a wrapper at `scripts/cre` that runs any command inside the image with the working directory mounted at `/work` and the host UID/GID. **Prefer the wrapper** unless the user has already set up their host natively:

```
docker build -t concert-reel-editor .        # one-time
./scripts/cre python3 scripts/audio_analyze.py depot/song.mp4 0 30 --out work/song/audio.json
./scripts/cre ffmpeg -i depot/song.mp4 ...
./scripts/cre bash                            # interactive shell
```

If the wrapper isn't available (e.g. older checkout), check whether ffmpeg + python deps are on the host before falling back to inline commands. Do not invoke ffmpeg directly from the host if it's not installed — build the image instead.

## Common pipeline (every category)

Every output goes through these stages. The "build plan" step is category-specific (see each reference). Everything else is shared.

1. **Inspect source**: get duration, resolution, frame rate, codec. Confirm the trim window the user gave makes sense (within source length).

2. **Extract audio** of the trim range for analysis. Run `scripts/audio_analyze.py` to detect beats (tempo, downbeats), vocal energy windows, and overall energy structure. This is essential for category 3 (cuts on downbeats) and useful for category 1 (modulate zoom on vocal peaks).

3. **Analyze visuals**: run `scripts/visual_analyze.py` on the trim range — this returns per-second face detections (YuNet) and person detections (HOG). For category 3, the positions are fixed across the whole video so a single reference frame suffices. For categories 1-2 you need the full timeline.

4. **Build the plan** (category-specific):
   - Category 1: continuous keyframes (cx, cy, zoom) every 0.5-1.5s with cubic spline interpolation. See `scripts/build_plan_narrative.py`.
   - Category 2: hardcoded Ken Burns keyframes — 5-7 anchors over the duration. See `scripts/build_plan_static.py`.
   - Category 3: EDL with hard cuts on downbeats, each shot defined as `(t_start, t_end, cx, cy, zoom_start, zoom_end)`. Optional cross-dissolve list. See `scripts/build_edl_multishot.py`.

5. **Preview the framings first**. ALWAYS generate a contact-sheet preview of the proposed framings before launching the full render. Show it to the user. Get sign-off, especially on subject positions and zoom amplitudes. This saves time vs. re-rendering everything after a "the cropping is wrong" comment.

6. **Render in chunks**. The chunked renderer (`scripts/render_chunk.py`) outputs MKV files. Split the work into 500-frame chunks (~20 seconds at 25 fps) — anything larger risks exceeding sandbox timeouts. Render chunks sequentially.

7. **Concat + mux + fade + compression**: single FFmpeg pass that concatenates MKV chunks, muxes with audio from the source (trimmed `-ss N -t M`), applies video and audio fade-in/fade-out, and re-encodes to H.264 (`-preset veryfast -crf 24` is the sweet spot — fast enough to fit the timeout budget, small enough for upload).

8. **Optional end card** (category 2 typically, others on request). See `scripts/make_endcard.py` — generates a 1080x1920 PNG with logo + text, then a 5-second video clip with audio silence, concatenated after the main video.

9. **Verify**: extract 6-12 thumbnails from the final video at key timestamps, compose into a contact sheet, show the user. Don't claim success without this verification.

## SIBB-flavored style rules (default; can be overridden)

These were the conventions that emerged from the three reference cases. They're the default — adjust if the user asks for something different.

- **9:16 vertical, 1080x1920** unless asked otherwise. Source is typically 1920x1080 or 2560x1440 16:9.
- **Fade in 1.0-1.5s at the start, fade out 1.3-1.5s at the end**. Audio + video synced. The fade-out can be slightly longer than the fade-in to give breathing room before a possible end card.
- **Zoom values stay in [1.0, 1.30]**. Below 1.0 is impossible (would require source wider than 16:9). Above 1.30 starts looking pixel-soft on the upscale. Tight close-ups: 1.20-1.30. Mid-shots: 1.10-1.15. Wide: 1.00-1.05.
- **No motion is fine, sometimes preferable.** A static plan is a deliberate choice that lets the music breathe. Don't add motion just because you can.
- **Cuts on downbeats only** for category 3. Snap each cut to the nearest detected downbeat from `librosa.beat.beat_track`.
- **Minimum plan duration ~4s**, ideally 5-7s for medium-tempo French chanson (~90 BPM). Faster music (>120 BPM) can tolerate ~3s plans.
- **CubicSpline interpolation** for category 1 (continuous motion). Smoothstep is fine for short transitions within a fixed shot in category 3.
- **Heavy Gaussian smoothing (σ=6-12 samples)** on the cx/cy/zoom timeline for category 1 — eliminates micro-saccades from the underlying detection noise.
- **Cross-dissolves are rare**: maximum 2 in a 60-second multi-shot edit, only at emotionally-justified transitions (entry into climax, exit toward conclusion). Default to hard cuts.

## Optional: subtitle (.srt) sidecar

If the user provides lyrics — either as a text file dropped next to the source in `depot/`, or pasted directly in the prompt — produce a `.srt` sidecar file alongside the final Reel. **Burn-in / on-video integration is explicitly out of scope.** The `.srt` is delivered as a standalone file the user will attach later themselves (YouTube upload, CapCut import, etc.). Auto-aligned burn-in was tried in this codebase and abandoned (2026-05-12) — REPET-based vocal energy separation is too unreliable on accordion-heavy chanson to produce correctly-timed cues. Until a real source-separation pipeline is added (Demucs etc.), do not re-attempt unless the user explicitly asks.

**Input detection.** Look for `<source-stem>.txt` or `<source-stem>.lyrics.txt` in the same folder as the source video. If absent and the user pasted lyrics in the prompt, save them to `work/<source-stem>.lyrics.txt` before processing. Accept free-form text — paragraphs, single block, or pre-broken lines. Don't require any pre-segmentation from the user.

**Extracted-lyrics confirmation gate (mandatory).** When the lyrics come from anything *other than* direct typed/pasted text — image OCR, screenshot of a notebook, photo of handwritten paper, audio attachment, video frame, scanned PDF, etc. — you MUST display your full transcription in chat and wait for explicit user confirmation **before** generating the SRT or saving the lyrics file. Flag every word you're unsure about (handwriting ambiguity, illegible passages, marginal annotations that may or may not be part of the song). A bad transcription that slips into the .srt is hard to spot, and if it's already burned into a render the only fix is to re-encode from scratch. This gate is non-negotiable — the same draft-and-sign-off principle that applies to the SRT itself applies one level upstream.

**Segmentation rules.**
- **Maximum 3-4 syllables per cue line.** Count syllables by collapsing adjacent vowels into one group (French heuristic — accented variants count). A rough count is fine; the user reviews the draft.
- **Preserve phrasing logic:** never split inside a word; prefer breaks at natural pauses (commas, periods, end of grammatical clauses, conjunctions like "et / mais / puis").
- If a single word exceeds 4 syllables it gets its own cue (don't try to split a word).
- Respect line breaks already present in the input as soft phrase hints — if the user pre-segmented, that's a signal worth honoring.

**Timing.** Use the per-0.5s vocal-energy windows from `audio_analyze.py` (the `windows[*].vocal_n` field, already normalized to [0, 1]). Identify vocal-active phrases as contiguous runs of windows with `vocal_n` ≥ threshold (default 0.25 — tune per song if needed). Allocate cues across phrases proportionally to total syllable count; within each phrase, distribute cues by syllable count too. Leave instrumental gaps (intros, solos, outros) blank.

**Draft and sign-off.** Before writing anything to `sortie/`, display the proposed `.srt` in the chat with timecodes and ask the user to confirm or correct. Only after sign-off, write the final file to `sortie/<source-stem> - Reel.srt`. This round-trip is mandatory — the user explicitly asked for it.

**Helper.** `scripts/build_srt.py` wraps tokenization, syllable counting, cue packing, vocal-phrase detection, and proportional timing. Inputs: the `audio_analysis.json` already produced by step 2 of the common pipeline, plus the lyrics text file. Output to stdout or to `--out path.srt`.

## Output file naming

Drop final videos in the user's chosen output folder (default `sortie/` if working inside this repo's depot/sortie workflow). Name format: `<source-stem> - Reel.mp4`. Keep intermediate `_v2`/`_v3` files only during iteration; rename to the final name and remove drafts once the user signs off.

If a lyrics sidecar was produced, write it next to the video as `<source-stem> - Reel.srt`.

## When something doesn't fit

- **Trim range outside source duration** → ask the user to verify the timecode. Don't silently clip.
- **Multiple musicians span more than 32% of source width** (category 3) → you can't show all of them at 9:16 with zoom=1.0. Options: (a) use 2-shots only, no "full band" wide; (b) add letterbox bars (top+bottom black). Discuss with user.
- **Whisper-based subtitles**: don't try to auto-transcribe singing voice over instrumentation — Whisper struggles and the timing is unreliable. If the user wants subtitles, they provide the lyrics; see the dedicated "Optional: subtitle (.srt) sidecar" section above. No on-video burn-in regardless of source.
- **Audio drift after concat**: if `ffmpeg concat` produces audio sync issues, switch from the `concat` demuxer to `concat` filter (re-encode all video).

## Inputs the user typically gives

- Source video file path
- Trim window (in MM:SS-MM:SS format usually)
- Category hint (sometimes — you may need to ask)
- Concert info for end card: venue name, date, address (category 2 typically)
- Logo path (PNG with transparency ideal)
- **Lyrics (optional)** for a `.srt` sidecar — as a `.txt` file in the same folder as the source, or pasted in the prompt. See the dedicated section above.

Confirm trim window matches what you'd compute from the source duration. Source can have a few seconds of leading silence/handling noise that the trim should skip.

## Working folders convention

If the user is using this repo as a working hub:
- `depot/` — source videos go here. Gitignored.
- `sortie/` — output Reels go here. Gitignored.
- `assets/` — logo, fonts, end-card templates. Versioned.

Outside that convention, just respect the paths the user gives.
