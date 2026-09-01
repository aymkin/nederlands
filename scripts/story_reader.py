#!/usr/bin/env python3
"""
LingQ-style Audio Reader for Dutch texts.

Generates a self-contained HTML page with synchronized audio and
sentence-by-sentence highlighting. Uses the edge-tts Python API for TTS
plus its per-word WordBoundary timings (no speech recognition needed).

Usage:
    python3 scripts/story_reader.py mini_stories.md/01.md --voice maarten

Output: mini_stories.md/01_reader.html (self-contained, no server needed)
"""

import argparse
import base64
import html as html_mod
import asyncio
import re
import sys
import tempfile
from pathlib import Path

import edge_tts

# Темп речи: "-10%" = 0.9x от скорости носителя (замерено на nl-NL голосах).
DEFAULT_RATE = "-10%"

VOICES = {
    "colette": "nl-NL-ColetteNeural",
    "fenna": "nl-NL-FennaNeural",
    "maarten": "nl-NL-MaartenNeural",
}


# ─── Parsing ──────────────────────────────────────────────────────────


STOP_HEADINGS = {"## Vragen", "## Woordenlijst"}


def parse_sentences(md_path: Path) -> list[str]:
    """Read MD file, return narrative sentences only.

    Handles both one-sentence-per-line and Prettier-wrapped paragraphs.
    Stops at known non-narrative headings (## Vragen, ## Woordenlijst).
    Skips headings, horizontal rules, blockquotes, table rows,
    HTML comments, and italic-only metadata lines.
    """
    raw_lines: list = []  # str = content, None = paragraph break
    with open(md_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if any(line.startswith(h) for h in STOP_HEADINGS):
                break
            if not line or line.startswith("#") or line == "---":
                raw_lines.append(None)
                continue
            if line.startswith(">") or line.startswith("|"):
                continue
            if line.startswith("<!--"):
                continue
            if line.startswith("_") and line.endswith("_") and not line.startswith("__"):
                continue
            raw_lines.append(line)

    # Merge continuation lines into paragraphs (handles Prettier proseWrap)
    paragraphs: list[str] = []
    buf: list[str] = []
    for item in raw_lines:
        if item is None:
            if buf:
                paragraphs.append(" ".join(buf))
                buf = []
        else:
            buf.append(item)
    if buf:
        paragraphs.append(" ".join(buf))

    # Split each paragraph into individual sentences
    sentences: list[str] = []
    for para in paragraphs:
        sentences.extend(_split_paragraph(para))

    return sentences


_NEW_SENT_RE = re.compile(r'\s+(?:["\u201c]?(?:\*\*)?[A-Z\u00c0-\u00d6\u00d8-\u00de]|\*\*[A-Z\u00c0-\u00d6\u00d8-\u00de])')


def _split_paragraph(text: str) -> list[str]:
    """Split a paragraph into sentences, keeping quoted dialogue intact.

    Tracks quote state so that .!? inside "dialogue" don't trigger splits.
    Also detects standalone quoted sentences ending with !" ." ?"
    """
    parts: list[str] = []
    start = 0
    in_quotes = False
    i = 0

    while i < len(text):
        ch = text[i]

        if ch == '"':
            was_in = in_quotes
            in_quotes = not in_quotes
            # Closing quote right after .!? → standalone quoted sentence
            if was_in and not in_quotes and i > 0 and text[i - 1] in ".!?":
                rest = text[i + 1:]
                if not rest.strip() or _NEW_SENT_RE.match(rest):
                    parts.append(text[start:i + 1].strip())
                    start = i + 1
                    while start < len(text) and text[start] == " ":
                        start += 1
                    i = start
                    continue

        elif ch in ".!?" and not in_quotes:
            rest = text[i + 1:]
            if not rest.strip():
                parts.append(text[start:i + 1].strip())
                start = i + 1
            elif _NEW_SENT_RE.match(rest):
                parts.append(text[start:i + 1].strip())
                start = i + 1
                while start < len(text) and text[start] == " ":
                    start += 1
                i = start
                continue

        i += 1

    remaining = text[start:].strip()
    if remaining:
        parts.append(remaining)

    return [p for p in parts if p]


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


# ─── TTS Generation ──────────────────────────────────────────────────


async def _synthesize(text: str, voice: str, rate: str, mp3_path: Path) -> list[dict]:
    """Stream edge-tts → MP3 on disk + per-word timings.

    The CLI has no --boundary flag, so it can only emit sentence-level
    subtitles. The Python API yields WordBoundary events whose text comes
    from the input rather than from recognition, so sentence boundaries
    are exact and no forced alignment is required.
    """
    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words: list[dict] = []
    with open(mp3_path, "wb") as fh:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({
                    "text": chunk["text"],
                    "start": chunk["offset"] / 1e7,
                    "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                })
    return words


def generate_tts(text: str, voice: str, rate: str, mp3_path: Path) -> list[dict]:
    """Blocking wrapper around _synthesize()."""
    return asyncio.run(_synthesize(text, voice, rate, mp3_path))


# ─── Timing Alignment ────────────────────────────────────────────────


def _speakable_tokens(sentence: str) -> int:
    """Count tokens that edge-tts will emit a WordBoundary for.

    Pure-punctuation tokens (em dashes, lone quotes) produce no event.
    """
    return sum(
        1 for t in strip_md(sentence).split() if any(c.isalnum() for c in t)
    )


def align_timings(sentences: list[str], words: list[dict]) -> list[dict]:
    """Map per-word timings → per-sentence [{start, end}, ...].

    Word events arrive in input order, so this is a sequential walk: each
    sentence consumes as many events as it has speakable tokens.
    """
    counts = [_speakable_tokens(s) for s in sentences]
    total = sum(counts)

    # Guard against silent desync: if tokenisation disagrees with the event
    # stream, rescale shares so the walk still spans the whole audio.
    if total and total != len(words):
        print(f"  Note: {total} tokens vs {len(words)} word events — rescaling")
        scale = len(words) / total
        counts = [max(1, round(c * scale)) for c in counts]

    timings: list[dict] = []
    i = 0
    for n in counts:
        span = words[i:i + n]
        i += n
        if span:
            timings.append({"start": span[0]["start"], "end": span[-1]["end"]})
        else:
            last = timings[-1]["end"] if timings else 0.0
            timings.append({"start": last, "end": last})
    return timings


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
        "--rate",
        default=DEFAULT_RATE,
        help="Speech rate: -10%% = 0.9x, +0%% = native (default: %(default)s)",
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

        print(f"Generating audio ({args.voice}, rate {args.rate})...")
        words = generate_tts(full_text, voice_id, args.rate, mp3)
        print(f"Word timings: {len(words)}")

        # 3. Align: sequential walk over the word stream
        timings = align_timings(sentences, words)

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
