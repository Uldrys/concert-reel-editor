# Category 2 — Static single musician

## When this category applies

One musician, fixed position in frame, camera doesn't move. The simplest category — most of the work is making it not look boring.

Examples:
- Solo accordionist standing against a wall
- Vocalist behind a mic stand
- Pianist at an instrument
- Anyone playing relatively still in a fixed spot

## Strategy

Gentle Ken Burns. The Ken Burns effect (named after the documentary filmmaker) is a slow zoom + small pan that makes static images/footage feel alive without being distracting. Here we apply it to a fixed-position video.

Two motions to consider:
1. **Slow zoom** over the entire duration. Typically start wide (zoom=1.0), tighten progressively (zoom=1.10-1.15) for the emotional middle, optionally pull back slightly at the end.
2. **Small vertical pan** to keep the face centered as the zoom tightens. With zoom going from 1.0 to 1.10, the cy can drift from 0.50 to ~0.42 to favor the upper body when tighter.

Optional but recommended:
3. **End card** with concert info on black background, 4-6 seconds, fade in from the main video's fade out. See `scripts/make_endcard.py`.

## Pipeline

1. Inspect source. Check for pillarboxing (vertical content in 16:9 with black bars) — common with phone footage. If pillarboxed, identify the active content region.
2. Identify the musician's approximate horizontal position. Usually centered (cx=0.5), but check.
3. Hand-write 5-7 keyframes for the duration: `(t, cx, cy, zoom)`. See `scripts/build_plan_static.py` for the template.
4. Render with `scripts/render_chunk.py` using CubicSpline interpolation across the keyframes.
5. If user wants end card: generate `end_card.png` with `scripts/make_endcard.py`, turn into 5s video with fade-in, concat after main video.
6. Final compression + fade in/out + mux audio.

## Key parameters

- **Zoom range for Ken Burns**: 1.00 to 1.10-1.15. Going past 1.15 starts feeling like a "real" zoom instead of subtle drift.
- **Pan range for cy**: ±0.05-0.08 from 0.50. Very small.
- **Number of keyframes**: 5-7. More creates micro-oscillation; fewer makes the motion feel mechanical.
- **End card duration**: 5 seconds works well. Less = readers can't process the info; more = boring.
- **End card fade**: 0.6-0.8s fade-in only (the main video's fade-out is the transition).

## Source pillarboxing detection

Many phone-recorded videos are vertical content placed inside a 16:9 container with black bars on the sides. Detect this before cropping:

```python
import cv2, numpy as np
img = cv2.imread("frame.png")
H, W = img.shape[:2]
mid = img[H//2, :, :].mean(axis=1)
non_black = np.where(mid > 30)[0]
content_left, content_right = non_black[0], non_black[-1]
```

If `content_right - content_left < 0.7 * W`, the source is pillarboxed. Adjust crop accordingly — your 9:16 crop should pull from inside the content region, not from the black bars.

## End card design (when used)

The end-card composition that worked well:
- Black background
- Logo in upper third (~60% of width, centered)
- Thin gold divider line below the logo
- "Concert" label in gold/accent color
- Title (e.g. venue name) in bold white, larger font
- Date in slightly smaller font
- Address (1-2 lines) in slightly dimmer color

See `scripts/make_endcard.py` for the working PIL implementation.

## Lessons learned from "Montmartre"

- Source was 1920x1080 phone footage pillarboxed to ~960px-wide content. Cropping a 608x1080 vertical slice from the middle worked fine — no black bars in the output.
- Zoom 1.0 → 1.10 over 30 seconds is enough motion. Anything more felt forced for a single musician.
- The end card concatenation requires both segments to have audio streams (even if the end card's is silent) — use `ffmpeg -f lavfi -i anullsrc` to generate silent audio for the end card.
- For a clean transition into the end card, fade out the main video over the last 1.3s, then fade in the end card from black over 0.6s.
