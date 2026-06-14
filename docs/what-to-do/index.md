# What to do with Loom

*Things you can build once your projects route through Loom — and how to make
each one.*

---

Loom isn't just a way to call AI vendors with one contract. Because every
`generate()` call flows through a single library, you get a single place to
capture cost, latency, caching, and routing decisions across every project and
every provider. That shared chokepoint makes a whole class of tooling cheap to
build — usually with **no per-call-site changes**.

This section is a growing catalogue of those builds. Each page walks through
the idea, what data Loom already gives you, the architecture, and a suggested
build order.

## The catalogue

<div class="grid cards" markdown>

-   :material-chart-line:{ .lg .middle } **[Observability dashboard](observability_dashboard.md)**

    ---

    A real-time provider-health / cost / throughput dashboard built entirely
    on the structured record Loom emits per call — requests/min, P95 latency,
    cache hit rate, cost saved, per-provider health, and a live request log.

</div>

More builds will land here over time. Have an idea? It probably maps onto data
Loom is already emitting.
