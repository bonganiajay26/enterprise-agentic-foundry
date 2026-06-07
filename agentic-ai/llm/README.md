# Universal LLM Provider Strategy

The Agentic AI Platform is **provider-agnostic by design**. No agent imports a
provider SDK directly or hardcodes a model name — every agent obtains its chat
model through this abstraction layer, configured declaratively in
[`agentic-ai/config/llm-config.yaml`](../config/llm-config.yaml).

This lets the platform run identically against OpenAI, Azure OpenAI, Anthropic
Claude, Google Gemini/Vertex AI, AWS Bedrock, Cohere, Mistral, Groq, Together AI,
Hugging Face, Ollama, or a custom enterprise-hosted endpoint — selectable per
environment, per agent, or per request, without a single code change.

---

## Why provider-agnostic?

| Concern | How the abstraction layer addresses it |
|---|---|
| **API key availability** | Pick whichever provider the customer already has a contract/key for |
| **Compliance / data residency** | `compliance.allowed_regions` + per-provider `compliance:` tags filter candidates *before* routing |
| **Cost** | `routing.strategy: cost` (or `weighted`) ranks candidates by `$/1M tokens` |
| **Latency** | Live p50 latency telemetry + `latency_tier` priors rank "fast" providers (Groq, local Ollama) higher |
| **Model capability** | `quality_tier` (low/medium/high/highest) lets reasoning-heavy agents (Architecture, Security, Incident Response) prefer Opus/GPT-4o/Gemini-Pro while cheap agents (Documentation) use mini/flash/haiku models |
| **Vendor outage** | Automatic fallback chain + circuit breaker — if Anthropic returns 5xx repeatedly, the router opens its circuit and fails over to Azure OpenAI / Bedrock without agent code noticing |
| **Air-gapped / private deployment** | `air-gapped` profile routes to `custom` (enterprise OpenAI-compatible gateway) or local Ollama — zero external network calls |

---

## Architecture

```
                      ┌──────────────────────────────┐
                      │   agentic-ai/config/         │
                      │   llm-config.yaml            │
                      │  (profiles, providers,       │
                      │   routing, compliance)       │
                      └──────────────┬───────────────┘
                                     │ loaded + env-expanded
                                     ▼
        ┌────────────────────────────────────────────────────┐
        │              provider_factory.py                   │
        │  resolve_chain(agent) → [ResolvedModel, ...]       │
        │  build_model(resolved) → BaseChatModel             │
        │  (lazy SDK imports — only configured providers     │
        │   need their package installed)                    │
        └───────────────────────┬────────────────────────────┘
                                 │
                                 ▼
        ┌────────────────────────────────────────────────────┐
        │                   router.py                        │
        │  LLMRouter.invoke(messages)                        │
        │   1. score_candidates(strategy, weights)           │
        │   2. skip circuit-OPEN providers                   │
        │   3. try hop 1..max_fallback_hops                  │
        │   4. record latency/success/failure → MetricsStore │
        │   5. emit structured telemetry (OTel/Prometheus)   │
        └───────────────────────┬────────────────────────────┘
                                 │ BaseChatModel.invoke result
                                 ▼
                      Architecture / Security / CI-CD /
                      Kubernetes / Cost / Documentation /
                      Incident Response / Performance Agents
```

---

## Quick start for agent authors

```python
# Simple — single shot, primary provider only (raises on construction failure)
from agentic_ai.llm import get_chat_model

llm = get_chat_model(agent_name="documentation_agent")
llm_with_tools = llm.bind_tools([generate_readme, generate_runbook])
result = llm_with_tools.invoke(messages)
```

```python
# Recommended for production agents — cost/latency-aware routing,
# automatic fallback across the provider chain, circuit breaker
from agentic_ai.llm import get_routed_model

router = get_routed_model(agent_name="incident_response_agent")
response = router.invoke(messages)   # never raises mid-incident unless EVERY provider is down
```

Both return LangChain-compatible objects — `bind_tools`, `with_structured_output`,
`.invoke`/`.ainvoke`/`.stream` all work as expected, because `LLMRouter.invoke`
delegates to the underlying `BaseChatModel.invoke` for the chosen provider.

---

## Selecting a provider — the four ways

### 1. Global environment variable override (deployment hotfix path)
```bash
# Force every agent in the cluster onto Bedrock during an Anthropic outage
export LLM_PROVIDER=bedrock
export LLM_MODEL=anthropic.claude-3-5-sonnet-20241022-v2:0
```

