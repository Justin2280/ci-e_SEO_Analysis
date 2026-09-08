"""
Minimale WordPress REST API-client (application password, basic auth).

Vereist in .env: WP_BASE_URL, WP_USERNAME, WP_APP_PASSWORD
Application password aanmaken: WP-admin → Gebruikers → Profiel → Application Passwords.

Gebruik:
    from src.wp_client import WPClient
    wp = WPClient()
    for p in wp.pages(): print(p["id"], p["link"], p["title"]["rendered"])
"""
from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class WPClient:
    def __init__(self) -> None:
        self.base = os.environ["WP_BASE_URL"].rstrip("/") + "/wp-json/wp/v2"
        self.auth = (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])

    def _get(self, path: str, **params) -> list | dict:
        r = requests.get(f"{self.base}/{path}", auth=self.auth, params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def pages(self, per_page: int = 100) -> list[dict]:
        return self._get("pages", per_page=per_page, status="publish")

    def posts(self, per_page: int = 100) -> list[dict]:
        return self._get("posts", per_page=per_page, status="publish")

    def page(self, page_id: int) -> dict:
        return self._get(f"pages/{page_id}")

    def update_page(self, page_id: int, **fields) -> dict:
        """fields: title=..., content=..., excerpt=..., meta={...}
        Let op: alleen aanroepen na expliciete bevestiging (zie CLAUDE.md)."""
        r = requests.post(f"{self.base}/pages/{page_id}", auth=self.auth, json=fields, timeout=30)
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    wp = WPClient()
    for p in wp.pages():
        print(p["id"], p["link"], "-", p["title"]["rendered"])
