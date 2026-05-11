# Category 3 — Multi-musician fixed stage

## When this category applies

Multiple musicians on a fixed stage, each at a stable position throughout the song. The musicians don't move much within the frame. The output is a multi-shot edit with cuts between framings (singles, two-shots, group shots).

Examples:
- 3-5 piece band in a club, cave, or bar venue
- Stage performance where each musician is anchored to a position
- Wedding/event band on a low stage

This is the most "professionally-edited-looking" category — it imitates what a TV music producer would do with multi-cam coverage, but from a single fixed source by virtually re-cropping different regions.

## Strategy

Build an EDL (Edit Decision List) — a list of shots, each defined as:
```
(t_start, t_end, cx, cy, zoom_start, zoom_end)
```

The cuts between consecutive shots are HARD CUTS (no transitions) snapped to musical downbeats. Optionally insert 1-2 cross-dissolves at emotional transition points (entry into climax, exit toward conclusion) — but use sparingly.

## Pipeline

1. Inspect source. Identify each musician's fixed position. The easiest way: extract one reference frame (`ffmpeg -ss 30 -i src.mp4 -frames:v 1 ref.png`), run YuNet face detection on it. For musicians whose face the detector misses (e.g. partially obscured by hats or instruments), measure manually.

2. Run `scripts/audio_analyze.py` to get:
   - `tempo` (BPM)
   - `beats` list (timestamps of every detected beat)
   - `vocal_energy` per 0.5s window (find peaks → these are emotionally important moments)

3. Compute downbeats: take every 4th beat as a downbeat candidate (works for 4/4 time signatures, which covers most popular music). For 3/4 (waltz/java), take every 3rd beat. The user can confirm meter if it's ambiguous.

4. Build the EDL:
   - Target 8-12 shots over a 60s reel (~5-7s per shot)
   - Snap each cut to the nearest downbeat
   - Open with an establishing shot (wide-ish 2-shot or full band if it fits)
   - Vary single shots, 2-shots, tight shots — don't repeat the same framing twice in a row
   - Add "reaction shots" of musicians who AREN'T playing the lead — keeps the visual interesting
   - At vocal energy peaks: shot of the vocalist or the duo
   - At instrumental breaks: shot of the lead instrumentalist
   - Reserve tight close-ups (zoom 1.20+) for the emotional peak of the song

5. Choose 0-2 cross-dissolve points. Default: zero. Reasonable: one cross-dissolve into the climax (the largest vocal peak in the second half of the song). More than 2 dissolves in 60s feels muddy.

6. Generate the framing preview contact-sheet before rendering. Show user. Adjust positions and timings if needed.

7. Render with `scripts/render_multishot.py` (a variant of render_chunk.py that handles the EDL with hard cuts + optional dissolves).

8. Concat + mux + fade. Standard.

## Framing math (9:16 from 16:9 source)

The 9:16 crop window has width = `H_source * 9/16` ≈ 0.316 * `W_source` at zoom=1.0. So you can only fit positions whose horizontal extent < 0.32 of source width.

Common positions in a 4-piece band at ~5m wide stage:
- Guitarist: cx ≈ 0.16-0.22
- Bassist/Contrabassist: cx ≈ 0.33-0.36
- Lead (accordion/keys/etc.): cx ≈ 0.50-0.55
- Singer: cx ≈ 0.65-0.72

Two-shot combinations (with zoom=1.0):
- Guitar + Bass: cx_avg ≈ 0.27, span 0.16 — fits
- Bass + Lead: cx_avg ≈ 0.44, span 0.18 — fits
- Lead + Singer: cx_avg ≈ 0.62, span 0.18 — fits

Showing all 4 in one 9:16 frame is usually impossible (their span exceeds 0.32). Either accept 2-shots only, or use letterbox bars to fit a wider crop into 1080x1920.

## EDL pattern that works

For a 4-piece band, 11-shot edit over 60s:

| # | Approx. time | Shot | Zoom | Motion |
|---|--------------|------|------|--------|
| 1 | 0-5s | Lead+Singer 2-shot | 1.0 | Static (establish) |
| 2 | 5-10s | Lead single | 1.05→1.15 | Slow zoom in |
| 3 | 10-16s | Singer single | 1.10 | Static |
| 4 | 16-21s | Guitar+Bass 2-shot | 1.0 | Static (rhythm section) |
| 5 | 21-26s | Guitar single | 1.10→1.04 | Subtle pull-back (reveal) |
| 6 | 26-31s | Lead+Singer 2-shot | 1.0 | Static (back to leads) |
| 7 | 31-37s | Lead tight | 1.30 | Static (emotional peak) |
| 8 | 37-42s | Bass single | 1.10→1.16 | Subtle push (build) |
| 9 | 42-47s | Guitar single | 1.10→1.20 | Zoom in (instrumental break) |
| 10 | 47-52s | Lead+Singer 2-shot | 1.00→1.05 | Subtle push (climax) |
| 11 | 52-59s | Singer tight | 1.25→1.10 | Pull back (settle) |

Adapt this template to the actual musical structure. The key principles:
- Establishing 2-shot first
- Rotate through all musicians early
- Reserve tight shots for emotional peaks
- End on a calmer framing (pull-back)

## Pro editing rules (apply these)

- **Minimum plan duration**: 4 seconds. Faster cuts feel like strobe.
- **No two consecutive zooms in the same direction**. If shot N is zoom-in, shot N+1 should be static or zoom-out.
- **No two consecutive identical framings**. Vary tight/wide/2-shot.
- **Reaction shots break vocal-focus monotony**. Insert a guitarist/bassist shot every 3-4 shots even if they're not soloing.
- **Cuts on downbeats only**. The drummer's downbeat = natural breath point in music.
- **Cross-dissolves are rare and intentional**. Reserve for entry into climax or exit toward conclusion.

## Renderer specifics

`scripts/render_multishot.py` handles:
- Smoothstep-interpolated zoom within each shot
- Hard cuts at shot boundaries
- Cross-dissolves (when configured) via per-frame `cv2.addWeighted` of two simultaneously-computed crops

For a 60s 25fps render, expect ~9-10s per 500-frame chunk on an average machine.

## Lessons learned from "Peggy"

- 4 musicians at cx 0.21, 0.36, 0.53, 0.69 in a 2560x1440 source. Detected via YuNet on a reference frame; manual measure for hatted faces the detector missed.
- 92 BPM → downbeats every ~2.6s; 8-beat phrases every ~5.2s — fit naturally into 5-7s shots.
- Two cross-dissolves of 0.4s placed at 47.32s (entry to climax) and 52.69s (exit to outro) — the rest hard cuts. Felt right; more dissolves would have been mushy.
- For "subtle build" zooms (e.g. bass at 1.10→1.16), keep amplitude ≤ 0.07. Anything bigger reads as a deliberate camera move and competes with the more dramatic zooms elsewhere.
