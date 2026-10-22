# CompanionPane

Open-model signals for one reply: choose a signal and the reply shades by its value in silver, kept apart from the family hues; autoencoder explanations list the span they quote.

Provide `text`, `signals` (`{id, name, kind: 'probe' | 'persona' | 'autoencoder', spans: {start, end, value 0 to 1}}`), and optionally `model`, `active` and `explanations` (`{quote, text}`).

- Keep the fixed sentence: these signals are the open model's reading of the text, "not the agent's own internals".
