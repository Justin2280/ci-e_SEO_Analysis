"""
Wekelijks rapport (module 5): combineert de nieuwste runs van
ai_visibility, seo_audit en search_console tot één rapport voor de directie.

Opbouw (gewone taal, geen jargon zonder uitleg):
    1. In het kort          — drie tot vijf zinnen met de belangrijkste cijfers en de trend
    2. Wat gaan we doen     — concrete acties, afgeleid uit de data, in volgorde van belang
    3. De cijfers           — AI-assistenten, Google, website-check (tabellen met ▲/▼)
    4. Uitleg van de termen

Output: data/reports/weekrapport-YYYY-MM-DD.md (markdown) en dezelfde inhoud als HTML-mail.

Vereist voor --email in .env (één van beide):
    Microsoft 365 / Exchange Online via Graph API (aanbevolen, app-registratie in Entra):
        MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET, REPORT_EMAIL_FROM (mailbox), REPORT_EMAIL_TO
    Klassiek SMTP (basic auth; op Exchange Online eind 2026 standaard uit):
        SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, REPORT_EMAIL_FROM, REPORT_EMAIL_TO

Gebruik:
    python -m src.report              # schrijft data/reports/weekrapport-YYYY-MM-DD.md (+ .html)
    python -m src.report --dry-run    # voorbeelddata, alleen naar stdout
    python -m src.report --email      # ook mailen
    python -m src.report --email-only # alleen het rapport van vandaag mailen
"""
from __future__ import annotations

import argparse
import html
import os
import re
import smtplib
import sys
from datetime import date, timedelta
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse

from src.common import REPORTS, load_runs, utf8_console

Run = tuple[date, list[dict]] | None
BRAND = "CI-Engineers"
PAGES = "pagina's"


# ---------------------------------------------------------------- pure helpers
def delta(cur: float | None, prev: float | None, decimals: int = 0, invert: bool = False) -> str:
    """Verschil als tekst: '+3 ▲', '−0.4 ▼', '±0' of '' zonder vorige waarde.
    invert=True: lager is beter (bijv. positie), dan krijgt een daling een ▲."""
    if cur is None or prev is None:
        return ""
    d = round(cur - prev, decimals)
    if d == 0:
        return "±0"
    better = (d < 0) if invert else (d > 0)
    sign = "+" if d > 0 else "−"
    val = f"{abs(d):.{decimals}f}"
    return f"{sign}{val} {'▲' if better else '▼'}"


def pct(n: int, total: int) -> float | None:
    return round(100 * n / total) if total else None


def _run(run: Run) -> tuple[date | None, list[dict]]:
    return (run[0], run[1]) if run else (None, [])


def _path(url: str) -> str:
    return urlparse(url).path or "/"


def _norm(url: str) -> str:
    return url.rstrip("/").lower()


def n_(count: int, singular: str, plural: str) -> str:
    """'1 pagina' / '3 pagina's'."""
    return f"{count} {singular if count == 1 else plural}"


def trend_words(cur: float | None, prev: float | None, invert: bool = False, unit: str = "") -> str:
    """'meer dan vorige keer (+3)', 'minder dan vorige keer (−2)', 'gelijk aan vorige keer' of ''."""
    if cur is None or prev is None:
        return ""
    d = round(cur - prev, 1)
    if d == 0:
        return "gelijk aan vorige keer"
    better = (d < 0) if invert else (d > 0)
    word = "beter" if better else "slechter"
    sign = "+" if d > 0 else "−"
    return f"{word} dan vorige keer: {sign}{abs(d):g}{unit}"


# ---------------------------------------------------------------- kerncijfers per module
def ai_stats(rows: list[dict]) -> dict:
    ok = [r for r in rows if not r.get("error")]
    hits = sum(1 for r in ok if r["brand_mentioned"])
    counts: dict[str, int] = {}
    for r in ok:
        for c in r["competitors_mentioned"]:
            counts[c] = counts.get(c, 0) + 1
    return {"answers": len(ok), "hits": hits, "errors": len(rows) - len(ok), "pct": pct(hits, len(ok)),
            "competitors": sorted(counts.items(), key=lambda x: -x[1]),
            "providers": sorted({r["provider"] for r in rows})}


