Bench is an internal instrument for seeing how our AI agents behave in health insurance and personal health. It should feel like technological slate: calm, smooth, exact. The one visual idea is the **channel**, a rounded groove routed through the surface and lit from the top left, taken from the softly bevelled tubes of a dark slate relief. Use it boldly in one place per view (the PageHeader's Relief) and quietly everywhere else (tracks, grooves, wells, the conversation's route). Never use neon, glows of colour, gradients as decoration, or grids of identical cards.

## Content fundamentals

- Write plain British English in sentence case. Short sentences. No exclamation marks, no emoji, no all-caps labels.
- Name things by what people do: "Start audit of 12 samples", "Download the Inspect log", "Save and label the next". A button's verb returns in its toast: "Cancel run" leads to "Run cancelled".
- Errors say what happened and how to fix it, without apology: "It used 400,000 of 400,000 tokens. Raise the budget in the launcher and start it again."
- Empty states invite the next step in the app's own words: "Nothing is waiting for your review." "No open model has read this run yet."
- Use these words exactly; they come from the data:
  - Run kinds: Explore, Measure, Lens, Playground, Scenario set, Companion.
  - Statuses: queued, running, succeeded, failed, cancelled, stopped at budget.
  - Intensity: absent (0), faint (1), clear (2), dominant (3); a two-judge median may be a half, such as 1.5.
  - Expected profile: present (with a band such as 1 to 2), absent, or either. Fit is a percentage per reply and per transcript.
  - Trust: trusted (agreement 0.8 or more), provisional (from 0.667), retired (below), unrated.
  - Families and labels: Care (emotional reaction, interpretation, exploration); Collaboration (reflection, open question, autonomy support, partnership); Judgement (calibrated uncertainty, scope discipline, referral, privacy care); Curiosity (purposeful question, reflexive question); Risk (sycophancy, false reassurance, over hedging, padding).
  - Review verdicts: agree, disagree (with a corrected value), unsure.
  - Open-model signal kinds: probe, persona vector, autoencoder explanation.
- Fixed wording, always as written:
  - Lens pages carry "Expressed disposition, read from text. Lens does not see inside the model." (PageHeader `note`).
  - Thinking summaries are labelled as summaries "of the agent's reasoning, written by a separate model".
  - The open-model pane says its signals are that model's reading of the text, "not the agent's own internals".
  - Reports say that everything in Bench is synthetic.
- Sample content is always synthetic. The house example: Priya Sandford, member TEST-100231, Gold cover, knee MRI claim CLM-TEST-5521 declined, seed `declined-mri-promise`, scenario type `claim_declined_distress`, Claims assistant prompt v12.

## Visual foundations

