import shutil
import subprocess
from pathlib import Path

import pytest


def _javascript_runner() -> str | None:
    return shutil.which("node") or next(
        (
            str(path)
            for path in (
                Path(
                    "/System/Library/Frameworks/JavaScriptCore.framework/"
                    "Versions/A/Helpers/jsc"
                ),
                Path("/usr/bin/jsc"),
            )
            if path.is_file()
        ),
        None,
    )


@pytest.mark.skipif(_javascript_runner() is None, reason="No JavaScript runtime installed")
def test_navigation_guard_prevents_stale_browser_updates() -> None:
    project_root = Path(__file__).parents[3]
    source = (
        project_root / "src/tcad_agent/web/static/ide-state.js"
    ).read_text()
    assertions = (
        project_root / "tests/js/ide_navigation_guard.test.js"
    ).read_text()
    completed = subprocess.run(
        [_javascript_runner() or "", "-e", f"{source}\n{assertions}"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
