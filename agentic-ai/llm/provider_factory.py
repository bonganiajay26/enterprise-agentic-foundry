"""
provider_factory.py — Universal LLM Provider Factory

Builds a LangChain-compatible chat model for ANY supported provider from a
single declarative config (agentic-ai/config/llm-config.yaml), so agents never
import a provider SDK directly. Adding a new provider = add an entry to the
PROVIDER_BUILDERS registry + the YAML config — zero changes to agent code.

Design goals:
  - Provider-agnostic: agents call `get_chat_model(agent_name=...)` and receive
    a `BaseChatModel`; they never know whether it's OpenAI, Bedrock, or Ollama.
  - Secrets never touch the YAML — every credential is resolved from environment
    variables (themselves populated by Key Vault / Secrets Manager / Vault at
    pod startup via External Secrets Operator).
  - Fail-closed: missing credentials raise `ProviderConfigError` immediately
    rather than silently falling through to a degraded provider.

Usage:
    from agentic_ai.llm.provider_factory import get_chat_model

    llm = get_chat_model(agent_name="architecture_agent")
    llm_with_tools = llm.bind_tools([analyze_repo, generate_diagram])
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

import yaml

logger = logging.getLogger("agentic_ai.llm.provider_factory")

CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "llm-config.yaml"
)


class ProviderConfigError(RuntimeError):
    """Raised when a provider cannot be constructed (missing key, bad config)."""


@dataclass(frozen=True)
class ResolvedModel:
    provider: str
    model: str
    region: str
    in_per_1m: float
    out_per_1m: float
    context_window: int
    quality_tier: str
    latency_tier: str = "standard"


# ---------------------------------------------------------------------------
# Config loading (cached at module level — reload via `reload_config()` in
# tests or after a hot config-map update).
# ---------------------------------------------------------------------------
_config_cache: Optional[dict] = None


def _expand_env(value: Any) -> Any:
    """Expand ${VAR:-default} style placeholders found in YAML scalars."""
    if not isinstance(value, str):
        return value
    if value.startswith("${") and value.endswith("}"):
        inner = value[2:-1]
        if ":-" in inner:
            var, default = inner.split(":-", 1)
            return os.environ.get(var, default)
        return os.environ.get(inner, "")
    return value


def _walk_expand(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _walk_expand(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_walk_expand(v) for v in node]
    return _expand_env(node)


def load_config(path: str = CONFIG_PATH) -> dict:
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    _config_cache = _walk_expand(raw)
    return _config_cache


def reload_config(path: str = CONFIG_PATH) -> dict:
    global _config_cache
    _config_cache = None
    return load_config(path)


# ---------------------------------------------------------------------------
# Resolution: agent_name -> (profile -> provider chain -> model)
# ---------------------------------------------------------------------------
def _require_env(var_name: str, provider: str) -> str:
    value = os.environ.get(var_name)
    if not value:
        raise ProviderConfigError(
            f"Provider '{provider}' requires environment variable '{var_name}' "
            f"(populate via External Secrets / Key Vault — never hardcode)."
        )
    return value


def resolve_chain(agent_name: Optional[str] = None) -> list[ResolvedModel]:
    """
    Returns an ordered list of candidate models (primary first, then
    fallbacks) for the given agent, after applying compliance filtering.
    Env vars LLM_PROVIDER / LLM_MODEL override everything (deployment hotfix
    path — e.g. "the Anthropic API is down, force Bedrock cluster-wide").
    """
    cfg = load_config()

    override_provider = os.environ.get("LLM_PROVIDER")
    override_model = os.environ.get("LLM_MODEL")
    if override_provider:
        models_cfg = cfg["providers"][override_provider]["models"]
        model_name = override_model or next(iter(models_cfg))
        return [_to_resolved(override_provider, model_name, cfg)]

    agent_overrides = cfg.get("agent_overrides", {})
    profile_name = (
        agent_overrides.get(agent_name, {}).get("profile")
        if agent_name
        else None
    ) or cfg["active_profile"]

    profile = cfg["profiles"][profile_name]
    chain_names = [profile["primary"]] + list(profile.get("fallbacks", []))

    candidates = []
    for provider_name in chain_names:
        model_override = profile.get("default_model_overrides", {}).get(provider_name)
        provider_cfg = cfg["providers"][provider_name]
        model_name = model_override or next(iter(provider_cfg["models"]))
        candidates.append(_to_resolved(provider_name, model_name, cfg))

    if cfg.get("compliance", {}).get("enforce"):
        candidates = _apply_compliance_filter(candidates, cfg)

    if not candidates:
        raise ProviderConfigError(
            f"No compliant provider chain resolved for agent='{agent_name}', "
            f"profile='{profile_name}'. Check compliance.allowed_regions in "
            f"llm-config.yaml."
        )
    return candidates


def _to_resolved(provider_name: str, model_name: str, cfg: dict) -> ResolvedModel:
    provider_cfg = cfg["providers"][provider_name]
    model_cfg = provider_cfg["models"][model_name]
    return ResolvedModel(
        provider=provider_name,
        model=model_name,
        region=provider_cfg.get("region", "global"),
        in_per_1m=model_cfg.get("in_per_1m", 0.0),
        out_per_1m=model_cfg.get("out_per_1m", 0.0),
        context_window=model_cfg.get("context_window", 8192),
        quality_tier=model_cfg.get("quality_tier", "medium"),
        latency_tier=model_cfg.get("latency_tier", "standard"),
    )


def _apply_compliance_filter(candidates: list[ResolvedModel], cfg: dict) -> list[ResolvedModel]:
    allowed_regions = set(cfg["compliance"].get("allowed_regions", []))
    air_gapped_only = cfg["compliance"].get("data_residency") == "on_prem_only"

    filtered = []
    for c in candidates:
        provider_cfg = cfg["providers"][c.provider]
        compliance_tags = set(provider_cfg.get("compliance", []))
        if air_gapped_only and "on_prem_only" not in compliance_tags and "air_gapped" not in compliance_tags:
            logger.info("compliance: dropping %s (not on-prem/air-gapped)", c.provider)
            continue
        if c.region not in ("global", "configurable", "on_prem") and c.region not in allowed_regions:
            logger.info("compliance: dropping %s (region '%s' not in allow-list)", c.provider, c.region)
            continue
        filtered.append(c)
    return filtered


# ---------------------------------------------------------------------------
# Provider builders — one factory function per LangChain integration.
# Each returns a `BaseChatModel`. Import statements are LAZY (inside the
# function) so the platform doesn't require every provider SDK to be
# installed — only the ones actually configured for use.
# ---------------------------------------------------------------------------
def _build_openai(resolved: ResolvedModel, **kwargs) -> Any:
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=resolved.model,
        api_key=_require_env("OPENAI_API_KEY", "openai"),
        base_url=os.environ.get("OPENAI_BASE_URL") or None,
        temperature=kwargs.get("temperature", 0.1),
        max_tokens=kwargs.get("max_tokens"),
        timeout=kwargs.get("timeout", 60),
    )


def _build_azure_openai(resolved: ResolvedModel, **kwargs) -> Any:
    from langchain_openai import AzureChatOpenAI
    return AzureChatOpenAI(
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", resolved.model),
        api_key=_require_env("AZURE_OPENAI_API_KEY", "azure_openai"),
        azure_endpoint=_require_env("AZURE_OPENAI_ENDPOINT", "azure_openai"),
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        temperature=kwargs.get("temperature", 0.1),
        max_tokens=kwargs.get("max_tokens"),
        timeout=kwargs.get("timeout", 60),
    )


def _build_anthropic(resolved: ResolvedModel, **kwargs) -> Any:
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(
        model=resolved.model,
        api_key=_require_env("ANTHROPIC_API_KEY", "anthropic"),
        base_url=os.environ.get("ANTHROPIC_BASE_URL") or None,
        temperature=kwargs.get("temperature", 0.1),
        max_tokens=kwargs.get("max_tokens", 4096),
        timeout=kwargs.get("timeout", 60),
    )


def _build_gemini(resolved: ResolvedModel, **kwargs) -> Any:
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=resolved.model,
        google_api_key=_require_env("GOOGLE_API_KEY", "gemini"),
        temperature=kwargs.get("temperature", 0.1),
        max_output_tokens=kwargs.get("max_tokens"),
    )


def _build_vertex_ai(resolved: ResolvedModel, **kwargs) -> Any:
    from langchain_google_vertexai import ChatVertexAI
    return ChatVertexAI(
        model_name=resolved.model,
        project=_require_env("GCP_PROJECT_ID", "vertex_ai"),
        location=os.environ.get("GCP_REGION", "us-central1"),
        temperature=kwargs.get("temperature", 0.1),
        max_output_tokens=kwargs.get("max_tokens"),
    )


def _build_bedrock(resolved: ResolvedModel, **kwargs) -> Any:
    from langchain_aws import ChatBedrock
    return ChatBedrock(
        model_id=resolved.model,
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        # Prefer IRSA / assume-role over static keys; static keys only as
        # a documented fallback for non-K8s environments.
        credentials_profile_name=os.environ.get("AWS_PROFILE") or None,
        model_kwargs={"temperature": kwargs.get("temperature", 0.1)},
    )


def _build_cohere(resolved: ResolvedModel, **kwargs) -> Any:
    from langchain_cohere import ChatCohere
    return ChatCohere(
        model=resolved.model,
        cohere_api_key=_require_env("COHERE_API_KEY", "cohere"),
        temperature=kwargs.get("temperature", 0.1),
    )


def _build_mistral(resolved: ResolvedModel, **kwargs) -> Any:
    from langchain_mistralai import ChatMistralAI
    return ChatMistralAI(
        model=resolved.model,
        api_key=_require_env("MISTRAL_API_KEY", "mistral"),
        endpoint=os.environ.get("MISTRAL_BASE_URL") or None,
        temperature=kwargs.get("temperature", 0.1),
    )


def _build_groq(resolved: ResolvedModel, **kwargs) -> Any:
    from langchain_groq import ChatGroq
    return ChatGroq(
        model=resolved.model,
        api_key=_require_env("GROQ_API_KEY", "groq"),
        temperature=kwargs.get("temperature", 0.1),
    )


def _build_together_ai(resolved: ResolvedModel, **kwargs) -> Any:
    from langchain_together import ChatTogether
    return ChatTogether(
        model=resolved.model,
        api_key=_require_env("TOGETHER_API_KEY", "together_ai"),
        temperature=kwargs.get("temperature", 0.1),
    )


def _build_huggingface(resolved: ResolvedModel, **kwargs) -> Any:
    from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
    endpoint = HuggingFaceEndpoint(
        endpoint_url=_require_env("HF_INFERENCE_ENDPOINT_URL", "huggingface"),
        huggingfacehub_api_token=_require_env("HUGGINGFACE_API_TOKEN", "huggingface"),
        temperature=kwargs.get("temperature", 0.1),
        max_new_tokens=kwargs.get("max_tokens", 2048),
    )
    return ChatHuggingFace(llm=endpoint)


def _build_ollama(resolved: ResolvedModel, **kwargs) -> Any:
    from langchain_ollama import ChatOllama
    return ChatOllama(
        model=resolved.model,
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=kwargs.get("temperature", 0.1),
    )


def _build_custom(resolved: ResolvedModel, **kwargs) -> Any:
    """OpenAI-compatible endpoint for enterprise-hosted / private models
    (vLLM, TGI, LM Studio, internal model gateways)."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=resolved.model,
        api_key=_require_env("CUSTOM_LLM_API_KEY", "custom"),
        base_url=_require_env("CUSTOM_LLM_ENDPOINT", "custom"),
        temperature=kwargs.get("temperature", 0.1),
        max_tokens=kwargs.get("max_tokens"),
    )