### 2. Profile selection (environment-level)
```bash
# Switch the entire platform's default routing chain
export LLM_PROFILE=regulated-region   # or local-dev | high-reasoning | air-gapped
```

### 3. Per-agent override (declarative, in `llm-config.yaml`)
```yaml
agent_overrides:
  architecture_agent:      { profile: high-reasoning }
  documentation_agent:     { profile: production-default, routing_strategy: cost }
  incident_response_agent: { profile: high-reasoning, routing_strategy: latency }
```

### 4. Routing strategy (per-call ranking of the resolved chain)
```yaml
routing:
  strategy: weighted   # cost | latency | quality | compliance | availability | weighted
  weights: { cost: 0.30, latency: 0.30, quality: 0.30, availability: 0.10 }
```

---

## Adding a new provider

1. Add an entry to `providers:` in `llm-config.yaml` with `api_key_env`,
   `region`, `compliance` tags, and a `models:` map (pricing + capability metadata).
2. Add a `_build_<provider>()` function to `provider_factory.py` that returns
   a LangChain `BaseChatModel` (lazy-import the SDK inside the function).
3. Register it in `PROVIDER_BUILDERS`.
4. Reference it from a `profiles.<name>.primary` / `.fallbacks` list.

No agent code changes required — the router and factory are fully generic.

---

## Secrets handling

**No API key, endpoint, or credential is ever stored in `llm-config.yaml`.**
Every sensitive value is referenced by environment-variable name
(`api_key_env: ANTHROPIC_API_KEY`) and resolved at runtime. In Kubernetes,
these env vars are populated by `ExternalSecret` resources
(see `helm/templates/externalsecret.yaml`) backed by Azure Key Vault, AWS
Secrets Manager, or GCP Secret Manager — never committed, never logged
(the platform's structured loggers redact `*_API_KEY`, `*_TOKEN`, `*_SECRET`
patterns by default; see `templates/nodejs-api/src/logger.js` and
`templates/python-fastapi/app/main.py` for the redaction config pattern).

---

## Compliance-aware routing

Set `compliance.enforce: true` and `compliance.allowed_regions` /
`data_residency` in `llm-config.yaml`. Before any cost/latency/quality scoring
happens, `_apply_compliance_filter()` removes every candidate whose `region`
is outside the allow-list or whose `compliance:` tags don't satisfy
`on_prem_only` / `air_gapped` requirements. This guarantees a regulated
workload (e.g. handling PII under GDPR, or FedRAMP-bound government data)
**physically cannot** route to a non-compliant provider, even under fallback.

---

## Cost & latency telemetry feedback loop

Every routing decision emits a structured `llm_router_decision` event
containing `provider`, `model`, `strategy`, `score`, `latency_ms`, and
`est_cost_per_1m_usd`. In production these are:

- Pushed to Prometheus as `llm_router_requests_total{provider,outcome}` and
  `llm_router_latency_ms_bucket{provider}` histograms (scraped by the
  `monitoring/` stack and visualized in the "AI Agents" Grafana folder —
  see `monitoring/grafana/provisioning/dashboards.yaml`)
- Consumed by the **Cost Optimization Agent** to recommend routing-strategy
  or profile changes when spend trends upward
- Consumed by the **Incident Response Agent** to correlate agent failures
  with upstream LLM-provider outages (cross-referencing circuit-breaker
  `OPEN` transitions against the incident timeline)

---

## Local development & air-gapped deployments

```bash
export LLM_PROFILE=local-dev   # routes to local Ollama first, Groq/OpenAI as cloud fallback
ollama pull llama3.1:8b
ollama serve
```

For fully air-gapped environments (no outbound internet from the cluster):

```bash
export LLM_PROFILE=air-gapped  # routes to `custom` (internal OpenAI-compatible
                               # gateway, e.g. vLLM/TGI behind an internal LB)
                               # with local Ollama as the only fallback
```

---

## Dependency footprint

Only the SDKs for **configured** providers need to be installed — imports are
lazy. See `agentic-ai/requirements.txt` for the full optional-dependency matrix
(`langchain-openai`, `langchain-anthropic`, `langchain-google-genai`,
`langchain-google-vertexai`, `langchain-aws`, `langchain-cohere`,
`langchain-mistralai`, `langchain-groq`, `langchain-together`,
`langchain-huggingface`, `langchain-ollama`).
