"""
SEO-audit voor ci-engineers.com (module 2).

Leest de sitemap (sitemap_index.xml van Yoast/Rank Math of een gewone sitemap.xml),
haalt elke pagina op en controleert: title, meta description, H1, canonical, noindex,
schema.org JSON-LD, interne/externe links, alt-teksten, woordaantal en laadtijd.

Output:
    data/results/seo_audit-YYYY-MM-DD.jsonl   (één rij per pagina, voor trends)
    data/reports/seo_audit-YYYY-MM-DD.md      (leesbaar rapport)

Gebruik:
    python -m src.seo_audit                  # hele site (post- en page-sitemap)
    python -m src.seo_audit --limit 5        # eerste 5 pagina's
    python -m src.seo_audit --dry-run        # geen netwerk, parseert tests/fixtures/*.html
    python -m src.seo_audit --sitemap https://ci-engineers.com/page-sitemap.xml
    python -m src.seo_audit --all-sitemaps   # ook category/tag/author-sitemaps
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import requests

from src.common import REPORTS, ROOT, now_iso, save_jsonl, utf8_console

USER_AGENT = "CI-Search-Manager/1.0 (+https://ci-engineers.com)"
FIXTURES = ROOT / "tests" / "fixtures"
DEFAULT_SITEMAPS = ("post-sitemap", "page-sitemap")  # standaard: alleen content-sitemaps

# Drempels voor de checks
TITLE_MAX = 60
DESC_MAX = 160
MIN_WORDS = 300
MAX_LOAD_MS = 2000
WANTED_SCHEMA = ("Organization", "LocalBusiness", "ProfessionalService")


def site_url() -> str:
    return (os.getenv("SITE_URL") or os.getenv("WP_BASE_URL") or "https://ci-engineers.com").rstrip("/")


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "nl,en;q=0.8"})
    return s


# ---------------------------------------------------------------- sitemap
def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_sitemap(xml_bytes: bytes) -> tuple[str, list[str]]:
    """Geeft ("index" | "urlset", [loc, ...]) terug. Namespace-agnostisch."""
    if xml_bytes[:2] == b"\x1f\x8b":
        xml_bytes = gzip.decompress(xml_bytes)
    root = ET.fromstring(xml_bytes)
    kind = "index" if _localname(root.tag) == "sitemapindex" else "urlset"
    # Alleen <loc> direct onder <url>/<sitemap>; Yoast zet ook <image:loc> in de sitemap.
    locs = [loc.text.strip()
            for entry in root if _localname(entry.tag) in ("url", "sitemap")
            for loc in entry if _localname(loc.tag) == "loc" and loc.text]
    return kind, locs


def fetch_sitemap_urls(sitemap_url: str, session: requests.Session,
                       include: tuple[str, ...] | None = DEFAULT_SITEMAPS) -> list[str]:
    """Alle pagina-URL's uit een sitemap of sitemap-index (recursief, gededupliceerd).
    include: substrings van child-sitemapnamen die meegenomen worden (None = alles)."""
    r = session.get(sitemap_url, timeout=20)
    r.raise_for_status()
    kind, locs = parse_sitemap(r.content)
    urls: list[str] = []
    if kind == "index":
        for child in locs:
            name = urlparse(child).path.rsplit("/", 1)[-1]
            if include is None or any(part in name for part in include):
                urls.extend(fetch_sitemap_urls(child, session, include=None))
    else:
        urls.extend(locs)
    return list(dict.fromkeys(urls))


def discover_sitemap(base: str, session: requests.Session) -> str:
    for cand in ("/sitemap_index.xml", "/sitemap.xml"):
        try:
            r = session.get(base + cand, timeout=20)
            if r.ok and b"<" in r.content[:200]:
                return r.url  # volgt redirects (sitemap.xml -> sitemap_index.xml)
        except requests.RequestException:
            continue
    raise RuntimeError(f"Geen sitemap gevonden op {base}")


# ---------------------------------------------------------------- HTML-parser
class PageParser(HTMLParser):
    """Verzamelt SEO-relevante onderdelen uit één HTML-pagina."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta_description = ""
        self.canonical = ""
        self.robots = ""
        self.h1: list[str] = []
        self.jsonld: list[str] = []
        self.links: list[str] = []
        self.images = 0
        self.images_without_alt = 0
        self.text_parts: list[str] = []
        self._in_head = False
        self._svg_depth = 0
        self._skip_depth = 0  # script/style/noscript
        self._in_title = False
        self._in_h1 = False
        self._in_jsonld = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "head":
            self._in_head = True
        elif tag == "svg":
            self._svg_depth += 1
        elif tag in ("script", "style", "noscript", "template"):
            self._skip_depth += 1
            if tag == "script" and (a.get("type") or "").strip().lower() == "application/ld+json":
                self._in_jsonld = True
                self._buf = []
        elif tag == "title" and self._svg_depth == 0 and not self.title:
            self._in_title = True
            self._buf = []
        elif tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            if name == "description" and not self.meta_description:
                self.meta_description = (a.get("content") or "").strip()
            elif name == "robots":
                self.robots = (a.get("content") or "").lower()
        elif tag == "link" and (a.get("rel") or "").lower() == "canonical":
            self.canonical = (a.get("href") or "").strip()
        elif tag == "h1" and self._svg_depth == 0:
            self._in_h1 = True
            self._buf = []
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"].strip())
        elif tag == "img":
            self.images += 1
            if not (a.get("alt") or "").strip():
                self.images_without_alt += 1

    def handle_endtag(self, tag):
        if tag == "head":
            self._in_head = False
        elif tag == "svg":
            self._svg_depth = max(0, self._svg_depth - 1)
        elif tag in ("script", "style", "noscript", "template"):
            self._skip_depth = max(0, self._skip_depth - 1)
            if tag == "script" and self._in_jsonld:
                self.jsonld.append("".join(self._buf))
                self._in_jsonld = False
        elif tag == "title" and self._in_title:
            self.title = " ".join("".join(self._buf).split())
            self._in_title = False
        elif tag == "h1" and self._in_h1:
            self.h1.append(" ".join("".join(self._buf).split()))
            self._in_h1 = False

    def handle_data(self, data):
        if self._in_jsonld or self._in_title or self._in_h1:
            self._buf.append(data)
        if self._skip_depth == 0 and not self._in_head and self._svg_depth == 0:
            self.text_parts.append(data)


