"""Text retrieval of media: scoring, licence gate, explanations, and plan assignment (no files needed)."""
import json
import unittest
from pathlib import Path

from uvs import media_index as M
from uvs import retrieval as R

ROOT = Path(__file__).resolve().parents[2]


def asset(name, *, tags=(), description="", license_="cc0", kind="image", sha=None, dhash=None):
    return M.Asset(path=f"/media/{name}", kind=kind, sha256=sha or f"sha-{name}", dhash=dhash,
                   tags=list(tags), description=description,
                   provenance={"source": "test", "license": license_})


class TermsTests(unittest.TestCase):
    def test_splits_underscores_hyphens_and_normalises_plurals(self):
        self.assertEqual(R.terms("city_street-students"), {"city", "street", "student"})

    def test_vietnamese_words_stay_whole(self):
        self.assertIn("phố", R.terms("Thành phố"))
        self.assertIn("thành", R.terms("Thành phố"))

    def test_query_terms_drop_stopwords_and_duplicates(self):
        self.assertEqual(R._query_terms("the city and the cities"), ["city"])


class ScoringTests(unittest.TestCase):
    def test_tag_match_scores_above_name_only_match(self):
        tagged = asset("a.jpg", tags=["city"])
        named = asset("city.jpg")
        hits = R.search([named, tagged], "city", min_score=0.3)
        self.assertEqual([h.asset.path for h in hits], ["/media/a.jpg", "/media/city.jpg"])
        self.assertAlmostEqual(hits[0].score, 1.0)
        self.assertAlmostEqual(hits[1].score, 1 / 3, places=3)

    def test_synonym_match_is_weaker_and_says_so(self):
        hits = R.search([asset("u.jpg", tags=["urban"])], "city", min_score=0.3)
        self.assertEqual(len(hits), 1)
        self.assertAlmostEqual(hits[0].score, 0.6, places=3)
        self.assertEqual(hits[0].matched, ["tags:urban (synonym of city)"])

    def test_missing_terms_are_reported_not_hidden(self):
        hits = R.search([asset("c.jpg", tags=["city"])], "city money", min_score=0.3)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].missing, ["money"])
        self.assertEqual(hits[0].matched, ["tags:city"])

    def test_no_invented_match_for_an_unlisted_synonym(self):
        # "canine" is not in the synonym table for "dog", so nothing is returned.
        self.assertEqual(R.search([asset("c.jpg", tags=["canine"])], "dog"), [])

    def test_weak_match_below_threshold_is_dropped(self):
        self.assertEqual(R.search([asset("city.jpg")], "city", min_score=0.5), [])

    def test_empty_query_returns_nothing(self):
        self.assertEqual(R.search([asset("a.jpg", tags=["the"])], "the and of"), [])

    def test_kind_filter(self):
        clip = asset("c.mp4", tags=["city"], kind="video")
        still = asset("c.jpg", tags=["city"], kind="image")
        hits = R.search([clip, still], "city", kind="video")
        self.assertEqual([h.asset.path for h in hits], ["/media/c.mp4"])


class LicenceAndDuplicateTests(unittest.TestCase):
    def test_unknown_licence_is_excluded_when_required(self):
        unknown = asset("u.jpg", tags=["city"], license_="unknown")
        known = asset("k.jpg", tags=["city"], license_="cc0")
        self.assertEqual(len(R.search([unknown, known], "city")), 2)
        hits = R.search([unknown, known], "city", require_known_licence=True)
        self.assertEqual([h.asset.path for h in hits], ["/media/k.jpg"])

    def test_identical_files_are_returned_once(self):
        a = asset("a.jpg", tags=["city"], sha="same")
        b = asset("b.jpg", tags=["city"], sha="same")
        self.assertEqual(len(R.search([a, b], "city")), 1)

    def test_visual_near_duplicates_are_returned_once(self):
        a = asset("a.jpg", tags=["city"], sha="s1", dhash="0000000000000000")
        b = asset("b.jpg", tags=["city"], sha="s2", dhash="0000000000000001")
        self.assertEqual(len(R.search([a, b], "city")), 1)