PROVIDER_BUILDERS: dict[str, Callable[..., Any]] = {
    "openai": _build_openai,
    "azure_openai": _build_azure_openai,
    "anthropic": _build_anthropic,
    "gemini": _build_gemini,
    "vertex_ai": _build_vertex_ai,
    "bedrock": _build_bedrock,
    "cohere": _build_cohere,
    "mistral": _build_mistral,
    "groq": _build_groq,
    "together_ai": _build_together_ai,
    "huggingface": _build_huggingface,
    "ollama": _build_ollama,
    "custom": _build_custom,
}


def build_model(resolved: ResolvedModel, **kwargs) -> Any:
    builder = PROVIDER_BUILDERS.get(resolved.provider)
    if builder is None:
        raise ProviderConfigError(f"No builder registered for provider '{resolved.provider}'")
    logger.info(
        "llm: building provider=%s model=%s region=%s quality=%s",
        resolved.provider, resolved.model, resolved.region, resolved.quality_tier,
    )
    return builder(resolved, **kwargs)


# ---------------------------------------------------------------------------
# Public entry point — what agents actually call.
# ---------------------------------------------------------------------------
def get_chat_model(agent_name: Optional[str] = None, **kwargs) -> Any:
    """
    Returns a ready-to-use `BaseChatModel` for the given agent, applying:
      1. Compliance filtering
      2. Profile / agent-override resolution
      3. The FIRST candidate that successfully constructs (subsequent
         candidates are tried only via the runtime `LLMRouter` fallback path
         — this factory call always returns the primary unless it fails to
         *construct* due to missing credentials).

    For full cost/latency-aware routing with live circuit breakers, use
    `agentic_ai.llm.router.LLMRouter` instead, which wraps this factory.
    """
    chain = resolve_chain(agent_name)
    last_error: Optional[Exception] = None
    for resolved in chain:
        try:
            return build_model(resolved, **kwargs)
        except ProviderConfigError as exc:
            logger.warning("llm: skipping %s — %s", resolved.provider, exc)
            last_error = exc
            continue
    raise ProviderConfigError(
        f"All providers in chain failed to construct for agent='{agent_name}'. "
        f"Last error: {last_error}"
    )
