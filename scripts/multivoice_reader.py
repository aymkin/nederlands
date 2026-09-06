#!/usr/bin/env python3
"""Multi-voice audio reader: a cast script → one MP3 + a self-contained HTML page.

Unlike story_reader.py (one voice, one pass), this narrates dialogue: each role
gets its own edge-tts voice and speech rate, segments are synthesised
separately and concatenated, so sentence boundaries are exact by construction.

Script format (markdown-ish, hand-editable):

    ---
    title: Boerderij der dieren
    subtitle: Drie hoofdstukken
    cast:
      verteller: colette +0%
      Majoor: maarten -12%
      Bokser: maarten +10%
    ---

    # De droom van Majoor

    Het is bijna nacht op de Herenhoeve.

    **Majoor:** Lieve vrienden, ik wil jullie iets vertellen.

    > Lieve dieren, luister goed,
    > een mooie tijd breekt aan.

`# ` starts a chapter. `**Role:**` makes the paragraph that role's speech;
anything else is the narrator. `> ` marks verse — lines are kept as written and
each line highlights separately. Blank lines separate segments.

Usage:
    python3 scripts/multivoice_reader.py script.md --out ~/Desktop/verhaal
    python3 scripts/multivoice_reader.py script.md --dry-run

Dependency: pip install edge-tts (plus ffmpeg for concatenation).
"""

import argparse
import asyncio
import base64
import html as html_mod
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import edge_tts

sys.path.insert(0, str(Path(__file__).resolve().parent))
from story_reader import (  # sequential word-stream walk + markdown handling
    STOP_HEADINGS,
    align_timings,
    md_to_html,
    strip_md,
)

VOICES = {
    "colette": "nl-NL-ColetteNeural",
    "fenna": "nl-NL-FennaNeural",
    "maarten": "nl-NL-MaartenNeural",
}
NARRATOR_KEY = "verteller"
DEFAULT_CAST = (NARRATOR_KEY, "+0%")

PAUSE_SAME = 0.55     # same speaker, new paragraph
PAUSE_SWITCH = 0.40   # voice change
PAUSE_CHAPTER = 1.30  # after a chapter heading
PAUSE_SCENE = 0.95    # across a --- scene break

# Role colours, assigned in order of first appearance. Light / dark pairs.
PALETTE = [
    ("#6B4076", "#C39BD0"), ("#2C6A5E", "#7FC7B8"), ("#3A6E96", "#94C2E0"),
    ("#7E6134", "#D4B579"), ("#9C4038", "#E09A92"), ("#4A5A8C", "#A3B0DC"),
]


# ─── Script parsing ───────────────────────────────────────────────────


