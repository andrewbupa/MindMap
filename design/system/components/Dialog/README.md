# Dialog

A confirmation over the page, such as cancelling a run.

Provide `title`, `children` (what will happen), `actions` (buttons, the safe one first), `open`, and `onClose` (Escape calls it). `inline` renders it in place, for previews.

- Title asks the question; the primary action repeats its verb: "Cancel run", not "OK".
- Uses `shadow-1`, one of only two places elevation appears.
