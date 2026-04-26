# mcp-dos-re-knowledge — DOS-era RE Knowledge Service

RAG-backed knowledge service for binary reverse engineering findings.
Sibling to `mcp-dos-re`; accepts fire-and-forget ingest POSTs on
`localhost:5176/ingest` and serves query tools over MCP.

---

## Design principle: md5-keyed, not path-keyed

Every chunk carries an `md5` metadata field as its primary identity. Files
get renamed, copied, backed up — the bytes don't change. Keying by md5
means an annotation written against `CASTLE.NPC` still surfaces when
looking up `castle_npc_copy.bin` if they're the same bytes.

The `filename` field is carried too, but as a hint, not an identifier.

---

## What gets indexed (selective ingest)

Router is in `ingest/router.py`. The rules:

| Tool               | Action                             |
|--------------------|------------------------------------|
| `identify`         | Upsert one chunk per md5           |
| `disassemble`      | Index per (md5, offset, length, bits) |
| `note`             | Always index (the high-signal path) |
| `hex_dump`         | **skip** (regenerable, noisy)      |
| `hex_view_colored` | **skip**                           |
| `find_strings`     | **skip**                           |
| `slice_bytes`      | **skip**                           |
| `md5`              | **skip**                           |
| `stat`             | **skip**                           |

The skipped tools are cheap to regenerate and would flood the index with
commodity output. The kept tools either cost real time (disassembly) or
carry human judgment (notes, which are the whole point of the service).

---

## Chunk kinds

```
identify     id = "identify/{md5}"
             ↳ one per md5; upserts on repeat
disassembly  id = "disassembly/{md5}/{bits}/{offset}/{length}"
             ↳ repeating the same region overwrites; different region = new
note         id = "note/{md5}/{offset}/{length}/{timestamp}"
             ↳ accumulates; two notes on the same region both kept
```

---

## Metadata schema

```python
{
    "source":      "note/d41d8cd98f00b204e9800998ecf8427e",   # prefix + md5
    "kind":        "note",        # identify | disassembly | note
    "md5":         "d41d8cd98f00b204e9800998ecf8427e",
    "filename":    "CASTLE.NPC",  # hint, not identity
    "offset":      0x90,
    "length":      144,
    "bits":        0,             # 16 / 32 / 64 for disassembly, 0 otherwise
    "tags":        "note,npc-record,u5,schedule",
    "indexed_at":  "2026-04-23T09:15:00Z",
    # Plus per-tag boolean keys (tag_note, tag_npc_record, ...) for filtering.
}
```

Tags are normalised via `tag_key()` in `ingest/chunker.py` — lowercase,
non-alphanumeric → underscore. Boolean per-tag keys are how `ask_tagged`
works (ChromaDB has no `$contains` operator on metadata).

---

## MCP tools

### Query

| Tool                        | Purpose                                             |
|-----------------------------|-----------------------------------------------------|
| `ask(question)`             | Semantic search across all findings                 |
| `ask_file(md5_or_path)`     | Every annotation for one file (md5 or exact name)   |
| `ask_offset(md5, offset)`   | Annotations whose byte range covers `offset`        |
| `ask_tagged(question, tags)`| Semantic search filtered to those tags              |

### Maintenance

| Tool                  | Purpose                                                       |
|-----------------------|---------------------------------------------------------------|
| `list_sources()`      | Every indexed source with chunk counts                        |
| `stats()`             | Totals by kind, distinct md5 count, top tags                  |
| `forget(source)`      | Delete chunks matching a source prefix                        |
| `forget_md5(md5)`     | Delete every chunk for a given md5                            |

No `retag_all` or `seed_*` tools — unlike pygame-knowledge, this collection
doesn't grow from a source tree. Everything enters via ingest or `note`.

---

## Container layout

```
mcp-dos-re-knowledge/
├── CLAUDE.md              ← this file
├── Dockerfile             ← CUDA base (shared embedding stack with mcp-knowledge)
├── requirements.txt       ← fastmcp, chromadb, httpx, uvicorn, onnxruntime-gpu
├── build-container.sh     ← links sibling model (pygame or sandbox) or downloads
├── start-container.sh     ← --device nvidia.com/gpu=all, PORT=5176, COLLECTION=dosre_knowledge
├── reset-knowledge.sh     ← wipe ChromaDB and restart
├── mcp-service.py         ← FastMCP + /ingest endpoint
├── ingest/
│   ├── chunker.py         ← md5-keyed chunk builders (identify/disassembly/note)
│   └── router.py          ← selective ingest routing
├── models/                ← embedding model (symlink to sibling if available)
└── knowledge/             ← ChromaDB persistent storage (gitignored)
```

---

## Known concerns

### 1. No passive `note` path — deliberate

The only way notes enter the index is through an explicit
`mcp-dos-re::note(...)` call. If you forget to call it, the finding is
lost when the conversation ends. This is intentional: auto-extracting
"findings" from hex dumps produces garbage. The friction of calling
`note` is a feature.

### 2. No whole-repo seeding

Unlike pygame-knowledge there's no `seed_python_source` equivalent. The
index grows transaction by transaction. If you want a jump-start on a
new binary, run `identify` + a broad `disassemble` once, then lay notes.

### 3. md5 collisions

md5 is cryptographically broken but collision-free in practice for the
file sizes we deal with (a few MB of DOS binaries). If a collision ever
matters, the fix is to swap `md5` for a `sha1`/`sha256` column everywhere
— no schema change to the query semantics.

### 4. Substring filename search is not supported

ChromaDB metadata filters require exact match. `ask_file(path)` works for
full filenames only. Partial / fuzzy match would require fetching all
metadatas and filtering in Python — cheap for a small collection but
grows linearly with corpus size. Not worth building until someone wants it.

---

## Non-goals

- No symbol recovery, no CFG reconstruction, no function boundary analysis.
  Those are Ghidra's job.
- No PE / ELF header parsing. Out of scope for "hand-rolled DOS formats."
- No embedding model fine-tuning. Pure retrieval against the stock
  `all-MiniLM-L6-v2`.
