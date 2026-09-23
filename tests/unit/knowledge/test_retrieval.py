from pathlib import Path

from tcad_agent.knowledge.models import Passage
from tcad_agent.knowledge.retrieve import KnowledgeIndex


def passage(
    passage_id: str,
    content: str,
    *,
    version: str,
    reviewed: bool,
    backend: str = "devsim",
) -> Passage:
    return Passage.create(
        id=passage_id,
        source_id=f"source-{passage_id}",
        title=f"Source {passage_id}",
        url=f"https://example.invalid/{passage_id}",
        license="Apache-2.0",
        access="public",
        trust="primary",
        backend=backend,
        version=version,
        reviewed=reviewed,
        content=content,
    )


def build_test_index(path: Path, passages: list[Passage]) -> KnowledgeIndex:
    return KnowledgeIndex.build(path / "knowledge.sqlite3", passages)


def test_reviewed_version_compatible_source_outranks_stale_source(tmp_path: Path) -> None:
    index = build_test_index(
        tmp_path,
        passages=[
            passage("old", "DEVSIM contact equation", version="1.0", reviewed=False),
            passage("current", "DEVSIM contact equation", version="2.9", reviewed=True),
        ],
    )
    hits = index.search(
        "contact equation",
        filters={"backend": "devsim", "version": "2.9"},
        limit=2,
    )
    assert [hit.id for hit in hits] == ["current"]
    assert hits[0].citation.source_id


def test_backend_filter_excludes_sentaurus_text(tmp_path: Path) -> None:
    index = build_test_index(
        tmp_path,
        [
            passage("devsim", "mobility model", version="2.9", reviewed=True),
            passage(
                "sentaurus",
                "mobility model",
                version="2025.09",
                reviewed=True,
                backend="sentaurus",
            ),
        ],
    )
    hits = index.search("mobility model", {"backend": "devsim"}, 5)
    assert hits
    assert all(hit.backend == "devsim" for hit in hits)
