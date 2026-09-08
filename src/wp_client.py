"""
WordPress REST API-client (application password, basic auth) — module 4.

Vereist in .env: WP_BASE_URL, WP_USERNAME, WP_APP_PASSWORD
Application password aanmaken: WP-admin → Gebruikers → Profiel → Application Passwords.
Zonder WP_USERNAME/WP_APP_PASSWORD werkt alleen lezen van publieke velden (incl. yoast_head_json).

SEO-metavelden:
- Yoast zet 'yoast_head_json' (title, description, robots, canonical, schema) op elk REST-object: lezen werkt altijd.
- Schrijven van Yoast-/Rank Math-velden kan alleen als ze via register_post_meta(show_in_rest) beschikbaar zijn.
  Daarvoor dient wp/mu-plugins/ci-seo-meta.php (op de server plaatsen in wp-content/mu-plugins/).

Gebruik:
    python -m src.wp_client --detect                       # welke SEO-plugin?
    python -m src.wp_client --list                         # alle pagina's + posts met title/description
    python -m src.wp_client --set 42 --title "..." --description "..."   # preview + bevestiging
    python -m src.wp_client --set 42 --title "..." --dry-run             # alleen preview

    from src.wp_client import WPClient
    wp = WPClient()
    for p in wp.pages(): print(p["id"], p["link"], p["title"]["rendered"])
"""
from __future__ import annotations

import argparse
import difflib
import os
import sys

import requests

from src.common import ROOT, utf8_console  # noqa: F401  (ROOT laadt .env)

YOAST_META = {"title": "_yoast_wpseo_title", "description": "_yoast_wpseo_metadesc",
              "focus_keyword": "_yoast_wpseo_focuskw"}
RANKMATH_META = {"title": "rank_math_title", "description": "rank_math_description",
                 "focus_keyword": "rank_math_focus_keyword"}


