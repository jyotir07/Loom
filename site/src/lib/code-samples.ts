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
    label: "generate()",
    filename: "app.py",
    language: "python",
    code: `import loom

result = loom.generate(
    provider="openai",
    modality="text",
    model="gpt-4o-mini",
    prompt="Summarize this transcript in five bullets.",
)

print(result["text"])
print(result["cost"]["usd"])      # 0.0000038
print(result["usage"]["total_tokens"])
`,
  },
  {
    id: "async",
    label: "async",
    filename: "api.py",
    language: "python",
    code: `from fastapi import FastAPI
from loom import AsyncLoom

app = FastAPI()
aclient = AsyncLoom.from_env()

@app.get("/answer")
async def answer(q: str):
    result = await aclient.generate(
        provider="openai",
        modality="text",
        model="gpt-4o-mini",
        prompt=q,
    )
    return {"text": result["text"], "cost": result["cost"]["usd"]}
`,
  },
  {
    id: "router",
    label: "smart routing",
    filename: "router.py",
    language: "python",
    code: `from loom import Loom, Router, Candidate

router = Router(
    candidates=[
        ("openai",    "text", "gpt-4o-mini"),
        Candidate("anthropic", "text", "claude-haiku-4-5"),
        ("openai",    "text", "gpt-4o", {"temperature": 0.2}),
    ],
    validator=lambda r: len(r["text"]) > 40,
)

client = Loom.from_env()
result = client.route(router, prompt="Explain quantum entanglement.")

result["_router"]["used"]    # which model won
result["_router"]["tried"]   # all attempted
`,
  },
  {
    id: "register",
    label: "register provider",
    filename: "setup.py",
    language: "python",
    code: `from loom import Catalog

c = Catalog.from_yaml("models.yaml")

# Register a new OpenAI-shape vendor in ~10 lines:
c.register_openai_compatible(
    key="newco",
    label="NewCo AI",
    base_url="https://api.newco.ai/v1",
    api_key_env="NEWCO_API_KEY",
)

c.register_model(
    provider="newco",
    model_id="newco-large",
    upstream_model="newco-large-2026-01",
    input_cost_per_1m=2.50,
    output_cost_per_1m=10.00,
)
`,
  },
  {
    id: "batch",
    label: "batch",
    filename: "batch.py",
    language: "python",
    code: `from loom import Loom, BatchRequest

client = Loom.from_env()

handle = client.submit_batch([
    BatchRequest(provider="openai", modality="text",
                 model="gpt-4o-mini",
                 prompt="summarize row 1", custom_id="row-1"),
    BatchRequest(provider="openai", modality="text",
                 model="gpt-4o-mini",
                 prompt="summarize row 2", custom_id="row-2"),
])

print(handle.id, handle.status())
results = handle.wait(poll_interval=60.0, timeout=24 * 3600)
`,
  },
];
