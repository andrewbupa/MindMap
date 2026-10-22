# Agora

Agora tests our AI agents three ways:

- **Inquiry** (Petri 3) asks what could go wrong across many situations.
- **Tally** (Bloom) asks how often one chosen behaviour occurs.
- **Ethos** asks which dispositions an agent expressed, how strongly, and whether
  they suited the moment. It reads expressed disposition from text.

Every run writes Inspect-format transcripts into one shared record.

- The brief: [docs/BRIEF.md](docs/BRIEF.md)
- Choices and open questions: [docs/DECISIONS.md](docs/DECISIONS.md)
- Running and deploying it: [docs/RUNBOOK.md](docs/RUNBOOK.md)
- Standing instructions for Claude Code: [CLAUDE.md](CLAUDE.md)

## Layout

| Path | What lives there |
| --- | --- |
| `python/` | uv workspace: `core` (models, migrations, storage), `api` (FastAPI), `worker` (job runners) |
| `web/` | Next.js interface |
| `agents/`, `seeds/`, `config/` | Prompts, seeds, taxonomy and model roles, reviewed in git |
| `design/` | Claude Design handoffs |
| `.do/app.yaml` | DigitalOcean App Platform spec |
| `infra/` | Local development support, and the runner for milestone 7 |

Start locally with `make dev`, then open <http://agora.localhost:3000>.

Everything in this repository is synthetic: no real personal or health data.
