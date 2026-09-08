"""
Wekelijks rapport (module 5): combineert de nieuwste runs van
ai_visibility, seo_audit en search_console tot één markdown-rapport,
met trend t.o.v. de vorige run. Optioneel per e-mail (--email, SMTP via .env).

Vereist voor --email in .env (één van beide):
    Microsoft 365 / Exchange Online via Graph API (aanbevolen, app-registratie in Entra):
        MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET, REPORT_EMAIL_FROM (mailbox), REPORT_EMAIL_TO
    Klassiek SMTP (basic auth; op Exchange Online eind 2026 standaard uit):
        SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, REPORT_EMAIL_FROM, REPORT_EMAIL_TO

Gebruik:
    python -m src.report              # schrijft data/reports/weekrapport-YYYY-MM-DD.md
    python -m src.report --dry-run    # voorbeelddata, alleen naar stdout
    python -m src.report --email      # ook mailen
"""
from __future__ import annotations

import argparse
import os
import smtplib
import sys
from datetime import date, timedelta
from email.message import EmailMessage
from pathlib import Path

from src.common import REPORTS, load_runs, utf8_console

Run = tuple[date, list[dict]] | None


# ---------------------------------------------------------------- pure helpers
def delta(cur: float | None, prev: float | None, decimals: int = 0, invert: bool = False) -> str:
    """Verschil als tekst: '+3', '−0.4', '±0' of '' zonder vorige waarde.
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


# ---------------------------------------------------------------- secties
def ai_section(cur: Run, prev: Run) -> list[str]:
    day, rows = _run(cur)
    _, prev_rows = _run(prev)
    out = ["## AI-zichtbaarheid (ChatGPT / Claude / Gemini)", ""]
    if not rows:
        return out + ["Geen data. Draai `python -m src.ai_visibility`.", ""]
    out.append(f"Run van {day}. Wordt CI-Engineers genoemd in de antwoorden?")
    out += ["", "| Provider | Genoemd | Vorige run |", "|---|---|---|"]
    ok_rows = [r for r in rows if not r.get("error")]
    errors = len(rows) - len(ok_rows)
    for prov in sorted({r["provider"] for r in rows}):
        sub = [r for r in ok_rows if r["provider"] == prov]
        n_err = sum(1 for r in rows if r["provider"] == prov and r.get("error"))
        psub = [r for r in prev_rows if r["provider"] == prov and not r.get("error")]
        hits = sum(1 for r in sub if r["brand_mentioned"])
        cur_pct = pct(hits, len(sub))
        prev_pct = pct(sum(1 for r in psub if r["brand_mentioned"]), len(psub)) if psub else None
        shown = f"{hits}/{len(sub)} ({cur_pct}%)" if sub else "geen antwoorden"
        note = f" ⚠ {n_err} fouten" if n_err else ""
        out.append(f"| {prov} | {shown}{note} | {delta(cur_pct, prev_pct) or '-'} |")
    if errors:
        first = next(r["error"] for r in rows if r.get("error"))
        out.append(f"\n⚠ {errors} vragen gaven een fout (niet meegeteld). Eerste fout: {first[:120]}")
    for tag in sorted({r["tag"] for r in rows}):
        sub = [r for r in ok_rows if r["tag"] == tag]
        out.append(f"\n- Doelgroep *{tag}*: genoemd in {sum(1 for r in sub if r['brand_mentioned'])}/{len(sub)}")
    counts: dict[str, int] = {}
    for r in rows:
        for c in r["competitors_mentioned"]:
            counts[c] = counts.get(c, 0) + 1
    if counts:
        top = sorted(counts.items(), key=lambda x: -x[1])[:5]
        out += ["", "Meest genoemde concurrenten: " + ", ".join(f"{k} ({v})" for k, v in top)]
    return out + [""]


def seo_section(cur: Run, prev: Run) -> list[str]:
    day, rows = _run(cur)
    _, prev_rows = _run(prev)
    out = ["## SEO-audit ci-engineers.com", ""]
    if not rows:
        return out + ["Geen data. Draai `python -m src.seo_audit`.", ""]

    def stats(rs: list[dict]) -> dict:
        ok = [r for r in rs if r.get("status") == 200]
        return {
            "pages": len(rs),
            "issues": sum(len(r.get("issues", [])) for r in rs),
            "no_desc": sum(1 for r in rs if not r.get("meta_description")),
            "no_alt": sum(r.get("images_without_alt", 0) for r in rs),
            "load": round(sum(r["load_ms"] for r in ok) / len(ok)) if ok else None,
        }

    s, p = stats(rows), (stats(prev_rows) if prev_rows else {})
    out.append(f"Run van {day}, {s['pages']} pagina's.")
    out += ["", "| Metriek | Nu | Verschil |", "|---|---|---|",
            f"| Issues totaal | {s['issues']} | {delta(s['issues'], p.get('issues'), invert=True) or '-'} |",
            f"| Pagina's zonder meta description | {s['no_desc']} | {delta(s['no_desc'], p.get('no_desc'), invert=True) or '-'} |",
            f"| Afbeeldingen zonder alt | {s['no_alt']} | {delta(s['no_alt'], p.get('no_alt'), invert=True) or '-'} |",
            f"| Gem. laadtijd (ms) | {s['load']} | {delta(s['load'], p.get('load'), invert=True) or '-'} |"]
    worst = sorted((r for r in rows if r.get("issues")), key=lambda r: -len(r["issues"]))[:5]
    if worst:
        out += ["", "Pagina's met de meeste issues:"]
        out += [f"- {r['url']} — {len(r['issues'])}: {'; '.join(r['issues'][:3])}" for r in worst]
    return out + [""]


def gsc_section(cur: Run, prev: Run) -> list[str]:
    day, rows = _run(cur)
    _, prev_rows = _run(prev)
    out = ["## Google Search Console", ""]
    q = [r for r in rows if r["dimensions"] == "query"]
    pq = [r for r in prev_rows if r["dimensions"] == "query"]
    if not q:
        return out + ["Geen data. Draai `python -m src.search_console`.", ""]

    def totals(rs: list[dict]) -> dict:
        imps = sum(r["impressions"] for r in rs)
        return {"clicks": sum(r["clicks"] for r in rs), "imps": imps,
                "pos": round(sum(r["position"] * r["impressions"] for r in rs) / imps, 1) if imps else None}

    t, pt = totals(q), (totals(pq) if pq else {})
    out.append(f"Periode {q[0]['period_start']} t/m {q[0]['period_end']} (run van {day}).")
    out += ["", "| Metriek | Nu | Verschil |", "|---|---|---|",
            f"| Klikken | {t['clicks']} | {delta(t['clicks'], pt.get('clicks')) or '-'} |",
            f"| Impressies | {t['imps']} | {delta(t['imps'], pt.get('imps')) or '-'} |",
            f"| Gem. positie | {t['pos']} | {delta(t['pos'], pt.get('pos'), 1, invert=True) or '-'} |",
            "", "Top-10 zoekwoorden:", "", "| Zoekwoord | Klikken | Impressies | Positie | Δ positie |", "|---|---|---|---|---|"]
    prev_pos = {r["query"]: r["position"] for r in pq}
    for r in sorted(q, key=lambda r: (-r["clicks"], -r["impressions"]))[:10]:
        out.append(f"| {r['query']} | {r['clicks']} | {r['impressions']} | {r['position']} "
                   f"| {delta(r['position'], prev_pos.get(r['query']), 1, invert=True) or '-'} |")
    movers = [(r["query"], r["position"], prev_pos[r["query"]]) for r in q
              if r["query"] in prev_pos and r["impressions"] >= 20]
    if movers:
        movers.sort(key=lambda m: m[1] - m[2])
        up = [f"{m[0]} ({m[2]}→{m[1]})" for m in movers[:3] if m[1] < m[2]]
        down = [f"{m[0]} ({m[2]}→{m[1]})" for m in movers[-3:][::-1] if m[1] > m[2]]
        out += ["", "Grootste stijgers: " + (", ".join(up) or "-"),
                "Grootste dalers: " + (", ".join(down) or "-")]
    return out + [""]


def build_report(ai: list[Run], seo: list[Run], gsc: list[Run], day: date | None = None) -> str:
    day = day or date.today()

    def pair(runs: list[Run]) -> tuple[Run, Run]:
        return (runs[0] if runs else None), (runs[1] if len(runs) > 1 else None)

    lines = [f"# Weekrapport CI Search Manager — {day.isoformat()}", "",
             "Trends vergelijken de nieuwste run met de run ervoor (▲ = beter, ▼ = slechter).", ""]
    lines += ai_section(*pair(ai))
    lines += seo_section(*pair(seo))
    lines += gsc_section(*pair(gsc))
    return "\n".join(lines).rstrip() + "\n"


def write_report(md: str, day: date | None = None) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"weekrapport-{(day or date.today()).isoformat()}.md"
    path.write_text(md, encoding="utf-8")
    return path


# ---------------------------------------------------------------- e-mail
GRAPH_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
GRAPH_SENDMAIL_URL = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"


def graph_message(md: str, subject: str, to: str, attachment_name: str) -> dict:
    """Payload voor Graph sendMail: platte tekst + het rapport als .md-bijlage (pure functie)."""
    import base64

    return {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": md},
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
    """Kiest Graph (Microsoft 365) als MS_* gezet is, anders SMTP."""
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
    ai_now = [{"provider": p, "tag": "opdrachtgever", "query": f"vraag {i}", "brand_mentioned": (i + j) % 3 == 0,
               "competitors_mentioned": ["Sweco"] if i % 2 else []} for j, p in enumerate(("openai", "anthropic", "gemini")) for i in range(5)]
    ai_prev = [dict(r, brand_mentioned=False) for r in ai_now]
    seo_now = [audit_html(f"https://ci-engineers.com/{fx.stem}/", fx.read_text(encoding="utf-8"), 200, 300)
               for fx in sorted(FIXTURES.glob("page_*.html"))]
    seo_prev = [dict(r, load_ms=450) for r in seo_now]
    gsc_now = to_rows(sample_api_rows(["query"]), ["query"], prev - timedelta(days=27), prev)
    gsc_prev = [dict(r, position=r["position"] + 1.5, clicks=r["clicks"] - 1) for r in gsc_now]
    return [(today, ai_now), (prev, ai_prev)], [(today, seo_now), (prev, seo_prev)], [(today, gsc_now), (prev, gsc_prev)]


if __name__ == "__main__":
    utf8_console()
    ap = argparse.ArgumentParser(description="Wekelijks rapport uit data/results/")
    ap.add_argument("--dry-run", action="store_true", help="voorbeelddata, alleen naar stdout")
    ap.add_argument("--email", action="store_true", help="rapport ook mailen (MS_* of SMTP_* in .env)")
    ap.add_argument("--email-only", action="store_true",
                    help="alleen het rapport van vandaag uit data/reports/ mailen, niets opnieuw bouwen")
    args = ap.parse_args()

    if args.dry_run:
        md = build_report(*sample_runs())
        print(md)
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
        print(f"Opgeslagen in {path}")

    if args.email or args.email_only:
        if not email_configured():
            print("[fout] Geen e-mailconfiguratie: zet MS_TENANT_ID/MS_CLIENT_ID/MS_CLIENT_SECRET of SMTP_* in .env",
                  file=sys.stderr)
            sys.exit(1)
        try:
            send_email(md, f"Weekrapport CI Search Manager {date.today().isoformat()}")
        except Exception as e:
            hint = graph_hint(str(e))
            print(f"[fout] Mailen mislukt: {e}" + (f"\n       → {hint}" if hint else ""), file=sys.stderr)
            sys.exit(1)
        print(f"Gemaild via {email_configured()} naar {os.environ['REPORT_EMAIL_TO']}")
