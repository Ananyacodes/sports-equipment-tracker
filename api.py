#!/usr/bin/env python3
"""
Sports Equipment Tracker - API service
Flask REST API over PostgreSQL. Owns all writes to the database;
the UI container talks to this over HTTP and never touches Postgres directly.
"""
import os
import time
from datetime import datetime, timezone

import pg8000.native
from flask import Flask, jsonify, request

app = Flask(__name__)

PGHOST = os.environ.get("PGHOST", "localhost")
PGPORT = int(os.environ.get("PGPORT", "5432"))
PGUSER = os.environ.get("PGUSER", "equip")
PGPASSWORD = os.environ.get("PGPASSWORD", "equippass")
PGDATABASE = os.environ.get("PGDATABASE", "equipment")
DEFAULT_THRESHOLD = 2


def get_conn():
    return pg8000.native.Connection(
        user=PGUSER, password=PGPASSWORD, host=PGHOST, port=PGPORT, database=PGDATABASE
    )


def wait_for_db(retries=20, delay=1.5):
    for attempt in range(retries):
        try:
            conn = get_conn()
            conn.close()
            return
        except Exception as e:
            print(f"Waiting for database... ({attempt + 1}/{retries}): {e}", flush=True)
            time.sleep(delay)
    raise RuntimeError("Database never became available")


def init_db():
    conn = get_conn()
    conn.run(
        """
        CREATE TABLE IF NOT EXISTS equipment (
            name        TEXT PRIMARY KEY,
            quantity    INTEGER NOT NULL CHECK (quantity >= 0),
            threshold   INTEGER NOT NULL DEFAULT 2
        )
        """
    )
    conn.run(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id          SERIAL PRIMARY KEY,
            name        TEXT NOT NULL REFERENCES equipment(name),
            action      TEXT NOT NULL CHECK (action IN ('issue', 'return')),
            quantity    INTEGER NOT NULL CHECK (quantity > 0),
            person      TEXT,
            ts          TIMESTAMPTZ NOT NULL
        )
        """
    )
    conn.close()


def now():
    return datetime.now(timezone.utc)


@app.route("/equipment", methods=["GET"])
def list_equipment():
    conn = get_conn()
    rows = conn.run("SELECT name, quantity, threshold FROM equipment ORDER BY name")
    conn.close()
    result = [
        {"name": r[0], "quantity": r[1], "threshold": r[2], "low_stock": r[1] < r[2]}
        for r in rows
    ]
    return jsonify(result)


@app.route("/equipment", methods=["POST"])
def add_equipment():
    data = request.get_json(force=True)
    name = data["name"]
    quantity = int(data["quantity"])
    threshold = int(data.get("threshold", DEFAULT_THRESHOLD))

    conn = get_conn()
    try:
        conn.run(
            "INSERT INTO equipment (name, quantity, threshold) VALUES (:name, :quantity, :threshold)",
            name=name, quantity=quantity, threshold=threshold,
        )
    except Exception:
        conn.close()
        return jsonify({"error": f"'{name}' already exists"}), 409
    conn.close()
    return jsonify({"message": f"Added '{name}'"}), 201


@app.route("/equipment/<name>/restock", methods=["POST"])
def restock(name):
    data = request.get_json(force=True)
    quantity = int(data["quantity"])
    conn = get_conn()
    conn.run(
        "UPDATE equipment SET quantity = quantity + :q WHERE name = :name",
        q=quantity, name=name,
    )
    conn.close()
    return jsonify({"message": f"Restocked '{name}' by {quantity}"})


@app.route("/equipment/<name>/issue", methods=["POST"])
def issue(name):
    data = request.get_json(force=True)
    quantity = int(data.get("quantity", 1))
    person = data.get("person")

    conn = get_conn()
    row = conn.run("SELECT quantity, threshold FROM equipment WHERE name = :name", name=name)
    if not row:
        conn.close()
        return jsonify({"error": f"'{name}' not found"}), 404
    qty, threshold = row[0]
    if qty < quantity:
        conn.close()
        return jsonify({"error": f"insufficient stock (have {qty}, need {quantity})"}), 400

    new_qty = qty - quantity
    conn.run("UPDATE equipment SET quantity = :q WHERE name = :name", q=new_qty, name=name)
    conn.run(
        "INSERT INTO transactions (name, action, quantity, person, ts) VALUES (:name, 'issue', :q, :person, :ts)",
        name=name, q=quantity, person=person, ts=now(),
    )
    conn.close()

    resp = {"message": f"Issued {quantity}x '{name}'", "remaining": new_qty}
    if new_qty < threshold:
        resp["warning"] = f"'{name}' stock ({new_qty}) is below threshold ({threshold})"
    return jsonify(resp)


@app.route("/equipment/<name>/return", methods=["POST"])
def return_item(name):
    data = request.get_json(force=True)
    quantity = int(data.get("quantity", 1))
    person = data.get("person")

    conn = get_conn()
    row = conn.run("SELECT quantity FROM equipment WHERE name = :name", name=name)
    if not row:
        conn.close()
        return jsonify({"error": f"'{name}' not found"}), 404
    new_qty = row[0][0] + quantity
    conn.run("UPDATE equipment SET quantity = :q WHERE name = :name", q=new_qty, name=name)
    conn.run(
        "INSERT INTO transactions (name, action, quantity, person, ts) VALUES (:name, 'return', :q, :person, :ts)",
        name=name, q=quantity, person=person, ts=now(),
    )
    conn.close()
    return jsonify({"message": f"Returned {quantity}x '{name}'", "available": new_qty})


@app.route("/history", methods=["GET"])
def history():
    name = request.args.get("name")
    limit = int(request.args.get("limit", 20))
    conn = get_conn()
    if name:
        rows = conn.run(
            "SELECT ts, name, action, quantity, person FROM transactions "
            "WHERE name = :name ORDER BY id DESC LIMIT :limit",
            name=name, limit=limit,
        )
    else:
        rows = conn.run(
            "SELECT ts, name, action, quantity, person FROM transactions ORDER BY id DESC LIMIT :limit",
            limit=limit,
        )
    conn.close()
    result = [
        {"ts": r[0].isoformat(), "name": r[1], "action": r[2], "quantity": r[3], "person": r[4]}
        for r in rows
    ]
    return jsonify(result)


if __name__ == "__main__":
    wait_for_db()
    init_db()
    app.run(host="0.0.0.0", port=5000)
