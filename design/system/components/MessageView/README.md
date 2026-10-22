# MessageView

One message on the conversation's route: a channel runs down the left and each message is a node on it. The system prompt and tool results fold away; the member is "played by the auditor"; tool calls sit under the agent's message.

Provide `role` (`system`, `member`, `agent` or `tool`), `children`, and optionally `author`, `index` (for M3 references), `toolCalls` (`{name, args}`) and `thinking` (`summary` or `full`).

- Stack MessageViews directly; the route joins up between them.
- Keep the reading column under 46rem.
