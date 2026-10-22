# Toast

A short confirmation that says what happened: "Verdict recorded".

Provide `children`, and optionally `tone` (`ok`, the default, `warn`, `danger`, `info`) and `action` (a LinkButton such as "Undo").

- Past tense, the same verb as the action that caused it.
- Uses `shadow-1`; dismisses itself, so never the only place an error appears.