class WPClient:
    def __init__(self) -> None:
        base = (os.getenv("WP_BASE_URL") or "https://ci-engineers.com").rstrip("/")
        self.root = base + "/wp-json"
        self.base = self.root + "/wp/v2"
        user, pw = os.getenv("WP_USERNAME"), os.getenv("WP_APP_PASSWORD")
        self.auth = (user, pw) if user and pw else None
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "CI-Search-Manager/1.0",
                                     "Cache-Control": "no-cache"})  # LiteSpeed-cache op Hostinger omzeilen

    # ------------------------------------------------------------ basis
    def _get(self, path: str, **params) -> list | dict:
        r = self.session.get(f"{self.base}/{path}", auth=self.auth, params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def _get_all(self, path: str, **params) -> list[dict]:
        """Alle items, gepagineerd via X-WP-TotalPages (max 100 per pagina)."""
        params.setdefault("per_page", 100)
        params.setdefault("status", "publish")
        if self.auth:
            params.setdefault("context", "edit")  # nodig om 'meta' terug te krijgen
        items: list[dict] = []
        page = 1
        while True:
            r = self.session.get(f"{self.base}/{path}", auth=self.auth, params={**params, "page": page}, timeout=30)
            r.raise_for_status()
            items.extend(r.json())
            if page >= int(r.headers.get("X-WP-TotalPages", "1")):
                return items
            page += 1

    def pages(self, per_page: int = 100) -> list[dict]:
        return self._get_all("pages", per_page=per_page)

    def posts(self, per_page: int = 100) -> list[dict]:
        return self._get_all("posts", per_page=per_page)

    def page(self, page_id: int) -> dict:
        return self._get(f"pages/{page_id}", **({"context": "edit"} if self.auth else {}))

    def item(self, kind: str, item_id: int) -> dict:
        """kind: 'pages' of 'posts'."""
        return self._get(f"{kind}/{item_id}", **({"context": "edit"} if self.auth else {}))

    def update_page(self, page_id: int, **fields) -> dict:
        """fields: title=..., content=..., excerpt=..., meta={...}
        Let op: alleen aanroepen na expliciete bevestiging (zie CLAUDE.md)."""
        return self._post(f"pages/{page_id}", fields)

    def _post(self, path: str, payload: dict) -> dict:
        if not self.auth:
            raise RuntimeError("Schrijven vereist WP_USERNAME en WP_APP_PASSWORD in .env")
        r = self.session.post(f"{self.base}/{path}", auth=self.auth, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------ SEO-plugin
    def namespaces(self) -> list[str]:
        r = self.session.get(self.root, timeout=30)
        r.raise_for_status()
        return r.json().get("namespaces", [])

    def detect_seo_plugin(self) -> str:
        """'yoast' | 'rankmath' | 'none'."""
        sample = self._get("pages", per_page=1, **({"context": "edit"} if self.auth else {}))
        first = sample[0] if sample else {}
        if "yoast_head_json" in first:
            return "yoast"
        if any(k.startswith("rank_math_") for k in (first.get("meta") or {})):
            return "rankmath"
        ns = self.namespaces()
        if any(n.startswith("yoast") for n in ns):
            return "yoast"
        if any(n.startswith("rankmath") for n in ns):
            return "rankmath"
        return "none"

    def meta_exposed(self) -> bool:
        """True als de SEO-metavelden via REST zichtbaar zijn (mu-plugin geïnstalleerd). Werkt zonder auth."""
        sample = self._get("pages", per_page=1, _fields="id,meta")
        meta = (sample[0].get("meta") or {}) if sample else {}
        keys = set(YOAST_META.values()) | set(RANKMATH_META.values())
        return bool(keys & set(meta))

    def meta_writable(self) -> bool:
        """True als schrijven kan: velden zichtbaar én inloggegevens aanwezig."""
        return bool(self.auth) and self.meta_exposed()

    def all_seo_meta(self) -> list[dict]:
        return [seo_meta(p, "pages") for p in self.pages()] + [seo_meta(p, "posts") for p in self.posts()]

    # ------------------------------------------------------------ schrijven (met bevestiging)
    def preview_seo_update(self, kind: str, item_id: int, new: dict) -> tuple[dict, str]:
        """Geeft (huidige meta, unified diff) terug; schrijft niets."""
        current = seo_meta(self.item(kind, item_id), kind)
        return current, seo_diff(current, new)

    def write_seo_meta(self, kind: str, item_id: int, new: dict, confirm: bool = False) -> dict:
        """Schrijft title/description/focus_keyword naar de SEO-plugin-meta.
        Vereist confirm=True (zie CLAUDE.md: nooit zonder expliciete bevestiging)."""
        if not confirm:
            raise RuntimeError("write_seo_meta: confirm=True vereist; toon eerst preview_seo_update()")
        plugin = self.detect_seo_plugin()
        keys = YOAST_META if plugin == "yoast" else RANKMATH_META
        meta = {keys[f]: v for f, v in new.items() if f in keys and v is not None}
        if not meta:
            raise ValueError("Niets te schrijven (title/description/focus_keyword)")
        result = self._post(f"{kind}/{item_id}", {"meta": meta})
        written = result.get("meta") or {}
        missing = [k for k in meta if k not in written]
        if missing:
            raise RuntimeError(
                f"WordPress accepteerde de velden {missing} niet. Staat wp/mu-plugins/ci-seo-meta.php op de server?")
        return result


# ---------------------------------------------------------------- pure helpers
def seo_meta(item: dict, kind: str = "pages") -> dict:
    """Genormaliseerde SEO-meta uit een REST-object (Yoast of Rank Math)."""
    meta = item.get("meta") or {}
    yoast = item.get("yoast_head_json") or {}
    out = {"id": item.get("id"), "type": kind, "link": item.get("link", ""),
           "wp_title": (item.get("title") or {}).get("rendered", ""),
           "title": "", "description": "", "focus_keyword": "", "robots": "", "canonical": "", "source": "none"}
    if yoast:
        robots = yoast.get("robots") or {}
        out.update(title=yoast.get("title", ""), description=yoast.get("description", ""),
                   canonical=yoast.get("canonical", ""), source="yoast",
                   robots=", ".join(v for k, v in robots.items() if k in ("index", "follow")),
                   focus_keyword=meta.get(YOAST_META["focus_keyword"], ""))
    elif any(k in meta for k in RANKMATH_META.values()):
        out.update(title=meta.get(RANKMATH_META["title"], ""), description=meta.get(RANKMATH_META["description"], ""),
                   focus_keyword=meta.get(RANKMATH_META["focus_keyword"], ""),
                   robots=", ".join(meta.get("rank_math_robots") or []), source="rankmath")
    return out


def seo_diff(current: dict, new: dict) -> str:
    """Unified diff van de velden title/description/focus_keyword."""
    fields = ("title", "description", "focus_keyword")
    old_lines = [f"{f}: {current.get(f, '')}" for f in fields]
    new_lines = [f"{f}: {new[f] if new.get(f) is not None else current.get(f, '')}" for f in fields]
    label = f"{current.get('type', '')}/{current.get('id', '')} {current.get('link', '')}"
    return "".join(difflib.unified_diff(
        [l + "\n" for l in old_lines], [l + "\n" for l in new_lines],
        fromfile=f"huidig  {label}", tofile=f"nieuw    {label}", n=3))


def print_table(rows: list[dict]) -> None:
    print(f"{'id':>5}  {'type':5}  {'title (len)':45}  {'descr (len)':>11}  link")
    for r in rows:
        t = f"{r['title'][:40]} ({len(r['title'])})"
        print(f"{r['id']:>5}  {r['type']:5}  {t:45}  {len(r['description']):>11}  {r['link']}")


# ---------------------------------------------------------------- CLI
if __name__ == "__main__":
    utf8_console()
    ap = argparse.ArgumentParser(description="WordPress SEO-metavelden lezen/schrijven")
    ap.add_argument("--detect", action="store_true", help="welke SEO-plugin draait de site")
    ap.add_argument("--list", action="store_true", help="alle pagina's/posts met SEO-title en description")
    ap.add_argument("--set", type=int, metavar="ID", help="SEO-meta van dit item wijzigen (preview + bevestiging)")
    ap.add_argument("--kind", default="pages", choices=["pages", "posts"])
    ap.add_argument("--title")
    ap.add_argument("--description")
    ap.add_argument("--focus", dest="focus_keyword")
    ap.add_argument("--dry-run", action="store_true", help="alleen preview, nooit schrijven")
    args = ap.parse_args()

    wp = WPClient()
    if args.detect:
        plugin = wp.detect_seo_plugin()
        print(f"SEO-plugin: {plugin}")
        exposed = wp.meta_exposed()
        print("Metavelden zichtbaar via REST:", "ja" if exposed else "nee (wp/mu-plugins/ci-seo-meta.php nog niet op de server)")
        print("Schrijven mogelijk:", "ja" if (exposed and wp.auth) else
              "nee (zet WP_USERNAME en WP_APP_PASSWORD in .env)" if exposed else "nee")
    if args.list:
        print_table(wp.all_seo_meta())
    if args.set:
        new = {k: getattr(args, k) for k in ("title", "description", "focus_keyword") if getattr(args, k) is not None}
        if not new:
            print("Geef --title, --description en/of --focus op", file=sys.stderr)
            sys.exit(2)
        current, diff = wp.preview_seo_update(args.kind, args.set, new)
        print(diff or "Geen wijzigingen.")
        if args.dry_run or not diff:
            sys.exit(0)
        if input("Typ JA om dit naar de live site te schrijven: ").strip() == "JA":
            wp.write_seo_meta(args.kind, args.set, new, confirm=True)
            print("Geschreven.")
        else:
            print("Geannuleerd, niets gewijzigd.")
    if not (args.detect or args.list or args.set):
        ap.print_help()
