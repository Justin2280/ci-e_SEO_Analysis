"""
Gedeelde helpers voor alle modules: paden, JSONL-opslag, run-historie en console-encoding.

Bestandsnaamgeving in data/results/:
    <module>-YYYY-MM-DD.jsonl      (seo_audit, search_console)
    YYYY-MM-DD.jsonl               (ai_visibility, oud formaat — blijft ondersteund)
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "data" / "results"
REPORTS = ROOT / "data" / "reports"

load_dotenv(ROOT / ".env")

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\.jsonl$")


def utf8_console() -> None:
    """Zorg dat ✔/✘ e.d. niet crashen op een Windows-console (cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def results_path(prefix: str, day: date | None = None) -> Path:
    """Pad van het JSONL-bestand voor een module op een dag.
    ai_visibility gebruikt het oude formaat zonder prefix."""
    day = day or date.today()
    name = f"{day.isoformat()}.jsonl" if prefix == "ai_visibility" else f"{prefix}-{day.isoformat()}.jsonl"
    return RESULTS / name


def save_jsonl(rows: list[dict], prefix: str) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = results_path(prefix)
    with out.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return out


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_runs(prefix: str, n: int = 2, results_dir: Path | None = None) -> list[tuple[date, list[dict]]]:
    """Nieuwste n runs van een module, nieuwste eerst: [(datum, rijen), ...]."""
    results_dir = results_dir or RESULTS
    if not results_dir.exists():
        return []
    pattern = "????-??-??.jsonl" if prefix == "ai_visibility" else f"{prefix}-????-??-??.jsonl"
    files = sorted(results_dir.glob(pattern), reverse=True)[:n]
    runs = []
    for p in files:
        m = _DATE_RE.search(p.name)
        if m:
            runs.append((date.fromisoformat(m.group(1)), read_jsonl(p)))
    return runs
