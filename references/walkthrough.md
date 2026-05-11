# End-to-end walkthrough

This file shows the concrete shell commands a Claude-powered tool would run from
zero to a finished Reel, for each of the 3 categories. Use these as a template
when working on a new video.

Assumes: the working directory is the repo root, the source video is in `depot/`,
ffmpeg is on PATH, and `pip install opencv-python librosa scipy pillow soundfile`
has been done once.

## Common preamble (every category)

```bash
SOURCE="depot/your_song.mp4"
START=155            # trim start in seconds
END=214              # trim end in seconds
DUR=$(echo "$END - $START" | bc)
WORK="work/$(basename "$SOURCE" .mp4)"
mkdir -p "$WORK"

# Audio analysis
python scripts/audio_analyze.py "$SOURCE" $START $END --out "$WORK/audio.json"
```

## Category 1 (Narrative)

```bash
# Visual analysis: full timeline, 2 fps sampling
python scripts/visual_analyze.py "$SOURCE" $START $END --out "$WORK/visual.json"

# Build the plan with default smoothing
python scripts/build_plan_narrative.py \
    --audio "$WORK/audio.json" \
    --visual "$WORK/visual.json" \
    --out "$WORK/keyframes.json"

# Optional: with a manual override file (see examples/chez_gegene_overrides.py)
python scripts/build_plan_narrative.py \
    --audio "$WORK/audio.json" --visual "$WORK/visual.json" \
    --override examples/chez_gegene_overrides.py \
    --out "$WORK/keyframes.json"

# Render in chunks of 500 frames
FPS=25
START_F=$(echo "$START * $FPS" | bc)
END_F=$(echo "$END * $FPS" | bc)
i=1
f=$START_F
while [ $f -lt $END_F ]; do
    nf=$(( f + 500 ))
    [ $nf -gt $END_F ] && nf=$END_F
    python scripts/render_chunk.py \
        --keyframes "$WORK/keyframes.json" \
        --start-frame $f --end-frame $nf \
        --out "$WORK/chunk${i}.mkv"
    f=$nf
    i=$(( i + 1 ))
done

# Concat list
ls "$WORK"/chunk*.mkv | sed "s/^/file '/" | sed "s/$/'/" > "$WORK/concat.txt"

# Final mux + fade + compress
ffmpeg -y -f concat -safe 0 -i "$WORK/concat.txt" \
    -ss $START -i "$SOURCE" \
    -map 0:v -map 1:a \
    -vf "fade=t=in:st=0:d=1.5,fade=t=out:st=$(echo $DUR - 1.5 | bc):d=1.5" \
    -af "afade=t=in:st=0:d=1.5,afade=t=out:st=$(echo $DUR - 1.5 | bc):d=1.5" \
    -c:v libx264 -preset veryfast -crf 24 -pix_fmt yuv420p \
    -movflags +faststart -c:a aac -b:a 128k -t $DUR \
    "sortie/$(basename "$SOURCE" .mp4) - Reel.mp4"
```

## Category 2 (Static single musician)

```bash
# No visual analysis needed - just build the Ken Burns plan
# Assume musician is centered (cx=0.5). Adjust if not.
python scripts/build_plan_static.py \
    --source "$SOURCE" --start $START --end $END \
    --cx 0.5 --out "$WORK/keyframes.json"

# Render (single chunk usually suffices for short clips, but chunk if >25s)
python scripts/render_chunk.py \
    --keyframes "$WORK/keyframes.json" \
    --start-frame $START_F --end-frame $END_F \
    --out "$WORK/main_silent.mkv"

# Optional end card
python scripts/make_endcard.py \
    --logo assets/logo.png \
    --title "Jardin des Capucins" \
    --date "Samedi 23 mai 2026 — 11:00" \
    --addr1 "Rue du Marché 2" --addr2 "1630 Bulle (CH)" \
    --out "$WORK/end_card.png"

ffmpeg -y -loop 1 -framerate 25 -i "$WORK/end_card.png" \
    -f lavfi -i "anullsrc=channel_layout=stereo:sample_rate=44100" \
    -t 5 -vf "fade=t=in:st=0:d=0.6" \
    -c:v libx264 -preset veryfast -crf 22 -pix_fmt yuv420p \
    -c:a aac -b:a 128k -shortest "$WORK/end_card.mp4"

# Main video with fade + audio
ffmpeg -y -i "$WORK/main_silent.mkv" \
    -ss $START -i "$SOURCE" \
    -map 0:v -map 1:a \
    -vf "fade=t=in:st=0:d=1.0,fade=t=out:st=$(echo $DUR - 1.3 | bc):d=1.3" \
    -af "afade=t=in:st=0:d=1.0,afade=t=out:st=$(echo $DUR - 1.3 | bc):d=1.3" \
    -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p \
    -c:a aac -b:a 128k "$WORK/main.mp4"

# Concat main + end card
cat > "$WORK/concat_final.txt" << EOF
file 'main.mp4'
file 'end_card.mp4'
EOF
ffmpeg -y -f concat -safe 0 -i "$WORK/concat_final.txt" \
    -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p \
    -movflags +faststart -c:a aac -b:a 128k \
    "sortie/$(basename "$SOURCE" .mp4) - Reel.mp4"
```

## Category 3 (Multi-musician)

```bash
# Visual analysis: reference frame only (positions are fixed)
python scripts/visual_analyze.py "$SOURCE" $START $END --reference \
    --out "$WORK/visual_ref.json"

# Build skeleton EDL (then EDIT IT manually — adjust focus per shot)
python scripts/build_edl_multishot.py \
    --audio "$WORK/audio.json" \
    --musicians "guitar=0.21,bass=0.36,accord=0.53,singer=0.69" \
    --out "$WORK/edl.json"

# Now manually edit $WORK/edl.json to set the right focus + zoom per shot.
# See examples/peggy_edl.json for a finished example.

# Render in chunks using the multi-shot renderer
i=1; f=$START_F
while [ $f -lt $END_F ]; do
    nf=$(( f + 500 ))
    [ $nf -gt $END_F ] && nf=$END_F
    python scripts/render_multishot.py \
        --edl "$WORK/edl.json" \
        --start-frame $f --end-frame $nf \
        --out "$WORK/chunk${i}.mkv"
    f=$nf
    i=$(( i + 1 ))
done

# Same concat + mux + fade as category 1
# ... (see Category 1 above)
```

## Preview contact-sheet (always do this before final render)

```python
import cv2, json, numpy as np
cap = cv2.VideoCapture("depot/your_song.mp4")
fps = cap.get(cv2.CAP_PROP_FPS)
# Sample 8-12 timestamps, generate 9:16 thumbs, compose grid
# See examples/preview_grid_snippet.py for a working example
```

Show the grid to the user BEFORE rendering. Saves time.
