import gzip
from pathlib import Path

from src.seo_audit import (audit_html, build_report, check_page, fetch_sitemap_urls,
                           parse_jsonld, parse_page, parse_sitemap)

FX = Path(__file__).parent / "fixtures"


def test_parse_page_ok():
    p = parse_page((FX / "page_ok.html").read_text(encoding="utf-8"), "https://ci-engineers.com/ok/")
    assert p["title"] == "CI-Engineers - Civiel ingenieursbureau"  # SVG-<title> genegeerd
    assert p["meta_description"].startswith("CI-Engineers is een jong")
    assert p["h1"] == ["Gespecialiseerd in infrastructurele werken"]
    assert p["canonical"] == "https://ci-engineers.com/ok/"
    assert p["noindex"] is False
    assert "Organization" in p["jsonld_types"] and "LocalBusiness" in p["jsonld_types"]
    assert p["internal_links"] == 3  # /, /diensten/, www-variant contact (fragment weg); mailto genegeerd
    assert p["external_links"] == 1
    assert p["images"] == 2 and p["images_without_alt"] == 0
    assert p["word_count"] > 300
    assert "niet meetellen" not in str(p)


def test_parse_page_bad_and_checks():
    p = parse_page((FX / "page_bad.html").read_text(encoding="utf-8"), "https://ci-engineers.com/bad/")
    issues = check_page(p, "https://ci-engineers.com/bad/", 200, 2500)
    joined = " | ".join(issues)
    assert "Title te lang" in joined
    assert "Meta description ontbreekt" in joined
    assert "Meerdere H1's (2)" in joined
    assert "Geen Organization/LocalBusiness-schema" in joined
    assert "2 afbeelding(en) zonder alt-tekst" in joined
    assert "noindex" in joined
    assert "Canonical wijkt af" in joined
    assert "Weinig tekst" in joined
    assert "Trage laadtijd" in joined


def test_parse_jsonld_graph_and_list_types():
    types = parse_jsonld(['{"@graph":[{"@type":"WebPage"},{"@type":["Organization","LocalBusiness"]}]}',
                         "kapot", '{"@type":"JobPosting"}'])
    assert types == ["WebPage", "Organization", "LocalBusiness", "JobPosting"]


def test_parse_sitemap_index_and_gzip():
    kind, locs = parse_sitemap((FX / "sitemap_index.xml").read_bytes())
    assert kind == "index" and len(locs) == 3
    kind, locs = parse_sitemap(gzip.compress((FX / "page-sitemap.xml").read_bytes()))
    assert kind == "urlset" and locs[0] == "https://ci-engineers.com/"
    assert not any("uploads" in l for l in locs)  # <image:loc> genegeerd


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content
        self.url = ""

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, timeout=20):
        self.calls.append(url)
        name = url.rsplit("/", 1)[-1]
        return FakeResponse((FX / (name if name != "post-sitemap.xml" else "page-sitemap.xml")).read_bytes()
                            if name != "author-sitemap.xml" else b"<urlset></urlset>")


def test_fetch_sitemap_urls_filters_children_and_dedupes():
    s = FakeSession()
    urls = fetch_sitemap_urls("https://ci-engineers.com/sitemap_index.xml", s)
    assert urls == ["https://ci-engineers.com/", "https://ci-engineers.com/diensten/"]
    assert not any("author" in c for c in s.calls)


def test_audit_html_and_report():
    row = audit_html("https://ci-engineers.com/ok/", (FX / "page_ok.html").read_text(encoding="utf-8"), 200, 100)
    assert row["module"] == "seo_audit" and row["issues"] == []
    md = build_report([row])
    assert "Pagina's gecontroleerd: **1**" in md and "| [/ok/]" in md
    bad = audit_html("https://ci-engineers.com/bad/", (FX / "page_bad.html").read_text(encoding="utf-8"), 200, 100)
    md = build_report([bad])
    assert "- Geen H1 — 1×" not in md and "- Meerdere H1's — 1×" in md and "- afbeelding(en) zonder alt-tekst — 1×" in md