def seo_stats(rows: list[dict]) -> dict:
    ok = [r for r in rows if r.get("status") == 200]
    return {
        "pages": len(rows),
        "issues": sum(len(r.get("issues", [])) for r in rows),
        "no_desc": [r for r in ok if not r.get("meta_description")],
        "no_h1": [r for r in ok if not r.get("h1")],
        "no_alt": sum(r.get("images_without_alt", 0) for r in rows),
        "slow": [r for r in ok if r.get("load_ms", 0) > 2000],
        "load": round(sum(r["load_ms"] for r in ok) / len(ok)) if ok else None,
        "errors": [r for r in rows if r.get("status") != 200],
    }


def gsc_stats(rows: list[dict]) -> dict:
    q = [r for r in rows if r["dimensions"] == "query"]
    pages = [r for r in rows if r["dimensions"] == "page"]
    imps = sum(r["impressions"] for r in q)
    return {
        "queries": q, "pages": pages,
        "clicks": sum(r["clicks"] for r in q), "imps": imps,
        "pos": round(sum(r["position"] * r["impressions"] for r in q) / imps, 1) if imps else None,
        "period": (q[0]["period_start"], q[0]["period_end"]) if q else None,
        "page_imps": {_norm(r["page"]): r["impressions"] for r in pages if r.get("page")},
    }


# ---------------------------------------------------------------- 1. In het kort
def summary_section(ai: Run, ai_prev: Run, seo: Run, seo_prev: Run, gsc: Run, gsc_prev: Run) -> list[str]:
    out = ["## In het kort", ""]
    _, ai_rows = _run(ai)
    _, seo_rows = _run(seo)
    _, gsc_rows = _run(gsc)
    if not (ai_rows or seo_rows or gsc_rows):
        return out + ["Er is nog geen data. Zodra de wekelijkse run heeft gedraaid, staat hier de samenvatting.", ""]

    if ai_rows:
        a, ap = ai_stats(ai_rows), ai_stats(_run(ai_prev)[1])
        if a["answers"]:
            t = trend_words(a["pct"], ap["pct"] if ap["answers"] else None, unit="%")
            times = "niet één keer" if a["hits"] == 0 else f"{a['hits']} keer"
            line = (f"**AI-assistenten**: we stelden {a['answers']} vragen aan ChatGPT, Claude en Gemini "
                    f"(zoals een opdrachtgever of sollicitant ze zou stellen). {BRAND} werd {times} genoemd")
            line += f" ({a['pct']}%), {t}." if t else f" ({a['pct']}%)."
            if a["competitors"]:
                top = ", ".join(f"{k} ({v}×)" for k, v in a["competitors"][:3])
                line += f" Concurrenten die wél genoemd worden: {top}."
            out.append(f"- {line}")
        if a["errors"]:
            out.append(f"- Let op: {a['errors']} vragen konden niet gesteld worden door een storing bij een AI-dienst; "
                       f"die tellen niet mee.")

    if gsc_rows:
        g, gp = gsc_stats(gsc_rows), gsc_stats(_run(gsc_prev)[1])
        t_imps = trend_words(g["imps"], gp["imps"] if gp["queries"] else None)
        t_pos = trend_words(g["pos"], gp["pos"] if gp["queries"] else None, invert=True)
        page_nr = f"pagina {int((g['pos'] - 1) // 10) + 1}" if g["pos"] else "-"
        line = (f"**Google**: onze site verscheen {g['imps']} keer in de zoekresultaten"
                f"{', ' + t_imps if t_imps else ''}, en kreeg daaruit {n_(g['clicks'], 'klik', 'klikken')}. "
                f"Gemiddeld staan we op plek {g['pos']}, dat is ongeveer {page_nr} van Google"
                f"{', ' + t_pos if t_pos else ''}. ")
        line += "Bezoekers klikken zelden verder dan pagina 1; hier valt de meeste winst te halen." if (g["pos"] or 0) > 10 \
            else "Dat is de eerste pagina, precies waar we willen staan."
        out.append(f"- {line}")

    if seo_rows:
        s, sp = seo_stats(seo_rows), seo_stats(_run(seo_prev)[1])
        t = trend_words(s["issues"], sp["issues"] if sp["pages"] else None, invert=True)
        line = (f"**Website**: {n_(s['pages'], 'pagina', PAGES)} gecontroleerd, "
                f"{n_(s['issues'], 'verbeterpunt', 'verbeterpunten')} gevonden{', ' + t if t else ''}. "
                f"Belangrijkste: {n_(len(s['no_desc']), 'pagina mist', PAGES + ' missen')} de korte omschrijving "
                f"die Google onder de link toont, en {n_(s['no_alt'], 'afbeelding heeft', 'afbeeldingen hebben')} "
                f"geen beschrijving.")
        out.append(f"- {line}")
    return out + [""]


