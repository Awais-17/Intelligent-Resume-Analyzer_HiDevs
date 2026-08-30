"""Unit tests for the resume screening system.

Run with:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from resume_screener.matcher import JobRequirements, compute_match
from resume_screener.parser import (parse_resume, read_resume_text)
from resume_screener.report import (render_report, render_summary,
                                    result_to_json)
from resume_screener.storage import (StorageError, append_to_results,
                                     load_json, save_json)

DATA = Path(__file__).resolve().parent.parent / "data"


class TestParsing(unittest.TestCase):
    def tearDown(self):
        pass

    def test_name_email_phone_parsing(self):
        parsed = parse_resume(DATA / "resumes" / "alice_johnson.txt")
        self.assertEqual(parsed.name.title(), "Alice Johnson")
        self.assertEqual(parsed.email, "alice.johnson@example.com")
        self.assertIsNotNone(parsed.phone)

    def test_skill_extraction(self):
        parsed = parse_resume(DATA / "resumes" / "alice_johnson.txt")
        lower = [s.lower() for s in parsed.skills]
        for skill in ("python", "docker", "aws", "kubernetes", "django",
                      "fastapi", "rest api", "kafka"):
            self.assertIn(skill, lower)

    def test_experience_extraction(self):
        parsed = parse_resume(DATA / "resumes" / "alice_johnson.txt")
        self.assertGreaterEqual(parsed.years_of_experience, 7.0)

    def test_education_extraction(self):
        parsed = parse_resume(DATA / "resumes" / "bob_martinez.txt")
        combined = " ".join(parsed.education).lower()
        self.assertIn("b.a", combined)

    def test_missing_file_raises(self):
        with self.assertRaises(Exception):
            parse_resume(DATA / "resumes" / "nonexistent.txt")

    def test_empty_text_raises(self):
        with TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.txt"
            empty.write_text("   \n\n", encoding="utf-8")
            with self.assertRaises(Exception):
                parse_resume(empty)


class TestMatching(unittest.TestCase):
    def test_score_range(self):
        reqs = JobRequirements.from_dict({
            "title": "Python Dev",
            "required_skills": ["python", "sql"],
            "preferred_skills": ["docker"],
            "min_years_experience": 3.0,
            "education_level": "Bachelor",
        })
        parsed = parse_resume(DATA / "resumes" / "alice_johnson.txt")
        result = compute_match(parsed, reqs)
        self.assertTrue(0.0 <= result.score <= 100.0)
        self.assertEqual(result.required_matched, ["python", "sql"])

    def test_strong_match_high_score(self):
        reqs = JobRequirements.from_dict(json.loads(
            (DATA / "job_requirements.json").read_text(encoding="utf-8")))
        alice = compute_match(
            parse_resume(DATA / "resumes" / "alice_johnson.txt"), reqs)
        self.assertGreaterEqual(alice.score, 80)
        self.assertEqual(alice.recommendation, "Strong Match")

    def test_weak_match_low_score(self):
        reqs = JobRequirements.from_dict({
            "title": "Senior Python Backend Engineer",
            "required_skills": ["python", "rest api", "sql", "docker", "aws"],
            "preferred_skills": ["kubernetes", "django", "fastapi", "kafka"],
            "min_years_experience": 4.0,
            "education_level": "Bachelor",
        })
        bob = compute_match(
            parse_resume(DATA / "resumes" / "bob_martinez.txt"), reqs)
        self.assertLess(bob.score, 60)
        self.assertIn("python", bob.required_missing)
        self.assertGreaterEqual(bob.min_experience_gap, 2.0)


class TestStorage(unittest.TestCase):
    def test_json_roundtrip(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.json"
            save_json({"a": 1, "b": [1, 2]}, path)
            self.assertEqual(load_json(path), {"a": 1, "b": [1, 2]})

    def test_append_to_results_creates_and_grows(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.json"
            append_to_results({"id": 1}, path)
            append_to_results({"id": 2}, path)
            data = load_json(path)
            self.assertEqual(len(data), 2)

    def test_load_missing_file_raises(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(StorageError):
                load_json(Path(tmp) / "nope.json")

    def test_bad_json_raises(self):
        with TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            with self.assertRaises(StorageError):
                load_json(bad)


class TestReport(unittest.TestCase):
    def test_render_report_contains_key_fields(self):
        reqs = JobRequirements.from_dict({"title": "Python Dev"})
        parsed = parse_resume(DATA / "resumes" / "carol_ng.txt")
        result = compute_match(parsed, reqs)
        text = render_report(result, reqs)
        for fragment in ("CANDIDATE ANALYSIS REPORT", "Carol Ng",
                         "Match score", "Recommendation"):
            self.assertIn(fragment, text)

    def test_summary_ordering(self):
        from resume_screener.matcher import MatchResult
        low = MatchResult(score=40.0, candidate_name="A")
        high = MatchResult(score=90.0, candidate_name="B")
        text = render_summary([low, high])
        self.assertLess(text.index("90.0"), text.index("40.0"))

    def test_json_record_shape(self):
        from resume_screener.matcher import MatchResult
        record = result_to_json(MatchResult(score=1.0))
        self.assertIn("candidate", record)
        self.assertIn("generated_at", record)


if __name__ == "__main__":
    unittest.main()