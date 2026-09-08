"""
AI-zichtbaarheidscheck voor ci-engineers.com.

Stelt de vragen uit config/queries.yaml aan OpenAI, Claude en Gemini en logt:
- of CI-Engineers genoemd wordt
- welke concurrenten genoemd worden
- het volledige antwoord (voor latere analyse)

Gebruik:
    python -m src.ai_visibility            # echte run
    python -m src.ai_visibility --dry-run  # geen API-calls, test de pipeline
    python -m src.ai_visibility --providers openai,anthropic
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

from src.common import ROOT, now_iso, save_jsonl, utf8_console

CONFIG = ROOT / "config" / "queries.yaml"

SYSTEM_PROMPT = (
    "Je bent een behulpzame assistent. Beantwoord de vraag zoals je dat voor een "
    "gewone gebruiker zou doen: noem concrete bedrijfsnamen waar je die kent."
)


# ---------------------------------------------------------------- providers
def ask_openai(question: str) -> str:
    from openai import OpenAI

    client = OpenAI()
    r = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": question}],
    )
    return r.choices[0].message.content or ""


def ask_anthropic(question: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    r = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}],
    )
    return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")


def ask_gemini(question: str) -> str:
    from google import genai

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    r = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
        contents=f"{SYSTEM_PROMPT}\n\n{question}",
    )
    return r.text or ""


PROVIDERS = {
    "openai": ("OPENAI_API_KEY", ask_openai),
    "anthropic": ("ANTHROPIC_API_KEY", ask_anthropic),
    "gemini": ("GEMINI_API_KEY", ask_gemini),
}


# ---------------------------------------------------------------- analyse
def mentioned(text: str, names: list[str]) -> list[str]:
    """Geeft de namen terug die (hoofdletterongevoelig, als los woord) in text voorkomen."""
    hits = []
    for name in names:
        pattern = r"(?<![\w-])" + re.escape(name) + r"(?![\w-])"
        if re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(name)
    return hits


# ---------------------------------------------------------------- main
def run(providers: list[str], dry_run: bool) -> list[dict]:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    brand = cfg["brand_aliases"]
    competitors = cfg["competitors"]
    rows = []

    for prov in providers:
        env_key, fn = PROVIDERS[prov]
        if not dry_run and not os.getenv(env_key):
            print(f"[skip] {prov}: {env_key} niet gezet", file=sys.stderr)
            continue
        for item in cfg["queries"]:
            q = item["q"]
            error = ""
            if dry_run:
                answer = f"(dry-run) Voorbeeldantwoord waarin Sweco en CI-Engineers genoemd worden."
            else:
                try:
                    answer = fn(q)
                except Exception as e:  # provider-fout mag de run niet stoppen
                    answer, error = "", str(e)[:200]
                    print(f"[error] {prov} / {q[:50]}…: {e}", file=sys.stderr)
            rows.append({
                "ts": now_iso(),
                "module": "ai_visibility",
                "provider": prov,
                "tag": item["tag"],
                "query": q,
                "brand_mentioned": bool(mentioned(answer, brand)),
                "competitors_mentioned": mentioned(answer, competitors),
                "answer": answer,
                "error": error,
            })
            mark = "!" if error else ("✔" if rows[-1]["brand_mentioned"] else "✘")
            print(f"[{prov}] {mark}  {q[:70]}")
    return rows


def save(rows: list[dict]) -> Path:
    return save_jsonl(rows, "ai_visibility")


def summary(rows: list[dict]) -> None:
    print("\n=== Samenvatting ===")
    for prov in sorted({r["provider"] for r in rows}):
        sub = [r for r in rows if r["provider"] == prov]
        ok = [r for r in sub if not r.get("error")]
        hits = sum(r["brand_mentioned"] for r in ok)
        errs = f"  ({len(sub) - len(ok)} fouten)" if len(ok) < len(sub) else ""
        print(f"{prov:10s} CI-Engineers genoemd in {hits}/{len(ok)} antwoorden{errs}")
    counts: dict[str, int] = {}
    for r in rows:
        for c in r["competitors_mentioned"]:
            counts[c] = counts.get(c, 0) + 1
    if counts:
        print("Meest genoemde concurrenten:",
              ", ".join(f"{k} ({v})" for k, v in sorted(counts.items(), key=lambda x: -x[1])))


if __name__ == "__main__":
    utf8_console()
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--providers", default=",".join(PROVIDERS),
                    help="komma-gescheiden: openai,anthropic,gemini")
    args = ap.parse_args()
    provs = [p.strip() for p in args.providers.split(",") if p.strip() in PROVIDERS]
    rows = run(provs, args.dry_run)
    if rows:
        path = save(rows)
        summary(rows)
        print(f"\nOpgeslagen in {path}")
