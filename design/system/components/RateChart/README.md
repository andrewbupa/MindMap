# RateChart

Elicitation rate by prompt version: each version a bead on the route, a whisker for the spread across repetitions, and its repetitions as small rings. A version that got worse turns `color-danger`, gains a ring and says by how much.

Provide `data` (`{version, rate, low, high, reps, worse?}` in order), and optionally `title` and `max`.

- Always pair with RateTable for screen readers and exports.