**Light and bezels.** One light source, top left, in both themes, and every edge answers it with a falloff, never a flat drop shadow.
- Raised controls (buttons, the selected tab, the active nav item, checked boxes) have a 1px bezel outline running from `color-bezel-hi` on top to `color-bezel-lo` below, a face that is lighter on top, and `shadow-raise` (a lit inner top line, then a soft falloff beneath). Hovering brightens the bezel toward `color-sheen`. Pressing reverses it: the bezel and face flip and the control sinks into `shadow-inset`.
- Grooves (tab and nav bars, tracks) run the other way: `color-bezel-lo` on the upper wall, `color-bezel-hi` on the lower lip, a `color-channel` floor with `shadow-inset` falling off from the top.
- Containers (cards, tables, dialogs, toasts, the agent's messages) catch the light on their top edge: their border runs from a mix of `color-bezel-hi` into `color-border` by 42% of their height.
- Fields keep a solid `color-border-strong` edge so they meet 3:1, with the well's falloff and lip inside it.

**Themes.** Dark (slate) is the first theme and the fallback; light (mist) mirrors it. Set `data-theme="dark"` or `"light"` on `html`. Both are first-class: check every new pairing in both.

**Surfaces.** The page is `color-bg` with a faint radial luminance from the top left toward `color-surface`. Content sits on `color-surface`; quiet fills use `color-surface-muted`. Separate regions with tone and space first, `color-border` hairlines second. Cards (`radius-md`, a `color-rim` top edge) group content; they are not the default container.

**Colour.**
- Text is `color-text`; secondary text `color-text-muted`. Both hold 4.5:1 on `color-bg`, `color-surface`, `color-surface-muted`, the status `-bg` tints and every family tint up to `intensity-3`, in both themes.
- `color-accent` is a pale steel in dark and a deep slate blue in light: primary buttons, links, the selected state. Text on it is `color-accent-text`.
- Status: `color-ok`, `color-warn`, `color-danger`, each on its own `-bg` tint. Every status carries a word and a glyph; colour never carries it alone.
- Lens families (`family-care`, `family-collaboration`, `family-judgement`, `family-curiosity`, `family-risk`) follow Okabe and Ito's colour-blind-safe set, muted for slate. They only group: the label name always shows beside the hue.
- Intensity shows as a family tint: `color-mix(in srgb, var(--family-…) var(--intensity-n), transparent)`. `intensity-1` 18%, `intensity-2` 30%, `intensity-3` 42%; absent shows none. (The brief's 20, 35 and 50% left text under 4.5:1 on dominant curiosity in dark.)
- `color-expected` is the faint lit band behind ProfileStrip tracks. `color-signal` is a silver, achromatic scale for open-model signals, kept apart from the five family hues.
- Charts use `color-chart-1` for the single series and `color-chart-grid` for rules. A worse version switches to `color-danger` and says so in words.
- Focus is a solid 2px `color-focus` outline, 2px off the control, 3:1 on every surface. Control edges use `color-border-strong` (3:1).

**Type.** Instrument Sans for everything people read; Spline Sans Mono only for hashes, IDs, model names and message references (M3). Page titles (`page-title`, `text-xl`) run at `font-stretch: 88%` for a precise, instrument-like headline; that condensed title is the typographic signature, so use it nowhere else. Body is `text-md` at `leading` 1.55, reading lines under 72 characters. Numbers in tables and charts use tabular figures. No all-caps, no eyebrow labels above headings.

**Spacing and layout.** Steps of 4: `space-1` to `space-7` (4, 8, 12, 16, 24, 32, 48). The main column grows to `content-width` (72rem) with `space-6` gutters. Left-align text; right-align numbers.

**Radii.** `radius-pill` for anything that moves or holds a value (buttons, badges, chips, tabs, nav, every channel), echoing the rounded ends of the routed channels. `radius-md` for containers (cards, fields, tables, notices; dialogs add 4px). `radius-sm` for small inline marks (Mono, citations, highlights, checkboxes).

**Elevation.** `shadow-1` only for dialogs and toasts. Everything else is either raised a hair (`shadow-raise`) or set into a channel (`shadow-inset`). In CSS, a bezel is a transparent 1px border with two background layers: the face on `padding-box`, the bezel gradient on `border-box`.

**Motion.** `--motion-fast` 120ms and `--motion-base` 220ms on `--ease-standard` (cubic-bezier(.2, .7, .2, 1)), defined in `components/bundle.css` because tokens hold no motion. Motion answers a person: pressing, opening, switching tabs. Two ambient exceptions, both still under reduced motion: the running status pulse and the light travelling along a loading or running channel. Never animate the Relief.

**The Relief.** The motif in full: routed ridges, like contour lines pressed into slate. Each ridge has a crisp 1.25px crest in `color-sheen`, a lit flank tapering away toward the top left, a shaded flank in `color-halo` tapering toward the bottom right, and a fine shaded lip under the crest. The flanks are stacks of strokes whose widths grow on a square curve, so the profile peaks sharply at the crest and tails off softly, with darker valleys between ridges. Flank strength is set per theme in `components/bundle.css` (`--bn-r-lit`, `--bn-r-shade`, `--bn-r-lip`). Ridges dissolve toward every edge of their box. Two routes: `route` (concentric ridges turning down, with a hairpin) in every PageHeader, and `hairpin` (one U-turn) in EmptyState. PageHeader gives it its own column beside the text, hidden below 900px, so it never sits under text. Keep it decorative (`aria-hidden`), at most once per view, never animated.

**Accessibility.** WCAG 2.2 AA throughout, checked in both themes across every component (1,225 text elements each) with axe-core and a pixel-level contrast check for text on gradients and bezels.
- Text contrast: 4.5:1 or more for all text, 3:1 or more for large text, on every surface, tint and bezel face. Disabled controls are exempt, as WCAG allows, but still carry their label.
- No text over imagery: the Relief has its own column in PageHeader and sits above, never behind, text in EmptyState. The cover's name sits on plain ground.
- Sizes: nothing under 12px. Body is 15px, hints and errors 13px because they carry instructions, Mono never smaller than 12px. Charts keep a 560px minimum width and scroll sideways rather than shrink their 12px labels.
- Structure: grids that present tables (TurnTimeline, CompareView) carry table, row, row-header and cell roles. Every chart has a text summary and RateChart pairs with RateTable.
- Interaction: every control has a visible label; focus is a 2px `color-focus` outline; Tabs move with arrow keys; highlights open with Enter; selected tabs and the current nav item change weight as well as fill. Long transcripts stay readable at 200% zoom.

## Iconography

Bench has no icon set or logo yet. The name is set in plain type (Instrument Sans, 640 weight, 86% width) beside a single accent bead; replace it when a real mark exists. Glyphs are drawn inline as small SVG at 10px, stroked in `currentColor`:

- Status: queued (ring), running (pulsing bead), succeeded (tick), failed (cross), cancelled (dash), stopped at budget (two bars).
- Trust: trusted (filled bead), provisional (half bead), retired (bead with a slash, struck text), unrated (dashed ring).
- ProfileStrip markers: ✓ expected and found, – expected but missing, ! expected absent but found, ⚑ judges differ by two points or more. Each has a text equivalent for screen readers.

## Intentional additions

Beyond the brief's inventory: the `Relief` component, which carries the visual language; tokens `color-border-strong`, `color-channel`, `color-rim`, `color-shade`, `color-halo`, `color-sheen`, `color-bezel-hi`, `color-bezel-lo`, `radius-pill`, `shadow-raise` and `shadow-inset`, which the channel, the bezels and the Relief need. Every other token and component name matches the brief, so `tokens.css` can replace `web/styles/tokens.css` without code changes.
