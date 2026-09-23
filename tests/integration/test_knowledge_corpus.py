from pathlib import Path

import pytest
import yaml

from tcad_agent.capabilities.models import CapabilityManifest
from tcad_agent.knowledge.ingest import KnowledgeIngestor
from tcad_agent.knowledge.models import SourceManifest
from tcad_agent.knowledge.retrieve import KnowledgeIndex

PROJECT_ROOT = Path(__file__).parents[2]


@pytest.mark.integration
def test_curated_corpus_passes_retrieval_evaluations(tmp_path: Path) -> None:
    source_document = yaml.safe_load(
        (PROJECT_ROOT / "knowledge-sources/manifests/sources.yaml").read_text()
    )
    sources = tuple(
        SourceManifest.model_validate(item) for item in source_document["sources"]
    )
    ingestor = KnowledgeIngestor()
    passages = tuple(
        passage
        for source in sources
        if source.local_path is not None
        for passage in ingestor.ingest_local(source, PROJECT_ROOT.parent)
    )
    index = KnowledgeIndex.build(tmp_path / "knowledge.sqlite3", passages)
    evaluation = yaml.safe_load(
        (PROJECT_ROOT / "evaluations/retrieval/questions.yaml").read_text()
    )

    for question in evaluation["questions"]:
        required = set(question.get("required_source_ids", ()))
        if not required:
            continue
        filters = {"backend": question["backend"]}
        if "version" in question:
            filters["version"] = question["version"]
        hits = index.search(question["query"], filters, limit=10)
        returned = {hit.citation.source_id for hit in hits}
        assert required <= returned, question["id"]


def test_sentaurus_retrieval_stays_closed_without_licensed_corpus() -> None:
    manifest = CapabilityManifest.from_backend("sentaurus")
    evaluation = yaml.safe_load(
        (PROJECT_ROOT / "evaluations/retrieval/questions.yaml").read_text()
    )
    boundary = next(
        item for item in evaluation["questions"] if item["id"] == "sentaurus-boundary"
    )

    assert manifest.execution_state == "unconfigured"
    assert boundary["expected_behavior"] == (
        "refuse_without_version_compatible_licensed_source"
    )
