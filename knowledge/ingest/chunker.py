"""Chunking logic for dos-re knowledge.

Chunks are keyed by (md5, offset, length, kind). Findings travel with the
bytes — renaming the file on disk doesn't orphan its annotations.

Chunk kinds:
  - identify     : one per md5, cached magic-byte result
  - disassembly  : one per (md5, offset, length, bits) — raw ndisasm output
  - note         : one per (md5, offset, length, sequence) — explicit findings
  - strings      : one per md5, full `strings -n N` output (game text)
  - text_view    : one per (md5, offset, length) of decoded text
  - pe-info      : one per md5, objdump -p output (PE/COFF structural overview)
  - pe-sections  : one per md5, objdump -h output (section headers)
  - pe-disasm    : one per md5, objdump -d output (PE code disassembly)

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
    "chunk_strings",
    "chunk_text_view",
    "chunk_pe_info",
    "chunk_pe_sections",
    "chunk_pe_disasm",
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


def chunk_strings(md5: str, filename: str, min_length: int, body: str) -> dict:
    """One chunk per md5 for `strings -n N` output.

    Indexes the embedded text of a binary (filenames, dialogue, version
    banners, error messages). Re-running with a different min_length
    upserts — the id is md5-only, so the latest call wins. The min_length
    is stored in metadata for reference.
    """
    tags = ["strings", f"min-{min_length}"]
    document = (
        f"FILE: {filename}\nMD5: {md5}\nMIN_LENGTH: {min_length}\n\n"
        f"{body}"
    )
    return {
        "id": f"strings/{md5}",
        "document": document,
        "metadata": {
            "source": f"strings/{md5}",
            "kind": "strings",
            "md5": md5,
            "filename": filename,
            "offset": 0,
            "length": 0,
            "bits": 0,
            "tags": ",".join(tags),
            "indexed_at": now_iso(),
        },
    }


def chunk_text_view(
    md5: str,
    filename: str,
    offset: int,
    length: int,
    encoding: str,
    body: str,
) -> dict:
    """One chunk per (md5, offset, length) of decoded text.

    Used for non-trivial encodings (high-bit-stripped, XOR 0x80, etc.)
    where text_view succeeded in producing readable output. Re-decoding
    the same region overwrites.
    """
    enc_tag = encoding.replace("-", "_")
    tags = ["text_view", f"encoding_{enc_tag}"]
    header = (
        f"FILE: {filename}\nMD5: {md5}\n"
        f"OFFSET: {hex(offset)}  LENGTH: {length}  ENCODING: {encoding}\n\n"
    )
    return {
        "id": f"text_view/{md5}/{offset}/{length}",
        "document": header + body,
        "metadata": {
            "source": f"text_view/{md5}",
            "kind": "text_view",
            "md5": md5,
            "filename": filename,
            "offset": offset,
            "length": length,
            "bits": 0,
            "encoding": encoding,
            "tags": ",".join(tags),
            "indexed_at": now_iso(),
        },
    }


def chunk_pe_info(md5: str, filename: str, body: str) -> dict:
    """One chunk per md5 for objdump -p output (PE/COFF structural overview)."""
    tags = ["pe-info", "pe", "objdump"]
    document = f"FILE: {filename}\nMD5: {md5}\n\nPE/COFF INFO:\n\n{body}"
    return {
        "id": f"pe-info/{md5}",
        "document": document,
        "metadata": {
            "source": f"pe-info/{md5}",
            "kind": "pe-info",
            "md5": md5,
            "filename": filename,
            "offset": 0,
            "length": 0,
            "bits": 0,
            "tags": ",".join(tags),
            "indexed_at": now_iso(),
        },
    }


def chunk_pe_sections(md5: str, filename: str, body: str) -> dict:
    """One chunk per md5 for objdump -h output (section headers)."""
    tags = ["pe-sections", "pe", "objdump"]
    document = f"FILE: {filename}\nMD5: {md5}\n\nPE/COFF SECTIONS:\n\n{body}"
    return {
        "id": f"pe-sections/{md5}",
        "document": document,
        "metadata": {
            "source": f"pe-sections/{md5}",
            "kind": "pe-sections",
            "md5": md5,
            "filename": filename,
            "offset": 0,
            "length": 0,
            "bits": 0,
            "tags": ",".join(tags),
            "indexed_at": now_iso(),
        },
    }


def chunk_pe_disasm(md5: str, filename: str, body: str) -> dict:
    """One chunk per md5 for objdump -d output (PE code disassembly).

    Whole-file disassembly is captured as a single chunk — objdump's
    output already partitions by section, so per-section sub-chunking
    would duplicate that layout in the index.
    """
    tags = ["pe-disasm", "pe", "objdump", "disassembly"]
    document = f"FILE: {filename}\nMD5: {md5}\n\nPE/COFF DISASSEMBLY:\n\n{body}"
    return {
        "id": f"pe-disasm/{md5}",
        "document": document,
        "metadata": {
            "source": f"pe-disasm/{md5}",
            "kind": "pe-disasm",
            "md5": md5,
            "filename": filename,
            "offset": 0,
            "length": 0,
            "bits": 0,
            "tags": ",".join(tags),
            "indexed_at": now_iso(),
        },
    }
