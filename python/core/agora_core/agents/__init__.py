"""The agent adapter: one way in to our agents for Petri, Bloom, Ethos and the rehearsal."""

# Registers the agoradev provider with Inspect, for development without provider keys.
from agora_core.agents import dev_model as _dev_model  # noqa: F401
