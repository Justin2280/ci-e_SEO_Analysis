import json
from datetime import date

from src.seo_suggest import (apply_suggestions, build_prompt, check_suggestion, fake_suggestion, make_suggestions,
                             parse_ids, select_pages, suggestions_markdown)

ITEMS = [
    {"id": 1388, "type": "pages", "link": "https://ci-engineers.com/nieuws/", "wp_title": "Nieuws", "title": "", "description": "Bekijk ons nieuws."},
    {"id": 692, "type": "pages", "link": "https://ci-engineers.com/contact/", "wp_title": "Contact", "title": "", "description": ""},
    {"id": 7, "type": "posts", "link": "https://ci-engineers.com/2026/07/a/", "wp_title": "Project A", "title": "", "description": " "},
]


def test_select_pages_without_description_pages_first():
    sel = select_pages(ITEMS)
    assert [m["id"] for m in sel] == [692, 7]
    assert [m["id"] for m in select_pages(ITEMS, ids={1388})] == [1388]  # expliciet gekozen, ook mét omschrijving
    assert len(select_pages(ITEMS, limit=1)) == 1
    assert parse_ids("692, 7;x") == {692, 7} and parse_ids("") is None


def test_check_suggestion_and_prompt():
    assert check_suggestion("kort") == ["te kort (4 < 110)"]
    assert check_suggestion("x" * 200) == ["te lang (200 > 155)"]
    assert check_suggestion("Ontdek " + "y" * 120) == ["clickbait-opening"]
    assert check_suggestion(fake_suggestion(ITEMS[1], "")["description"]) == []
    prompt = build_prompt(ITEMS[1], "Neem contact op met ons kantoor in Zaandam.")
    assert "https://ci-engineers.com/contact/" in prompt and "Zaandam" in prompt and "110-155" in prompt


def test_make_suggestions_handles_failures_and_markdown():
    def suggest(meta, text):
        if meta["id"] == 7:
            raise RuntimeError("API kapot")
        return fake_suggestion(meta, text)

    rows = make_suggestions(select_pages(ITEMS), lambda url: "tekst", suggest)
    assert rows[0]["id"] == 692 and rows[0]["proposed_description"] and rows[0]["warnings"] == []
    assert rows[1]["id"] == 7 and rows[1]["proposed_description"] == "" and "mislukt" in rows[1]["warnings"][0]
    md = suggestions_markdown(rows, date(2026, 9, 8))
    assert md.startswith("# SEO-voorstellen 08-09-2026") and "## Contact  (id 692, pages)" in md and "> " in md


class FakeWP:
    def __init__(self):
        self.written = []

    def write_seo_meta(self, kind, item_id, new, confirm=False):
        assert confirm is True
        if item_id == 7:
            raise RuntimeError("geen rechten")
        self.written.append((kind, item_id, new))
        return {"meta": new}


def test_apply_suggestions_requires_confirmation_and_marks_applied(tmp_path):
    rows = [{"id": 692, "type": "pages", "link": "https://ci-engineers.com/contact/", "wp_title": "Contact", "title": "",
             "description": "", "proposed_description": "Nieuwe omschrijving.", "focus_keyword": "contact", "warnings": []},
            {"id": 7, "type": "posts", "link": "https://ci-engineers.com/2026/07/a/", "wp_title": "A", "title": "",
             "description": "", "proposed_description": "Ook nieuw.", "focus_keyword": "a", "warnings": []}]
    path = tmp_path / "seo-voorstellen-2026-09-08.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    wp = FakeWP()
    assert apply_suggestions(path, None, lambda: False, wp=wp) == 0 and wp.written == []
    assert apply_suggestions(path, None, lambda: True, wp=wp) == 1
    assert wp.written == [("pages", 692, {"description": "Nieuwe omschrijving.", "focus_keyword": "contact"})]
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved[0]["applied_at"] and "toepassen mislukt: geen rechten" in saved[1]["warnings"][0]
    assert "✔ Toegepast op" in path.with_suffix(".md").read_text(encoding="utf-8")
    assert apply_suggestions(path, {692}, lambda: True, wp=wp) == 0  # al toegepast → niets te doen
