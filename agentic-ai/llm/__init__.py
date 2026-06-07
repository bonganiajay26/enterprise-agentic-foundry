"""
agentic_ai.llm — Provider-agnostic LLM abstraction layer.

Public surface:
    get_chat_model(agent_name)   -> BaseChatModel        (simple, single-shot)
    get_routed_model(agent_name) -> LLMRouter            (cost/latency/fallback aware)
    resolve_chain(agent_name)    -> list[ResolvedModel]  (introspection / dashboards)

See agentic-ai/config/llm-config.yaml for provider/profile/routing configuration
and agentic-ai/llm/README.md for the full provider strategy write-up.
"""

from agentic_ai.llm.provider_factory import (
    get_chat_model,
    resolve_chain,
    build_model,
    reload_config,
    ResolvedModel,
    ProviderConfigError,
)
from agentic_ai.llm.router import (
    LLMRouter,
    get_routed_model,
    AllProvidersExhaustedError,
    RoutingDecision,
)

__all__ = [
    "get_chat_model",
    "get_routed_model",
    "resolve_chain",
    "build_model",
    "reload_config",
    "ResolvedModel",
    "ProviderConfigError",
    "LLMRouter",
    "AllProvidersExhaustedError",
    "RoutingDecision",
]
