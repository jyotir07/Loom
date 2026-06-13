"""Flask demo app — thin consumer of the `loom` package.

Phase 1 outcome: this file no longer owns the catalog or the provider
adapters. They live in `loom.catalog` and `loom.providers`. The app
is just routes + a login wall + a small bit of introspection for the
UI's "view source" button.
"""

import importlib
import inspect
import os
import re
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

import app_patch

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


PROVIDER_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VALID_MODALITIES = {"text", "image", "video"}

PROJECT_ROOT = Path(__file__).parent
CATALOG_DATA_PATH = PROJECT_ROOT / "loom" / "catalog" / "_data.py"
PROVIDERS_DIR = PROJECT_ROOT / "loom" / "providers"
PROVIDERS_INIT_PATH = PROVIDERS_DIR / "__init__.py"


@app.post("/models_catelog/api/models/add")
def add_model():
    """Runtime add-model: DB upsert + catalog patch + (if new) codegen.

    Body (JSON):
        provider_key:     str (matches ^[a-z][a-z0-9_]*$)
        provider_label:   str
        modality:         "text" | "image" | "video"
        model_id:         str
        model_name:       str (defaults to model_id)
        upstream_model:   str | None
        params:           dict | None
        input_inr_per_1m: float | None
        output_inr_per_1m: float | None
        cost_inr:         float | None
        is_free:          bool

    For a brand-new provider, also generates loom/providers/<key>_provider.py
    using the OpenAI-compatible template and registers it in the _LAZY
    registry.
    """
    payload = request.get_json(silent=True) or {}
    provider_key = (payload.get("provider_key") or "").strip().lower()
    provider_label = (payload.get("provider_label") or "").strip()
    modality = (payload.get("modality") or "").strip().lower()
    model_id = (payload.get("model_id") or "").strip()
    model_name = (payload.get("model_name") or "").strip() or model_id
    upstream_model = (payload.get("upstream_model") or "").strip() or None
    params = payload.get("params") or None
    input_rate = payload.get("input_inr_per_1m")
    output_rate = payload.get("output_inr_per_1m")
    image_cost = payload.get("cost_inr")
    is_free = bool(payload.get("is_free") or False)
    base_url = (payload.get("base_url") or "").strip() or None
    api_key_env = (payload.get("api_key_env") or "").strip() or None

    if not PROVIDER_KEY_RE.match(provider_key):
        return jsonify({"error": "provider_key must match ^[a-z][a-z0-9_]*$"}), 400
    if not provider_label:
        return jsonify({"error": "provider_label is required"}), 400
    if not model_id:
        return jsonify({"error": "model_id is required"}), 400
    if modality not in VALID_MODALITIES:
        return jsonify({"error": f"modality must be one of {sorted(VALID_MODALITIES)}"}), 400

    is_new_provider = provider_key not in loom_providers._LAZY  # noqa: SLF001
    target_provider_file = PROVIDERS_DIR / f"{provider_key}_provider.py"
    if is_new_provider and target_provider_file.exists():
        return jsonify({
            "error": (
                f"loom/providers/{provider_key}_provider.py already exists on "
                "disk but isn't registered. Delete it or pick a different "
                "provider_key."
            ),
        }), 409

    # Step 1: DB upsert (best-effort — log a soft error if Postgres isn't reachable).
    db_status: dict = {"ok": False, "error": None}
    try:
        import seed_db

        seed_db.upsert_one(
            provider_key=provider_key,
            provider_label=provider_label,
            model_id=model_id,
            model_name=model_name,
            modality=modality,
            upstream_model=upstream_model,
            params=params,
            input_inr_per_1m=input_rate,
            output_inr_per_1m=output_rate,
            cost_inr=image_cost,
            is_free=is_free,
        )
        db_status["ok"] = True
    except Exception as err:  # noqa: BLE001 — Postgres may not be configured locally
        db_status["error"] = f"{type(err).__name__}: {err}"

    # Step 2: Patch loom/catalog/_data.py.
    try:
        catalog_status = app_patch.add_catalog_entry(
            CATALOG_DATA_PATH,
            provider_key=provider_key,
            provider_label=provider_label,
            modality=modality,
            model_id=model_id,
            model_name=model_name,
            upstream_model=upstream_model,
            params=params,
            input_inr_per_1m=input_rate,
            output_inr_per_1m=output_rate,
            cost_inr=image_cost,
            is_free=is_free,
        )
    except Exception as err:  # noqa: BLE001
        return jsonify({
            "stage": "catalog",
            "db": db_status,
            "error": f"{type(err).__name__}: {err}",
        }), 500

    created_file: str | None = None
    registry_status: str | None = None

    if is_new_provider:
        # Step 3: codegen a starter provider module.
        try:
            source = app_patch.generate_provider_source(
                provider_key=provider_key,
                provider_label=provider_label,
                base_url=base_url or "https://api.example.com/v1",
                api_key_env=api_key_env,
            )
            target_provider_file.write_text(source, encoding="utf-8")
            created_file = f"loom/providers/{provider_key}_provider.py"
        except Exception as err:  # noqa: BLE001
            _safe_rollback(provider_key, modality, model_id)
            return jsonify({
                "stage": "codegen",
                "db": db_status,
                "error": f"{type(err).__name__}: {err}",
            }), 500

        # Step 4: register in _LAZY.
        try:
            registry_status = app_patch.add_provider_to_registry(
                PROVIDERS_INIT_PATH,
                provider_key=provider_key,
                module_path=f"loom.providers.{provider_key}_provider",
            )
        except Exception as err:  # noqa: BLE001
            try:
                target_provider_file.unlink()
            except OSError:
                pass
            _safe_rollback(provider_key, modality, model_id)
            return jsonify({
                "stage": "registry",
                "db": db_status,
                "error": f"{type(err).__name__}: {err}",
            }), 500

    # Step 5: best-effort in-process refresh.
    _reload_loom_modules()

    return jsonify({
        "ok": True,
        "provider_key": provider_key,
        "model_id": model_id,
        "modality": modality,
        "db": db_status,
        "catalog": catalog_status,
        "registry": registry_status,
        "created_file": created_file,
    })


def _safe_rollback(provider_key: str, modality: str, model_id: str) -> None:
    try:
        app_patch.rollback_catalog_entry(
            CATALOG_DATA_PATH,
            provider_key=provider_key,
            modality=modality,
            model_id=model_id,
        )
    except Exception:  # noqa: BLE001 — best effort
        pass


def _reload_loom_modules() -> None:
    """Re-import the catalog data + provider registry so this process sees the edits."""
    try:
        import loom.catalog._data as _data_mod
        import loom.catalog._catalog as _catalog_mod
        import loom.catalog as _catalog_pkg
        import loom.providers as _providers_pkg

        importlib.reload(_data_mod)
        importlib.reload(_catalog_mod)
        importlib.reload(_catalog_pkg)
        importlib.reload(_providers_pkg)
        # Rebuild this app's client + the module-level CATALOG binding.
        global _client, CATALOG
        _client = loom.Loom.from_env()
        CATALOG = _catalog_pkg.CATALOG
    except Exception:  # noqa: BLE001 — debug reloader will resync next request
        pass


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=3001, debug=True)