# ---------------------------------------------------------------- 2. Wat gaan we doen
def actions_section(ai: Run, seo: Run, gsc: Run) -> list[str]:
    out = ["## Wat gaan we doen", "",
           "Acties in volgorde van belang, afgeleid uit de cijfers hieronder.", ""]
    _, ai_rows = _run(ai)
    _, seo_rows = _run(seo)
    _, gsc_rows = _run(gsc)
    actions: list[str] = []
    s = seo_stats(seo_rows) if seo_rows else None
    g = gsc_stats(gsc_rows) if gsc_rows else None

    if s and s["no_desc"]:
        # Prioriteit: pagina's die Google al toont (impressies), daarna korte paden (home, diensten, contact ...)
        def prio(r):
            imps = (g or {}).get("page_imps", {}).get(_norm(r["url"]), 0) if g else 0
            depth = _path(r["url"]).strip("/").count("/")
            is_post = "/20" in r["url"] or depth >= 1 and "werken-bij" not in r["url"]
            return (-imps, depth, is_post, r["url"])
        top = sorted(s["no_desc"], key=prio)[:5]
        pages = ", ".join(f"[{_path(r['url'])}]({r['url']})" for r in top)
        actions.append(
            f"**Korte omschrijvingen schrijven** voor {n_(len(s['no_desc']), 'pagina', PAGES)} (de tekst van 1–2 zinnen die Google onder "
            f"de link toont; nu verzint Google er zelf iets). Begin met: {pages}. "
            f"Voorstellen kunnen automatisch gemaakt worden: *Actions → SEO-voorstellen*.")

    if g:
        weak = [r for r in g["pages"] if r["impressions"] >= 20 and r["ctr"] < 0.01]
        if weak:
            pages = ", ".join(f"[{_path(r['page'])}]({r['page']}) ({r['impressions']}× getoond, plek {r['position']})"
                              for r in sorted(weak, key=lambda r: -r["impressions"])[:3])
            actions.append(f"**Titel en omschrijving aantrekkelijker maken** van pagina's die Google wel toont maar "
                           f"waar niemand op klikt: {pages}.")
        chances = [r for r in g["queries"] if 3 < r["position"] <= 20 and r["impressions"] >= 3]
        if chances:
            words = ", ".join(f"\"{r['query']}\" (plek {r['position']})"
                              for r in sorted(chances, key=lambda r: (r["position"], -r["impressions"]))[:5])
            actions.append(f"**Kansrijke zoekwoorden uitbouwen**: hierop staan we net onder de top, een betere pagina "
                           f"kan ons naar pagina 1 brengen: {words}.")
        top_q = sorted(g["queries"], key=lambda r: -r["impressions"])[:3]
        if top_q and all(r["clicks"] == 0 for r in top_q):
            words = ", ".join(f"\"{r['query']}\" (plek {r['position']})" for r in top_q)
            actions.append(f"**Een sterke pagina maken voor de meest gezochte termen** waarop we nu ver weg staan: "
                           f"{words}. Denk aan een duidelijke dienstenpagina met die woorden in de titel.")

    if ai_rows:
        a = ai_stats(ai_rows)
        if a["answers"] and (a["pct"] or 0) < 30:
            comp = ", ".join(k for k, _ in a["competitors"][:3]) or "grote bureaus"
            actions.append(
                f"**Zorgen dat AI-assistenten ons kennen**: ze noemen nu {comp}, niet ons. AI's halen hun kennis uit "
                f"duidelijke webteksten en vermeldingen elders. Concreet: (1) een pagina per dienst met de vraag als kop "
                f"(bijv. \"Constructeurs detacheren in Noord-Holland\"), (2) vermelding op branchesites zoals "
                f"NLingenieurs en in bedrijvengidsen, (3) nieuwsberichten over projecten met {BRAND} voluit in de tekst.")

    if s:
        if s["no_h1"]:
            pages = ", ".join(f"[{_path(r['url'])}]({r['url']})" for r in s["no_h1"][:4])
            actions.append(f"**Hoofdkop toevoegen** op {n_(len(s['no_h1']), 'pagina', PAGES)} zonder duidelijke titel bovenaan "
                           f"(voor Google én bezoekers): {pages}.")
        if s["no_alt"]:
            actions.append(f"**Beschrijvingen bij afbeeldingen** ({n_(s['no_alt'], 'stuk', 'stuks')}): in WordPress bij elke foto een "
                           f"korte 'alt-tekst' invullen, bijv. \"Kademuur Amaliahaven tijdens de bouw\". Goed voor Google "
                           f"Afbeeldingen en verplicht voor toegankelijkheid.")
        if s["slow"]:
            actions.append(f"**Trage pagina's versnellen** ({len(s['slow'])} pagina's laden langer dan 2 seconden).")
        if s["errors"]:
            actions.append(f"**Kapotte pagina's herstellen**: {len(s['errors'])} pagina's uit de sitemap geven een fout.")

    if not actions:
        actions.append("Geen dringende acties: alles ziet er goed uit. Volgende week kijken we naar de trend.")
    out += [f"{i}. {a}" for i, a in enumerate(actions, 1)]
    return out + [""]


