from src.wp_client import seo_diff, seo_meta

YOAST_ITEM = {
    "id": 1388, "link": "https://ci-engineers.com/nieuws/", "title": {"rendered": "Nieuws"},
    "meta": {"_yoast_wpseo_focuskw": "nieuws"},
    "yoast_head_json": {"title": "Nieuws - CI Engineers", "description": "Bekijk hier ons nieuws.",
                        "robots": {"index": "index", "follow": "follow", "max-snippet": "max-snippet:-1"},
                        "canonical": "https://ci-engineers.com/nieuws/"},
}
RM_ITEM = {"id": 7, "link": "https://x.nl/a/", "title": {"rendered": "A"},
           "meta": {"rank_math_title": "A | X", "rank_math_description": "Over A", "rank_math_robots": ["index"]}}


def test_seo_meta_yoast():
    m = seo_meta(YOAST_ITEM, "pages")
    assert m["source"] == "yoast" and m["title"] == "Nieuws - CI Engineers"
    assert m["description"] == "Bekijk hier ons nieuws." and m["robots"] == "index, follow"
    assert m["focus_keyword"] == "nieuws" and m["canonical"].endswith("/nieuws/")


def test_seo_meta_rankmath_and_none():
    m = seo_meta(RM_ITEM, "posts")
    assert m["source"] == "rankmath" and m["title"] == "A | X" and m["robots"] == "index"
    assert seo_meta({"id": 1, "title": {"rendered": "x"}})["source"] == "none"


def test_seo_diff_only_changed_fields():
    cur = seo_meta(YOAST_ITEM)
    d = seo_diff(cur, {"description": "Nieuwe beschrijving"})
    assert "-description: Bekijk hier ons nieuws." in d
    assert "+description: Nieuwe beschrijving" in d
    assert "title: Nieuws - CI Engineers" in d and "-title" not in d
    assert seo_diff(cur, {"title": cur["title"]}) == ""
