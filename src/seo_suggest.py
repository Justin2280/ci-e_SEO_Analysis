"""
SEO-voorstellen (module 6): laat Claude per pagina zonder korte omschrijving een voorstel schrijven
voor de meta description en het focus-zoekwoord, op basis van de zichtbare paginatekst.
Toepassen gebeurt pas na expliciete bevestiging (JA in de CLI, of 'bevestig: JA' in de GitHub-workflow).

Stap 1 — voorstellen maken (leest de site, schrijft niets naar WordPress):
    python -m src.seo_suggest                     # alle pagina's/posts zonder omschrijving
    python -m src.seo_suggest --limit 5           # eerste 5
    python -m src.seo_suggest --ids 692,1042      # alleen deze WordPress-id's
    python -m src.seo_suggest --dry-run           # geen API-calls, voorbeeldvoorstellen
    → data/suggestions/seo-voorstellen-YYYY-MM-DD.json (+ .md om te beoordelen)

Stap 2 — beoordelen: lees de .md; pas eventueel teksten aan in de .json (veld "proposed_description").

Stap 3 — toepassen in Yoast (vereist WP_USERNAME/WP_APP_PASSWORD en de mu-plugin):
    python -m src.seo_suggest --apply data/suggestions/seo-voorstellen-YYYY-MM-DD.json
    python -m src.seo_suggest --apply ... --ids 692      # alleen deze pagina's
    python -m src.seo_suggest --apply ... --yes          # zonder JA-prompt (alleen voor de workflow met bevestiging)

Vereist in .env: ANTHROPIC_API_KEY (stap 1); optioneel SUGGEST_MODEL (standaard claude-opus-5).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from src.common import ROOT, now_iso, utf8_console

SUGGESTIONS = ROOT / "data" / "suggestions"
DESC_MIN, DESC_MAX = 110, 155
DEFAULT_MODEL = "claude-opus-5"

SYSTEM_PROMPT = (
    "Je bent een Nederlandse SEO-copywriter voor CI-Engineers, een civieltechnisch ingenieursbureau en "
    "detacheringsbureau uit Noord-Holland (constructeurs, ontwerpleiders, BIM-modelleurs; bruggen, kademuren, "
    "wegen, sluizen). Doelgroepen: opdrachtgevers (gemeenten, waterschappen, aannemers, ingenieursbureaus) en "
    "sollicitanten. Schrijf feitelijk en concreet, in de wij-vorm, zonder overdrijving of clickbait. "
    "Gebruik uitsluitend informatie uit de aangeleverde paginatekst; verzin geen projecten, cijfers of diensten."
)

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string",
                        "description": f"Meta description van {DESC_MIN}-{DESC_MAX} tekens, één of twee zinnen, "
                                       "Nederlands, met de belangrijkste zoekterm en (waar natuurlijk) CI-Engineers."},
        "focus_keyword": {"type": "string",
                          "description": "Het belangrijkste zoekwoord van deze pagina, 1-4 woorden, kleine letters."},
        "reason": {"type": "string", "description": "Eén zin: waarom deze omschrijving past bij de pagina."},
    },
    "required": ["description", "focus_keyword", "reason"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------- pure helpers
def select_pages(items: list[dict], ids: set[int] | None = None, limit: int | None = None) -> list[dict]:
    """Pagina's/posts zonder meta description (of expliciet gekozen id's)."""
    out = [m for m in items if (ids and m["id"] in ids) or (not ids and not (m.get("description") or "").strip())]
    out.sort(key=lambda m: (m["type"] != "pages", m["link"]))  # pagina's vóór posts
    return out[:limit] if limit else out


def build_prompt(meta: dict, page_text: str) -> str:
    return (
        f"Pagina: {meta['link']}\n"
        f"Titel in WordPress: {meta.get('wp_title') or '-'}\n"
        f"Huidige SEO-titel: {meta.get('title') or '-'}\n"
        f"Huidige omschrijving: {meta.get('description') or '(ontbreekt)'}\n\n"
        f"Zichtbare tekst van de pagina:\n\"\"\"\n{page_text}\n\"\"\"\n\n"
        f"Schrijf een meta description van {DESC_MIN}-{DESC_MAX} tekens en kies het focus-zoekwoord."
    )


def check_suggestion(desc: str) -> list[str]:
    """Waarschuwingen bij een voorstel (lengte, leestekens); leeg = in orde."""
    warn = []
    if len(desc) < DESC_MIN:
        warn.append(f"te kort ({len(desc)} < {DESC_MIN})")
    if len(desc) > DESC_MAX + 5:
        warn.append(f"te lang ({len(desc)} > {DESC_MAX})")
    if "\n" in desc:
        warn.append("bevat regeleinde")
    if desc.lower().startswith(("ontdek", "klik hier")):
        warn.append("clickbait-opening")
    return warn


def suggestions_markdown(rows: list[dict], day: date) -> str:
    out = [f"# SEO-voorstellen {day.strftime('%d-%m-%Y')}", "",
           f"{len(rows)} voorstellen voor pagina's zonder korte omschrijving (meta description). "
           "Beoordeel ze hieronder; teksten aanpassen kan in het .json-bestand (veld `proposed_description`). "
           "Toepassen: *Actions → SEO-voorstellen → toepassen* met bevestiging **JA**, of "
           "`python -m src.seo_suggest --apply <json>`.", ""]
    for r in rows:
        warn = ", ".join(r.get("warnings") or [])
        out += [f"## {r['wp_title'] or r['link']}  (id {r['id']}, {r['type']})", "",
                f"- Pagina: {r['link']}",
                f"- Focus-zoekwoord: **{r['focus_keyword']}**",
                f"- Voorstel ({len(r['proposed_description'])} tekens){' ⚠ ' + warn if warn else ''}:",
                "", f"> {r['proposed_description']}", "",
                f"- Waarom: {r.get('reason', '')}", ""]
        if r.get("applied_at"):
            out.append(f"- ✔ Toegepast op {r['applied_at']}")
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def parse_ids(text: str | None) -> set[int] | None:
    if not text:
        return None
    return {int(x) for x in text.replace(";", ",").split(",") if x.strip().isdigit()}


# ---------------------------------------------------------------- Claude
def ask_claude(meta: dict, page_text: str, model: str | None = None) -> dict:
    """Eén voorstel via de Anthropic API met gegarandeerd JSON-antwoord (output_config.format)."""
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model or os.getenv("SUGGEST_MODEL", DEFAULT_MODEL),
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_prompt(meta, page_text)}],
        output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude weigerde deze pagina (stop_reason=refusal)")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def fake_suggestion(meta: dict, page_text: str) -> dict:
    """Voor --dry-run en tests: geen API-call."""
    base = (meta.get("wp_title") or "deze pagina").strip()
    desc = (f"{base} van CI-Engineers: civieltechnisch ingenieursbureau en detachering van constructeurs "
            f"in Noord-Holland. Bekijk wat wij voor u kunnen doen.")
    return {"description": desc, "focus_keyword": base.lower()[:30], "reason": "dry-run voorbeeld"}


# ---------------------------------------------------------------- stap 1: voorstellen
def make_suggestions(pages: list[dict], fetch_text, suggest) -> list[dict]:
    rows = []
    for i, meta in enumerate(pages, 1):
        try:
            text = fetch_text(meta["link"])
            s = suggest(meta, text)
            desc = " ".join(s["description"].split())
            row = {**{k: meta.get(k, "") for k in ("id", "type", "link", "wp_title", "title", "description")},
                   "proposed_description": desc, "focus_keyword": s.get("focus_keyword", "").strip().lower(),
                   "reason": s.get("reason", ""), "warnings": check_suggestion(desc), "created": now_iso()}
            mark = "⚠" if row["warnings"] else "✔"
            print(f"[{i}/{len(pages)}] {mark} {meta['link']}  ({len(desc)} tekens)")
        except Exception as e:  # één mislukte pagina mag de rest niet stoppen
            row = {**{k: meta.get(k, "") for k in ("id", "type", "link", "wp_title", "title", "description")},
                   "proposed_description": "", "focus_keyword": "", "reason": "", "warnings": [f"mislukt: {e}"],
                   "created": now_iso()}
            print(f"[{i}/{len(pages)}] ✘ {meta['link']}: {e}", file=sys.stderr)
        rows.append(row)
    return rows


def save_suggestions(rows: list[dict], day: date | None = None) -> tuple[Path, Path]:
    day = day or date.today()
    SUGGESTIONS.mkdir(parents=True, exist_ok=True)
    js = SUGGESTIONS / f"seo-voorstellen-{day.isoformat()}.json"
    md = SUGGESTIONS / f"seo-voorstellen-{day.isoformat()}.md"
    js.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    md.write_text(suggestions_markdown(rows, day), encoding="utf-8")
    return js, md


def latest_suggestions_file() -> Path | None:
    files = sorted(SUGGESTIONS.glob("seo-voorstellen-????-??-??.json"))
    return files[-1] if files else None


# ---------------------------------------------------------------- stap 3: toepassen
def apply_suggestions(path: Path, ids: set[int] | None, confirm, wp=None) -> int:
    """Schrijft voorstellen naar Yoast. confirm() wordt één keer aangeroepen met de diff en moet True geven."""
    from src.wp_client import WPClient, seo_diff

    rows = json.loads(path.read_text(encoding="utf-8"))
    todo = [r for r in rows if r.get("proposed_description") and not r.get("applied_at")
            and (not ids or r["id"] in ids)]
    if not todo:
        print("Niets toe te passen (geen open voorstellen voor deze selectie).")
        return 0
    diffs = [seo_diff(r, {"description": r["proposed_description"], "focus_keyword": r["focus_keyword"]}) for r in todo]
    print("\n".join(d for d in diffs if d))
    print(f"\n{len(todo)} pagina's worden aangepast in Yoast (meta description + focus-zoekwoord).")
    if not confirm():
        print("Geannuleerd, niets gewijzigd.")
        return 0
    wp = wp or WPClient()
    done = 0
    for r in todo:
        try:
            wp.write_seo_meta(r["type"], r["id"], {"description": r["proposed_description"],
                                                 "focus_keyword": r["focus_keyword"]}, confirm=True)
            r["applied_at"] = now_iso()
            done += 1
            print(f"✔ {r['link']}")
        except Exception as e:
            r["warnings"] = (r.get("warnings") or []) + [f"toepassen mislukt: {e}"]
            print(f"✘ {r['link']}: {e}", file=sys.stderr)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    path.with_suffix(".md").write_text(suggestions_markdown(rows, date.fromisoformat(path.stem[-10:])), encoding="utf-8")
    print(f"\n{done}/{len(todo)} toegepast; bijgewerkt: {path.name}")
    return done


# ---------------------------------------------------------------- CLI
if __name__ == "__main__":
    utf8_console()
    ap = argparse.ArgumentParser(description="SEO-voorstellen maken (Claude) en na bevestiging toepassen in Yoast")
    ap.add_argument("--dry-run", action="store_true", help="geen API-calls; voorbeeldvoorstellen op fixtures")
    ap.add_argument("--limit", type=int, help="maximaal aantal pagina's")
    ap.add_argument("--ids", help="alleen deze WordPress-id's, komma-gescheiden")
    ap.add_argument("--apply", metavar="JSON", nargs="?", const="latest",
                    help="voorstellen uit dit bestand toepassen (zonder pad: het nieuwste bestand)")
    ap.add_argument("--yes", action="store_true", help="geen JA-prompt bij --apply (alleen met expliciete bevestiging elders)")
    args = ap.parse_args()
    ids = parse_ids(args.ids)

    if args.apply:
        path = latest_suggestions_file() if args.apply == "latest" else Path(args.apply)
        if not path or not path.exists():
            print("[fout] Geen voorstellenbestand gevonden; maak eerst voorstellen.", file=sys.stderr)
            sys.exit(1)
        confirm = (lambda: True) if args.yes else (lambda: input("Typ JA om dit naar de live site te schrijven: ").strip() == "JA")
        apply_suggestions(path, ids, confirm)
        sys.exit(0)

    if args.dry_run:
        from src.seo_audit import FIXTURES, extract_text
        pages = [{"id": 1, "type": "pages", "link": "https://ci-engineers.com/contact/", "wp_title": "Contact",
                  "title": "Contact - CI Engineers", "description": ""},
                 {"id": 2, "type": "pages", "link": "https://ci-engineers.com/werken-bij-ci/", "wp_title": "Werken bij CI",
                  "title": "", "description": ""}]
        fx = (FIXTURES / "page_ok.html").read_text(encoding="utf-8")
        rows = make_suggestions(select_pages(pages, ids, args.limit), lambda url: extract_text(fx), fake_suggestion)
    else:
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("[fout] ANTHROPIC_API_KEY ontbreekt in .env", file=sys.stderr)
            sys.exit(1)
        from src.seo_audit import extract_text, fetch_page, make_session
        from src.wp_client import WPClient

        session = make_session()
        wp = WPClient()
        pages = select_pages(wp.all_seo_meta(), ids, args.limit)
        print(f"{len(pages)} pagina's zonder omschrijving; voorstellen maken met {os.getenv('SUGGEST_MODEL', DEFAULT_MODEL)}…")
        rows = make_suggestions(pages, lambda url: extract_text(fetch_page(url, session)[1]), ask_claude)

    if not rows:
        print("Geen pagina's zonder omschrijving gevonden.")
        sys.exit(0)
    js, md = save_suggestions(rows)
    print(f"\nOpgeslagen: {js}\nBeoordelen: {md}")
