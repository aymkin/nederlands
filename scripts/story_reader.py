#!/usr/bin/env python3
"""
LingQ-style Audio Reader for Dutch texts.

Generates a self-contained HTML page with synchronized audio and
sentence-by-sentence highlighting. Uses edge-tts for TTS + VTT timings.

Usage:
    python3 scripts/story_reader.py mini_stories.md/01.md --voice maarten

Output: mini_stories.md/01_reader.html (self-contained, no server needed)
"""

import argparse
import base64
import html as html_mod
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Optional: Whisper forced alignment (reuses helpers from audio_to_anki.py)
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from audio_to_anki import (
        transcribe_with_whisper,
        extract_words_from_whisper,
        find_best_match,
        normalize_text,
    )
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

VOICES = {
    "colette": "nl-NL-ColetteNeural",
    "fenna": "nl-NL-FennaNeural",
    "maarten": "nl-NL-MaartenNeural",
}


# ─── Parsing ──────────────────────────────────────────────────────────


STOP_HEADINGS = {"## Vragen", "## Woordenlijst"}


def parse_sentences(md_path: Path) -> list[str]:
    """Read MD file, return narrative sentences only.

    Stops at known non-narrative headings (## Vragen, ## Woordenlijst).
    Skips other headings, horizontal rules, blockquotes, table rows,
    HTML comments, and italic-only metadata lines.
    """
    sentences = []
    with open(md_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if any(line.startswith(h) for h in STOP_HEADINGS):
                break
            if not line or line.startswith("#"):
                continue
            if line == "---":
                continue
            if line.startswith(">") or line.startswith("|"):
                continue
            if line.startswith("<!--"):
                continue
            if line.startswith("_") and line.endswith("_") and not line.startswith("__"):
                continue
            sentences.append(line)
    return sentences


def md_to_html(text: str) -> str:
    """Convert markdown bold/italic to HTML tags for display."""
    text = html_mod.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<em>\1</em>", text)
    return text


def strip_md(text: str) -> str:
    """Strip markdown formatting for clean TTS input."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)
    return text


def parse_timestamp(ts: str) -> float:
    """Parse '00:00:03,412' or '00:00:03.412' → seconds."""
    ts = ts.replace(",", ".")
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_vtt(vtt_path: Path) -> list[dict]:
    """Parse VTT/SRT → [{start, end, text}, ...]."""
    content = vtt_path.read_text(encoding="utf-8")
    cues = []
    pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*\n"
        r"((?:(?!\d{2}:\d{2}:\d{2}).+\n?)+)",
        re.MULTILINE,
    )
    for m in pattern.finditer(content):
        cues.append({
            "start": parse_timestamp(m.group(1)),
            "end": parse_timestamp(m.group(2)),
            "text": m.group(3).strip(),
        })
    return cues


# ─── TTS Generation ──────────────────────────────────────────────────


def generate_tts(text: str, voice: str, mp3_path: Path, vtt_path: Path):
    """Run edge-tts CLI → MP3 + VTT."""
    result = subprocess.run(
        [
            "edge-tts",
            "-t", text,
            "-v", voice,
            "--write-media", str(mp3_path),
            "--write-subtitles", str(vtt_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"edge-tts error: {result.stderr}", file=sys.stderr)
        sys.exit(1)


# ─── Timing Matching ─────────────────────────────────────────────────


def match_timings(sentences: list[str], cues: list[dict]) -> list[dict]:
    """Map VTT cues → per-sentence [{start, end}, ...]."""
    if not cues:
        return [{"start": 0, "end": 0} for _ in sentences]

    if len(cues) == len(sentences):
        return [{"start": c["start"], "end": c["end"]} for c in cues]

    # Greedy assignment: accumulate cues until they cover each sentence
    timings = []
    cue_idx = 0

    for sent in sentences:
        if cue_idx >= len(cues):
            timings.append({"start": cues[-1]["end"], "end": cues[-1]["end"]})
            continue

        start = cues[cue_idx]["start"]
        end = cues[cue_idx]["end"]
        accumulated_len = len(cues[cue_idx]["text"])
        cue_idx += 1

        while cue_idx < len(cues) and accumulated_len < len(sent) * 0.8:
            end = cues[cue_idx]["end"]
            accumulated_len += len(cues[cue_idx]["text"]) + 1
            cue_idx += 1

        timings.append({"start": start, "end": end})

    return timings


# ─── Whisper Forced Alignment ────────────────────────────────────────


def align_timings_whisper(sentences: list[str], mp3_path: Path) -> list[dict]:
    """Forced alignment via Whisper — ~95% precise sentence boundaries.

    Replaces VTT-cue greedy matching. Whisper transcribes the MP3 with
    word-level timestamps; each MD sentence is matched against the word
    stream via sliding-window fuzzy matching (SequenceMatcher).
    """
    whisper_data = transcribe_with_whisper(mp3_path, word_timestamps=True)
    whisper_words = extract_words_from_whisper(whisper_data)
    if not whisper_words:
        return [{"start": 0, "end": 0} for _ in sentences]

    raw_timings: list[dict | None] = []
    search_idx = 0
    matched = 0

    for sent in sentences:
        plain = strip_md(sent)
        words = normalize_text(plain).split()
        if not words:
            raw_timings.append(None)
            continue
        match = find_best_match(words, whisper_words, search_idx)
        if match:
            raw_timings.append({"start": match["start"], "end": match["end"]})
            search_idx = match["match_idx"]
            matched += 1
        else:
            raw_timings.append(None)

    print(f"Aligned {matched} / {len(sentences)} sentences")
    audio_end = whisper_words[-1]["end"] if whisper_words else 0
    return _interpolate_gaps(raw_timings, audio_end)


def _interpolate_gaps(timings: list[dict | None], audio_end: float) -> list[dict]:
    """Replace None entries with interpolated spans between known neighbors."""
    n = len(timings)
    result: list[dict] = []
    i = 0
    while i < n:
        t = timings[i]
        if t is not None:
            result.append(t)
            i += 1
            continue
        # Find previous known end
        prev_end = 0.0
        for j in range(i - 1, -1, -1):
            if timings[j] is not None:
                prev_end = timings[j]["end"]
                break
        # Find next known start and count consecutive Nones
        gap_count = 1
        next_start = audio_end
        for j in range(i + 1, n):
            if timings[j] is None:
                gap_count += 1
            else:
                next_start = timings[j]["start"]
                break
        # Equal split across consecutive Nones
        span = max(0.0, (next_start - prev_end) / gap_count)
        for k in range(gap_count):
            start = prev_end + span * k
            result.append({"start": start, "end": start + span})
        i += gap_count
    return result


# ─── HTML Generation ─────────────────────────────────────────────────


def build_html(
    sentences: list[str],
    timings: list[dict],
    mp3_path: Path,
    title: str,
) -> str:
    with open(mp3_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("ascii")

    sent_html = "\n".join(
        f'    <p class="s" data-i="{i}" data-s="{t["start"]:.3f}" '
        f'data-e="{t["end"]:.3f}">{md_to_html(s)}</p>'
        for i, (s, t) in enumerate(zip(sentences, timings))
    )

    timings_js = (
        "[" + ",".join(f'[{t["start"]:.3f},{t["end"]:.3f}]' for t in timings) + "]"
    )

    return _HTML_TEMPLATE.format(
        title=html_mod.escape(title),
        sentences=sent_html,
        audio_b64=audio_b64,
        timings_js=timings_js,
    )


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{
  font-family:Georgia,'Times New Roman',serif;
  background:#faf9f6;color:#2c2c2c;
  line-height:1.85;
}}
.wrap{{
  max-width:620px;margin:0 auto;
  padding:48px 24px 140px;
}}
h1{{
  font-size:1.3em;font-weight:600;
  color:#555;margin-bottom:28px;
  font-family:system-ui,-apple-system,sans-serif;
}}
.s{{
  font-size:1.25em;
  padding:10px 16px;margin:2px -16px;
  border-radius:6px;cursor:pointer;
  transition:background .15s,color .15s;
}}
.s:hover{{background:#efeee8}}
.s.active{{background:#fef3c7;color:#111}}
.player{{
  position:fixed;bottom:0;left:0;right:0;
  background:#fff;
  border-top:1px solid #e5e2db;
  padding:14px 24px;
  display:flex;align-items:center;gap:14px;
  z-index:100;
  box-shadow:0 -2px 16px rgba(0,0,0,.05);
}}
.btn{{
  width:46px;height:46px;border-radius:50%;
  border:none;background:#2c2c2c;color:#fff;
  font-size:16px;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  flex-shrink:0;transition:background .15s;
}}
.btn:hover{{background:#444}}
.btn svg{{fill:#fff;width:18px;height:18px}}
.mid{{flex:1;display:flex;flex-direction:column;gap:5px}}
.bar{{
  width:100%;height:6px;background:#e8e5de;
  border-radius:3px;cursor:pointer;overflow:hidden;
}}
.fill{{
  height:100%;width:0%;background:#2c2c2c;
  border-radius:3px;transition:width .15s linear;
}}
.time{{
  font-size:.75em;color:#999;
  font-family:system-ui,sans-serif;
}}
.spd{{
  background:none;border:1px solid #ccc;
  border-radius:4px;padding:4px 10px;
  font-size:.8em;cursor:pointer;color:#666;
  font-family:system-ui,sans-serif;
}}
.spd:hover{{border-color:#999;color:#333}}
</style>
</head>
<body>

<div class="wrap">
  <h1>{title}</h1>
{sentences}
</div>

<div class="player">
  <button class="btn" id="pb">
    <svg viewBox="0 0 24 24"><polygon id="pi" points="8,5 19,12 8,19"/></svg>
  </button>
  <div class="mid">
    <div class="bar" id="bar"><div class="fill" id="fill"></div></div>
    <span class="time" id="tm">0:00 / 0:00</span>
  </div>
  <button class="spd" id="sp">1x</button>
</div>

<audio id="au" preload="auto"
  src="data:audio/mpeg;base64,{audio_b64}"></audio>

<script>
(function(){{
const au=document.getElementById('au'),
  pb=document.getElementById('pb'),
  pi=document.getElementById('pi'),
  bar=document.getElementById('bar'),
  fill=document.getElementById('fill'),
  tm=document.getElementById('tm'),
  sp=document.getElementById('sp'),
  ss=document.querySelectorAll('.s'),
  T={timings_js},
  rates=[.7,.85,1,1.25,1.5];
let ri=2,cur=-1;

function fmt(s){{
  const m=Math.floor(s/60),sec=Math.floor(s%60);
  return m+':'+(sec<10?'0':'')+sec;
}}

pb.onclick=()=>au.paused?au.play():au.pause();

au.onplay=()=>pi.setAttribute('points','6,5 6,19 10,19 10,5 14,5 14,19 18,19 18,5');
au.onpause=()=>pi.setAttribute('points','8,5 19,12 8,19');

au.ontimeupdate=()=>{{
  const t=au.currentTime,d=au.duration||1;
  fill.style.width=(t/d*100)+'%';
  tm.textContent=fmt(t)+' / '+fmt(d);
  let ai=-1;
  for(let i=T.length-1;i>=0;i--){{
    if(t>=T[i][0]&&t<T[i][1]){{ai=i;break;}}
  }}
  if(ai===cur)return;
  cur=ai;
  ss.forEach((el,i)=>{{
    if(i===ai){{
      el.classList.add('active');
      el.scrollIntoView({{behavior:'smooth',block:'center'}});
    }}else{{
      el.classList.remove('active');
    }}
  }});
}};

bar.onclick=e=>{{
  const r=bar.getBoundingClientRect();
  au.currentTime=(e.clientX-r.left)/r.width*au.duration;
}};

ss.forEach(el=>el.onclick=()=>{{
  au.currentTime=parseFloat(el.dataset.s);
  if(au.paused)au.play();
}});

sp.onclick=()=>{{
  ri=(ri+1)%rates.length;
  au.playbackRate=rates[ri];
  sp.textContent=rates[ri]+'x';
}};
}})();
</script>

</body>
</html>
"""


# ─── Main ─────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="LingQ-style Audio Reader — self-contained HTML with synced audio",
    )
    parser.add_argument("input", type=Path, help="MD file (one sentence per line)")
    parser.add_argument(
        "--voice",
        default="maarten",
        choices=VOICES.keys(),
        help="TTS voice (default: maarten)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output HTML path (default: <input_stem>_reader.html next to input)",
    )
    parser.add_argument(
        "--no-align",
        action="store_true",
        help="Skip Whisper forced alignment, use VTT greedy matching fallback",
    )
    args = parser.parse_args()

    input_path = args.input.resolve()
    if not input_path.exists():
        print(f"File not found: {input_path}")
        return 1

    voice_id = VOICES[args.voice]
    title = input_path.stem
    output_path = (
        args.output.resolve()
        if args.output
        else input_path.with_name(f"{title}_reader.html")
    )

    # 1. Parse
    sentences = parse_sentences(input_path)
    if not sentences:
        print("No sentences found!")
        return 1
    print(f"Sentences: {len(sentences)}")

    # 2. Generate TTS
    full_text = " ".join(strip_md(s) for s in sentences)
    with tempfile.TemporaryDirectory() as tmp:
        mp3 = Path(tmp) / "audio.mp3"
        vtt = Path(tmp) / "audio.vtt"

        print(f"Generating audio ({args.voice})...")
        generate_tts(full_text, voice_id, mp3, vtt)

        # 3. Align timings — Whisper forced alignment (default) or VTT greedy fallback
        if WHISPER_AVAILABLE and not args.no_align:
            print("Aligning with Whisper (forced alignment)...")
            timings = align_timings_whisper(sentences, mp3)
        else:
            if not WHISPER_AVAILABLE and not args.no_align:
                print("Warning: whisper not importable, using VTT greedy fallback")
                print("  Install: pip install openai-whisper")
            cues = parse_vtt(vtt)
            print(f"VTT cues: {len(cues)}")
            if len(cues) != len(sentences):
                print(
                    f"  Warning: cue count ({len(cues)}) != sentence count "
                    f"({len(sentences)}), using greedy matching"
                )
            timings = match_timings(sentences, cues)

        # 5. Build HTML
        page = build_html(sentences, timings, mp3, title)

    # 6. Write
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding="utf-8")

    size_kb = output_path.stat().st_size / 1024
    print(f"Output: {output_path}")
    print(f"Size: {size_kb:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
