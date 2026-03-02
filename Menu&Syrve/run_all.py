#!/usr/bin/env python3
"""
run_all.py — Shishka Menu & Syrve pipeline launcher
=====================================================
Usage:
    python3 run_all.py            # generate TSVs + HTMLs only
    python3 run_all.py --upload   # generate + upload to Google Sheets

What it does:
    1. generate_tsvs.py      → all .tsv source files
    2. generate_operations.py → operational HTML tables
    3. generate_costing.py   → costing + modifier cost HTML tables
    4. upload_to_sheets.py   → (--upload only) push HTML tables to Google Sheets
"""

import subprocess
import sys
import os
import time

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD = "--upload" in sys.argv

PIPELINE = [
    ("generate_tsvs.py",       "Generating source TSVs"),
    ("generate_operations.py", "Generating operational HTML tables"),
    ("generate_costing.py",    "Generating costing HTML tables"),
]

if UPLOAD:
    PIPELINE.append(("upload_to_sheets.py", "Uploading to Google Sheets"))

# ── Runner ────────────────────────────────────────────────────────────────────
def run_step(script, description):
    path = os.path.join(SCRIPT_DIR, script)
    print(f"\n{'─'*60}")
    print(f"  ▶  {description}")
    print(f"     {script}")
    print(f"{'─'*60}")
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, path],
        cwd=SCRIPT_DIR,
        capture_output=True,
        text=True,
    )
    elapsed = time.time() - t0
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        print(f"\n❌  ERROR in {script} (exit {result.returncode}):")
        print(result.stderr.strip())
        sys.exit(1)
    print(f"  ✅ Done in {elapsed:.1f}s")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{'='*60}")
    print("  🥬  Shishka Menu & Syrve — Pipeline Runner")
    print(f"  Mode: {'generate + upload' if UPLOAD else 'generate only'}")
    print(f"{'='*60}")

    t_start = time.time()
    for script, desc in PIPELINE:
        run_step(script, desc)

    total = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"  🎉  Pipeline complete in {total:.1f}s")
    if not UPLOAD:
        print("  ℹ️   Run with --upload to push to Google Sheets:")
        print("       python3 run_all.py --upload")
    print(f"{'='*60}\n")
