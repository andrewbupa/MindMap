# Design

Everything about how Agora looks lives here. Nothing in this folder ships in the app image (`.dockerignore` excludes it); the app takes what it needs through handoffs.

| Path | What it is |
| --- | --- |
| `agora-design-system.html` | The design system in one file. Open it in any browser, offline. Every component is live, with a Dark, Light or Both switch at the top left. |
| `system/` | The source of truth: `tokens.json`, its compiled `tokens.css`, the guidelines (`README.md`), real font files with their licences, and every component with its usage notes, preview and reference code (`components/bundle.css`, `bundle.js`, `index.d.ts`). |
| `system/tokens.app.css` | The tokens ready for the app, with font paths for `web/public/fonts/`. It replaces `web/styles/tokens.css`. |
| `handoffs/` | One dated folder per handoff, each with a `HANDOFF.md` telling Claude Code what to build. The latest is `handoffs/2026-10-23-design-system/`. |

## Working with it

- **To view the system,** open `agora-design-system.html`.
- **To build from it,** ask Claude Code to read the latest `HANDOFF.md` and follow it.
- **To change it,** edit `system/tokens.json` and the component files, then rebuild `tokens.css` and `tokens.app.css` from it. Or use Claude Design: link this repository, run `/design-sync` from Claude Code so designs use the real components, and save each new handoff here as a dated folder.
- Read `system/README.md` before any change. Its rules on contrast, sizes, the motif and fixed wording apply to every screen.
