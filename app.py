import importlib
import inspect
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import models_catalog
import providers
from models_catalog import CATALOG, resolve
from providers import _catalog_writer, _code_gen

# Load .env from the directory next to this file regardless of CWD,
# and override pre-existing env so edits to .env take effect after a restart.
load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)

app = Flask(__name__, static_url_path="/models_catelog/static")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "prometrix-dev-secret-change-me")

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

# Names of env vars we'll surface on /api/diagnostic (presence + length only,
# never values).
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

    module = providers.REGISTRY.get(provider)
    if module is None:
        return jsonify({"error": f"unknown provider '{provider}'"}), 400

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

    helper = getattr(module, f"_{modality}", None)
    add(helper)

    # Pull in any module-local helpers referenced from the modality function.
    if helper is not None and helper in seen:
        try:
            helper_src = inspect.getsource(helper)
        except (TypeError, OSError):
            helper_src = ""
        for name in dir(module):
            if not name.startswith("_") or name in ("_client", f"_{modality}"):
                continue
            obj = getattr(module, name, None)
            if not callable(obj):
                continue
            if getattr(obj, "__module__", None) != module.__name__:
                continue
            if f"{name}(" in helper_src:
                add(obj)

    if not sections:
        return jsonify({"error": "no source available"}), 404

    return jsonify({
        "code": "\n\n".join(s.rstrip() for s in sections),
        "language": "python",
        "filename": f"providers/{provider}_provider.py",
    })


@app.post("/models_catelog/api/generate")
def generate():
    payload = request.get_json(silent=True) or {}
    provider = payload.get("provider")
    modality = payload.get("modality")
    model_id = payload.get("model")
    prompt = (payload.get("prompt") or "").strip()

    if not all([provider, modality, model_id, prompt]):
        return jsonify({"error": "provider, modality, model and prompt are required"}), 400

    try:
        upstream_model, params = resolve(provider, modality, model_id)
    except KeyError as err:
        return jsonify({"error": str(err)}), 400

    try:
        result = providers.generate(provider, modality, upstream_model, params, prompt)
        return jsonify(result)
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 400
    except NotImplementedError as err:
        return jsonify({"error": str(err)}), 501
    except Exception as err:  # noqa: BLE001 - surface upstream error to UI
        return jsonify({"error": f"{type(err).__name__}: {err}"}), 500


PROVIDER_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VALID_MODALITIES = {"text", "image", "video"}

PROJECT_ROOT = Path(__file__).parent
CATALOG_PATH = PROJECT_ROOT / "models_catalog.py"
PROVIDERS_DIR = PROJECT_ROOT / "providers"
INIT_PATH = PROVIDERS_DIR / "__init__.py"


@app.post("/models_catelog/api/models/add")
def add_model():
    payload = request.get_json(silent=True) or {}
    provider_key = (payload.get("provider_key") or "").strip().lower()
    provider_label = (payload.get("provider_label") or "").strip()
    model_id = (payload.get("model_id") or "").strip()
    modality = (payload.get("modality") or "").strip().lower()
    model_name = (payload.get("model_name") or "").strip() or model_id

    if not PROVIDER_KEY_RE.match(provider_key):
        return jsonify({"error": "provider_key must match ^[a-z][a-z0-9_]*$"}), 400
    if not provider_label:
        return jsonify({"error": "provider_label is required"}), 400
    if not model_id:
        return jsonify({"error": "model_id is required"}), 400
    if modality not in VALID_MODALITIES:
        return jsonify({"error": f"modality must be one of {sorted(VALID_MODALITIES)}"}), 400

    is_new_provider = provider_key not in providers.REGISTRY
    target_provider_file = PROVIDERS_DIR / f"{provider_key}_provider.py"

    if is_new_provider and target_provider_file.exists():
        return jsonify({
            "error": (
                f"providers/{provider_key}_provider.py already exists on disk but is "
                "not registered. Delete it or pick a different provider_key."
            )
        }), 409

    # Step 1: DB upsert.
    try:
        import seed_db
        seed_db.upsert_one(
            provider_key=provider_key,
            provider_label=provider_label,
            model_id=model_id,
            model_name=model_name,
            modality=modality,
        )
    except Exception as err:  # noqa: BLE001 - surface DB error to UI
        return jsonify({
            "stage": "db",
            "error": f"{type(err).__name__}: {err}",
        }), 500

    # Step 2: Patch models_catalog.py.
    try:
        catalog_status = _catalog_writer.add_catalog_entry(
            CATALOG_PATH, provider_key, provider_label,
            model_id, model_name, modality,
        )
    except Exception as err:  # noqa: BLE001
        return jsonify({
            "stage": "catalog",
            "error": f"{type(err).__name__}: {err}",
            "note": "DB row was created but models_catalog.py could not be updated.",
        }), 500

    created_file = None
    init_status = "unchanged"

    # Steps 3 + 4: only when the provider is brand new.
    if is_new_provider:
        try:
            source = _code_gen.generate_provider_source(
                provider_key=provider_key,
                provider_label=provider_label,
                model_id=model_id,
                modality=modality,
                providers_dir=PROVIDERS_DIR,
            )
        except Exception as err:  # noqa: BLE001
            # Roll back the catalog edit so the file stays consistent.
            _safe_rollback(provider_key, model_id, modality)
            return jsonify({
                "stage": "codegen",
                "error": f"{type(err).__name__}: {err}",
                "note": "DB row remains; models_catalog.py edit rolled back.",
            }), 422

        try:
            target_provider_file.write_text(source, encoding="utf-8")
        except OSError as err:
            _safe_rollback(provider_key, model_id, modality)
            return jsonify({
                "stage": "write_file",
                "error": f"{type(err).__name__}: {err}",
            }), 500

        try:
            init_status = _catalog_writer.add_provider_to_init(
                INIT_PATH, provider_key,
            )
        except Exception as err:  # noqa: BLE001
            # Best-effort cleanup: remove the freshly-written provider file.
            try:
                target_provider_file.unlink()
            except OSError:
                pass
            _safe_rollback(provider_key, model_id, modality)
            return jsonify({
                "stage": "init",
                "error": f"{type(err).__name__}: {err}",
            }), 500

        created_file = f"providers/{provider_key}_provider.py"

    # Step 5: best-effort in-process refresh (debug reloader will redo this).
    _reload_modules()

    return jsonify({
        "ok": True,
        "provider_key": provider_key,
        "model_id": model_id,
        "modality": modality,
        "catalog": catalog_status,
        "init": init_status,
        "created_file": created_file,
    })


def _safe_rollback(provider_key, model_id, modality):
    try:
        _catalog_writer.rollback_catalog_entry(
            CATALOG_PATH, provider_key, model_id, modality,
        )
    except Exception:  # noqa: BLE001 - best effort
        pass


def _reload_modules():
    try:
        importlib.reload(models_catalog)
        importlib.reload(providers)
        # Re-bind globals that were imported by name.
        global CATALOG, resolve
        CATALOG = models_catalog.CATALOG
        resolve = models_catalog.resolve
    except Exception:  # noqa: BLE001 - debug reloader will fix it
        pass


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=3001, debug=True)