# ---------------------------------------------------------------- 3. De cijfers
def ai_section(cur: Run, prev: Run) -> list[str]:
    day, rows = _run(cur)
    _, prev_rows = _run(prev)
    out = ["### Wat AI-assistenten over ons zeggen", ""]
    if not rows:
        return out + ["Geen data. Draai `python -m src.ai_visibility`.", ""]
    out.append(f"Gemeten op {day}. Per AI-dienst: in hoeveel antwoorden wordt {BRAND} genoemd?")
    out += ["", "| AI-dienst | Genoemd | Vorige keer |", "|---|---|---|"]
    ok_rows = [r for r in rows if not r.get("error")]
    errors = len(rows) - len(ok_rows)
    names = {"openai": "ChatGPT (OpenAI)", "anthropic": "Claude (Anthropic)", "gemini": "Gemini (Google)"}
    for prov in sorted({r["provider"] for r in rows}):
        sub = [r for r in ok_rows if r["provider"] == prov]
        n_err = sum(1 for r in rows if r["provider"] == prov and r.get("error"))
        psub = [r for r in prev_rows if r["provider"] == prov and not r.get("error")]
        hits = sum(1 for r in sub if r["brand_mentioned"])
        cur_pct = pct(hits, len(sub))
        prev_pct = pct(sum(1 for r in psub if r["brand_mentioned"]), len(psub)) if psub else None
        shown = f"{hits} van {len(sub)} ({cur_pct}%)" if sub else "geen antwoorden"
        note = f" ⚠ {n_err} storingen" if n_err else ""
        out.append(f"| {names.get(prov, prov)} | {shown}{note} | {delta(cur_pct, prev_pct) or '-'} |")
    if errors:
        first = next(r["error"] for r in rows if r.get("error"))
        out.append(f"\n⚠ {errors} vragen konden niet gesteld worden (storing bij de AI-dienst, niet meegeteld). "
                   f"Melding: {first[:100]}")
    for tag in sorted({r["tag"] for r in rows}):
        sub = [r for r in ok_rows if r["tag"] == tag]
        label = {"opdrachtgever": "Vragen van opdrachtgevers", "personeel": "Vragen van sollicitanten"}.get(tag, tag)
        out.append(f"\n- {label}: genoemd in {sum(1 for r in sub if r['brand_mentioned'])} van {len(sub)}")
    a = ai_stats(rows)
    if a["competitors"]:
        out += ["", "Concurrenten die de AI's wél noemen: " + ", ".join(f"{k} ({v}×)" for k, v in a["competitors"][:5])]
    return out + [""]


