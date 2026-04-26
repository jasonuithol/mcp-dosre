"""mcp-dos-re-knowledge: RAG-backed knowledge service for DOS-era RE findings.

Built on `mcp-knowledge-base`, which provides the FastMCP + ChromaDB +
/ingest scaffolding. This module adds only the dos-re-specific pieces:
the chunker, the md5-keyed retrieval tools, and the bespoke result
formatters (hex offsets, md5 truncation, byte length).

Collection is `dosre_knowledge`. The primary key for all chunks is md5 —
so annotations travel with the bytes rather than with a filename.
"""

from __future__ import annotations

import os

from mcp_knowledge_base import KnowledgeService, ServiceConfig

from ingest.chunker import tag_key
from ingest.router import DosreIngestRouter

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INSTRUCTIONS = (
    "Knowledge base for DOS-era binary RE findings. Chunks are keyed by "
    "md5 so annotations survive filename changes. Use `ask(question)` "
    "for general retrieval, `ask_file(md5_or_path)` to list everything "
    "known about one file, `ask_offset(md5, offset)` to find "
    "annotations that cover a specific byte range."
)

# ---------------------------------------------------------------------------
# Service assembly
# ---------------------------------------------------------------------------

svc = KnowledgeService(ServiceConfig.from_env(
    name="dos-re-knowledge",
    collection_name="dosre_knowledge",
    port=5176,
    header_keys=[],  # dos-re uses a custom result formatter, not the header-key one
    instructions=INSTRUCTIONS,
))

# Only `list_sources` and `forget` (prefix-match) match dos-re's display
# contract directly. `ask`/`ask_tagged`/`stats` need the custom formatters
# below (hex offsets, md5 truncation, distinct-md5 count).
svc.register_default_tools(include={"list_sources", "forget"})
svc.set_ingest_router(DosreIngestRouter(svc.collection))

# Aliases for use inside tool closures
collection = svc.collection
mcp = svc.mcp


# ---- Domain-specific result formatters -----------------------------------


def _format_results(results: dict) -> str:
    """Format ChromaDB .query() results."""
    if not results["ids"] or not results["ids"][0]:
        return "No results found."
    lines = []
    for i, (doc, meta, dist) in enumerate(
        zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
    ):
        similarity = 1 - dist
        header = (
            f"[{i+1}] kind={meta.get('kind','?')} "
            f"md5={meta.get('md5','?')[:12]} "
            f"offset={hex(int(meta.get('offset',0)))} "
            f"length={meta.get('length',0)} "
            f"similarity={similarity:.2f}"
        )
        tags = meta.get("tags", "")
        if tags:
            header += f" tags=[{tags}]"
        lines.append(header)
        lines.append(doc[:1500])
        lines.append("")
    return "\n".join(lines)


def _format_get_results(results: dict) -> str:
    """Format ChromaDB .get() results (no distances)."""
    ids = results.get("ids", [])
    if not ids:
        return "No results found."
    lines = [f"{len(ids)} results:", ""]
    for id_, doc, meta in zip(ids, results["documents"], results["metadatas"]):
        header = (
            f"[{meta.get('kind','?')}] {id_} "
            f"offset={hex(int(meta.get('offset',0)))} "
            f"length={meta.get('length',0)}"
        )
        lines.append(header)
        lines.append(doc[:1500])
        lines.append("")
    return "\n".join(lines)


# ---- Domain-specific query tools -----------------------------------------


@svc.tool()
def ask(question: str) -> str:
    """Semantic search across all dos-re findings. Returns the top 5."""
    results = collection.query(query_texts=[question], n_results=5)
    return _format_results(results)


@svc.tool()
def ask_tagged(question: str, tags: list[str]) -> str:
    """Filtered semantic search — tags like 'npc-record', 'schedule', 'bits-16'."""
    keys = [tag_key(t) for t in tags if t]
    if not keys:
        where = None
    elif len(keys) == 1:
        where = {keys[0]: True}
    else:
        where = {"$and": [{k: True} for k in keys]}
    results = collection.query(query_texts=[question], n_results=5, where=where)
    return _format_results(results)