class PlanAssignmentTests(unittest.TestCase):
    def _plan(self, *scenes):
        return {"scenes": [{"id": s[0], "visual": s[1], "text": s[2]} for s in scenes]}

    def test_each_asset_is_used_once_and_the_second_scene_says_why(self):
        assets = [asset("c.jpg", tags=["city"])]
        plan = self._plan(("s1", "b_roll", "city streets"), ("s2", "b_roll", "city at night"))
        result = R.plan_broll(plan, assets)
        self.assertEqual(result["scenes"][0]["status"], "matched")
        self.assertEqual(result["scenes"][1]["status"], "unfilled")
        self.assertEqual(result["scenes"][1]["reason"], "best match is already used in scene s1")
        self.assertEqual(result["counts"], {"matched": 1, "unfilled": 1, "generated": 0})

    def test_generated_visuals_get_no_footage(self):
        assets = [asset("c.jpg", tags=["chart", "enrollment"])]
        plan = self._plan(("s1", "chart", "enrollment grew"))
        row = R.plan_broll(plan, assets)["scenes"][0]
        self.assertEqual(row["status"], "generated")
        self.assertIsNone(row["path"])

    def test_scene_without_content_words_is_unfilled(self):
        plan = self._plan(("s1", "b_roll", "the and of"))
        row = R.plan_broll(plan, [asset("c.jpg", tags=["city"])])["scenes"][0]
        self.assertEqual(row["reason"], "scene text has no content words to match")

    def test_demo_plan_with_unrelated_footage_fills_nothing_by_invention(self):
        plan = json.loads((ROOT / "examples/narrative_demo/data_plan.json").read_text(encoding="utf-8"))
        unrelated = [asset("forest.jpg", tags=["forest", "tree"]), asset("sea.jpg", tags=["ocean"])]
        result = R.plan_broll(plan, unrelated)
        footage = [r for r in result["scenes"] if r["status"] != "generated"]
        self.assertTrue(footage, "demo plan should contain footage scenes")
        self.assertTrue(all(r["status"] == "unfilled" and r["path"] is None for r in footage))

    def test_licence_gate_applies_to_plan(self):
        assets = [asset("c.jpg", tags=["city"], license_="unknown")]
        plan = self._plan(("s1", "b_roll", "city"))
        self.assertEqual(R.plan_broll(plan, assets)["scenes"][0]["status"], "matched")
        self.assertEqual(R.plan_broll(plan, assets, require_known_licence=True)["scenes"][0]["status"],
                         "unfilled")


class SidecarTests(unittest.TestCase):
    def test_sidecar_tags_and_description_are_sanitised(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            img = Path(tmp) / "a.png"
            from PIL import Image
            Image.new("RGB", (8, 8), (10, 20, 30)).save(img)
            img.with_suffix(".png.json").write_text(json.dumps({
                "source": "own", "license": "cc0",
                "tags": ["  City ", "city", "", 7, "night", "x" * 100],
                "description": "d" * 900}), encoding="utf-8")
            a = M.index_file(img)
        self.assertEqual(a.tags[:3], ["city", "night", "x" * 60])
        self.assertEqual(len(a.tags), 3)
        self.assertEqual(len(a.description), M.MAX_DESCRIPTION)
        self.assertEqual(a.provenance, {"source": "own", "license": "cc0"})

    def test_missing_sidecar_gives_no_tags_and_unknown_licence(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            from PIL import Image
            img = Path(tmp) / "a.png"
            Image.new("RGB", (8, 8)).save(img)
            a = M.index_file(img)
        self.assertEqual(a.tags, [])
        self.assertEqual(a.provenance["license"], "unknown")
        self.assertIn("no provenance sidecar", a.notes)


if __name__ == "__main__":
    unittest.main()