def seo_section(cur: Run, prev: Run) -> list[str]:
    day, rows = _run(cur)
    _, prev_rows = _run(prev)
    out = ["### Hoe onze website ervoor staat", ""]
    if not rows:
        return out + ["Geen data. Draai `python -m src.seo_audit`.", ""]
    s, p = seo_stats(rows), (seo_stats(prev_rows) if prev_rows else None)
    out.append(f"Gemeten op {day}: {s['pages']} pagina's automatisch gecontroleerd.")
    out += ["", "| Wat | Nu | Vorige keer |", "|---|---|---|",
            f"| Verbeterpunten totaal | {s['issues']} | {delta(s['issues'], p['issues'] if p else None, invert=True) or '-'} |",
            f"| Pagina's zonder korte omschrijving voor Google | {len(s['no_desc'])} | {delta(len(s['no_desc']), len(p['no_desc']) if p else None, invert=True) or '-'} |",
            f"| Pagina's zonder hoofdkop | {len(s['no_h1'])} | {delta(len(s['no_h1']), len(p['no_h1']) if p else None, invert=True) or '-'} |",
            f"| Afbeeldingen zonder beschrijving | {s['no_alt']} | {delta(s['no_alt'], p['no_alt'] if p else None, invert=True) or '-'} |",
            f"| Gemiddelde laadtijd | {s['load']} ms | {delta(s['load'], p['load'] if p else None, invert=True) or '-'} |"]
    worst = sorted((r for r in rows if r.get("issues")), key=lambda r: -len(r["issues"]))[:5]
    if worst:
        out += ["", "Pagina's met de meeste verbeterpunten:"]
        out += [f"- [{_path(r['url'])}]({r['url']}): {'; '.join(r['issues'][:3])}" for r in worst]
    return out + [""]


def gsc_section(cur: Run, prev: Run) -> list[str]:
    day, rows = _run(cur)
    _, prev_rows = _run(prev)
    out = ["### Hoe Google ons vindt", ""]
    g = gsc_stats(rows) if rows else None
    if not g or not g["queries"]:
        return out + ["Geen data. Draai `python -m src.search_console`.", ""]
    gp = gsc_stats(prev_rows) if prev_rows else None
    out.append(f"Periode {g['period'][0]} t/m {g['period'][1]} (Google loopt enkele dagen achter).")
    out += ["", "| Wat | Nu | Vorige keer |", "|---|---|---|",
            f"| Keer getoond in Google | {g['imps']} | {delta(g['imps'], gp['imps'] if gp and gp['queries'] else None) or '-'} |",
            f"| Klikken naar onze site | {g['clicks']} | {delta(g['clicks'], gp['clicks'] if gp and gp['queries'] else None) or '-'} |",
            f"| Gemiddelde plek (1 = bovenaan) | {g['pos']} | {delta(g['pos'], gp['pos'] if gp and gp['queries'] else None, 1, invert=True) or '-'} |",
            "", "Waar mensen op zoeken als ze ons te zien krijgen (top 10):", "",
            "| Zoekwoord | Klikken | Getoond | Plek | Verschil plek |", "|---|---|---|---|---|"]
    prev_pos = {r["query"]: r["position"] for r in (gp["queries"] if gp else [])}
    for r in sorted(g["queries"], key=lambda r: (-r["clicks"], -r["impressions"]))[:10]:
        out.append(f"| {r['query']} | {r['clicks']} | {r['impressions']} | {r['position']} "
                   f"| {delta(r['position'], prev_pos.get(r['query']), 1, invert=True) or '-'} |")
    movers = [(r["query"], r["position"], prev_pos[r["query"]]) for r in g["queries"]
              if r["query"] in prev_pos and r["impressions"] >= 20]
    if movers:
        movers.sort(key=lambda m: m[1] - m[2])
        up = [f"{m[0]} ({m[2]}→{m[1]})" for m in movers[:3] if m[1] < m[2]]
        down = [f"{m[0]} ({m[2]}→{m[1]})" for m in movers[-3:][::-1] if m[1] > m[2]]
        out += ["", "Grootste stijgers: " + (", ".join(up) or "-"),
                "Grootste dalers: " + (", ".join(down) or "-")]
    return out + [""]


GLOSSARY = [
    "**AI-assistenten**: ChatGPT, Claude en Gemini. Steeds meer mensen vragen daar om een aanbeveling in plaats van te googelen.",
    "**Getoond (impressies)**: hoe vaak een link naar onze site in Google-zoekresultaten stond, ook als niemand klikte.",
    "**Plek**: de positie in Google; plek 1–10 is de eerste pagina. Boven plek 10 ziet bijna niemand ons.",
    "**Korte omschrijving (meta description)**: de 1–2 zinnen die Google onder de link toont. Ontbreekt die, dan kiest Google zelf een stuk tekst.",
    "**Hoofdkop (H1)**: de grote titel bovenaan een pagina. Google gebruikt die om te begrijpen waar de pagina over gaat.",
    "**Alt-tekst**: een korte beschrijving van een afbeelding voor Google en voor blinde bezoekers.",
    "**▲ / ▼**: beter / slechter dan de vorige meting.",
]


