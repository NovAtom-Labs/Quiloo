"""Deterministic clarification rules for consequential missing inputs."""

from __future__ import annotations

import re

from tcad_agent.control.models import ClarificationQuestion


class ClarificationGate:
    _silicon_region = re.compile(r"\b([pn])\s*[- ]?\s*Si\s+region\b", re.IGNORECASE)
    _explicit_thickness = re.compile(
        r"\b([pn])\s*[- ]?\s*Si\b.{0,80}?\b(?:thick(?:ness)?|width|length)\b"
        r".{0,40}?\b\d+(?:\.\d+)?\s*(?:nm|um|µm|mm|cm|m)\b",
        re.IGNORECASE | re.DOTALL,
    )

    def required_questions(
        self, prompt: str, answers: dict[str, str]
    ) -> tuple[ClarificationQuestion, ...]:
        questions: list[ClarificationQuestion] = []
        regions = {match.lower() for match in self._silicon_region.findall(prompt)}
        regions_with_thickness = {
            match.lower() for match in self._explicit_thickness.findall(prompt)
        }
        for region in sorted(regions - regions_with_thickness):
            field = f"geometry.{region}_region_thickness"
            if field not in answers:
                questions.append(
                    ClarificationQuestion(
                        field=field,
                        prompt=f"What thickness should the {region}-Si region use?",
                    )
                )
        contact_field = "contacts.treatment"
        requests_metal_semantics = bool(
            re.search(r"\b(?:aluminum|aluminium|Al)\b", prompt, re.IGNORECASE)
            and re.search(r"work\s+function", prompt, re.IGNORECASE)
        )
        declares_treatment = bool(
            re.search(r"\b(?:ohmic|schottky|metal[- ]work[- ]function)\b", prompt, re.IGNORECASE)
        )
        if requests_metal_semantics and not declares_treatment and contact_field not in answers:
            questions.append(
                ClarificationQuestion(
                    field=contact_field,
                    prompt=(
                        "Should the metal-semiconductor interfaces be modeled as ohmic, "
                        "Schottky, or explicit metal work-function contacts?"
                    ),
                )
            )
        return tuple(questions)