def parse_jsonld(scripts: list[str]) -> list[str]:
    """Alle @type-waarden uit JSON-LD-blokken (incl. @graph en lijst-@type)."""
    types: list[str] = []

    def walk(node):
        if isinstance(node, list):
            for n in node:
                walk(n)
        elif isinstance(node, dict):
            t = node.get("@type")
            if isinstance(t, str):
                types.append(t)
            elif isinstance(t, list):
                types.extend(x for x in t if isinstance(x, str))
            for key in ("@graph", "mainEntity", "itemListElement"):
                if key in node:
                    walk(node[key])

    for raw in scripts:
        try:
            walk(json.loads(raw.strip()))
        except (json.JSONDecodeError, ValueError):
            continue
    return list(dict.fromkeys(types))


def _same_host(a: str, b: str) -> bool:
    ha = urlparse(a).netloc.lower().removeprefix("www.")
    hb = urlparse(b).netloc.lower().removeprefix("www.")
    return ha == hb


def extract_text(html: str, max_chars: int = 4000) -> str:
    """Zichtbare tekst van een pagina (zonder head/script/svg), ingekort. Voor tekstvoorstellen (seo_suggest)."""
    p = PageParser()
    p.feed(html)
    p.close()
    text = " ".join("".join(p.text_parts).split())
    return text[:max_chars]


