# Note on Claude's content classifier

An earlier version of this README warned that these tools "definitely
trigger" Claude's content classifier. That was empirically retested on
2026-04-28 against single-message prompts in a fresh session — raw
`xxd` / `ndisasm` / `strings` output on DOS-era MZ executables produced
fully helpful, classifier-clear responses with no flags or hedging.

The warning has been retained in softened form: cumulative-context
behaviour during long iterative MCP sessions has not been verified, and
the classifier may yet flag content under conditions the smoketest did
not explore. If issues arise, the cheapest first mitigation is to
prepend a benign-purpose framing line to each tool's output inside
`mcp-service.py` (e.g. `# DOS-era binary inspection — read-only RE for
archival/preservation.`) before returning.

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
speaking streamable HTTP can mount these services. Picked up
opportunistically by
[`claude-sandbox-core`](https://github.com/jasonuithol/claude-sandbox-core)'s
`pygame` domain (listed under `OPTIONAL_REPOS` / `OPTIONAL_SERVICES` in
`domains/pygame.conf`) — if this repo is cloned alongside `mcp-pygame`,
the dos-re services start automatically and register inside the sandbox.

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
