"""Seed Postgres with the providers + models catalog.

Reads connection settings from .env (POSTGRES_HOST, POSTGRES_PORT,
POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_SCHEMA) and
inserts everything in models_catalog.CATALOG into two tables:

    <schema>.providers (id, key, label)
    <schema>.models    (id, provider_id, model_id, name, upstream_model,
                        modality, params, input_inr_per_1m,
                        output_inr_per_1m, cost_inr, is_free)

Idempotent — re-running upserts on (provider key) and
(provider_id, modality, model_id).

If POSTGRES_SCHEMA is empty, falls back to "public".
"""

import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
from dotenv import load_dotenv

from models_catalog import CATALOG

load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)


def get_conn():
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def get_schema():
    schema = (os.environ.get("POSTGRES_SCHEMA") or "").strip()
    return schema or "public"


def create_schema_and_tables(cur, schema):
    cur.execute(
        sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema))
    )
    cur.execute(
        sql.SQL("""
            CREATE TABLE IF NOT EXISTS {}.providers (
                id     SERIAL PRIMARY KEY,
                key    TEXT NOT NULL UNIQUE,
                label  TEXT NOT NULL
            )
        """).format(sql.Identifier(schema))
    )
    cur.execute(
        sql.SQL("""
            CREATE TABLE IF NOT EXISTS {schema}.models (
                id                SERIAL PRIMARY KEY,
                provider_id       INTEGER NOT NULL
                    REFERENCES {schema}.providers(id) ON DELETE CASCADE,
                model_id          TEXT NOT NULL,
                name              TEXT NOT NULL,
                upstream_model    TEXT,
                modality          TEXT NOT NULL,
                params            JSONB,
                input_inr_per_1m  NUMERIC(14, 4),
                output_inr_per_1m NUMERIC(14, 4),
                cost_inr          NUMERIC(14, 7),
                is_free           BOOLEAN NOT NULL DEFAULT FALSE,
                UNIQUE (provider_id, modality, model_id)
            )
        """).format(schema=sql.Identifier(schema))
    )


def upsert_providers(cur, schema):
    rows = [(key, data["label"]) for key, data in CATALOG.items()]
    execute_values(
        cur,
        sql.SQL("""
            INSERT INTO {}.providers (key, label) VALUES %s
            ON CONFLICT (key) DO UPDATE SET label = EXCLUDED.label
        """).format(sql.Identifier(schema)).as_string(cur),
        rows,
    )
    cur.execute(
        sql.SQL("SELECT key, id FROM {}.providers").format(sql.Identifier(schema))
    )
    return dict(cur.fetchall())


def upsert_models(cur, schema, provider_ids):
    rows = []
    for provider_key, data in CATALOG.items():
        provider_id = provider_ids[provider_key]
        for modality, entries in data["modalities"].items():
            for entry in entries:
                params = entry.get("params")
                rows.append((
                    provider_id,
                    entry["id"],
                    entry["name"],
                    entry.get("model"),
                    modality,
                    json.dumps(params) if params else None,
                    entry.get("input_inr_per_1m"),
                    entry.get("output_inr_per_1m"),
                    entry.get("cost_inr"),
                    bool(entry.get("free", False)),
                ))

    execute_values(
        cur,
        sql.SQL("""
            INSERT INTO {}.models (
                provider_id, model_id, name, upstream_model, modality,
                params, input_inr_per_1m, output_inr_per_1m, cost_inr, is_free
            ) VALUES %s
            ON CONFLICT (provider_id, modality, model_id) DO UPDATE SET
                name              = EXCLUDED.name,
                upstream_model    = EXCLUDED.upstream_model,
                params            = EXCLUDED.params,
                input_inr_per_1m  = EXCLUDED.input_inr_per_1m,
                output_inr_per_1m = EXCLUDED.output_inr_per_1m,
                cost_inr          = EXCLUDED.cost_inr,
                is_free           = EXCLUDED.is_free
        """).format(sql.Identifier(schema)).as_string(cur),
        rows,
    )
    return len(rows)


def upsert_one(provider_key, provider_label, model_id, model_name, modality,
               upstream_model=None, params=None,
               input_inr_per_1m=None, output_inr_per_1m=None,
               cost_inr=None, is_free=False):
    """Upsert a single provider + model row. Used by the runtime add-model
    endpoint so the UI can add models without re-running the full seed.

    Returns (provider_db_id, model_db_id).
    """
    schema = get_schema()
    with get_conn() as conn:
        with conn.cursor() as cur:
            create_schema_and_tables(cur, schema)

            cur.execute(
                sql.SQL("""
                    INSERT INTO {}.providers (key, label) VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET label = EXCLUDED.label
                    RETURNING id
                """).format(sql.Identifier(schema)),
                (provider_key, provider_label),
            )
            provider_id = cur.fetchone()[0]

            cur.execute(
                sql.SQL("""
                    INSERT INTO {}.models (
                        provider_id, model_id, name, upstream_model, modality,
                        params, input_inr_per_1m, output_inr_per_1m, cost_inr, is_free
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (provider_id, modality, model_id) DO UPDATE SET
                        name              = EXCLUDED.name,
                        upstream_model    = EXCLUDED.upstream_model,
                        params            = EXCLUDED.params,
                        input_inr_per_1m  = EXCLUDED.input_inr_per_1m,
                        output_inr_per_1m = EXCLUDED.output_inr_per_1m,
                        cost_inr          = EXCLUDED.cost_inr,
                        is_free           = EXCLUDED.is_free
                    RETURNING id
                """).format(sql.Identifier(schema)),
                (
                    provider_id, model_id, model_name, upstream_model, modality,
                    json.dumps(params) if params else None,
                    input_inr_per_1m, output_inr_per_1m, cost_inr, bool(is_free),
                ),
            )
            model_db_id = cur.fetchone()[0]
        conn.commit()
    return provider_id, model_db_id


def main():
    schema = get_schema()
    print(f"Using schema: {schema}")
    with get_conn() as conn:
        with conn.cursor() as cur:
            create_schema_and_tables(cur, schema)
            provider_ids = upsert_providers(cur, schema)
            n_models = upsert_models(cur, schema, provider_ids)
        conn.commit()
    print(f"Seeded {len(provider_ids)} providers and {n_models} models.")


if __name__ == "__main__":
    try:
        main()
    except KeyError as err:
        print(f"Missing required env var: {err}", file=sys.stderr)
        sys.exit(1)
