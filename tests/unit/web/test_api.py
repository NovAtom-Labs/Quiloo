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
    assert "Agent Kronig workspace" in page.text


def test_root_serves_workspace_ide_shell(tmp_path: Path) -> None:
    page = client(tmp_path).get("/")
    parser = ButtonTextParser()
    parser.feed(page.text)

    assert parser.elements["workspace-browser"] == "aside"
    assert parser.elements["repository-tree"] == "div"
    assert parser.elements["workspace-main"] == "main"
    assert "workspace-tabs" not in parser.elements
    assert parser.elements["workspace-context-name"] == "strong"
    assert parser.elements["workspace-context-state"] == "span"
    assert parser.elements["file-viewer"] == "section"
    assert parser.elements["file-viewer-body"] == "div"
    assert parser.elements["file-editor"] == "textarea"
    assert parser.elements["file-viewer-download"] == "a"
    assert parser.elements["agent-panel"] == "aside"
    assert parser.elements["conversation-select"] == "select"
    assert "conversation-list" not in parser.elements
    assert "Select a conversation" in page.text
    assert parser.elements["conversation-messages"] == "div"
    assert parser.elements["agent-progress"] == "div"
    assert parser.elements["agent-activity"] == "div"
    assert parser.elements["open-workspace"] == "button"
    assert parser.elements["browse-workspace"] == "button"
    assert parser.elements["create-conversation"] == "button"
    assert parser.elements["refresh-conversation"] == "button"
    assert parser.elements["toggle-agent-panel"] == "button"
    assert parser.elements["close-agent-panel"] == "button"
    assert parser.elements["file-viewer-edit"] == "button"
    assert parser.elements["file-viewer-save"] == "button"
    assert parser.elements["file-viewer-cancel"] == "button"
    assert 'href="/simulate"' not in page.text
    assert "No workspace open" not in page.text


def test_workspace_header_separates_product_and_company_branding(tmp_path: Path) -> None:
    page = client(tmp_path).get("/").text

    product_wordmark = '<strong class="product-wordmark" aria-label="Agent Kronig">'
    agent_name = '<span class="product-agent" aria-hidden="true">Agent</span>'
    kronig_name = '<span class="product-kronig" aria-hidden="true">Kronig</span>'
    company = '<span class="company-lockup" aria-label="NovAtom Labs">'
    atom = (
        '<img class="company-atom" '
        'src="/static/novatom-atom-mark.svg" alt="" aria-hidden="true">'
    )
    assert product_wordmark in page
    assert agent_name in page
    assert kronig_name in page
    assert company in page
    assert atom in page
    assert '<span class="company-nov">Nov</span>' in page
    assert '<span class="company-atom-text">Atom</span>' in page
    assert '<span class="company-labs">Labs</span>' in page
    assert page.index(agent_name) < page.index(kronig_name)
    assert page.index(product_wordmark) < page.index('id="workspace-status"') < page.index(company)
    assert "Research workspace" not in page
    assert "Local runtime" not in page
    assert 'id="run-controls" class="run-controls" hidden' in page
    assert 'aria-valuenow="420"' in page


def test_typography_assets_are_self_hosted_and_served(tmp_path: Path) -> None:
    web = client(tmp_path)
    theme = web.get("/static/theme.css")

    assert theme.status_code == 200
    assert '--font-sans: "IBM Plex Sans"' in theme.text
    assert '--font-mono: "IBM Plex Mono"' in theme.text
    assert "https://" not in theme.text

    font_paths = (
        "/static/fonts/ibm-plex-sans-roman.woff2",
        "/static/fonts/ibm-plex-sans-italic.woff2",
        "/static/fonts/ibm-plex-mono-roman.woff2",
        "/static/fonts/ibm-plex-mono-italic.woff2",
    )
    for font_path in font_paths:
        response = web.get(font_path)
        assert response.status_code == 200
        assert response.content.startswith(b"wOF2")


def test_file_viewer_uses_one_compact_toolbar(tmp_path: Path) -> None:
    page = client(tmp_path).get("/").text

    assert 'class="file-viewer-utilities"' in page
    assert 'id="file-viewer-meta" class="file-viewer-meta" hidden' in page
    assert 'id="file-viewer-kind"' not in page
    assert page.index('id="file-viewer-edit"') < page.index(
        'id="file-viewer-refresh"'
    )
    assert page.index('id="file-viewer-download"') < page.index(
        'id="file-viewer-close"'
    )


def test_legacy_guided_pages_redirect_to_repository_workspace(tmp_path: Path) -> None:
    web = client(tmp_path)
    simulation = web.get("/simulate", follow_redirects=False)
    request_stage = web.get(
        f"/requests/{uuid4()}/results", follow_redirects=False
    )

    assert simulation.status_code == 307
    assert simulation.headers["location"] == "/"
    assert request_stage.status_code == 307
    assert request_stage.headers["location"] == "/"


def test_workspace_uses_scientific_theme(tmp_path: Path) -> None:
    web = client(tmp_path)
    workspace_page = web.get("/")
    theme = web.get("/static/theme.css?v=20260925-1")

    assert 'href="/static/theme.css?v=20260925-1"' in workspace_page.text
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
