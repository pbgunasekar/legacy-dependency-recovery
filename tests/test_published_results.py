"""The published results file matches its recorded digest (timings excluded)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import compare_results  # noqa: E402


def test_published_digest():
    expected = open(os.path.join(ROOT, "results", "expected_digest.txt")).read().strip()
    assert compare_results.digest(os.path.join(ROOT, "results", "results.json")) == expected