def build_report(ai: list[Run], seo: list[Run], gsc: list[Run], day: date | None = None) -> str:
    day = day or date.today()

    def pair(runs: list[Run]) -> tuple[Run, Run]:
        return (runs[0] if runs else None), (runs[1] if len(runs) > 1 else None)

    ai_c, ai_p = pair(ai)
    seo_c, seo_p = pair(seo)
    gsc_c, gsc_p = pair(gsc)
    lines = [f"# Online zichtbaarheid {BRAND} — weekrapport {day.strftime('%d-%m-%Y')}", "",
             "Automatisch gemeten: wat AI-assistenten over ons zeggen, hoe Google ons vindt en hoe de website ervoor staat.", ""]
    lines += summary_section(ai_c, ai_p, seo_c, seo_p, gsc_c, gsc_p)
    lines += actions_section(ai_c, seo_c, gsc_c)
    lines += ["## De cijfers", ""]
    lines += ai_section(ai_c, ai_p)
    lines += gsc_section(gsc_c, gsc_p)
    lines += seo_section(seo_c, seo_p)
    lines += ["## Uitleg van de termen", ""] + [f"- {g}" for g in GLOSSARY] + [""]
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------- markdown → HTML (subset voor de mail)
HTML_STYLE = (
    "font-family:Segoe UI,Arial,sans-serif;font-size:15px;line-height:1.5;color:#222;max-width:760px;margin:0 auto;padding:16px")
TABLE_STYLE = "border-collapse:collapse;margin:8px 0 16px 0;font-size:14px"
CELL_STYLE = "border:1px solid #d0d0d0;padding:6px 10px;text-align:left;vertical-align:top"
TH_STYLE = CELL_STYLE + ";background:#f0f3f7"


def _inline(text: str) -> str:
    """Bold, cursief, links en de ▲/▼/⚠-kleuren; de rest wordt ge-escaped."""
    text = html.escape(text, quote=False)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" style="color:#1a5fb4">\1</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = text.replace("▲", '<span style="color:#1a7f37;font-weight:bold">▲</span>')
    text = text.replace("▼", '<span style="color:#c0392b;font-weight:bold">▼</span>')
    text = text.replace("⚠", '<span style="color:#b26a00">⚠</span>')
    return text


def md_to_html(md: str) -> str:
    """Zet de markdown van build_report om naar eenvoudige, mailvriendelijke HTML (inline CSS, geen scripts)."""
    out: list[str] = []
    lines = md.splitlines()
    i = 0
    list_tag = None

    def close_list():
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None

    while i < len(lines):
        line = lines[i]
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-|:]+\|$", lines[i + 1]):
            close_list()
            headers = [c.strip() for c in line.strip("|").split("|")]
            out.append(f'<table style="{TABLE_STYLE}"><tr>' +
                       "".join(f'<th style="{TH_STYLE}">{_inline(h)}</th>' for h in headers) + "</tr>")
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip("|").split("|")]
                out.append("<tr>" + "".join(f'<td style="{CELL_STYLE}">{_inline(c)}</td>' for c in cells) + "</tr>")
                i += 1
            out.append("</table>")
            continue
        m = re.match(r"^(#{1,3}) (.*)", line)
        if m:
            close_list()
            level = len(m.group(1))
            style = {1: "font-size:22px;margin:0 0 4px 0", 2: "font-size:18px;margin:24px 0 8px 0;border-bottom:2px solid #1a5fb4;padding-bottom:4px",
                     3: "font-size:16px;margin:18px 0 6px 0"}[level]
            out.append(f'<h{level} style="{style}">{_inline(m.group(2))}</h{level}>')
        elif re.match(r"^- ", line):
            if list_tag != "ul":
                close_list(); out.append('<ul style="margin:4px 0 12px 0;padding-left:22px">'); list_tag = "ul"
            out.append(f'<li style="margin:4px 0">{_inline(line[2:])}</li>')
        elif re.match(r"^\d+\. ", line):
            if list_tag != "ol":
                close_list(); out.append('<ol style="margin:4px 0 12px 0;padding-left:22px">'); list_tag = "ol"
            out.append(f'<li style="margin:6px 0">{_inline(line.split(". ", 1)[1])}</li>')
        elif line.strip():
            close_list()
            out.append(f'<p style="margin:6px 0">{_inline(line)}</p>')
        else:
            close_list()
        i += 1
    close_list()
    return f'<div style="{HTML_STYLE}">' + "\n".join(out) + "</div>"


