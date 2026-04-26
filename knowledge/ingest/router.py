"""Ingest router for dos-re findings.

Selective triggers — this is the key design decision:

  disassemble  -> indexed (md5+offset+length+bits keyed; regeneration is slow)
  identify     -> upserted one-per-md5 (cheap cache)
  note         -> always indexed (the high-signal path)
  everything else -> skipped

hex_dump / hex_view_colored / find_strings / slice_bytes / md5 / stat are
skipped because they're cheap to regenerate and would flood the index with
noise.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mcp_knowledge_base import IngestRouter

from .chunker import (
    chunk_disassembly,
    chunk_identify,
    chunk_note,
    upsert_chunks,
)

if TYPE_CHECKING:
    import chromadb

logger = logging.getLogger("mcp-dos-re-knowledge.router")

SKIP_TOOLS = {
    "hex_dump",
    "hex_view_colored",
    "find_strings",
    "slice_bytes",
    "md5",
    "stat",
}


class DosreIngestRouter(IngestRouter):
    """Routes tool payloads from mcp-dos-re to chunking logic."""

    def __init__(self, collection: "chromadb.Collection"):
        self.collection = collection

    def _index_chunks(self, chunks: list[dict]) -> None:
        if not chunks:
            return
        upsert_chunks(self.collection, chunks)
        logger.info("Indexed %d chunks", len(chunks))

    def route(self, payload: dict) -> dict:
        tool = payload.get("tool", "")
        success = payload.get("success", True)
        result = payload.get("result", "")
        args = payload.get("args", {}) or {}

        if tool in SKIP_TOOLS:
            return {"action": "skipped", "chunks": 0}

        if tool == "identify":
            if not success:
                return {"action": "skipped_identify_failed", "chunks": 0}
            md5 = args.get("md5", "") or ""
            if not md5:
                return {"action": "skipped_identify_no_md5", "chunks": 0}
            chunk = chunk_identify(
                md5=md5,
                filename=args.get("filename", ""),
                result=result,
            )
            self._index_chunks([chunk])
            return {"action": "indexed_identify", "chunks": 1}

        if tool == "disassemble":
            if not success:
                return {"action": "skipped_disasm_failed", "chunks": 0}
            md5 = args.get("md5", "") or ""
            if not md5:
                return {"action": "skipped_disasm_no_md5", "chunks": 0}
            chunk = chunk_disassembly(
                md5=md5,
                filename=args.get("filename", ""),
                bits=int(args.get("bits", 16)),
                offset=int(args.get("offset", 0)),
                length=int(args.get("length", 0)),
                body=result,
            )
            self._index_chunks([chunk])
            return {"action": "indexed_disassembly", "chunks": 1}

        if tool == "note":
            md5 = args.get("md5", "") or ""
            if not md5:
                return {"action": "skipped_note_no_md5", "chunks": 0}
            chunk = chunk_note(
                md5=md5,
                offset=int(args.get("offset", 0)),
                length=int(args.get("length", 0)),
                text=result,
                user_tags=list(args.get("tags", []) or []),
            )
            self._index_chunks([chunk])
            return {"action": "indexed_note", "chunks": 1}

        logger.debug("Unhandled tool: %s", tool)
        return {"action": "skipped_unknown", "chunks": 0}
