from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.run_ci_desktop_tests import failure_annotation


def test_desktop_failure_annotation_is_bounded_and_github_safe() -> None:
    annotation = failure_annotation("x" * 5000 + "\nfailed 100%\rsecret")

    assert annotation.startswith("::error title=Desktop test suite failed::")
    assert "failed 100%25%0Dsecret" in annotation
    assert len(annotation) <= 4050


def test_desktop_failure_annotation_handles_empty_output() -> None:
    assert failure_annotation("") == (
        "::error title=Desktop test suite failed::"
        "Desktop tests exited without diagnostic output"
    )
