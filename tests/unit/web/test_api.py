from pathlib import Path

from fastapi.testclient import TestClient

from tcad_agent.control.service import ControlService
from tcad_agent.control.store import SqliteRequestStore
from tcad_agent.model_gateway.base import ScriptedModelGateway
from tcad_agent.web.app import create_app
from tcad_agent.web.launcher import DEFAULT_HOST


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
    assert web.get("/health").json() == {"status": "ok"}
    page = web.get("/")
    assert page.status_code == 200
    assert "NovAtom TCAD Agent" in page.text


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