def parse_script(path: Path) -> tuple[dict, dict, list]:
    """→ (meta, cast, blocks). Raises ValueError on a malformed script."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    if not m:
        raise ValueError("script must open with a --- frontmatter block ---")
    head, rest = m.group(1), m.group(2)

    meta, cast, in_cast = {}, {}, False
    for line in head.split("\n"):
        if not line.strip():
            continue
        if re.match(r"^cast:\s*$", line):
            in_cast = True
            continue
        if in_cast and line.startswith((" ", "\t")):
            role, spec = line.split(":", 1)
            parts = spec.split()
            if len(parts) != 2 or parts[0] not in VOICES:
                raise ValueError(f"bad cast line: {line.strip()!r} "
                                 f"(expected '<role>: <voice> <rate>')")
            cast[role.strip()] = (parts[0], parts[1])
            continue
        in_cast = False
        key, _, val = line.partition(":")
        meta[key.strip()] = val.strip()

    cast.setdefault(NARRATOR_KEY, DEFAULT_CAST)

    blocks = []
    for chunk in re.split(r"\n\s*\n", rest):
        chunk = chunk.strip()
        if not chunk:
            continue
        if any(chunk.startswith(h) for h in STOP_HEADINGS):
            break  # exercises and glossaries are read, not narrated
        if re.fullmatch(r"-{3,}|\*{3,}", chunk):
            blocks.append({"type": "break"})
            continue
        if chunk.startswith("<!--") or chunk.startswith("|"):
            continue
        if chunk.startswith("_") and chunk.endswith("_") and "\n" not in chunk:
            continue  # italic-only metadata line under the title
        if chunk.startswith("# "):
            blocks.append({"type": "chapter", "title": chunk[2:].strip()})
            continue
        if chunk.startswith(">"):
            lines = [re.sub(r"^>\s?", "", ln) for ln in chunk.split("\n")]
            role = meta.get("verse_role", "")
            blocks.append({"type": "speech", "role": role, "verse": True,
                           "sentences": [ln.strip() for ln in lines if ln.strip()]})
            continue
        role = ""
        sm = re.match(r"\*\*(.+?):\*\*\s*(.*)", chunk, re.S)
        if sm:
            role, chunk = sm.group(1).strip(), sm.group(2).strip()
        blocks.append({"type": "speech", "role": role, "verse": False,
                       "sentences": split_sentences(chunk)})

    unknown = {b["role"] for b in blocks
               if b["type"] == "speech" and b["role"] and b["role"] not in cast}
    if unknown:
        raise ValueError(f"roles used but not in cast: {sorted(unknown)}")
    return meta, cast, blocks


def split_sentences(text: str) -> list[str]:
    text = " ".join(text.split())
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]


# ─── Audio ────────────────────────────────────────────────────────────


async def _synth(text: str, voice: str, rate: str, path: Path) -> list[dict]:
    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words = []
    with open(path, "wb") as fh:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                fh.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append({"text": ch["text"],
                              "start": ch["offset"] / 1e7,
                              "end": (ch["offset"] + ch["duration"]) / 1e7})
    return words


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def build_audio(blocks: list, cast: dict, tmp: Path, out_mp3: Path) -> float:
    """Synthesise every segment, concatenate, and stamp absolute timings."""
    parts, prev_role, pending_gap, idx = [], None, None, 0

    for blk in blocks:
        if blk["type"] == "chapter":
            pending_gap = PAUSE_CHAPTER
            continue
        if blk["type"] == "break":
            pending_gap = PAUSE_SCENE
            continue
        voice_key, rate = cast.get(blk["role"] or NARRATOR_KEY, DEFAULT_CAST)
        if parts:
            gap = pending_gap or (PAUSE_SAME if blk["role"] == prev_role
                                  else PAUSE_SWITCH)
            sp = tmp / f"gap_{idx:03d}.mp3"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-t", str(gap),
                            "-i", "anullsrc=r=24000:cl=mono", "-q:a", "4",
                            str(sp), "-y"], check=True)
            parts.append(sp)
        pending_gap = None

        seg = tmp / f"seg_{idx:03d}.mp3"
        words = asyncio.run(_synth(strip_md(" ".join(blk["sentences"])),
                                   VOICES[voice_key], rate, seg))
        blk["timings"] = align_timings(blk["sentences"], words)
        blk["part"] = seg.name
        parts.append(seg)
        prev_role = blk["role"]
        idx += 1
        print(f"  {idx:>3}  {blk['role'] or NARRATOR_KEY:<14} {rate:>5}  "
              f"{len(blk['sentences']):>2} zinnen  {duration(seg):6.2f}s")

    listing = tmp / "parts.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c:a", "libmp3lame", "-q:a", "4",
                    str(out_mp3), "-y"], cwd=tmp, check=True)

    offset, speech = 0.0, [b for b in blocks if b["type"] == "speech"]
    bi = 0
    for p in parts:
        d = duration(p)
        if p.name.startswith("seg_"):
            for t in speech[bi]["timings"]:
                t["start"] += offset
                t["end"] += offset
            bi += 1
        offset += d

    total = duration(out_mp3)
    drift = abs(total - offset)
    print(f"\n  parts {offset:.2f}s   concat {total:.2f}s   drift {drift:.3f}s")
    if drift > 1.0:
        raise RuntimeError(f"concat drift {drift:.2f}s — timings would desync")
    return total


# ─── HTML ─────────────────────────────────────────────────────────────


def slugify(role: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", role.lower()).strip("-")
    return s or "verteller"


def build_html(meta: dict, cast: dict, blocks: list, mp3: Path,
               total: float) -> str:
    roles = []
    for b in blocks:
        if b["type"] == "speech" and b["role"] and b["role"] not in roles:
            roles.append(b["role"])
    colors = {r: PALETTE[i % len(PALETTE)] for i, r in enumerate(roles)}

    tokens_l = "\n".join(f"  --c-{slugify(r)}:{colors[r][0]};" for r in roles)
    tokens_d = "\n".join(f"    --c-{slugify(r)}:{colors[r][1]};" for r in roles)
    classes = "\n".join(f".v-{slugify(r)} {{ --vc:var(--c-{slugify(r)}); }}"
                        for r in roles)

    rows = [f'<tr><td><span class="dot v-verteller"></span>Verteller</td>'
            f'<td class="mono">{cast[NARRATOR_KEY][0]}</td>'
            f'<td class="mono num">{cast[NARRATOR_KEY][1]}</td></tr>']
    for r in roles:
        v, rate = cast.get(r, DEFAULT_CAST)
        rows.append(f'<tr><td><span class="dot v-{slugify(r)}"></span>'
                    f'{html_mod.escape(r)}</td><td class="mono">{v}</td>'
                    f'<td class="mono num">{rate}</td></tr>')

    body, si = [], 0
    for b in blocks:
        if b["type"] == "chapter":
            body.append(f'<h2 class="ch">{html_mod.escape(b["title"])}</h2>')
            continue
        if b["type"] == "break":
            body.append('<hr class="scene">')
            continue
        cls = f'seg v-{slugify(b["role"])}'
        if b["role"]:
            cls += " spoken"
        if b["verse"]:
            cls += " verse"
        spans = []
        for s, t in zip(b["sentences"], b["timings"]):
            spans.append(f'<span class="s" data-a="{t["start"]:.3f}" '
                         f'data-b="{t["end"]:.3f}">{md_to_html(s)}</span>')
            si += 1
        who = (f'<span class="who">{html_mod.escape(b["role"])}</span>'
               if b["role"] else "")
        body.append(f'<p class="{cls}">{who}'
                    f'{("<br>" if b["verse"] else " ").join(spans)}</p>')

    mm, ss = int(total) // 60, int(total) % 60
    audio_b64 = base64.b64encode(mp3.read_bytes()).decode("ascii")
    return _TEMPLATE.format(
        title=html_mod.escape(meta.get("title", mp3.stem)),
        subtitle=html_mod.escape(meta.get("subtitle", "")),
        footer=html_mod.escape(meta.get("footer", "")),
        tokens_light=tokens_l, tokens_dark=tokens_d, role_classes=classes,
        cast_rows="\n".join(rows), body="\n".join(body),
        mmss=f"{mm}:{ss:02d}", total=f"{total:.2f}", audio_b64=audio_b64,
        n_sent=si)


_TEMPLATE = """<title>{title}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Literata:opsz,wght@7..72,400;7..72,600&family=Archivo:wght@500;600&display=swap">
<style>
:root {{
  --paper:#EFEBE0; --raised:#F7F4EC; --ink:#1E1B16; --soft:#6B6455;
  --rule:#DAD4C4; --lamp:#C8A02E; --lamp-wash:rgba(200,160,46,.26);
  --vocab:#7D2E23; --c-verteller:#6B6455;
{tokens_light}
  --shadow:0 1px 2px rgba(30,27,22,.07), 0 8px 24px rgba(30,27,22,.06);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --paper:#16171B; --raised:#1E2026; --ink:#E7E1D4; --soft:#9A9384;
    --rule:#33353D; --lamp:#E3BE58; --lamp-wash:rgba(227,190,88,.17);
    --vocab:#E8A584; --c-verteller:#9A9384;
{tokens_dark}
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.35);
  }}
}}
:root[data-theme="dark"] {{
  --paper:#16171B; --raised:#1E2026; --ink:#E7E1D4; --soft:#9A9384;
  --rule:#33353D; --lamp:#E3BE58; --lamp-wash:rgba(227,190,88,.17);
  --vocab:#E8A584; --c-verteller:#9A9384;
{tokens_dark}
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.35);
}}

