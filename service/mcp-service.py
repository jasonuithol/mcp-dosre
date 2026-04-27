#!/usr/bin/env python3
"""
mcp-service.py — dos-re

Binary-analysis tools for DOS-era reverse engineering. Runs inside a Docker
container; exposes hex / strings / magic / disassembly / md5 / stat / note
to Claude Code over HTTP.

Register with Claude Code (run this inside the claude-sandbox-core container):
    claude mcp add dos-re --transport http http://localhost:5175/mcp

All file reads are confined to PROJECTS_DIR (read-only bind of ~/Projects).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import FastMCP
from mcp_knowledge_base import KnowledgeReporter

# ── Config ────────────────────────────────────────────────────────────────────

PROJECTS_DIR = Path(os.environ.get("PROJECTS_DIR", "/opt/projects")).resolve()

# Generous caps to keep tool output manageable. A 4 MB .OVL disassembles to
# ~40 MB of text — more than Claude wants to read in one go.
MAX_SLICE_BYTES = 1 * 1024 * 1024       # 1 MB base64 slice
MAX_TEXT_OUTPUT = 400 * 1024            # 400 KB of textual tool output


# ── Path safety ───────────────────────────────────────────────────────────────

def _resolve_path(path: str) -> Path:
    """Resolve `path` to an absolute path under PROJECTS_DIR.

    Accepts either an absolute path already inside PROJECTS_DIR, or a
    relative path that will be joined to PROJECTS_DIR. Symlinks are
    resolved and the result is rejected if it escapes PROJECTS_DIR.
    """
    p = Path(path)
    if not p.is_absolute():
        p = PROJECTS_DIR / p
    p = p.resolve()
    try:
        p.relative_to(PROJECTS_DIR)
    except ValueError:
        raise ValueError(
            f"Path outside {PROJECTS_DIR}: {path!r} (resolved to {p})"
        )
    if not p.exists():
        raise FileNotFoundError(f"No such file: {p}")
    if not p.is_file():
        raise ValueError(f"Not a regular file: {p}")
    return p


# ── Knowledge reporter ────────────────────────────────────────────────────────

_reporter = KnowledgeReporter(service="mcp-dos-re")
_report = _reporter.report


# ── Subprocess helpers ────────────────────────────────────────────────────────

def _run(cmd: list[str], input_bytes: bytes | None = None) -> tuple[bool, str]:
    """Run a command, capture combined stdout+stderr, truncate if huge."""
    proc = subprocess.run(
        cmd,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    out = proc.stdout or b""
    text = out.decode("utf-8", errors="replace")
    if len(text) > MAX_TEXT_OUTPUT:
        text = (
            text[:MAX_TEXT_OUTPUT]
            + f"\n\n[... truncated at {MAX_TEXT_OUTPUT} bytes; "
              f"re-invoke with a narrower offset/length range]"
        )
    return proc.returncode == 0, text


async def _run_async(cmd: list[str], input_bytes: bytes | None = None):
    return await asyncio.to_thread(_run, cmd, input_bytes)


# ── MCP server ────────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="dos-re",
    instructions=(
        "Binary reverse-engineering tools for DOS-era files. Read-only; "
        "all paths resolve under /opt/projects. "
        "When a region might be text (NPC dialogue, filenames, descriptions) "
        "prefer text_view — it auto-detects common encodings (plain, "
        "high-bit-stripped, XOR 0x80) and returns readable text, or tells "
        "you clearly that it couldn't decode. "
        "Use hex_dump for structure inspection, disassemble for .OVL / .EXE "
        "code, identify + find_strings for first contact with an unknown "
        "blob. Call note(...) to persist a finding to the knowledge base "
        "keyed by md5+offset."
    ),
)


# ── hex_dump ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def hex_dump(
    path: str,
    offset: int = 0,
    length: int = 256,
    width: int = 16,
) -> str:
    """Hex dump via `xxd`. The everyday view.

    Args:
        path: File path (absolute under /opt/projects, or relative to it).
        offset: Byte offset to start at (decimal).
        length: Number of bytes to dump. Default 256.
        width: Bytes per line. Default 16.
    """
    try:
        p = _resolve_path(path)
    except Exception as e:
        return f"FAILED\n\n{e}"

    cmd = ["xxd", "-s", str(offset), "-l", str(length), "-c", str(width), str(p)]
    ok, out = await _run_async(cmd)
    return out if ok else f"FAILED\n\n{out}"


# ── hex_view_colored ──────────────────────────────────────────────────────────

@mcp.tool()
async def hex_view_colored(path: str, offset: int = 0, length: int = 256) -> str:
    """Colorised hex view via `hexyl`. Good for eyeballing repeating patterns.

    Output contains ANSI colour codes — render in a terminal or strip with
    `sed 's/\\x1b\\[[0-9;]*m//g'` if piping.
    """
    try:
        p = _resolve_path(path)
    except Exception as e:
        return f"FAILED\n\n{e}"

    cmd = ["hexyl", "--skip", str(offset), "--length", str(length), str(p)]
    ok, out = await _run_async(cmd)
    return out if ok else f"FAILED\n\n{out}"


# ── identify ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def identify(path: str) -> str:
    """Magic-byte identification via `file`. First-contact tool for an
    unknown blob. Result is cached in the knowledge base keyed by md5."""
    try:
        p = _resolve_path(path)
    except Exception as e:
        result = f"FAILED\n\n{e}"
        _report("identify", {"path": path}, result, False)
        return result

    ok, out = await _run_async(["file", "--brief", str(p)])
    result = out.strip() if ok else f"FAILED\n\n{out}"

    # Compute md5 so the knowledge router can key this properly.
    md5_hex = ""
    try:
        md5_hex = _md5_of(p)
    except Exception:
        pass

    _report(
        "identify",
        {"path": str(p), "filename": p.name, "md5": md5_hex},
        result,
        ok,
    )
    return result


# ── find_strings ──────────────────────────────────────────────────────────────

@mcp.tool()
async def find_strings(path: str, min_length: int = 4) -> str:
    """Extract printable strings via `strings -n MIN`."""
    try:
        p = _resolve_path(path)
    except Exception as e:
        return f"FAILED\n\n{e}"

    ok, out = await _run_async(["strings", "-n", str(min_length), str(p)])
    return out if ok else f"FAILED\n\n{out}"


# ── text_view ─────────────────────────────────────────────────────────────────

@mcp.tool()
async def text_view(path: str, offset: int = 0, length: int = 1024) -> str:
    """Auto-detect text encoding in a byte range and return it as readable text.

    Tries common DOS-era transforms and picks whichever yields the most
    printable output:

      - plain ASCII
      - high-bit-stripped  (b & 0x7F) — Ultima V TLK/LOOK files etc.
      - XOR with 0x80

    If none score well, returns a diagnostic explaining it couldn't decode
    the region — use that as a cue to ask the user about the format, or to
    fall back to hex_dump / disassemble.

    Output markers:
      '|'  — 0x00 byte (common record separator)
      '.'  — other non-printable byte

    Args:
        path: File to read.
        offset: Start byte (decimal).
        length: Bytes to read. Default 1024.
    """
    try:
        p = _resolve_path(path)
    except Exception as e:
        return f"FAILED\n\n{e}"

    try:
        with p.open("rb") as f:
            f.seek(offset)
            data = f.read(length)
    except Exception as e:
        return f"FAILED\n\n{e}"

    if not data:
        return "FAILED\n\nread 0 bytes (offset past EOF?)"

    candidates = [
        ("plain",                          data),
        ("high-bit-stripped (b & 0x7F)",   bytes(b & 0x7F for b in data)),
        ("XOR 0x80",                       bytes(b ^ 0x80 for b in data)),
    ]
    scored = [(name, buf, _printable_ratio(buf)) for name, buf in candidates]
    scored.sort(key=lambda x: -x[2])
    best_name, best_buf, best_score = scored[0]

    # Threshold is deliberately strict: legitimate text with some control
    # bytes (field separators, schedule bytes) still scores ~0.90+. Code
    # and compressed data typically stay below 0.50. Anything in between
    # is the uncertain zone where we punt to the user.
    THRESHOLD = 0.85

    if best_score < THRESHOLD:
        lines = [
            "COULD NOT DECODE AS TEXT",
            "",
            f"Best-scoring transform was '{best_name}' at {best_score:.2f} "
            f"printable ratio (below the {THRESHOLD:.2f} threshold).",
            "",
            "All candidates:",
        ]
        for name, _, score in scored:
            lines.append(f"  {name:<32s} {score:.2f}")
        lines += [
            "",
            "This region is probably one of:",
            "  - compressed data  (LZ77, RLE, custom)",
            "  - executable code  (try disassemble)",
            "  - a custom encoding  (XOR key, scrambled, etc.)",
            "  - structured binary records  (not meant to be text)",
            "",
            "If you know the encoding, say so and I'll decode it. "
            "Otherwise inspect with hex_dump to eyeball structure.",
        ]
        return "\n".join(lines)

    header = (
        f"ENCODING: {best_name}\n"
        f"CONFIDENCE: {best_score:.2f} printable ratio "
        f"(range {offset}..{offset + len(data)})\n\n"
    )
    return header + _render_bytes(best_buf)


# ── disassemble ───────────────────────────────────────────────────────────────

@mcp.tool()
async def disassemble(
    path: str,
    bits: int = 16,
    offset: int = 0,
    length: int = 0,
) -> str:
    """Disassemble with `ndisasm -b {bits}`.

    Args:
        path: File to disassemble.
        bits: 16, 32, or 64. 16 = real-mode DOS (.OVL / .COM), 32 = PE32,
              64 = PE32+. Default 16.
        offset: Byte offset to start at (passed as `-o`). For offset > 0
                ndisasm still reads from the beginning; if you want only
                the tail, combine with a slice (dd) — done automatically
                when length > 0 by feeding a sliced stdin.
        length: Bytes to disassemble. 0 = whole file from offset.

    Result is indexed in the knowledge base keyed by (md5, offset, length, bits).
    """
    if bits not in (16, 32, 64):
        return f"FAILED\n\nbits must be 16, 32, or 64 (got {bits})"

    try:
        p = _resolve_path(path)
    except Exception as e:
        result = f"FAILED\n\n{e}"
        _report(
            "disassemble",
            {"path": path, "bits": bits, "offset": offset, "length": length},
            result,
            False,
        )
        return result

    md5_hex = ""
    try:
        md5_hex = _md5_of(p)
    except Exception:
        pass

    if length > 0:
        # Slice via dd, then pipe to ndisasm over stdin. ndisasm `-` reads
        # stdin and respects `-o` for the origin address label.
        dd_ok, dd_bytes = await asyncio.to_thread(_read_slice, p, offset, length)
        if not dd_ok:
            result = f"FAILED\n\n{dd_bytes}"
            _report(
                "disassemble",
                {"path": str(p), "bits": bits, "offset": offset,
                 "length": length, "md5": md5_hex},
                result,
                False,
            )
            return result
        cmd = ["ndisasm", "-b", str(bits), "-o", hex(offset), "-"]
        ok, out = await _run_async(cmd, input_bytes=dd_bytes)
    else:
        cmd = ["ndisasm", "-b", str(bits), "-o", hex(offset), str(p)]
        ok, out = await _run_async(cmd)

    result = out if ok else f"FAILED\n\n{out}"
    _report(
        "disassemble",
        {
            "path": str(p),
            "filename": p.name,
            "bits": bits,
            "offset": offset,
            "length": length,
            "md5": md5_hex,
        },
        result,
        ok,
    )
    return result


# ── slice_bytes ───────────────────────────────────────────────────────────────

@mcp.tool()
async def slice_bytes(path: str, offset: int, length: int) -> str:
    """Return `length` bytes starting at `offset`, base64-encoded.

    Useful for handing a specific record to a Python parser without round-
    tripping through hex text. Capped at {MAX_SLICE_BYTES} bytes.
    """
    if length <= 0:
        return "FAILED\n\nlength must be > 0"
    if length > MAX_SLICE_BYTES:
        return (
            f"FAILED\n\nlength {length} exceeds MAX_SLICE_BYTES "
            f"({MAX_SLICE_BYTES}). Narrow the range or call again."
        )
    try:
        p = _resolve_path(path)
    except Exception as e:
        return f"FAILED\n\n{e}"

    ok, data = await asyncio.to_thread(_read_slice, p, offset, length)
    if not ok:
        return f"FAILED\n\n{data}"
    return base64.b64encode(data).decode("ascii")


# ── md5 / stat ────────────────────────────────────────────────────────────────

@mcp.tool()
async def md5(path: str) -> str:
    """md5 hex digest of the file. Cheap identity check across sessions."""
    try:
        p = _resolve_path(path)
    except Exception as e:
        return f"FAILED\n\n{e}"
    try:
        return await asyncio.to_thread(_md5_of, p)
    except Exception as e:
        return f"FAILED\n\n{e}"


@mcp.tool()
async def stat(path: str) -> str:
    """One-call file fingerprint: size, mtime, md5."""
    try:
        p = _resolve_path(path)
    except Exception as e:
        return f"FAILED\n\n{e}"
    try:
        st = p.stat()
        md5_hex = await asyncio.to_thread(_md5_of, p)
    except Exception as e:
        return f"FAILED\n\n{e}"
    mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
    return (
        f"path: {p}\n"
        f"size: {st.st_size} bytes\n"
        f"mtime: {mtime}\n"
        f"md5: {md5_hex}\n"
    )


# ── note ──────────────────────────────────────────────────────────────────────

@mcp.tool()
async def note(
    md5: str,
    offset: int,
    length: int,
    text: str,
    tags: list[str] | None = None,
) -> str:
    """Persist a finding to the knowledge base.

    This is the high-signal ingest path: you've decoded a struct, spotted
    a record boundary, cross-referenced a value range — save it. Chunks
    are keyed by (md5, offset, length) so they travel with the bytes even
    if filenames change.

    Args:
        md5: md5 hex of the file this note is about (use `md5` tool first).
        offset: byte offset of the region the note describes.
        length: byte length of the region.
        text: the note itself. Struct definitions, value ranges, theories —
              whatever you want findable later.
        tags: optional list, e.g. ['npc-record', 'u5', 'schedule'].
    """
    tags = tags or []
    args = {
        "md5": md5,
        "offset": offset,
        "length": length,
        "tags": tags,
    }
    # The text is the payload, not args. Match the build→knowledge contract
    # where `result` carries the indexable body.
    _report("note", args, text, True)
    return (
        f"noted: md5={md5} offset={offset} length={length} "
        f"tags={tags} ({len(text)} chars)"
    )


# ── Internals ────────────────────────────────────────────────────────────────

def _md5_of(p: Path) -> str:
    h = hashlib.md5()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_slice(p: Path, offset: int, length: int) -> tuple[bool, bytes | str]:
    try:
        with p.open("rb") as f:
            f.seek(offset)
            return True, f.read(length)
    except Exception as e:
        return False, f"read slice failed at offset={offset} length={length}: {e}"


# Printable = standard ASCII printable range plus common whitespace and NUL
# (which is how many DOS formats mark field/record boundaries, so we don't
# want it to count against the score).
_PRINTABLE_OK = set(range(0x20, 0x7F)) | {0x00, 0x09, 0x0A, 0x0D}


def _printable_ratio(data: bytes) -> float:
    if not data:
        return 0.0
    return sum(1 for b in data if b in _PRINTABLE_OK) / len(data)


def _render_bytes(data: bytes) -> str:
    """Render a byte string with visible markers for non-printable bytes."""
    out = []
    for b in data:
        if b == 0x00:
            out.append("|")              # record / field separator
        elif 0x20 <= b <= 0x7E or b in (0x09, 0x0A, 0x0D):
            out.append(chr(b))
        else:
            out.append(".")
    return "".join(out)


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"PROJECTS_DIR={PROJECTS_DIR}")
    print(f"KNOWLEDGE_URL={_reporter.url}")
    print("Starting dos-re MCP on http://0.0.0.0:5175")
    print()
    print("Register with Claude Code:")
    print("  claude mcp add dos-re --transport http http://localhost:5175/mcp")
    print()
    sys.stdout.flush()
    mcp.run(transport="streamable-http", host="0.0.0.0", port=5175)