def parse_page(html: str, base_url: str) -> dict:
    p = PageParser()
    p.feed(html)
    p.close()
    internal = external = 0
    seen: set[str] = set()
    for href in p.links:
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        full, _ = urldefrag(urljoin(base_url, href))
        if full in seen:
            continue
        seen.add(full)
        if _same_host(full, base_url):
            internal += 1
        else:
            external += 1
    text = " ".join("".join(p.text_parts).split())
    words = len(re.findall(r"\w+", text))
    return {
        "title": p.title,
        "title_len": len(p.title),
        "meta_description": p.meta_description,
        "desc_len": len(p.meta_description),
        "h1": p.h1,
        "canonical": p.canonical,
        "noindex": "noindex" in p.robots,
        "jsonld_types": parse_jsonld(p.jsonld),
        "internal_links": internal,
        "external_links": external,
        "images": p.images,
        "images_without_alt": p.images_without_alt,
        "word_count": words,
    }


# ---------------------------------------------------------------- checks
def check_page(parsed: dict, url: str, status: int, load_ms: float) -> list[str]:
    issues: list[str] = []
    if status != 200:
        issues.append(f"HTTP-status {status}")
    if not parsed["title"]:
        issues.append("Title ontbreekt")
    elif parsed["title_len"] > TITLE_MAX:
        issues.append(f"Title te lang ({parsed['title_len']} > {TITLE_MAX} tekens)")
    if not parsed["meta_description"]:
        issues.append("Meta description ontbreekt")
    elif parsed["desc_len"] > DESC_MAX:
        issues.append(f"Meta description te lang ({parsed['desc_len']} > {DESC_MAX} tekens)")
    if len(parsed["h1"]) == 0:
        issues.append("Geen H1")
    elif len(parsed["h1"]) > 1:
        issues.append(f"Meerdere H1's ({len(parsed['h1'])})")
    if not any(t in WANTED_SCHEMA for t in parsed["jsonld_types"]):
        issues.append("Geen Organization/LocalBusiness-schema (JSON-LD)")
    if parsed["images_without_alt"]:
        issues.append(f"{parsed['images_without_alt']} afbeelding(en) zonder alt-tekst")
    if parsed["noindex"]:
        issues.append("Pagina staat op noindex")
    if parsed["canonical"] and urldefrag(parsed["canonical"])[0].rstrip("/") != url.rstrip("/"):
        issues.append(f"Canonical wijkt af: {parsed['canonical']}")
    if parsed["word_count"] < MIN_WORDS:
        issues.append(f"Weinig tekst ({parsed['word_count']} woorden < {MIN_WORDS})")
    if load_ms > MAX_LOAD_MS:
        issues.append(f"Trage laadtijd ({load_ms:.0f} ms > {MAX_LOAD_MS} ms)")
    return issues


# ---------------------------------------------------------------- crawl
def fetch_page(url: str, session: requests.Session) -> tuple[int, str, float, str]:
    t0 = time.perf_counter()
    r = session.get(url, timeout=20)
    load_ms = (time.perf_counter() - t0) * 1000
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return r.status_code, r.text, load_ms, r.url


def audit_html(url: str, html: str, status: int = 200, load_ms: float = 0.0, final_url: str | None = None) -> dict:
    parsed = parse_page(html, url)
    row = {"ts": now_iso(), "module": "seo_audit", "url": url, "final_url": final_url or url,
           "status": status, "load_ms": round(load_ms)}
    row.update(parsed)
    row["issues"] = check_page(parsed, row["final_url"], status, load_ms)
    return row


def audit(urls: list[str], session: requests.Session, delay: float = 0.5) -> list[dict]:
    rows = []
    for i, url in enumerate(urls, 1):
        try:
            status, html, load_ms, final = fetch_page(url, session)
            row = audit_html(url, html, status, load_ms, final)
        except requests.RequestException as e:
            row = {"ts": now_iso(), "module": "seo_audit", "url": url, "final_url": url, "status": 0,
                   "load_ms": 0, "issues": [f"Ophalen mislukt: {e}"]}
        rows.append(row)
        print(f"[{i}/{len(urls)}] {len(row['issues']):2d} issues  {url}")
        if delay and i < len(urls):
            time.sleep(delay)
    return rows


def dry_run_rows() -> list[dict]:
    rows = []
    for fx in sorted(FIXTURES.glob("page_*.html")):
        url = f"https://ci-engineers.com/{fx.stem.removeprefix('page_')}/"
        rows.append(audit_html(url, fx.read_text(encoding="utf-8"), 200, 123.0))
        print(f"[dry-run] {len(rows[-1]['issues']):2d} issues  {url}")
    return rows