def write_report(md: str, day: date | None = None) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    stem = f"weekrapport-{(day or date.today()).isoformat()}"
    path = REPORTS / f"{stem}.md"
    path.write_text(md, encoding="utf-8")
    (REPORTS / f"{stem}.html").write_text(
        "<!doctype html><html lang='nl'><head><meta charset='utf-8'><title>Weekrapport</title></head><body>"
        + md_to_html(md) + "</body></html>", encoding="utf-8")
    return path


# ---------------------------------------------------------------- e-mail
GRAPH_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
GRAPH_SENDMAIL_URL = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"


def graph_message(md: str, subject: str, to: str, attachment_name: str) -> dict:
    """Payload voor Graph sendMail: HTML-body + het rapport als .md-bijlage (pure functie)."""
    import base64

    return {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": md_to_html(md)},
            "toRecipients": [{"emailAddress": {"address": a.strip()}} for a in to.split(",") if a.strip()],
            "attachments": [{
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": attachment_name,
                "contentType": "text/markdown",
                "contentBytes": base64.b64encode(md.encode("utf-8")).decode("ascii"),
            }],
        },
        "saveToSentItems": True,
    }


def send_email_graph(md: str, subject: str) -> None:
    """Verstuurt via Microsoft Graph (client credentials, Mail.Send). Werkt met Exchange Online zonder SMTP."""
    import requests

    env = {k: os.environ[k].strip() for k in ("MS_TENANT_ID", "MS_CLIENT_ID", "MS_CLIENT_SECRET",
                                              "REPORT_EMAIL_FROM", "REPORT_EMAIL_TO")}
    sender, to = env["REPORT_EMAIL_FROM"], env["REPORT_EMAIL_TO"]
    r = requests.post(GRAPH_TOKEN_URL.format(tenant=env["MS_TENANT_ID"]), timeout=30, data={
        "client_id": env["MS_CLIENT_ID"], "client_secret": env["MS_CLIENT_SECRET"],
        "scope": "https://graph.microsoft.com/.default", "grant_type": "client_credentials"})
    if not r.ok:
        raise RuntimeError(f"Graph token mislukt ({r.status_code}): {graph_error_text(r)}")
    token = r.json()["access_token"]
    payload = graph_message(md, subject, to, f"weekrapport-{date.today().isoformat()}.md")
    r = requests.post(GRAPH_SENDMAIL_URL.format(sender=sender), json=payload, timeout=30,
                      headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 202:
        raise RuntimeError(f"Graph sendMail mislukt ({r.status_code}): {graph_error_text(r)}")


def graph_error_text(r) -> str:
    """Leesbare foutmelding uit een Microsoft-antwoord (AADSTS-code + omschrijving, geen secrets)."""
    try:
        j = r.json()
        err = j.get("error")
        if isinstance(err, dict):  # Graph: {"error": {"code": ..., "message": ...}}
            return f"{err.get('code')}: {err.get('message')}"
        return f"{err}: {j.get('error_description', '')}"[:400]  # login.microsoftonline.com
    except ValueError:
        return r.text[:300]


GRAPH_HINTS = {
    "AADSTS90002": "MS_TENANT_ID klopt niet (tenant niet gevonden). Controleer 'Map-id (tenant)' in Entra.",
    "AADSTS700016": "MS_CLIENT_ID hoort niet bij deze tenant. Controleer 'Toepassings-id (client)' in Entra.",
    "AADSTS7000215": "MS_CLIENT_SECRET is onjuist: waarschijnlijk de secret-ID i.p.v. de Waarde geplakt.",
    "AADSTS7000222": "Het clientgeheim is verlopen; maak een nieuw geheim aan in Entra.",
    "ErrorAccessDenied": "Mail.Send heeft geen beheerderstoestemming, of een access policy blokkeert deze mailbox.",
    "ResourceNotFound": "REPORT_EMAIL_FROM is geen bestaande mailbox in deze tenant.",
}


def graph_hint(message: str) -> str:
    return next((hint for code, hint in GRAPH_HINTS.items() if code in message), "")


def email_configured() -> str | None:
    """'graph' | 'smtp' | None, afhankelijk van welke variabelen gezet zijn."""
    if os.getenv("MS_TENANT_ID") and os.getenv("MS_CLIENT_ID") and os.getenv("MS_CLIENT_SECRET"):
        return "graph"
    if os.getenv("SMTP_HOST"):
        return "smtp"
    return None


def send_email(md: str, subject: str) -> None:
    """Kiest Graph (Microsoft 365) als MS_* gezet is, anders SMTP. Body is HTML, met .md-bijlage."""
    if email_configured() == "graph":
        send_email_graph(md, subject)
        return
    host, port = os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587"))
    user, password = os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"]
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("REPORT_EMAIL_FROM", user)
    msg["To"] = os.environ["REPORT_EMAIL_TO"]
    msg.set_content(md)
    msg.add_alternative(md_to_html(md), subtype="html")
    msg.add_attachment(md.encode("utf-8"), maintype="text", subtype="markdown",
                       filename=f"weekrapport-{date.today().isoformat()}.md")
    with smtplib.SMTP(host, port, timeout=30) as s:
        s.starttls()
        s.login(user, password)
        s.send_message(msg)


# ---------------------------------------------------------------- dry-run data
def sample_runs() -> tuple[list[Run], list[Run], list[Run]]:
    from src.search_console import sample_api_rows, to_rows
    from src.seo_audit import FIXTURES, audit_html

    today, prev = date.today(), date.today() - timedelta(days=7)
    ai_now = [{"provider": p, "tag": "opdrachtgever" if i % 2 else "personeel", "query": f"vraag {i}",
               "brand_mentioned": (i + j) % 3 == 0, "competitors_mentioned": ["Sweco"] if i % 2 else []}
              for j, p in enumerate(("openai", "anthropic", "gemini")) for i in range(5)]
    ai_prev = [dict(r, brand_mentioned=False) for r in ai_now]
    seo_now = [audit_html(f"https://ci-engineers.com/{fx.stem}/", fx.read_text(encoding="utf-8"), 200, 300)
               for fx in sorted(FIXTURES.glob("page_*.html"))]
    seo_prev = [dict(r, load_ms=450) for r in seo_now]
    period = (prev - timedelta(days=27), prev)
    gsc_now = to_rows(sample_api_rows(["query"]), ["query"], *period) + to_rows(sample_api_rows(["page"]), ["page"], *period)
    gsc_prev = [dict(r, position=r["position"] + 1.5, clicks=max(0, r["clicks"] - 1)) for r in gsc_now]
    return [(today, ai_now), (prev, ai_prev)], [(today, seo_now), (prev, seo_prev)], [(today, gsc_now), (prev, gsc_prev)]


if __name__ == "__main__":
    utf8_console()
    ap = argparse.ArgumentParser(description="Wekelijks rapport uit data/results/")
    ap.add_argument("--dry-run", action="store_true", help="voorbeelddata, alleen naar stdout")
    ap.add_argument("--email", action="store_true", help="rapport ook mailen (MS_* of SMTP_* in .env)")
    ap.add_argument("--email-only", action="store_true",
                    help="alleen het rapport van vandaag uit data/reports/ mailen, niets opnieuw bouwen")
    ap.add_argument("--html", action="store_true", help="bij --dry-run: HTML tonen i.p.v. markdown")
    args = ap.parse_args()

    if args.dry_run:
        md = build_report(*sample_runs())
        print(md_to_html(md) if args.html else md)
        sys.exit(0)

    if args.email_only:
        path = REPORTS / f"weekrapport-{date.today().isoformat()}.md"
        if not path.exists():
            print(f"[fout] {path} bestaat niet; draai eerst python -m src.report", file=sys.stderr)
            sys.exit(1)
        md = path.read_text(encoding="utf-8")
    else:
        md = build_report(load_runs("ai_visibility"), load_runs("seo_audit"), load_runs("search_console"))
        path = write_report(md)
        print(md)
        print(f"Opgeslagen in {path} (+ .html)")

    if args.email or args.email_only:
        if not email_configured():
            print("[fout] Geen e-mailconfiguratie: zet MS_TENANT_ID/MS_CLIENT_ID/MS_CLIENT_SECRET of SMTP_* in .env",
                  file=sys.stderr)
            sys.exit(1)
        try:
            send_email(md, f"Weekrapport online zichtbaarheid {BRAND} — {date.today().strftime('%d-%m-%Y')}")
        except Exception as e:
            hint = graph_hint(str(e))
            print(f"[fout] Mailen mislukt: {e}" + (f"\n       → {hint}" if hint else ""), file=sys.stderr)
            sys.exit(1)
        print(f"Gemaild via {email_configured()} naar {os.environ['REPORT_EMAIL_TO']}")
