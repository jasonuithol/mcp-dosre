# WARNING

Actually using these extensions will definitely trigger violations of
Claude's usage policy classifier. In short, even decompiled STRINGS look
suspicious to the classifier if they are in byte code and maybe have some
suspicious 00's in them. After all, 00's is how you hack the system right?
Anyway, I cannot recommend using these plugins right now on Claude Code.

# mcp-dosre

MCP service pair for reverse-engineering DOS-era binaries — hex inspection,
magic/strings identification, 16/32/64-bit x86 disassembly, and a RAG
knowledge base that accumulates findings indexed by md5 hash.

| Subdir | Container | Port | Purpose |
|--------|-----------|------|---------|
| `service/` | `mcp-dos-re` | 5175 | Hex / strings / magic / disasm / md5 / stat / note tools |
| `knowledge/` | `mcp-dos-re-knowledge` | 5176 | RAG over disassembly, identify results, and explicit notes |

Both mount `~/Projects` read-only at `/opt/projects`. The two halves are
paired: `service/` POSTs structured findings at `knowledge/`'s `/ingest`
endpoint.

## Consumers

This is a service-pack only — it does not launch Claude. Any MCP client
speaking streamable HTTP can mount these services. Currently picked up
opportunistically by [`claude-pygame`](../claude-pygame/)'s `start.sh`
when `~/Projects/mcp-dosre/start.sh` is present.

## Quick start

```bash
./setup.sh              # one-time, idempotent (builds both images)
./start.sh
./stop.sh               # when done
```

To validate setup works from bare state:

```bash
./clean.sh && ./setup.sh && ./start.sh
```

## Design notes

- **md5-keyed knowledge** — findings travel with the bytes, not the file
  path. Renaming `CASTLE.NPC` doesn't orphan its annotations.
- **Selective ingest** — `disassemble`, `identify`, and explicit `note(...)`
  calls get indexed; `hex_dump` / `slice_bytes` / `find_strings` don't
  (cheap to regenerate, noisy to index).
- **Read-only** — no write tools; the `/workspace` mount is `:ro`.
- **Collection `dosre_knowledge`** — separate from `pygame_knowledge`.
  Different domain, different retrieval semantics.

See `knowledge/CLAUDE.md` for the knowledge service's design.