* {{ box-sizing:border-box; }}
body {{
  background:var(--paper); color:var(--ink);
  font-family:"Literata",Georgia,"Times New Roman",serif;
  font-size:19px; line-height:1.78; margin:0;
  padding:0 20px calc(120px + env(safe-area-inset-bottom));
  -webkit-text-size-adjust:100%;
}}
.wrap {{ max-width:40rem; margin:0 auto; }}
header {{ padding:64px 0 8px; border-bottom:1px solid var(--rule); }}
h1 {{
  font-family:"Fraunces",Georgia,serif; font-weight:700;
  font-size:clamp(2.1rem,7vw,3rem); line-height:1.06; margin:0 0 10px;
  letter-spacing:-.015em; text-wrap:balance;
}}
.sub {{ color:var(--soft); font-size:.9rem; margin:0 0 26px; }}
.sub b {{ color:var(--ink); font-weight:600; }}
details.cast {{ margin:22px 0 6px; }}
details.cast summary {{
  font-family:"Archivo",system-ui,sans-serif; font-size:.74rem;
  letter-spacing:.1em; text-transform:uppercase; color:var(--soft);
  cursor:pointer; padding:8px 0; list-style:none;
}}
details.cast summary::-webkit-details-marker {{ display:none; }}
details.cast summary::before {{ content:"\\25B8  "; }}
details.cast[open] summary::before {{ content:"\\25BE  "; }}
details.cast summary:focus-visible {{ outline:2px solid var(--lamp); outline-offset:3px; }}
table {{ border-collapse:collapse; width:100%; font-size:.84rem; margin-bottom:10px; }}
td {{ padding:6px 10px 6px 0; border-bottom:1px solid var(--rule); vertical-align:baseline; }}
.mono {{ font-family:"Archivo",system-ui,sans-serif; color:var(--soft); }}
.num {{ font-variant-numeric:tabular-nums; text-align:right; white-space:nowrap; }}
.dot {{
  display:inline-block; width:9px; height:9px; border-radius:50%;
  margin-right:9px; background:var(--vc); vertical-align:baseline;
}}
.v-verteller {{ --vc:var(--c-verteller); }}
{role_classes}
h2.ch {{
  font-family:"Fraunces",Georgia,serif; font-weight:500; font-size:1.55rem;
  margin:68px 0 30px; padding-top:26px; border-top:1px solid var(--rule);
  letter-spacing:-.01em; text-wrap:balance;
}}
h2.ch:first-of-type {{ border-top:none; margin-top:40px; }}
p.seg {{ margin:0 0 1.35em; color:var(--ink); }}
p.spoken {{ padding-left:16px; border-left:2px solid var(--vc); }}
p.spoken .who {{
  display:block; color:var(--vc);
  font-family:"Archivo",system-ui,sans-serif;
  font-size:.68rem; font-weight:600; letter-spacing:.12em;
  text-transform:uppercase; margin-bottom:.3em;
}}
p.verse {{ font-style:italic; line-height:1.6; }}
hr.scene {{
  border:none; height:1px; background:var(--rule);
  width:56px; margin:34px auto 34px;
}}
.s b {{ font-weight:600; color:var(--vocab); }}
.s {{
  cursor:pointer; border-radius:3px; padding:1px 2px; margin:0 -2px;
  transition:background-color .18s ease, box-shadow .18s ease;
}}
.s:hover {{ background:rgba(128,128,128,.14); }}
.s:focus-visible {{ outline:2px solid var(--lamp); outline-offset:1px; }}
.s.on {{
  background:var(--lamp-wash);
  box-shadow:0 0 0 5px var(--lamp-wash), 0 0 22px 8px var(--lamp-wash);
}}
@media (prefers-reduced-motion: reduce) {{
  .s {{ transition:none; }} html {{ scroll-behavior:auto; }}
}}
.bar {{
  position:fixed; left:0; right:0; bottom:0; background:var(--raised);
  border-top:1px solid var(--rule); box-shadow:var(--shadow);
  padding:10px 16px calc(10px + env(safe-area-inset-bottom));
}}
.bar .inner {{
  max-width:40rem; margin:0 auto; display:flex; align-items:center; gap:12px;
  font-family:"Archivo",system-ui,sans-serif; font-size:.8rem;
}}
button {{
  font:inherit; font-family:"Archivo",system-ui,sans-serif; cursor:pointer;
  background:transparent; color:var(--ink); border:1px solid var(--rule);
  border-radius:7px; padding:7px 11px;
}}
button:hover {{ border-color:var(--lamp); }}
button:focus-visible {{ outline:2px solid var(--lamp); outline-offset:2px; }}
#play {{ min-width:52px; font-size:1rem; line-height:1; padding:9px 12px; }}
#follow[aria-pressed="true"] {{ border-color:var(--lamp); color:var(--lamp); }}
.time {{ color:var(--soft); font-variant-numeric:tabular-nums; white-space:nowrap; }}
#seek {{ flex:1; min-width:60px; accent-color:var(--lamp); }}
footer {{
  margin:56px 0 0; padding-top:20px; border-top:1px solid var(--rule);
  color:var(--soft); font-size:.78rem; font-family:"Archivo",system-ui,sans-serif;
}}
</style>

