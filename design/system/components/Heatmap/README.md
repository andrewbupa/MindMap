# Heatmap

Judge dimensions by transcript: our custom dimensions first, Petri's built-in ones folded away. Each cell is a ScoreCell over a cool steel tint (`color-chart-1`) that deepens with the score.

Provide `dimensions` and `builtIn` (`{key, label}`), and `transcripts` (`{id, label, seed?, href, scores: {key: {value, samples?, href?}}}`).

- The tint never passes 28% of `color-chart-1`, so the score and its "of 10" keep 4.5:1. High scores also take a `color-danger` bead, so concern never rests on the tint alone.
- Order rows worst first when the view supports it.
