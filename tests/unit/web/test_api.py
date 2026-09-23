from html.parser import HTMLParser
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from tcad_agent.control.service import ControlService
from tcad_agent.control.store import SqliteRequestStore
from tcad_agent.model_gateway.base import ScriptedModelGateway
from tcad_agent.web.app import create_app
from tcad_agent.web.launcher import DEFAULT_HOST


class ButtonTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.buttons: dict[str, str] = {}
        self.elements: dict[str, str] = {}
        self._current_button: str | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if attributes.get("id"):
            self.elements[attributes["id"]] = tag
        if tag == "button" and attributes.get("id"):
            self._current_button = attributes["id"]

    def handle_data(self, data: str) -> None:
        if self._current_button is not None:
            self.buttons[self._current_button] = (
                self.buttons.get(self._current_button, "") + data
            ).strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "button":
            self._current_button = None


def client(tmp_path: Path) -> TestClient:
    control = ControlService(
        store=SqliteRequestStore(tmp_path / "requests.sqlite3"),
        gateway=ScriptedModelGateway(()),
        workspace=tmp_path / "workspace",
    )
    return TestClient(create_app(control))


def test_root_and_health_are_local_researcher_entrypoints(tmp_path: Path) -> None:
    web = client(tmp_path)
    assert DEFAULT_HOST == "127.0.0.1"
    health = web.get("/health").json()
    assert health["status"] == "ok"
    assert len(health["runtime_fingerprint"]) == 16
    page = web.get("/")
    assert page.status_code == 200
    assert "Quiloo workspace" in page.text


def test_root_serves_workspace_ide_shell(tmp_path: Path) -> None:
    page = client(tmp_path).get("/")
    parser = ButtonTextParser()
    parser.feed(page.text)

    assert parser.elements["workspace-browser"] == "aside"
    assert parser.elements["repository-tree"] == "div"
    assert parser.elements["workspace-main"] == "main"
    assert parser.elements["workspace-tabs"] == "nav"
    assert parser.elements["agent-panel"] == "aside"
    assert parser.elements["conversation-messages"] == "div"
    assert parser.elements["agent-activity"] == "div"
    assert parser.elements["open-workspace"] == "button"
    assert parser.elements["create-conversation"] == "button"


def test_guided_simulation_remains_available(tmp_path: Path) -> None:
    page = client(tmp_path).get("/simulate")
    assert page.status_code == 200
    assert 'id="workflow-progress"' in page.text
    assert 'id="results-workspace"' in page.text


def test_workspace_and_simulation_share_scientific_theme(tmp_path: Path) -> None:
    web = client(tmp_path)

    workspace_page = web.get("/")
    simulation_page = web.get("/simulate")
    theme = web.get("/static/theme.css?v=20260924-1")

    assert 'href="/static/theme.css?v=20260924-1"' in workspace_page.text
    assert 'href="/static/theme.css?v=20260924-1"' in simulation_page.text
    assert theme.status_code == 200
    assert theme.headers["content-type"].startswith("text/css")


def test_workflow_runtime_uses_operational_copy(tmp_path: Path) -> None:
    script = client(tmp_path).get("/static/app.js?v=20260924-4")

    assert script.status_code == 200
    assert "Simulation workflow" in script.text
    assert "From research intent to <em>validated</em> device evidence." not in script.text


def test_create_request_enters_clarification(tmp_path: Path) -> None:
    prompt = Path("examples/prompts/al-pn-al-equilibrium.md").read_text()
    response = client(tmp_path).post(
        "/api/requests", json={"prompt": prompt, "backend": "sentaurus"}
    )
    assert response.status_code == 201
    assert response.json()["state"] == "needs_clarification"
    assert {question["field"] for question in response.json()["questions"]} >= {
        "geometry.p_region_thickness",
        "geometry.n_region_thickness",
        "contacts.treatment",
    }


def test_clarification_form_has_explicit_continue_action(tmp_path: Path) -> None:
    page = client(tmp_path).get("/simulate")
    parser = ButtonTextParser()
    parser.feed(page.text)
    assert parser.buttons["answer"] == "Continue to plan"


def test_researcher_page_exposes_workflow_review_and_results_regions(
    tmp_path: Path,
) -> None:
    page = client(tmp_path).get("/simulate")
    parser = ButtonTextParser()
    parser.feed(page.text)
    assert parser.elements["workflow-progress"] == "ol"
    assert parser.elements["request-page"] == "section"
    assert parser.elements["clarify-page"] == "section"
    assert parser.elements["review-page"] == "section"
    assert parser.elements["results-page"] == "section"
    assert parser.elements["plan-summary"] == "div"
    assert parser.elements["review-details"] == "div"
    assert parser.elements["results-overview"] == "div"
    assert parser.elements["field-selector"] == "select"
    assert parser.elements["field-scale"] == "select"
    assert parser.elements["field-chart"] == "svg"
    assert parser.elements["bias-results"] == "tbody"
    assert parser.elements["field-data"] == "tbody"
    assert parser.elements["validation-list"] == "div"
    assert parser.elements["artifacts"] == "details"


def test_persistent_workflow_urls_serve_the_application_shell(tmp_path: Path) -> None:
    web = client(tmp_path)
    request_id = uuid4()
    for stage in ("clarify", "review", "results"):
        response = web.get(f"/requests/{request_id}/{stage}")
        assert response.status_code == 200
        assert 'id="workflow-progress"' in response.text


def test_invalid_request_identifier_is_rejected(tmp_path: Path) -> None:
    response = client(tmp_path).get("/api/requests/not-a-uuid")
    assert response.status_code == 422


def test_unexpected_errors_do_not_echo_secrets() -> None:
    secret = "ABSK-never-return-this"

    class ExplodingControl:
        def submit(self, prompt: str, *, backend: str):
            raise RuntimeError(f"provider rejected {secret}")

    web = TestClient(create_app(ExplodingControl()), raise_server_exceptions=False)
    response = web.post("/api/requests", json={"prompt": "simulate", "backend": "devsim"})
    assert response.status_code == 500
    assert secret not in response.text
    assert response.json() == {
        "code": "internal_error",
        "message": "The request failed without exposing provider or credential details.",
    }
