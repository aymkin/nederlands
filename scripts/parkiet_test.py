#!/usr/bin/env python3
"""
Parkiet multi-voice story test.

Tests narrator + character voices using [S1]-[S4] speaker tags
on the first 10 sentences from verhaal_galopperen_door_nederland.md.

Usage:
    source scripts/.venv/bin/activate
    PYTORCH_ENABLE_MPS_FALLBACK=1 python scripts/parkiet_test.py
"""

import os
import re
import subprocess
import sys
import time

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import torch
from transformers import AutoProcessor, DiaForConditionalGeneration

# ── Speaker mapping ──────────────────────────────────────────────────
# Parkiet generates a distinct voice per speaker tag.
# [S1] = Yulia (narrator + her dialogue)
# [S2] = Iliko
# [S3] = Alexander
# [S4] = Other characters (omroepstem, strangers)

SPEAKER_MAP = {
    "narrator": "S1",  # Yulia — narrates and speaks in first person
    "yulia": "S1",
    "ik": "S1",
    "iliko": "S2",
    "alexander": "S3",
    "hij": "S3",       # "hij" in this story = Alexander (context-dependent)
    "other": "S4",
}

MODEL_ID = "pevers/parkiet"
OUTPUT_DIR = "parkiet_test_audio"

# ── First 10 sentences with manual speaker assignment ────────────────
# Format: (speaker_key, clean_text)
# Dialogue sentences use the character's voice,
# narration uses the narrator's voice.

SENTENCES = [
    ("narrator", "Het is zaterdagochtend, negen uur..."),
    ("narrator", "Ik sta op het station in Hilversum met Iliko..."),
    ("narrator", "We willen naar Den Haag, winkelen, lekker eten, nieuwe kleren kopen..."),
    ("iliko",    "Waar gaan we eigenlijk naartoe?... vraagt Iliko voor de derde keer..."),
    ("yulia",    "Den Haag!... zeg ik... Dat heb ik al drie keer gezegd..."),
    ("narrator", "Maar het vertrek van onze trein is vertraagd..."),
    ("iliko",    "Hoe lang duurt het nog?... vraagt Iliko..."),
    ("narrator", "Ik kijk op m'n telefoon en zucht..."),
    ("yulia",    "Twintig minuten vertraging... zeg ik..."),
    ("iliko",    "Dat is echt irritant... zegt Iliko... Normaal vertrekt de intercity om kwart over negen..."),
]


def load_model():
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Device: {device}")

    processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = DiaForConditionalGeneration.from_pretrained(
        MODEL_ID, trust_remote_code=True, dtype=torch.float32
    ).to(device)

    print(f"Model loaded on {device}\n")
    return model, processor, device


def generate_sentence(model, processor, device, speaker_tag, text, out_path):
    """Generate audio for a single sentence with speaker tag."""
    prompt = f"[{speaker_tag}] {text}"
    inputs = processor(text=prompt, return_tensors="pt", padding=True).to(device)

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=1024,
            guidance_scale=3.0,
            temperature=1.8,
            top_p=0.90,
            top_k=50,
        )

    audio = processor.batch_decode(output)
    processor.save_audio(audio, out_path)


def concat_audio(file_list, output_path, pause_ms=500):
    """Concatenate MP3 files with pauses."""
    filter_parts = []
    inputs = []
    for i, f in enumerate(file_list):
        inputs.extend(["-i", f])
        filter_parts.append(f"[{i}:a]apad=pad_dur={pause_ms}ms[a{i}]")

    join = "".join(f"[a{i}]" for i in range(len(file_list)))
    filter_str = ";".join(filter_parts) + f";{join}concat=n={len(file_list)}:v=0:a=1[out]"

    subprocess.run(
        ["ffmpeg", "-y", *inputs, "-filter_complex", filter_str, "-map", "[out]", output_path],
        capture_output=True,
    )


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    model, processor, device = load_model()

    speaker_labels = {"S1": "Yulia/narrator", "S2": "Iliko", "S3": "Alexander", "S4": "Other"}

    files = []
    total_time = 0

    print("Generating 10 sentences with multi-voice...\n")
    for i, (speaker_key, text) in enumerate(SENTENCES, 1):
        speaker_tag = SPEAKER_MAP[speaker_key]
        label = speaker_labels[speaker_tag]
        out = os.path.join(OUTPUT_DIR, f"story_{i:02d}_{speaker_tag}.mp3")

        t0 = time.time()
        generate_sentence(model, processor, device, speaker_tag, text, out)
        elapsed = time.time() - t0
        total_time += elapsed
        files.append(out)

        print(f"  [{i:2d}/10] [{speaker_tag}={label:>16s}] {elapsed:5.1f}s  {text[:60]}...")

    print(f"\n  Total generation: {total_time:.0f}s")

    # Concatenate all into one file
    concat_path = os.path.join(OUTPUT_DIR, "story_multi_voice.mp3")
    concat_audio(files, concat_path, pause_ms=600)
    print(f"\n  → {concat_path}")

    # Also make single-voice version for comparison (all [S1])
    print("\nGenerating same 10 sentences with single voice [S1]...\n")
    files_single = []
    total_time = 0
    for i, (_, text) in enumerate(SENTENCES, 1):
        out = os.path.join(OUTPUT_DIR, f"story_{i:02d}_single.mp3")
        t0 = time.time()
        generate_sentence(model, processor, device, "S1", text, out)
        elapsed = time.time() - t0
        total_time += elapsed
        files_single.append(out)
        print(f"  [{i:2d}/10] [S1] {elapsed:5.1f}s")

    print(f"\n  Total generation: {total_time:.0f}s")

    concat_single = os.path.join(OUTPUT_DIR, "story_single_voice.mp3")
    concat_audio(files_single, concat_single, pause_ms=600)
    print(f"  → {concat_single}")

    print(f"\n{'='*60}")
    print("Compare:")
    print(f"  Multi-voice:  {concat_path}")
    print(f"  Single-voice: {concat_single}")
    print(f"\n  open {OUTPUT_DIR}/story_multi_voice.mp3")
    print(f"  open {OUTPUT_DIR}/story_single_voice.mp3")


if __name__ == "__main__":
    main()
