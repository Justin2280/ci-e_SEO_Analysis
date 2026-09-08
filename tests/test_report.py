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
    assert md.startswith("# Weekrapport CI Search Manager — 2026-09-08")
    assert "## AI-zichtbaarheid" in md and "| openai |" in md and "▲" in md
    assert "## SEO-audit" in md and "Pagina's zonder meta description" in md
    assert "## Google Search Console" in md and "ci engineers" in md


def test_build_report_without_data():
    md = build_report([], [], [])
    assert md.count("Geen data") == 3
