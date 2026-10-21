# Bloom behaviours

One folder per behaviour, in the format petri_bloom reads: `BEHAVIOR.md` holds
YAML front matter and the definition, and an optional `examples/` folder holds
example transcripts. Every example must be synthetic.

Bench reads these front matter keys as well as petri_bloom's own:

- `agents`: the agents this behaviour is measured on.
- `scenario_type`: the Lens scenario type of its scenarios, for expected profiles.
- `content_notes`: notes such as `self_harm` that gate who may read its transcripts.

Scenarios are generated from a behaviour in Bench (Measure, then the behaviour,
then "Generate scenarios") and stored in Postgres, never in this folder. Changing
`BEHAVIOR.md` makes a new behaviour version, whose scenarios must be generated
again; rates are only compared across prompt versions that faced the same
scenario set.

Every behaviour should keep:

- `modality: conversation`. Our agents answer their own tools from fixtures, so
  the auditor never simulates tool results.
- `instructions.ideation` naming the synthetic records the agent can look up, and
  asking for no real organisations, people or contact details.
- `instructions.evaluation` telling the auditor that the agent's system prompt is
  fixed, and never to ask the agent to show its reasoning.
