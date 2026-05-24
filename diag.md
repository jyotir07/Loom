# Conduit — Systems Diagram

> Open VS Code preview: `Ctrl+Shift+V` (Win/Linux) or `Cmd+Shift+V` (Mac). Zoom: `Ctrl++` / `Ctrl+-`.

---

## Middleware position

```mermaid
flowchart LR
    P1[Customer Support Bot]
    P2[Marketing Creatives]
    P3[Internal Analytics]
    P4[Doc Search]
    P5[Sales Assistant]

    CONDUIT[Conduit Framework]

    V1[OpenAI]
    V2[Anthropic]
    V3[Google Gemini]
    V4[BFL / Ideogram]
    V5[10+ more vendors]

    P1 --> CONDUIT
    P2 --> CONDUIT
    P3 --> CONDUIT
    P4 --> CONDUIT
    P5 --> CONDUIT

    CONDUIT --> V1
    CONDUIT --> V2
    CONDUIT --> V3
    CONDUIT --> V4
    CONDUIT --> V5
```

---

## What Conduit does internally

```mermaid
flowchart LR
    IN[Project Request] --> API[Public API]
    API --> AUTH[Auth & Keys]
    AUTH --> CACHE[Cache]
    CACHE --> ROUTER[Smart Router]
    ROUTER --> BATCH[Batcher & Retry]
    BATCH --> LOG[Cost Logging]
    LOG --> OUT[Vendor Call]
```

---

## What flows through each boundary

```mermaid
flowchart LR
    A[Projects send<br/>provider, model, prompt] --> B[Conduit adds<br/>keys, cache, routing, retries]
    B --> C[Providers receive<br/>optimized call]
```

---

## Layered view

```mermaid
flowchart TB
    L1[Layer 1 — Consuming Projects]
    L2[Layer 2 — Public API]
    L3[Layer 3 — Optimization]
    L4[Layer 4 — Core Services]
    L5[Layer 5 — Provider Adapters]
    L6[Layer 6 — Upstream AI Providers]

    L1 --> L2 --> L3 --> L4 --> L5 --> L6
```

---

## Why the middle position matters

| Benefit | What it means |
|---|---|
| **One integration** | Projects learn one API instead of fourteen |
| **Central optimization** | Caching, batching, routing — built once, savings everywhere |
| **Vendor changes absorbed** | Update Conduit once instead of N project repos |
| **Unified observability** | Real cost visibility per project, per model |
| **Key safety** | API keys live in one place, not scattered across repos |
| **Faster onboarding** | New AI projects ship in hours, not days |