<div class="wrap">
<header>
  <h1>{title}</h1>
  <p class="sub">{subtitle} · <b>{mmss}</b> luisteren · klik op een zin om
     daar te beginnen</p>
</header>

<details class="cast">
  <summary>Rolverdeling</summary>
  <table><tbody>
{cast_rows}
  </tbody></table>
</details>

{body}

<footer>{footer}</footer>
</div>

<div class="bar">
  <div class="inner">
    <button id="play" aria-label="Afspelen">&#9654;</button>
    <span class="time" id="tcur">0:00</span>
    <input id="seek" type="range" min="0" max="{total}" step="0.1" value="0"
           aria-label="Positie">
    <span class="time">{mmss}</span>
    <button id="rate" aria-label="Snelheid">1&times;</button>
    <button id="follow" aria-pressed="true" aria-label="Meelopen">&#8681;</button>
  </div>
</div>

<audio id="au" preload="metadata" src="data:audio/mpeg;base64,{audio_b64}"></audio>

<script>
(function () {{
  var au = document.getElementById('au');
  var spans = Array.prototype.slice.call(document.querySelectorAll('.s'));
  var starts = spans.map(function (s) {{ return parseFloat(s.dataset.a); }});
  var ends = spans.map(function (s) {{ return parseFloat(s.dataset.b); }});
  var cur = -1, follow = true;
  var RATES = [0.7, 0.85, 1, 1.15, 1.3], ri = 2;

  function fmt(t) {{
    t = Math.max(0, Math.floor(t || 0));
    return Math.floor(t / 60) + ':' + String(t % 60).padStart(2, '0');
  }}
  function find(t) {{
    var lo = 0, hi = starts.length - 1, best = -1;
    while (lo <= hi) {{
      var mid = (lo + hi) >> 1;
      if (starts[mid] <= t) {{ best = mid; lo = mid + 1; }} else {{ hi = mid - 1; }}
    }}
    if (best >= 0 && t > ends[best] + 1.6) return -1;
    return best;
  }}
  function paint(i) {{
    if (i === cur) return;
    if (cur >= 0) spans[cur].classList.remove('on');
    cur = i;
    if (i < 0) return;
    spans[i].classList.add('on');
    if (follow) {{
      var r = spans[i].getBoundingClientRect();
      if (r.top < 90 || r.bottom > innerHeight - 150) {{
        spans[i].scrollIntoView({{ block: 'center', behavior: 'smooth' }});
      }}
    }}
  }}

  var seek = document.getElementById('seek'), dragging = false;
  au.addEventListener('timeupdate', function () {{
    paint(find(au.currentTime));
    if (!dragging) seek.value = au.currentTime;
    document.getElementById('tcur').textContent = fmt(au.currentTime);
  }});
  seek.addEventListener('input', function () {{ dragging = true; }});
  seek.addEventListener('change', function () {{
    dragging = false; au.currentTime = parseFloat(seek.value);
  }});

  var playBtn = document.getElementById('play');
  function sync() {{
    var p = !au.paused;
    playBtn.innerHTML = p ? '&#10074;&#10074;' : '&#9654;';
    playBtn.setAttribute('aria-label', p ? 'Pauzeren' : 'Afspelen');
  }}
  playBtn.addEventListener('click', function () {{ au.paused ? au.play() : au.pause(); }});
  au.addEventListener('play', sync);
  au.addEventListener('pause', sync);

  document.getElementById('rate').addEventListener('click', function () {{
    ri = (ri + 1) % RATES.length;
    au.playbackRate = RATES[ri];
    this.innerHTML = RATES[ri] + '&times;';
  }});
  document.getElementById('follow').addEventListener('click', function () {{
    follow = !follow;
    this.setAttribute('aria-pressed', String(follow));
  }});

  spans.forEach(function (s, i) {{
    s.tabIndex = 0;
    function go() {{ au.currentTime = starts[i]; paint(i); au.play(); }}
    s.addEventListener('click', go);
    s.addEventListener('keydown', function (e) {{
      if (e.key === 'Enter' || e.key === ' ') {{ e.preventDefault(); go(); }}
    }});
  }});

  addEventListener('keydown', function (e) {{
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'BUTTON') return;
    if (e.code === 'Space') {{ e.preventDefault(); au.paused ? au.play() : au.pause(); }}
    if (e.key === 'ArrowLeft') au.currentTime = Math.max(0, au.currentTime - 5);
    if (e.key === 'ArrowRight') au.currentTime += 5;
  }});
}})();
</script>
"""


# ─── Main ─────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser(
        description="Cast script → multi-voice MP3 + self-contained HTML reader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Script format is documented at the top of this file.")
    ap.add_argument("script", type=Path, help="Cast script (.md)")
    ap.add_argument("--out", type=Path, default=None,
                    help="Output basename; .mp3/.html appended "
                         "(default: script path without extension)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Parse and report the segment plan, synthesise nothing")
    args = ap.parse_args()

    if not args.script.exists():
        print(f"Script not found: {args.script}")
        return 1
    try:
        meta, cast, blocks = parse_script(args.script)
    except ValueError as e:
        print(f"Script error: {e}")
        return 1

    speech = [b for b in blocks if b["type"] == "speech"]
    n_sent = sum(len(b["sentences"]) for b in speech)
    chapters = [b["title"] for b in blocks if b["type"] == "chapter"]
    print(f"{meta.get('title', args.script.stem)}: {len(chapters)} hoofdstukken, "
          f"{len(speech)} segmenten, {n_sent} zinnen")
    for role, (v, r) in cast.items():
        used = sum(1 for b in speech if (b["role"] or NARRATOR_KEY) == role)
        print(f"  {role:<14} {v:<9} {r:>5}   {used} segmenten")

    if args.dry_run:
        return 0

    base = args.out or args.script.with_suffix("")
    base.parent.mkdir(parents=True, exist_ok=True)
    mp3, page = Path(f"{base}.mp3"), Path(f"{base}.html")

    print("\nSynthesising...")
    with tempfile.TemporaryDirectory() as tmp:
        total = build_audio(blocks, cast, Path(tmp), mp3)
        page.write_text(build_html(meta, cast, blocks, mp3, total),
                        encoding="utf-8")

    print(f"\nAudio: {mp3}  ({mp3.stat().st_size / 1024:.0f} KB)")
    print(f"Page:  {page}  ({page.stat().st_size / 1048576:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
