flowchart TD

subgraph group_public["Public API"]
  node_exports["Package exports<br/>Python API<br/>[__init__.py]"]
  node_client["Loom client<br/>orchestrator<br/>[_loom.py]"]
  node_router["Generation router<br/>convenience API<br/>[_router.py]"]
end

subgraph group_orchestration["Orchestration"]
  node_types["Normalized types<br/>request/response contract<br/>[types.py]"]
  node_call_key["Call keys<br/>request identity<br/>[_call_key.py]"]
  node_cache[("Response cache<br/>optimization stage<br/>[_cache.py]")]
  node_dedup["Concurrent deduplication<br/>optimization stage<br/>[_dedup.py]"]
end

subgraph group_routing["Routing &amp; Resilience"]
  node_selector["Candidate selector<br/>routing policy<br/>[selector.py]"]
  node_strategies["Routing strategies<br/>selection policy<br/>[strategy.py]"]
  node_health["Provider health<br/>runtime signals<br/>[health.py]"]
  node_balancer["Load balancer<br/>routing policy<br/>[balancer.py]"]
  node_retry_fallback["Retry &amp; failover<br/>resilience stage<br/>[_retry.py]"]
end

subgraph group_providers["Provider Layer"]
  node_registry["Provider registry<br/>adapter registry<br/>[__init__.py]"]
  node_adapters["Native adapters<br/>vendor boundary<br/>[_common.py]"]
  node_compatible["OpenAI-compatible adapter<br/>shared vendor adapter"]
  node_provider_apis{{"AI provider APIs<br/>external services"}}
  node_batch["Batch submission<br/>provider extension<br/>[batch.py]"]
end

subgraph group_operations["Data &amp; Operations"]
  node_catalog[("Model catalog<br/>metadata registry<br/>[_catalog.py]")]
  node_catalog_backends[("Catalog backends<br/>storage adapters<br/>[backends.py]")]
  node_vault["Credentials vault<br/>credential source<br/>[vault.py]"]
  node_pricing["Pricing &amp; cost<br/>post-call accounting<br/>[_pricing.py]"]
  node_analytics[("Analytics<br/>observability sink<br/>[analytics.py]")]
end

node_exports -->|"exports"| node_client
node_router -->|"delegates generation"| node_client
node_client -->|"uses contract"| node_types
node_client -->|"resolves model metadata"| node_catalog
node_catalog -->|"loads from"| node_catalog_backends
node_client -->|"resolves credentials"| node_vault
node_client -->|"derives identity"| node_call_key
node_call_key -->|"cache lookup"| node_cache
node_call_key -->|"coalesces work"| node_dedup
node_client -->|"routes unfixed targets"| node_selector
node_selector -->|"applies"| node_strategies
node_selector -->|"consults"| node_health
node_selector -.->|"optionally uses"| node_balancer
node_selector -->|"selected dispatch"| node_retry_fallback
node_retry_fallback -->|"dispatches and fails over"| node_registry
node_registry -->|"native providers"| node_adapters
node_registry -->|"compatible providers"| node_compatible
node_adapters -->|"vendor SDK/API calls"| node_provider_apis
node_compatible -->|"compatible API calls"| node_provider_apis
node_provider_apis -->|"usage result"| node_pricing
node_pricing -->|"records cost and outcome"| node_analytics
node_client -.->|"optional provider extension"| node_batch

click node_exports "https://github.com/jyotir07/loom/blob/main/loom/__init__.py"
click node_client "https://github.com/jyotir07/loom/blob/main/loom/_loom.py"
click node_router "https://github.com/jyotir07/loom/blob/main/loom/_router.py"
click node_types "https://github.com/jyotir07/loom/blob/main/loom/types.py"
click node_call_key "https://github.com/jyotir07/loom/blob/main/loom/_call_key.py"
click node_cache "https://github.com/jyotir07/loom/blob/main/loom/_cache.py"
click node_dedup "https://github.com/jyotir07/loom/blob/main/loom/_dedup.py"
click node_catalog "https://github.com/jyotir07/loom/blob/main/loom/catalog/_catalog.py"
click node_catalog_backends "https://github.com/jyotir07/loom/blob/main/loom/catalog/backends.py"
click node_vault "https://github.com/jyotir07/loom/blob/main/loom/vault.py"
click node_selector "https://github.com/jyotir07/loom/blob/main/loom/routing/selector.py"
click node_strategies "https://github.com/jyotir07/loom/blob/main/loom/routing/strategy.py"
click node_health "https://github.com/jyotir07/loom/blob/main/loom/routing/health.py"
click node_balancer "https://github.com/jyotir07/loom/blob/main/loom/routing/balancer.py"
click node_retry_fallback "https://github.com/jyotir07/loom/blob/main/loom/_retry.py"
click node_registry "https://github.com/jyotir07/loom/blob/main/loom/providers/__init__.py"
click node_adapters "https://github.com/jyotir07/loom/blob/main/loom/providers/_common.py"
click node_compatible "https://github.com/jyotir07/loom/blob/main/loom/providers/_openai_compatible.py"
click node_pricing "https://github.com/jyotir07/loom/blob/main/loom/_pricing.py"
click node_analytics "https://github.com/jyotir07/loom/blob/main/loom/observability/analytics.py"
click node_batch "https://github.com/jyotir07/loom/blob/main/loom/batch.py"

classDef toneNeutral fill:#f8fafc,stroke:#334155,stroke-width:1.5px,color:#0f172a
classDef toneBlue fill:#dbeafe,stroke:#2563eb,stroke-width:1.5px,color:#172554
classDef toneAmber fill:#fef3c7,stroke:#d97706,stroke-width:1.5px,color:#78350f
classDef toneMint fill:#dcfce7,stroke:#16a34a,stroke-width:1.5px,color:#14532d
classDef toneRose fill:#ffe4e6,stroke:#e11d48,stroke-width:1.5px,color:#881337
classDef toneIndigo fill:#e0e7ff,stroke:#4f46e5,stroke-width:1.5px,color:#312e81
classDef toneTeal fill:#ccfbf1,stroke:#0f766e,stroke-width:1.5px,color:#134e4a
class node_exports,node_client,node_router toneBlue
class node_types,node_call_key,node_cache,node_dedup toneAmber
class node_selector,node_strategies,node_health,node_balancer,node_retry_fallback toneMint
class node_registry,node_adapters,node_compatible,node_provider_apis,node_batch toneRose
class node_catalog,node_catalog_backends,node_vault,node_pricing,node_analytics toneIndigo
