"""
Google Search Console-data voor ci-engineers.com (module 3).

Haalt via de Search Console API de zoekwoorden, posities, klikken en CTR op
van de laatste 28 dagen (GSC loopt ~2-3 dagen achter, zie --lag).

Vereist in .env:
    GSC_SERVICE_ACCOUNT_FILE   pad naar het service-account-JSON (bijv. config/gsc-service-account.json)
    GSC_SITE_URL               property zoals in GSC: "sc-domain:ci-engineers.com" of "https://ci-engineers.com/"

Eenmalige setup (zie README): Google Cloud-project → Search Console API aanzetten →
service account + JSON-sleutel → het service-account-e-mailadres in GSC toevoegen als gebruiker.

Gebruik:
    python -m src.search_console              # laatste 28 dagen, dimensies query / page / page+query
    python -m src.search_console --dry-run    # geen API-calls, voorbeelddata
    python -m src.search_console --days 7 --dims query
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

from src.common import now_iso, save_jsonl, utf8_console

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
DEFAULT_DIMS = ("query", "page", "page,query")
ROW_LIMIT = 5000  # API-maximum is 25000 per call


# ---------------------------------------------------------------- pure helpers
def date_range(days: int = 28, lag: int = 3, today: date | None = None) -> tuple[date, date]:
    """(start, eind) inclusief; eind = vandaag - lag omdat GSC-data enkele dagen achterloopt."""
    today = today or date.today()
    end = today - timedelta(days=lag)
    start = end - timedelta(days=days - 1)
    return start, end


def to_rows(api_rows: list[dict], dims: list[str], start: date, end: date) -> list[dict]:
    """Zet API-rijen ({keys:[...], clicks, impressions, ctr, position}) om naar JSONL-rijen."""
    out = []
    for r in api_rows:
        keys = dict(zip(dims, r.get("keys", [])))
        out.append({
            "ts": now_iso(),
            "module": "search_console",
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "dimensions": ",".join(dims),
            "page": keys.get("page"),
            "query": keys.get("query"),
            "clicks": int(r.get("clicks", 0)),
            "impressions": int(r.get("impressions", 0)),
            "ctr": round(float(r.get("ctr", 0.0)), 4),      # fractie 0-1
            "position": round(float(r.get("position", 0.0)), 1),
        })
    return out


def sample_api_rows(dims: list[str]) -> list[dict]:
    """Voorbeelddata voor --dry-run."""
    samples = [
        ("civiel ingenieursbureau noord-holland", "https://ci-engineers.com/", 12, 340, 8.4),
        ("constructeur detachering", "https://ci-engineers.com/diensten/", 5, 210, 14.2),
        ("ci engineers", "https://ci-engineers.com/", 40, 95, 1.3),
        ("ingenieursbureau zaandam", "https://ci-engineers.com/contact/", 2, 180, 22.7),
    ]
    rows = []
    for q, page, clicks, imps, pos in samples:
        keys = [{"query": q, "page": page}[d] for d in dims]
        rows.append({"keys": keys, "clicks": clicks, "impressions": imps,
                     "ctr": clicks / imps, "position": pos})
    return rows


# ---------------------------------------------------------------- API
def build_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    path = os.environ["GSC_SERVICE_ACCOUNT_FILE"]
    creds = service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def query_gsc(service, site: str, start: date, end: date, dims: list[str],
              row_limit: int = ROW_LIMIT) -> list[dict]:
    """Alle rijen voor één dimensiecombinatie, gepagineerd via startRow."""
    rows: list[dict] = []
    start_row = 0
    while True:
        body = {"startDate": start.isoformat(), "endDate": end.isoformat(),
                "dimensions": dims, "rowLimit": row_limit, "startRow": start_row}
        resp = service.searchanalytics().query(siteUrl=site, body=body).execute()
        batch = resp.get("rows", [])
        rows.extend(batch)
        if len(batch) < row_limit:
            return rows
        start_row += row_limit


def fetch_all(service, site: str, start: date, end: date, dim_sets: list[list[str]]) -> list[dict]:
    rows = []
    for dims in dim_sets:
        api_rows = query_gsc(service, site, start, end, dims)
        rows.extend(to_rows(api_rows, dims, start, end))
        print(f"[{','.join(dims):10s}] {len(api_rows)} rijen")
    return rows


# ---------------------------------------------------------------- samenvatting
def summary(rows: list[dict]) -> None:
    print("\n=== Samenvatting ===")
    by_query = [r for r in rows if r["dimensions"] == "query"]
    by_page = [r for r in rows if r["dimensions"] == "page"]
    if by_query:
        clicks = sum(r["clicks"] for r in by_query)
        imps = sum(r["impressions"] for r in by_query)
        avg_pos = sum(r["position"] * r["impressions"] for r in by_query) / imps if imps else 0
        print(f"{clicks} klikken, {imps} impressies, gem. positie {avg_pos:.1f} "
              f"({by_query[0]['period_start']} t/m {by_query[0]['period_end']})")
        print("Top-10 zoekwoorden (klikken / impressies / positie):")
        for r in sorted(by_query, key=lambda r: (-r["clicks"], -r["impressions"]))[:10]:
            print(f"  {r['query'][:50]:50s} {r['clicks']:4d} / {r['impressions']:5d} / {r['position']:5.1f}")
    weak = [r for r in by_page if r["impressions"] >= 50 and r["ctr"] < 0.01]
    if weak:
        print("Pagina's met veel impressies maar CTR < 1% (title/description verbeteren):")
        for r in sorted(weak, key=lambda r: -r["impressions"])[:10]:
            print(f"  {r['page']}  ({r['impressions']} impressies, positie {r['position']})")


if __name__ == "__main__":
    utf8_console()
    ap = argparse.ArgumentParser(description="Google Search Console-export")
    ap.add_argument("--dry-run", action="store_true", help="geen API-calls, voorbeelddata")
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--lag", type=int, default=3, help="dagen vertraging van GSC-data")
    ap.add_argument("--site", default=os.getenv("GSC_SITE_URL"), help="property, bijv. sc-domain:ci-engineers.com")
    ap.add_argument("--dims", default=";".join(DEFAULT_DIMS),
                    help="dimensiesets, puntkomma-gescheiden, bijv. 'query;page;page,query'")
    args = ap.parse_args()

    start, end = date_range(args.days, args.lag)
    dim_sets = [d.split(",") for d in args.dims.split(";") if d.strip()]

    if args.dry_run:
        rows = []
        for dims in dim_sets:
            rows.extend(to_rows(sample_api_rows(dims), dims, start, end))
    else:
        missing = [k for k in ("GSC_SERVICE_ACCOUNT_FILE",) if not os.getenv(k)]
        if missing or not args.site:
            print(f"[fout] Zet GSC_SERVICE_ACCOUNT_FILE en GSC_SITE_URL in .env", file=sys.stderr)
            sys.exit(1)
        rows = fetch_all(build_service(), args.site, start, end, dim_sets)

    if not rows:
        print("Geen data ontvangen", file=sys.stderr)
        sys.exit(1)
    path = save_jsonl(rows, "search_console")
    summary(rows)
    print(f"\nOpgeslagen in {path}")
