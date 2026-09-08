"""
Gedeelde helpers voor alle modules: paden, JSONL-opslag, run-historie en console-encoding.

Bestandsnaamgeving in data/results/:
    <module>-YYYY-MM-DD.jsonl      (seo_audit, search_console)
    YYYY-MM-DD.jsonl               (ai_visibility, oud formaat — blijft ondersteund)
Eén bestand = één run; een herhaalde run op dezelfde dag vervangt het bestand.
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
    """Schrijft de rijen van één run naar het dagbestand. Een tweede run op dezelfde dag
    overschrijft de eerste (anders telt het weekrapport alles dubbel)."""
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = results_path(prefix)
    with out.open("w", encoding="utf-8") as f:
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


# ---------------------------------------------------------------- .env-check
ENV_KEYS: dict[str, list[str]] = {
    "ai_visibility (minimaal één provider)": ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"],
    "search_console": ["GSC_SERVICE_ACCOUNT_FILE", "GSC_SITE_URL"],
    "wp_client (schrijven)": ["WP_USERNAME", "WP_APP_PASSWORD"],
    "report --email (Microsoft 365 / Graph)": ["MS_TENANT_ID", "MS_CLIENT_ID", "MS_CLIENT_SECRET",
                                              "REPORT_EMAIL_FROM", "REPORT_EMAIL_TO"],
    "report --email (SMTP, alternatief)": ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "REPORT_EMAIL_TO"],
}


def missing_keys(env: dict[str, str]) -> dict[str, list[str]]:
    """Per module de ontbrekende .env-sleutels (lege waarde telt als ontbrekend).
    Voor ai_visibility geldt: één provider is genoeg."""
    out: dict[str, list[str]] = {}
    for module, keys in ENV_KEYS.items():
        missing = [k for k in keys if not (env.get(k) or "").strip()]
        if module.startswith("ai_visibility") and len(missing) < len(keys):
            missing = []
        if module.startswith("report --email"):
            graph_ok = all((env.get(k) or "").strip() for k in ENV_KEYS["report --email (Microsoft 365 / Graph)"])
            smtp_ok = all((env.get(k) or "").strip() for k in ENV_KEYS["report --email (SMTP, alternatief)"])
            if graph_ok or smtp_ok:
                missing = []  # één van de twee routes is genoeg
        if module == "search_console" and (env.get("GSC_SERVICE_ACCOUNT_JSON") or "").strip():
            missing = [k for k in missing if k != "GSC_SERVICE_ACCOUNT_FILE"]  # inhoud via env (GitHub Actions)
        elif module == "search_console" and "GSC_SERVICE_ACCOUNT_FILE" not in missing:
            path = Path(env["GSC_SERVICE_ACCOUNT_FILE"])
            if not (path if path.is_absolute() else ROOT / path).exists():
                missing.append("GSC_SERVICE_ACCOUNT_FILE (bestand niet gevonden)")
        out[module] = missing
    return out


def check_env() -> bool:
    """Print per module of de .env compleet is; True als alles klaarstaat."""
    import os

    env_file = ROOT / ".env"
    print(f".env: {'gevonden' if env_file.exists() else 'ONTBREEKT (kopieer .env.example naar .env)'}")
    report = missing_keys(dict(os.environ))
    in_actions = bool(os.getenv("GITHUB_ACTIONS"))
    for module, missing in report.items():
        if in_actions and module.startswith("wp_client"):
            print(f"– {module:38s} niet nodig in GitHub Actions (alleen lokaal, schrijven gebeurt handmatig)")
            report[module] = []
            continue
        mark = "✔" if not missing else "✘"
        print(f"{mark} {module:38s} {'klaar' if not missing else 'ontbreekt: ' + ', '.join(missing)}")
    print("Modules seo_audit en wp_client (lezen) hebben geen keys nodig.")
    return not any(report.values())


if __name__ == "__main__":
    import argparse

    utf8_console()
    ap = argparse.ArgumentParser(description="Gedeelde helpers; --check-env controleert de .env")
    ap.add_argument("--check-env", action="store_true")
    args = ap.parse_args()
    if args.check_env:
        sys.exit(0 if check_env() else 1)
    ap.print_help()
