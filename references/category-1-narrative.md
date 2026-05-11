# Category 1 — Narrative (movement through space)

## When this category applies

Musicians physically move through the frame during the song: walking, processing, approaching the camera, etc. The source camera is fixed (or near-fixed) and you see the action play out across the wide shot. There is no cutting in the output — the whole clip is a single continuous shot that follows the action.

Concrete examples:
- Duo walking through a vineyard while playing
- Musicians entering and exiting frame
- A long take where the band moves around the venue

If you find yourself wanting to cut between subjects, you're in Category 3 territory, not here.

## Strategy

Two phases of motion in the output:

1. **Auto-tracked phase**: when subjects are detected in frame, the crop follows them with a soft, continuous pan. Use face/person detections every 0.5s, build a `(cx, cy, zoom)` per-timestep array, smooth heavily, interpolate with CubicSpline.

2. **Manual override phase**: there will almost always be a moment that needs to be hand-tuned — the musicians enter from a specific side, exit through another, or the auto-tracker briefly fails. Identify these manually and override the keyframes for that window.

## Pipeline

1. Extract audio for the trim range.
2. Run `scripts/audio_analyze.py` to get vocal/instrumental energy windows. Use this only to modulate zoom slightly (+0.05 at peaks) — not for cuts.
3. Run `scripts/visual_analyze.py` to get face/person detections per 0.5s sample.
4. Run `scripts/build_plan_narrative.py` which:
   - Computes per-window cx/cy from detections
   - Fills detection gaps with gap-aware drift toward neutral
   - Computes per-window zoom from detection sizes (closer subjects → tighter zoom)
   - Applies any user-specified manual overrides
   - Applies Gaussian smoothing (σ=6-12)
   - Subsamples to ~1.5s keyframes
   - Outputs `keyframes.json`
5. Generate preview contact-sheet, show user.
6. Render chunks with `scripts/render_chunk.py` (it reads keyframes.json and uses CubicSpline interp).
7. Concat + mux + fade. Standard.

## Key parameters

- **Smoothing sigma**: 6-12 samples (each sample = 0.5s, so 3-6s of smoothing). Higher = more fluid but loses tracking accuracy. If the user reports "saccades", increase σ.
- **Keyframe spacing after subsampling**: ~1.5s. Combined with CubicSpline this gives genuinely fluid motion.
- **Override window**: when user describes a specific behavior the auto-tracker can't infer ("they walk in from the right at t=58s"), hardcode that. Place override BEFORE the Gaussian smoothing pass so the pre-override drift blends in naturally. For a hold-then-drift pattern (e.g. camera holds on right until subjects appear, then drifts left), apply the override AFTER smoothing on the core hold region.
- **Zoom range**: stay [1.0, 1.20]. Tight close-ups motivated by subject size — when face width in frame > 0.07, no zoom needed (subject already big in crop).

## When subjects vanish from frame

Detection will simply return no faces/persons for those windows. The plan builder fills these with a drift-to-center strategy: stay anchored at the last known cx for ~2s, then linearly drift toward cx=0.5, completing the drift over ~4s. This prevents the camera from staying locked to an empty side of the frame when subjects are gone for a long time.

If a drift-to-center isn't what you want (e.g., the user wants the camera to ANTICIPATE re-entry from the same side), use a manual override.

## Renderer specifics

Use `scripts/render_chunk.py` which reads `keyframes.json`. The renderer:
- Computes `(cx, cy, zoom)` at every output frame by CubicSpline-interpolating the keyframes
- Clamps zoom ≥ 1.0
- Clamps `(cx, cy)` so the crop window stays inside the source
- Crops the source frame, resizes with `INTER_LINEAR`, pipes to FFmpeg (libx264, ultrafast preset)

Chunk size: 500 frames at 25fps = 20 seconds. Fits within the 45s sandbox timeout.

## Lessons learned from "Chez Gégène 2"

- Smoothstep between keyframes has C¹ continuity but NOT C² — acceleration jumps at each keyframe. With dense 0.5s keyframes this produces perceptible micro-saccades. CubicSpline fixes this completely.
- Heavy Gaussian smoothing (σ=12) on the underlying signal can fight against manual overrides — apply overrides AFTER smoothing on the override's core region, then do a light re-smoothing (σ=3) at the boundaries to avoid hard steps.
- When subjects exit one side of the frame and you don't want a "left → right then right → left" wobble before they re-enter: hold the camera on the re-entry side for the ENTIRE absence period. Don't try to track gracefully back to center if you know subjects will return.