# ---------------------------------------------------------------- rapport
def build_report(rows: list[dict], day: date | None = None) -> str:
    day = day or date.today()
    n = len(rows)
    with_issues = [r for r in rows if r["issues"]]
    ok_rows = [r for r in rows if r.get("status") == 200 and "load_ms" in r]
    avg_load = sum(r["load_ms"] for r in ok_rows) / len(ok_rows) if ok_rows else 0
    counts: dict[str, int] = {}
    for r in rows:
        for issue in r["issues"]:
            key = re.sub(r"^\d+ |\s*\([^)]*\d[^)]*\)|: .*$", "", issue).strip()
            counts[key] = counts.get(key, 0) + 1

    out = [f"# SEO-audit ci-engineers.com — {day.isoformat()}", "",
           f"- Pagina's gecontroleerd: **{n}**",
           f"- Pagina's met issues: **{len(with_issues)}**",
           f"- Gemiddelde laadtijd: **{avg_load:.0f} ms**", "",
           "## Meest voorkomende issues", ""]
    if counts:
        out += [f"- {k} — {v}×" for k, v in sorted(counts.items(), key=lambda x: -x[1])]
    else:
        out.append("- Geen issues gevonden 🎉")
    out += ["", "## Per pagina", "",
            "| Pagina | Status | Laadtijd | Title (len) | Descr. (len) | H1 | Schema | Issues |",
            "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        path = urlparse(r["url"]).path or "/"
        out.append(
            f"| [{path}]({r['url']}) | {r.get('status', '')} | {r.get('load_ms', '')} ms "
            f"| {r.get('title_len', '')} | {r.get('desc_len', '')} | {len(r.get('h1', []))} "
            f"| {', '.join(r.get('jsonld_types', [])) or '-'} | {len(r['issues'])} |")
    out += ["", "## Issues per pagina", ""]
    for r in with_issues:
        out.append(f"### {r['url']}")
        out += [f"- {i}" for i in r["issues"]]
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def write_report(rows: list[dict]) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"seo_audit-{date.today().isoformat()}.md"
    path.write_text(build_report(rows), encoding="utf-8")
    return path


def summary(rows: list[dict]) -> None:
    print("\n=== Samenvatting ===")
    print(f"{len(rows)} pagina's, {sum(1 for r in rows if r['issues'])} met issues, "
          f"{sum(len(r['issues']) for r in rows)} issues totaal")


if __name__ == "__main__":
    utf8_console()
    ap = argparse.ArgumentParser(description="SEO-audit op basis van de sitemap")
    ap.add_argument("--dry-run", action="store_true", help="geen netwerk; parseert tests/fixtures/page_*.html")
    ap.add_argument("--sitemap", help="sitemap-URL (standaard: SITE_URL/sitemap_index.xml)")
    ap.add_argument("--limit", type=int, help="maximaal aantal pagina's")
    ap.add_argument("--delay", type=float, default=0.5, help="seconden tussen requests")
    ap.add_argument("--all-sitemaps", action="store_true", help="ook category/tag/author-sitemaps")
    ap.add_argument("--no-report", action="store_true", help="geen markdown-rapport schrijven")
    args = ap.parse_args()

    if args.dry_run:
        rows = dry_run_rows()
    else:
        session = make_session()
        sitemap = args.sitemap or discover_sitemap(site_url(), session)
        urls = fetch_sitemap_urls(sitemap, session, include=None if args.all_sitemaps else DEFAULT_SITEMAPS)
        if args.limit:
            urls = urls[: args.limit]
        print(f"{len(urls)} URL's uit {sitemap}")
        rows = audit(urls, session, delay=args.delay)

    if not rows:
        print("Geen pagina's gevonden", file=sys.stderr)
        sys.exit(1)
    path = save_jsonl(rows, "seo_audit")
    summary(rows)
    print(f"JSONL opgeslagen in {path}")
    if not args.no_report:
        print(f"Rapport opgeslagen in {write_report(rows)}")
