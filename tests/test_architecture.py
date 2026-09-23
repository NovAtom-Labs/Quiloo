import re
from pathlib import Path

SRC_ROOT = Path(__file__).parents[1] / "src" / "tcad_agent"
RUNNERS_ROOT = SRC_ROOT / "runners"


def test_product_modules_do_not_branch_on_fixture_device_names() -> None:
    forbidden = {"pn_diode", "pin_diode", "moscap", "mosfet"}
    source = "\n".join(path.read_text() for path in SRC_ROOT.rglob("*.py"))
    assert not (forbidden & set(re.findall(r"[a-z_]+", source.lower())))


def test_no_shell_execution_in_runner_sources() -> None:
    source = "\n".join(path.read_text() for path in RUNNERS_ROOT.rglob("*.py"))
    assert "shell=True" not in source
    assert "os.system" not in source


def test_backend_specific_code_is_confined_to_adapters() -> None:
    generic_modules = [
        path
        for path in SRC_ROOT.rglob("*.py")
        if "adapters" not in path.parts and path.name != "cli.py"
    ]
    for path in generic_modules:
        assert "import tcad_agent.adapters.devsim" not in path.read_text()
        assert "import tcad_agent.adapters.sentaurus" not in path.read_text()
