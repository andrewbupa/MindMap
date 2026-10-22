# ScoreCell

A judge score with a small mark showing where it sits and how the samples spread; links to its evidence.

Provide `value`, and optionally `max` (10), `samples` (other repetitions' scores), `href`, `label`, `threshold` (7) and `concern` (false when high is good).

- A score at or over the threshold takes a `color-danger` bead; others `color-chart-1`. The number always shows.
