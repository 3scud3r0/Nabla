"""Resolve explicit document evidence links against a scientific artifact DAG."""
from .document_model import Document
from ..core.scientific_artifact import ScientificArtifact
from ..core.semantic_contracts import require_digest
from ..core.semantic_ir import fingerprint
from ..knowledge.lineage import LineageGraph


def document_reference_graph(document: Document, artifact: ScientificArtifact):
    if not isinstance(document, Document) or not isinstance(artifact, ScientificArtifact):
        raise ValueError("Document and scientific artifact required")
    available = {node.content_id for node in artifact.nodes}
    sections, referenced = [], set()
    for index, section in enumerate(document.sections):
        links = [require_digest(key) for key in section.evidence_ids]
        if len(set(links)) != len(links) or any(key not in available for key in links):
            raise ValueError("Duplicate or unresolved document evidence")
        referenced.update(links)
        sections.append({"index": index, "heading": section.heading, "evidence_ids": sorted(links),
                         "citation_keys": sorted(section.citations)})
    nodes = [{"id": node.content_id, "parents": list(node.parents)} for node in artifact.nodes]
    nodes.append({"id": document.content_id, "parents": sorted(referenced)})
    graph = LineageGraph.create(nodes)
    report = {"schema_version": 1, "document_id": document.content_id, "artifact_id": artifact.content_id,
              "sections": sections, "lineage": graph.to_data(), "lineage_id": graph.content_id,
              "scope": "explicit reference availability; text entailment and editorial acceptance require review"}
    return {**report, "report_id": fingerprint(report)}
