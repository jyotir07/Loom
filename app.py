"""Flask demo app — thin consumer of the `loom` package.

Phase 1 outcome: this file no longer owns the catalog or the provider
adapters. They live in `loom.catalog` and `loom.providers`. The app
is just routes + a login wall + a small bit of introspection for the
UI's "view source" button.
"""

import inspect
import os
from pathlib import Path

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import loom
from loom import providers as loom_providers
from loom.catalog import CATALOG
from loom.errors import LoomError, ModelNotFoundError, ProviderError

# Load .env from the directory next to this file regardless of CWD,
# and override pre-existing env so edits to .env take effect after a restart.
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)

app = Flask(__name__, static_url_path="/models_catelog/static")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "prometrix-dev-secret-change-me")

# A shared Loom instance — the Flask routes use this directly rather
# than going through the module-level `loom.generate` so we can swap
# in custom config later (catalog backend, cache backend, etc).
_client = loom.Loom.from_env()

AUTH_USER = "admin"
AUTH_PASS = "prometrix@2026"

PUBLIC_ENDPOINTS = {"login", "static"}


@app.before_request
def _require_login():
    if request.endpoint in PUBLIC_ENDPOINTS:
        return None
    if session.get("logged_in"):
        return None
    return redirect(url_for("login", next=request.path))


@app.route("/models_catelog/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if username == AUTH_USER and password == AUTH_PASS:
            session["logged_in"] = True
            dest = request.args.get("next") or url_for("index")
            return redirect(dest)
        error = "Invalid username or password."
    return render_template("login.html", error=error)


@app.get("/models_catelog/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# Env vars surfaced on /api/diagnostic (presence + length only, never values).
ENV_KEYS = [
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "XAI_API_KEY",
    "MISTRAL_API_KEY",
    "DEEPSEEK_API_KEY",
    "MINIMAX_API_KEY",
    "ZAI_API_KEY",
    "BFL_API_KEY",
    "IDEOGRAM_API_KEY",
    "ARK_API_KEY",
    "TENCENT_SECRET_ID",
    "TENCENT_SECRET_KEY",
]

PLACEHOLDER_VALUES = {
    "",
    "your_openai_api_key_here", "your_gemini_api_key_here",
    "your_anthropic_api_key_here", "your_xai_api_key_here",
    "your_mistral_api_key_here", "your_deepseek_api_key_here",
    "your_minimax_api_key_here", "your_zai_api_key_here",
    "your_bfl_api_key_here", "your_ideogram_api_key_here",
    "your_ark_api_key_here", "your_tencent_secret_id_here",
    "your_tencent_secret_key_here",
}


@app.get("/")
def root():
    return redirect(url_for("index"))


@app.get("/models_catelog")
def index():
    return render_template("index.html")


@app.get("/models_catelog/api/catalog")
def catalog():
    return jsonify({
        provider: {
            "label": data["label"],
            "modalities": data["modalities"],
        }
        for provider, data in CATALOG.items()
    })


@app.get("/models_catelog/api/diagnostic")
def diagnostic():
    def info(name):
        raw = os.getenv(name) or ""
        stripped = raw.strip()
        return {
            "present": bool(stripped),
            "length": len(stripped),
            "looks_like_placeholder": stripped in PLACEHOLDER_VALUES,
            "has_surrounding_whitespace": raw != stripped,
        }
    return jsonify({name: info(name) for name in ENV_KEYS})


@app.get("/models_catelog/api/code")
def code():
    provider = request.args.get("provider")
    modality = request.args.get("modality")
    if not provider or not modality:
        return jsonify({"error": "provider and modality required"}), 400

    if provider not in loom_providers.available():
        return jsonify({
            "error": f"provider '{provider}' has no Loom adapter yet",
        }), 404

    try:
        # Touch the dispatcher to lazy-load the module, then grab it.
        loom_providers._module_for(provider)  # noqa: SLF001
        module = loom_providers._LOADED[provider]  # noqa: SLF001
    except Exception as err:  # noqa: BLE001
        return jsonify({"error": f"{type(err).__name__}: {err}"}), 500

    sections = []
    seen = set()

    def add(fn):
        if fn is None or fn in seen:
            return
        seen.add(fn)
        try:
            sections.append(inspect.getsource(fn))
        except (TypeError, OSError):
            pass

    add(getattr(module, "_client", None))
    add(getattr(module, "generate", None))
    add(getattr(module, f"_{modality}", None))

    if not sections:
        return jsonify({"error": "no source available"}), 404

    return jsonify({
        "code": "\n\n".join(s.rstrip() for s in sections),
        "language": "python",
        "filename": f"loom/providers/{provider}_provider.py",
    })


@app.post("/models_catelog/api/generate")
def generate():
    payload = request.get_json(silent=True) or {}
    provider = payload.get("provider")
    modality = payload.get("modality")
    model_id = payload.get("model")
    prompt = (payload.get("prompt") or "").strip()

    if not all([provider, modality, model_id, prompt]):
        return jsonify({
            "error": "provider, modality, model and prompt are required",
        }), 400

    try:
        result = _client.generate(
            provider=provider,
            modality=modality,
            model=model_id,
            prompt=prompt,
        )
        return jsonify(result)
    except ModelNotFoundError as err:
        return jsonify({"error": str(err)}), 400
    except ProviderError as err:
        return jsonify({"error": str(err)}), 400
    except NotImplementedError as err:
        return jsonify({"error": str(err)}), 501
    except LoomError as err:
        return jsonify({"error": f"{type(err).__name__}: {err}"}), 500
    except Exception as err:  # noqa: BLE001 - surface upstream error to UI
        return jsonify({"error": f"{type(err).__name__}: {err}"}), 500


@app.post("/models_catelog/api/models/add")
def add_model():
    # The runtime add-model flow (DB upsert + catalog patcher + codegen) is
    # being reworked for the package layout — tracked under Phase 2.
    # For now the catalog is editable by hand in loom/catalog/_data.py.
    return jsonify({
        "error": (
            "the runtime add-model endpoint is being reworked for the loom "
            "package layout and will return in Phase 2. Edit "
            "loom/catalog/_data.py directly to add models in the meantime."
        ),
    }), 503


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=3001, debug=True)