@svc.tool()
def ask_file(md5_or_path: str) -> str:
    """List every annotation about one file, keyed by md5.

    If the argument is 32 hex chars it's treated as md5 directly; otherwise
    it's treated as a filename substring match.
    """
    ident = md5_or_path.strip().lower()
    if len(ident) == 32 and all(c in "0123456789abcdef" for c in ident):
        where = {"md5": ident}
    else:
        # Fall back to filename equality; Chroma metadata filters don't
        # support substring, so users will need to pass an exact filename.
        where = {"filename": md5_or_path}

    results = collection.get(where=where, include=["documents", "metadatas"])
    return _format_get_results(results)


@svc.tool()
def ask_offset(md5: str, offset: int) -> str:
    """Find annotations whose byte range contains `offset`.

    Returns chunks where metadata offset <= offset < (offset + length),
    plus any identify/note entries at offset 0 length 0 for that md5
    (treated as whole-file metadata).
    """
    md5 = md5.strip().lower()
    results = collection.get(where={"md5": md5}, include=["documents", "metadatas"])
    if not results.get("ids"):
        return f"No findings for md5={md5}"

    hits = []
    for id_, doc, meta in zip(
        results["ids"], results["documents"], results["metadatas"]
    ):
        m_off = int(meta.get("offset", 0))
        m_len = int(meta.get("length", 0))
        if m_len == 0 and m_off == 0:
            hits.append((id_, doc, meta))
        elif m_off <= offset < (m_off + m_len):
            hits.append((id_, doc, meta))

    if not hits:
        return f"No annotations cover offset {hex(offset)} for md5={md5}"

    lines = [f"Annotations covering {hex(offset)} (md5={md5}): {len(hits)}", ""]
    for id_, doc, meta in hits:
        lines.append(f"[{meta.get('kind','?')}] {id_}")
        lines.append(doc[:1500])
        lines.append("")
    return "\n".join(lines)


# ---- stats() override (kind-based, includes distinct-md5 count) ---------


@svc.tool()
def stats() -> str:
    """Size, breakdown by kind, top tags, file count."""
    count = collection.count()
    if count == 0:
        return "Knowledge base is empty."

    all_meta = collection.get(include=["metadatas"])
    kinds: dict[str, int] = {}
    md5s: set[str] = set()
    tags_count: dict[str, int] = {}
    for meta in all_meta["metadatas"]:
        k = meta.get("kind", "unknown")
        kinds[k] = kinds.get(k, 0) + 1
        if meta.get("md5"):
            md5s.add(meta["md5"])
        for tag in meta.get("tags", "").split(","):
            tag = tag.strip()
            if tag:
                tags_count[tag] = tags_count.get(tag, 0) + 1

    lines = [
        f"Total chunks: {count}",
        f"Distinct files (by md5): {len(md5s)}",
        "",
        "Kinds:",
    ]
    for k, c in sorted(kinds.items(), key=lambda x: -x[1]):
        lines.append(f"  {k}: {c}")
    lines.append("\nTop tags:")
    for tag, c in sorted(tags_count.items(), key=lambda x: -x[1])[:20]:
        lines.append(f"  {tag}: {c}")
    return "\n".join(lines)


# ---- forget_md5 (md5-keyed companion to default `forget`) ----------------


@svc.tool()
def forget_md5(md5: str) -> str:
    """Remove every chunk for a given md5 (identify + disassembly + notes)."""
    md5 = md5.strip().lower()
    results = collection.get(where={"md5": md5})
    ids = results.get("ids", [])
    if not ids:
        return f"No chunks found for md5={md5}"
    collection.delete(ids=ids)
    return f"Deleted {len(ids)} chunks for md5={md5}"


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    svc.run()
