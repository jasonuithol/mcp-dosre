"""Chunking logic for dos-re knowledge.

Chunks are keyed by (md5, offset, length, kind). Findings travel with the
bytes — renaming the file on disk doesn't orphan its annotations.

Three chunk kinds:
  - identify    : one per md5, cached magic-byte result
  - disassembly : one per (md5, offset, length, bits) — raw ndisasm output
  - note        : one per (md5, offset, length, sequence) — explicit findings

The cross-domain primitives — `tag_key`, `tag_flags`, `upsert_chunks`,
`sanitize_for_id`, `now_iso` — live in `mcp_knowledge_base.chunks` and are
re-exported here for the convenience of existing call-sites.
"""

from __future__ import annotations

from mcp_knowledge_base import (
    now_iso,
    sanitize_for_id,
    tag_flags,
    tag_key,
    upsert_chunks,
)

__all__ = [
    "chunk_identify",
    "chunk_disassembly",
    "chunk_note",
    # Re-exports from mcp_knowledge_base for downstream convenience
    "tag_key",
    "tag_flags",
    "upsert_chunks",
]


# ── chunk builders ───────────────────────────────────────────────────────────

def chunk_identify(md5: str, filename: str, result: str) -> dict:
    """One chunk per md5 for the magic-byte identification.

    Uses a md5-only id so repeated identify() calls on the same bytes
    upsert rather than duplicate.
    """
    tags = ["identify", "magic-byte"]
    document = f"FILE: {filename}\nMD5: {md5}\n\nIDENTIFY: {result}\n"
    return {
        "id": f"identify/{md5}",
        "document": document,
        "metadata": {
            "source": f"identify/{md5}",
            "kind": "identify",
            "md5": md5,
            "filename": filename,
            "offset": 0,
            "length": 0,
            "bits": 0,
            "tags": ",".join(tags),
            "indexed_at": now_iso(),
        },
    }


def chunk_disassembly(
    md5: str,
    filename: str,
    bits: int,
    offset: int,
    length: int,
    body: str,
) -> dict:
    """One chunk per (md5, offset, length, bits) region of disassembly.

    Re-disassembling the same region overwrites — the id captures the
    exact parameters.
    """
    tags = ["disassembly", f"bits-{bits}"]
    header = (
        f"FILE: {filename}\nMD5: {md5}\n"
        f"OFFSET: {hex(offset)}  LENGTH: {length}  BITS: {bits}\n\n"
    )
    return {
        "id": f"disassembly/{md5}/{bits}/{offset}/{length}",
        "document": header + body,
        "metadata": {
            "source": f"disassembly/{md5}",
            "kind": "disassembly",
            "md5": md5,
            "filename": filename,
            "offset": offset,
            "length": length,
            "bits": bits,
            "tags": ",".join(tags),
            "indexed_at": now_iso(),
        },
    }


def chunk_note(
    md5: str,
    offset: int,
    length: int,
    text: str,
    user_tags: list[str],
) -> dict:
    """One chunk per explicit note call.

    Notes accumulate — the id includes a timestamp so two notes on the same
    region are both preserved. `forget` can target them individually via
    the full id, or by md5 prefix via `forget_md5`.
    """
    now = now_iso()
    tags = ["note"] + [t for t in user_tags if t]
    header = (
        f"MD5: {md5}\n"
        f"OFFSET: {hex(offset)}  LENGTH: {length}\n"
        f"TAGS: {','.join(user_tags)}\n\n"
    )
    return {
        "id": f"note/{md5}/{offset}/{length}/{sanitize_for_id(now)}",
        "document": header + text,
        "metadata": {
            "source": f"note/{md5}",
            "kind": "note",
            "md5": md5,
            "filename": "",
            "offset": offset,
            "length": length,
            "bits": 0,
            "tags": ",".join(tags),
            "indexed_at": now,
        },
    }
