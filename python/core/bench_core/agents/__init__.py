"""The agent adapter: one way in to our agents for Petri, Bloom, Lens and the playground."""

# Registers the benchdev provider with Inspect, for development without provider keys.
from bench_core.agents import dev_model as _dev_model  # noqa: F401
