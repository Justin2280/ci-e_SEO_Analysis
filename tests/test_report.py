from datetime import date

from src.report import build_report, delta, sample_runs


def test_delta_formats():
    assert delta(5, 3) == "+2 ▲"
    assert delta(3, 5) == "−2 ▼"
    assert delta(3, 5, invert=True) == "−2 ▲"
    assert delta(4.25, 4.5, 1, invert=True) == "−0.2 ▲"
    assert delta(2, 2) == "±0"
    assert delta(2, None) == "" and delta(None, 2) == ""


def test_build_report_with_samples_and_trends():
    md = build_report(*sample_runs(), day=date(2026, 9, 8))
    assert md.startswith("# Online zichtbaarheid CI-Engineers — weekrapport 08-09-2026")
    assert "## In het kort" in md and "**AI-assistenten**" in md and "**Google**" in md and "**Website**" in md
    assert "## Wat gaan we doen" in md and "1. **" in md
    assert "### Wat AI-assistenten over ons zeggen" in md and "| ChatGPT (OpenAI) |" in md and "▲" in md
    assert "### Hoe onze website ervoor staat" in md and "korte omschrijving" in md
    assert "### Hoe Google ons vindt" in md and "ci engineers" in md
    assert "## Uitleg van de termen" in md


def test_build_report_without_data():
    md = build_report([], [], [])
    assert md.count("Geen data") == 3


def test_graph_message_payload():
    import base64

    from src.report import graph_message

    p = graph_message("# Rapport", "Onderwerp", "a@ci-engineers.com, b@ci-engineers.com", "weekrapport.md")
    m = p["message"]
    assert m["subject"] == "Onderwerp" and m["body"]["contentType"] == "HTML" and "<h1" in m["body"]["content"]
    assert [r["emailAddress"]["address"] for r in m["toRecipients"]] == ["a@ci-engineers.com", "b@ci-engineers.com"]
    att = m["attachments"][0]
    assert att["name"] == "weekrapport.md"
    assert base64.b64decode(att["contentBytes"]).decode() == "# Rapport"


def test_email_configured(monkeypatch):
    from src.report import email_configured

    for k in ("MS_TENANT_ID", "MS_CLIENT_ID", "MS_CLIENT_SECRET", "SMTP_HOST"):
        monkeypatch.delenv(k, raising=False)
    assert email_configured() is None
    monkeypatch.setenv("SMTP_HOST", "smtp.office365.com")
    assert email_configured() == "smtp"
    monkeypatch.setenv("MS_TENANT_ID", "t"); monkeypatch.setenv("MS_CLIENT_ID", "c"); monkeypatch.setenv("MS_CLIENT_SECRET", "s")
    assert email_configured() == "graph"


def test_ai_section_excludes_error_rows():
    from datetime import date

    from src.report import ai_section

    rows = [{"provider": "gemini", "tag": "personeel", "brand_mentioned": False, "competitors_mentioned": [],
             "error": "404 NOT_FOUND model niet beschikbaar"} for _ in range(3)]
    rows += [{"provider": "openai", "tag": "personeel", "brand_mentioned": True, "competitors_mentioned": []}]
    md = "\n".join(ai_section((date(2026, 9, 8), rows), None))
    assert "| Gemini (Google) | geen antwoorden ⚠ 3 storingen |" in md
    assert "| ChatGPT (OpenAI) | 1 van 1 (100%) |" in md
    assert "3 vragen konden niet gesteld worden" in md and "404 NOT_FOUND" in md
    assert "Vragen van sollicitanten: genoemd in 1 van 1" in md


def test_graph_error_text_and_hint():
    from src.report import graph_error_text, graph_hint

    class R:
        text = "x"

        def json(self):
            return {"error": "invalid_request", "error_description": "AADSTS90002: Tenant 'abc' not found."}

    msg = graph_error_text(R())
    assert msg.startswith("invalid_request: AADSTS90002")
    assert "MS_TENANT_ID" in graph_hint(msg)
    assert graph_hint("iets anders") == ""


def test_actions_and_summary_from_data():
    from datetime import date

    from src.report import actions_section, summary_section

    seo = [{"url": "https://ci-engineers.com/contact/", "status": 200, "meta_description": "", "h1": [], "issues": ["x"],
            "images_without_alt": 2, "load_ms": 100},
           {"url": "https://ci-engineers.com/2026/07/nieuws/", "status": 200, "meta_description": "", "h1": ["k"],
            "issues": ["x"], "images_without_alt": 0, "load_ms": 100}]
    gsc = [{"dimensions": "query", "query": "ingenieursbureau", "clicks": 0, "impressions": 22, "ctr": 0.0,
            "position": 49.8, "period_start": "2026-08-09", "period_end": "2026-09-05", "page": None},
           {"dimensions": "query", "query": "civieltechnisch ingenieursbureau", "clicks": 0, "impressions": 4, "ctr": 0.0,
            "position": 6.0, "period_start": "2026-08-09", "period_end": "2026-09-05", "page": None},
           {"dimensions": "page", "page": "https://ci-engineers.com/contact/", "clicks": 0, "impressions": 30, "ctr": 0.0,
            "position": 40.0, "period_start": "2026-08-09", "period_end": "2026-09-05", "query": None}]
    ai = [{"provider": "openai", "tag": "opdrachtgever", "brand_mentioned": False, "competitors_mentioned": ["Sweco"]}]
    run = date(2026, 9, 8)
    acts = "\n".join(actions_section((run, ai), (run, seo), (run, gsc)))
    assert "Korte omschrijvingen schrijven** voor 2 pagina's" in acts
    assert acts.index("/contact/") < acts.index("/2026/07/nieuws/")  # pagina met impressies eerst
    assert "Kansrijke zoekwoorden" in acts and "civieltechnisch ingenieursbureau" in acts
    assert "AI-assistenten ons kennen" in acts and "Sweco" in acts
    assert "Hoofdkop toevoegen** op 1 pagina " in acts
    summ = "\n".join(summary_section((run, ai), None, (run, seo), None, (run, gsc), None))
    assert "niet één keer genoemd" in summ and "plek 43.1" in summ and "pagina 5 van Google" in summ
    assert "2 pagina's missen" in summ


def test_md_to_html_tables_lists_and_trend_colors():
    from src.report import md_to_html

    md = "# Titel\n\n## Kop\n\n- punt **vet** [link](https://x.nl)\n\n1. actie\n\n| A | B |\n|---|---|\n| 1 | +2 ▲ |\n"
    h = md_to_html(md)
    assert "<h1" in h and "<h2" in h and "<ul" in h and "<ol" in h and "<table" in h
    assert "<strong>vet</strong>" in h and 'href="https://x.nl"' in h
    assert "#1a7f37" in h  # groen voor ▲
    assert "<script" not in h
