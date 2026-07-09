export interface CodeSample {
  id: string;
  label: string;
  filename: string;
  language: "python";
  code: string;
}

export const codeSamples: CodeSample[] = [
  {
    id: "generate",
    label: "intelligent routing",
    filename: "route.py",
    language: "python",
    code: `import loom

# State intent — Loom picks the provider and model, health-aware.
result = loom.generate(router="cheapest", prompt="Summarize this transcript.")

print(result["text"])
print(result["cost"]["usd"])          # 0.0000041
print(result["_router"]["used"])      # "gemini:text:gemini-2.5-flash"

# A provider order, a named strategy, or nothing at all:
loom.generate(providers=["gemini", "openai"], prompt="...")
loom.generate(router="fastest", prompt="...")
loom.generate(prompt="...")           # fully automatic — balanced
`,
  },
  {
    id: "async",
    label: "sync + async",
    filename: "api.py",
    language: "python",
    code: `from fastapi import FastAPI
from loom import AsyncLoom

app = FastAPI()
aclient = AsyncLoom.from_env()

@app.get("/answer")
async def answer(q: str):
    # Same intent-based routing, fully async.
    result = await aclient.generate(router="fastest", prompt=q)
    return {"text": result["text"], "cost": result["cost"]["usd"]}
`,
  },
  {
    id: "structured",
    label: "structured outputs",
    filename: "extract.py",
    language: "python",
    code: `from pydantic import BaseModel
from loom import Loom

class User(BaseModel):
    name: str
    age: int

client = Loom.from_env()

# Validated object out, provider-agnostic.  pip install loom[structured]
user = client.generate(prompt="Extract the user from: ...", schema=User)

assert isinstance(user, User)
print(user.name, user.age)
`,
  },
  {
    id: "compare",
    label: "benchmark providers",
    filename: "benchmark.py",
    language: "python",
    code: `from loom import Loom

client = Loom.from_env()

report = client.compare(
    providers=["openai", "anthropic", "gemini"],
    prompt="Explain quantum entanglement.",
)

for row in report:
    print(row.provider, row.model, row.latency_ms, row.cost_usd)

report.summary.cheapest.provider    # lowest cost row
report.summary.fastest.provider     # lowest latency row
`,
  },
  {
    id: "fallback",
    label: "automatic fallback",
    filename: "resilient.py",
    language: "python",
    code: `from loom import Loom, FallbackPolicy

client = Loom.from_env()

# Survive an outage — walk the chain on retryable failures.
result = client.generate(
    prompt="Draft a launch announcement.",
    router="balanced",
    fallback=FallbackPolicy(retries=3,
                            providers=["gemini", "openai", "anthropic"]),
)

result["_router"]["used"]      # provider that answered
result["_router"]["tried"]     # every provider attempted
`,
  },
];
