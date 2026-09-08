from datetime import date

from src.search_console import date_range, query_gsc, sample_api_rows, to_rows


def test_date_range_respects_lag():
    start, end = date_range(days=28, lag=3, today=date(2026, 9, 8))
    assert end == date(2026, 9, 5)
    assert start == date(2026, 8, 9)
    assert (end - start).days + 1 == 28


def test_to_rows_maps_keys_by_dimension():
    rows = to_rows(sample_api_rows(["page", "query"]), ["page", "query"], date(2026, 8, 1), date(2026, 8, 28))
    r = rows[0]
    assert r["module"] == "search_console" and r["dimensions"] == "page,query"
    assert r["page"].startswith("https://") and r["query"]
    assert 0 <= r["ctr"] <= 1 and r["clicks"] == 12
    only_query = to_rows(sample_api_rows(["query"]), ["query"], date(2026, 8, 1), date(2026, 8, 28))
    assert only_query[0]["page"] is None


class FakeQuery:
    def __init__(self, pages):
        self.pages, self.bodies = pages, []

    def query(self, siteUrl, body):
        self.bodies.append(body)
        return self

    def execute(self):
        return {"rows": self.pages[len(self.bodies) - 1]}


class FakeService:
    def __init__(self, pages):
        self.q = FakeQuery(pages)

    def searchanalytics(self):
        return self.q


def test_query_gsc_paginates_with_start_row():
    full = [{"keys": [f"q{i}"], "clicks": 1, "impressions": 2, "ctr": 0.5, "position": 3.0} for i in range(2)]
    svc = FakeService([full, full[:1]])
    rows = query_gsc(svc, "sc-domain:x", date(2026, 8, 1), date(2026, 8, 2), ["query"], row_limit=2)
    assert len(rows) == 3
    assert [b["startRow"] for b in svc.q.bodies] == [0, 2]
