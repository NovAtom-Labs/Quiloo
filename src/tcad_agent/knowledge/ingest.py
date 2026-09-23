"""Manifest-gated text chunking for local, authorized sources."""

from __future__ import annotations

import re
from pathlib import Path

from tcad_agent.knowledge.models import Passage, SourceManifest


class KnowledgeIngestor:
    TEXT_SUFFIXES = frozenset({".json", ".md", ".py", ".rst", ".txt", ".yaml", ".yml"})

    def ingest_text(self, source: SourceManifest, text: str) -> tuple[Passage, ...]:
        if not source.license or not source.access:
            raise ValueError("knowledge sources require license and access metadata")
        chunks = self._chunks(text)
        return tuple(
            Passage.create(
                id=f"{source.id}:{index}",
                source_id=source.id,
                title=source.title,
                url=source.url,
                license=source.license,
                access=source.access,
                trust=source.trust,
                backend=source.backend,
                version=source.version,
                reviewed=source.reviewed,
                content=chunk,
            )
            for index, chunk in enumerate(chunks)
        )

    def ingest_local(self, source: SourceManifest, root: Path) -> tuple[Passage, ...]:
        if source.local_path is None:
            raise ValueError("local_path is required for local ingestion")
        path = (root / source.local_path).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("knowledge local_path escapes the approved root")
        if path.is_file():
            return self.ingest_text(source, path.read_text(encoding="utf-8"))
        if not path.is_dir():
            raise FileNotFoundError(f"knowledge source does not exist: {path}")
        passages: list[Passage] = []
        for document in sorted(
            item
            for item in path.rglob("*")
            if item.is_file() and item.suffix.lower() in self.TEXT_SUFFIXES
        ):
            if not document.resolve().is_relative_to(path):
                raise ValueError(
                    f"knowledge document escapes the approved root: {document}"
                )
            relative = document.relative_to(path).as_posix()
            text = f"Source file: {relative}\n\n{document.read_text(encoding='utf-8')}"
            for index, chunk in enumerate(self._chunks(text)):
                passages.append(
                    Passage.create(
                        id=f"{source.id}:{relative}:{index}",
                        source_id=source.id,
                        title=f"{source.title}: {relative}",
                        url=source.url,
                        license=source.license,
                        access=source.access,
                        trust=source.trust,
                        backend=source.backend,
                        version=source.version,
                        reviewed=source.reviewed,
                        content=chunk,
                    )
                )
        if not passages:
            raise ValueError(f"knowledge source contains no supported text files: {path}")
        return tuple(passages)

    @staticmethod
    def _chunks(text: str) -> tuple[str, ...]:
        sections = re.split(r"(?m)(?=^#{1,6}\s)|\n\s*\n", text)
        chunks = tuple(section.strip() for section in sections if section.strip())
        if not chunks:
            raise ValueError("source contains no indexable text")
        return chunks
