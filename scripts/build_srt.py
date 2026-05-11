"""
Build a draft .srt subtitle file from free-form lyrics + audio analysis.

Pipeline:
1. Tokenize lyrics into words; count syllables per word with a French
   vowel-group heuristic (collapse adjacent vowels into one group, drop a
   trailing silent "e" after a consonant).
2. Greedy-pack words into cue lines of <= max_syllables (default 4), respecting:
   - word boundaries (never split a word),
   - punctuation as preferred break points (, . ; : ! ? — line breaks),
   - if a single word exceeds the cap it gets its own cue.
3. Read per-0.5s vocal-energy windows from audio_analysis.json and find
   contiguous "vocal phrases" where vocal_n >= threshold.
4. Distribute cues across phrases proportionally to syllable count; within
   each phrase, time each cue by syllable count too.
5. Emit SubRip .srt with timestamps relative to the trim start (0 = first
   frame of the Reel).

Usage:
    python build_srt.py <audio_analysis.json> <lyrics.txt> [--out reel.srt]
                        [--threshold 0.25] [--max-syll 4]

Example:
    python build_srt.py work/audio.json depot/peggy.lyrics.txt \\
        --out sortie/"peggy - Reel.srt"
"""
import argparse
import json
import re
import sys
from pathlib import Path

VOWELS = set("aeiouyàâäéèêëîïôöùûüœæ")
PUNCT_RE = re.compile(r"[.,;:!?—–\-]")
WORD_RE = re.compile(r"[\wÀ-ÿœæ']+|[.,;:!?—–\-]", re.UNICODE)


def syllable_count(word: str) -> int:
    w = word.lower()
    w = re.sub(r"[^a-zàâäéèêëîïôöùûüœæ']", "", w)
    if not w:
        return 0
    count = 0
    in_v = False
    for ch in w:
        if ch in VOWELS:
            if not in_v:
                count += 1
                in_v = True
        else:
            in_v = False
    # Drop trailing silent "e" if preceded by a consonant and we have >=2 syllables.
    if w.endswith("e") and count >= 2 and len(w) >= 2 and w[-2] not in VOWELS:
        count -= 1
    return max(count, 1)


def tokenize_lyrics(text: str):
    """Return [(word, break_after_flag), ...].
    break_after_flag is True when a punctuation or line-break follows the word.
    """
    tokens = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if tokens:
                w, _ = tokens[-1]
                tokens[-1] = (w, True)
            continue
        line_tokens = []
        for p in WORD_RE.findall(line):
            if PUNCT_RE.fullmatch(p):
                if line_tokens:
                    w, _ = line_tokens[-1]
                    line_tokens[-1] = (w, True)
            else:
                line_tokens.append((p, False))
        if line_tokens:
            w, _ = line_tokens[-1]
            line_tokens[-1] = (w, True)
            tokens.extend(line_tokens)
    return tokens


def pack_cues(tokens, max_syllables=4):
    """Greedy-pack tokens into cue lines of <= max_syllables.
    Returns [(text, syllable_count), ...]."""
    cues = []
    cur_words = []
    cur_syll = 0

    def flush():
        nonlocal cur_words, cur_syll
        if cur_words:
            cues.append((" ".join(cur_words), cur_syll))
            cur_words, cur_syll = [], 0

    for word, brk in tokens:
        s = syllable_count(word)
        if s > max_syllables:
            flush()
            cues.append((word, s))
            continue
        if cur_syll + s > max_syllables:
            flush()
            cur_words, cur_syll = [word], s
        else:
            cur_words.append(word)
            cur_syll += s
        # Honor punctuation/line-break breaks once we've got something meaningful.
        if brk and cur_syll >= 2:
            flush()
    flush()
    return cues


def vocal_phrases(windows, window_sec, threshold=0.25, min_phrase_sec=0.5):
    """Return [(start_s, end_s), ...] for contiguous vocal-active windows."""
    phrases = []
    cur_start = None
    for w in windows:
        t = w["t"]
        if w.get("vocal_n", 0) >= threshold:
            if cur_start is None:
                cur_start = t
        else:
            if cur_start is not None:
                phrases.append((cur_start, t))
                cur_start = None
    if cur_start is not None:
        last_t = windows[-1]["t"] + window_sec
        phrases.append((cur_start, last_t))
    return [(s, e) for s, e in phrases if e - s >= min_phrase_sec]


def distribute(cues, phrases):
    """Allocate cues to phrases proportionally to syllable count; within
    each phrase, time cues by syllable share. Returns [(start, end, text), ...].
    """
    if not phrases or not cues:
        return []
    total_syll = sum(s for _, s in cues)
    total_phrase = sum(e - s for s, e in phrases)
    if total_phrase <= 0:
        return []

    syll_per_sec = total_syll / total_phrase

    timed = []
    cue_idx = 0
    n_cues = len(cues)

    for p_start, p_end in phrases:
        if cue_idx >= n_cues:
            break
        budget = (p_end - p_start) * syll_per_sec
        phrase_cues = []
        # Take cues until we've consumed our syllable budget for this phrase.
        while cue_idx < n_cues and budget > 0:
            phrase_cues.append(cues[cue_idx])
            budget -= cues[cue_idx][1]
            cue_idx += 1
        if not phrase_cues:
            continue
        phrase_syll = sum(s for _, s in phrase_cues)
        t = p_start
        for text, s in phrase_cues:
            dur = (p_end - p_start) * (s / phrase_syll)
            timed.append((t, t + dur, text))
            t += dur

    # Leftover cues — append after the last phrase with a default pace.
    if cue_idx < n_cues:
        t = timed[-1][1] if timed else 0.0
        for text, s in cues[cue_idx:]:
            dur = max(0.4, s * 0.3)
            timed.append((t, t + dur, text))
            t += dur

    return timed


def format_ts(t: float) -> str:
    if t < 0:
        t = 0.0
    h = int(t // 3600)
    t -= h * 3600
    m = int(t // 60)
    t -= m * 60
    s = int(t)
    ms = int(round((t - s) * 1000))
    if ms == 1000:
        ms = 0
        s += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def emit_srt(timed) -> str:
    out = []
    for i, (start, end, text) in enumerate(timed, 1):
        out.append(str(i))
        out.append(f"{format_ts(start)} --> {format_ts(end)}")
        out.append(text)
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("audio_json", help="audio_analysis.json from audio_analyze.py")
    ap.add_argument("lyrics", help="lyrics .txt file")
    ap.add_argument("--out", default=None, help="output .srt path (default: stdout)")
    ap.add_argument("--threshold", type=float, default=0.25,
                    help="vocal_n threshold for phrase detection (default 0.25)")
    ap.add_argument("--max-syll", type=int, default=4,
                    help="max syllables per cue line (default 4)")
    args = ap.parse_args()

    with open(args.audio_json, encoding="utf-8") as f:
        audio = json.load(f)
    text = Path(args.lyrics).read_text(encoding="utf-8")

    tokens = tokenize_lyrics(text)
    cues = pack_cues(tokens, max_syllables=args.max_syll)
    phrases = vocal_phrases(audio["windows"], audio.get("window_sec", 0.5),
                            threshold=args.threshold)
    timed = distribute(cues, phrases)
    srt = emit_srt(timed)

    if args.out:
        Path(args.out).write_text(srt, encoding="utf-8")
        print(f"Wrote {args.out} ({len(timed)} cues, {len(phrases)} vocal phrases)",
              file=sys.stderr)
    else:
        sys.stdout.write(srt)


if __name__ == "__main__":
    main()
