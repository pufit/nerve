# Nerve

Personal AI assistant — lightweight, single-process, purpose-built.

Nerve is a Python-based personal AI system that replaces OpenClaw with a focused, efficient alternative. It integrates Claude as the AI engine, Telegram as the primary communication channel, and provides a React web UI for full-featured interaction.

## Features

- **Agent Engine** — Claude Agent SDK with built-in tools (Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch) plus custom task/memory tools
- **Telegram Bot** — Receive messages, run agent, stream responses with partial message updates
- **Web UI** — React interface with chat, task management, memory file editing, diagnostics
- **Cron** — APScheduler-based job system with isolated and persistent sessions
- **Sync Engine** — Cursor-based JSONL sync for Telegram (Telethon), Gmail (gog CLI), GitHub (gh CLI)
- **Memory** — File-based markdown memory + memU semantic index over conversations and files (SQLite-persisted)
- **Task System** — Markdown task files with SQLite indexing and escalation reminders
- **Single Process** — No microservices, no Docker. FastAPI + uvicorn, ~50-80MB RAM

## Quick Start

```bash
# Clone and install
cd nerve
uv venv && source .venv/bin/activate
uv pip install -e .

# Interactive setup wizard — creates config, workspace, and cron jobs
nerve init

# Or start directly (auto-runs wizard on fresh install)
nerve start -f

# Check setup
nerve doctor
```

For Docker / non-interactive environments:

```bash
ANTHROPIC_API_KEY=sk-ant-... nerve init --non-interactive

# Or use Claude subscription instead of API key:
NERVE_USE_PROXY=1 nerve init --non-interactive
```

## Configuration

Two config files:
- `config.yaml` — Template settings (committed)
- `config.local.yaml` — Secrets and overrides (gitignored)

See [docs/config.md](docs/config.md) for all options.

## Architecture

```
nerve (single Python process)
├── Gateway (FastAPI) — HTTP API + WebSocket
├── Agent Engine (Claude Agent SDK) — AI with tools
├── Channels — Telegram Bot + Web UI
├── Cron Service (APScheduler) — Scheduled jobs
├── Sync Engine — Telegram/Gmail/GitHub data ingestion
├── Memory — File-based + memU semantic index (conversations + files, SQLite)
└── Tasks — Markdown files + SQLite index
```

See [docs/architecture.md](docs/architecture.md) for details.

## Documentation

- [Architecture](docs/architecture.md) — System overview, data flow, module responsibilities
- [Setup](docs/setup.md) — Installation, config, HTTPS, systemd, first run
- [Config](docs/config.md) — All config options with descriptions and defaults
- [API Reference](docs/api.md) — REST API and WebSocket protocol
- [Sync Engine](docs/sync.md) — How sync works, adding sources, cursor model
- [Tasks](docs/tasks.md) — Task file format, escalation rules
- [Memory](docs/memory.md) — Memory file conventions, memU integration
- [Cron](docs/cron.md) — Cron job format, session modes, source runners
- [Web UI](docs/web-ui.md) — Frontend architecture, building, development
- [Migration](docs/migration.md) — Migrating from OpenClaw

## Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_sessions.py -v

# Run a single test class
pytest tests/test_db.py::TestSchemaMigration -v
```

Tests cover:
- **`test_proxy.py`** (32 tests) — ProxyConfig, NerveConfig proxy properties, ProxyService lifecycle, binary download, health checks, bootstrap proxy mode, subsystem wiring
- **`test_bootstrap.py`** (15 tests) — Fresh install detection, non-interactive setup, deferred writes, CLI integration, config permissions
- **`test_db.py`** (31 tests) — Schema V3 migration, session CRUD, field updates, lifecycle events, channel mappings, cleanup queries, backward compatibility
- **`test_sessions.py`** (41 tests) — SessionManager lifecycle transitions, channel persistence, running state, fork/resume, cron/hook sessions, archive/cleanup, orphan recovery, race condition regression
- **`test_streaming.py`** (9 tests) — Broadcaster register/unregister, bounded buffers, buffer stats

## Requirements

- Python 3.12+
- Node.js 18+ (for web UI build)
- Claude Code CLI (bundled with claude-agent-sdk)
- Anthropic API key **or** Claude subscription via [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) proxy
- Optional: OpenAI API key (for memU embeddings), Telegram bot token, gog CLI, gh CLI
