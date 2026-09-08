import json
from datetime import date

from src.common import load_runs, results_path


def test_results_path_naming():
    assert results_path("ai_visibility", date(2026, 9, 8)).name == "2026-09-08.jsonl"
    assert results_path("seo_audit", date(2026, 9, 8)).name == "seo_audit-2026-09-08.jsonl"


def test_load_runs_newest_first(tmp_path):
    for name, val in (("2026-09-01.jsonl", 1), ("2026-09-08.jsonl", 2), ("seo_audit-2026-09-08.jsonl", 3)):
        (tmp_path / name).write_text(json.dumps({"v": val}) + "\n", encoding="utf-8")
    runs = load_runs("ai_visibility", n=2, results_dir=tmp_path)
    assert [d.isoformat() for d, _ in runs] == ["2026-09-08", "2026-09-01"]
    assert runs[0][1] == [{"v": 2}]
    assert load_runs("seo_audit", results_dir=tmp_path)[0][1] == [{"v": 3}]
    assert load_runs("search_console", results_dir=tmp_path) == []


def test_missing_keys():
    from src.common import missing_keys

    empty = missing_keys({})
    assert empty["wp_client (schrijven)"] == ["WP_USERNAME", "WP_APP_PASSWORD"]
    assert "GSC_SITE_URL" in empty["search_console"]
    assert empty["ai_visibility (minimaal één provider)"] == ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]
    one_provider = missing_keys({"GEMINI_API_KEY": "x"})
    assert one_provider["ai_visibility (minimaal één provider)"] == []
    gsc = missing_keys({"GSC_SERVICE_ACCOUNT_FILE": "config/bestaat-niet.json", "GSC_SITE_URL": "sc-domain:x"})
    assert gsc["search_console"] == ["GSC_SERVICE_ACCOUNT_FILE (bestand niet gevonden)"]


def test_missing_keys_email_either_route():
    from src.common import missing_keys

    graph = missing_keys({"MS_TENANT_ID": "t", "MS_CLIENT_ID": "c", "MS_CLIENT_SECRET": "s",
                          "REPORT_EMAIL_FROM": "a@x.nl", "REPORT_EMAIL_TO": "b@x.nl"})
    assert graph["report --email (Microsoft 365 / Graph)"] == [] and graph["report --email (SMTP, alternatief)"] == []
    assert "MS_TENANT_ID" in missing_keys({})["report --email (Microsoft 365 / Graph)"]
