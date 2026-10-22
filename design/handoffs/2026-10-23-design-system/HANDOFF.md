# Handoff: the Agora design system

23 October 2026. The first full handoff: tokens, type, the bezel and groove treatment, the ridge motif, and all 41 components from `docs/CLAUDE_DESIGN_BRIEF.md`, in dark and light. View it in `design/agora-design-system.html`; build from `design/system/`.

Plan the work as one milestone, list open questions, and wait for approval before coding, as `CLAUDE.md` asks. Record every decision in `docs/DECISIONS.md`.

## What to build, in order

1. **Fonts.** Copy `design/system/fonts/*.woff2` to `web/public/fonts/` with both `OFL-*.txt` licences. Instrument Sans for everything people read; Spline Sans Mono only for hashes, IDs, model names and message references.
2. **Tokens.** Replace `web/styles/tokens.css` with `design/system/tokens.app.css`. Every token name the components read today is kept. New tokens: `color-border-strong`, `color-channel`, `color-rim`, `color-shade`, `color-halo`, `color-sheen`, `color-bezel-hi`, `color-bezel-lo`, `color-expected`, `color-signal`, `radius-pill`, `shadow-1`, `shadow-raise`, `shadow-inset`, `intensity-1` to `intensity-3`.
3. **Themes.** Themes now switch on `data-theme` on `<html>` instead of `prefers-color-scheme`. Set it before first paint with a small inline script in the root layout: the person's saved choice if any, otherwise the OS preference. Add a Dark/Light choice under Settings, preferences. Dark is the design's first theme.
4. **Motion.** Copy the motion variables (`--motion-fast`, `--motion-base`, `--ease-standard`) and the theme helper variables (`--bn-raise-top`, `--bn-bezel`, `--bn-groove`, `--bn-edge` and the rest at the top of `design/system/components/bundle.css`) into the global stylesheet. They must be declared on `:root, [data-theme]` as there, so they resolve inside each theme.
5. **Foundations.** Restyle `web/components/ui/` to match `bundle.css`: Button, LinkButton, Field, Select, Checkbox, Radio, Tabs, Dialog, Toast, Notice, Card, PageHeader, Badge, Mono, AppShell, Nav. Build the ones marked "to build" in the brief. The bezel technique: a transparent 1px border with the face on `padding-box` and the bezel gradient on `border-box`; a plain colour may only be the last background layer.
6. **Relief and PageHeader.** Add `Relief` (the ridge motif, `bundle.js`) as a component. PageHeader puts it in its own grid column beside the text, hidden below 900px. It is decorative (`aria-hidden`) and never sits under text.
7. **Everything else.** Restyle data, runs, transcripts, Ethos and agents components to match their previews: the Heatmap tint is `color-chart-1` at up to 28%; Ethos intensities are 18, 30 and 42%; TurnTimeline and CompareView carry table, row, row-header and cell roles; RateChart keeps a 560px minimum width and scrolls rather than shrinking text.

Each component's `README.md` in `design/system/components/` gives its props, rules and fixed wording; the `preview.html` beside it shows the intended result. `bundle.js` is a reference implementation in plain `React.createElement`; port it to typed components that fit the codebase rather than copying it whole.

## Decisions to record

- Ethos intensities change from 20, 35 and 50% to 18, 30 and 42%, so text keeps 4.5:1 on the dominant Curiosity tint in dark.
- Theme switching moves from `prefers-color-scheme` to `data-theme`, with the OS preference as the default.
- `Relief` is a component beyond the brief's inventory; it carries the visual language.

## Done when

- Every screen matches its component previews in both themes.
- axe-core reports no violations in either theme across the app's main routes.
- All text meets 4.5:1 (3:1 at 24px, or 18.66px bold), nothing renders under 12px, hints and errors are 13px, and no text sits over the Relief.
- Reduced motion stills the running pulse and the loading light.
