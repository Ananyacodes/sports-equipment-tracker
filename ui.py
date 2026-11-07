#!/usr/bin/env python3
"""
Sports Equipment Tracker - UI service
Thin Flask frontend. Holds no database connection of its own —
everything goes through the API container over HTTP.
"""
import os

import requests
from flask import Flask, redirect, render_template_string, request, url_for

app = Flask(__name__)
API_URL = os.environ.get("API_URL", "http://localhost:5000")

PAGE = """
<!doctype html>
<title>Sports Equipment Tracker</title>
<style>
  body { font-family: sans-serif; max-width: 800px; margin: 2rem auto; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 2rem; }
  th, td { border: 1px solid #ccc; padding: 0.5rem; text-align: left; }
  .low { color: #c0392b; font-weight: bold; }
  form { display: inline-block; margin: 0 1rem 1rem 0; padding: 1rem; border: 1px solid #ddd; }
  .flash { padding: 0.5rem; margin-bottom: 1rem; }
  .ok { background: #e8f8ef; }
  .err { background: #fdecea; }
</style>
<h1>Sports Equipment Tracker</h1>
{% if message %}<div class="flash {{ 'err' if error else 'ok' }}">{{ message }}</div>{% endif %}

<table>
  <tr><th>Equipment</th><th>Qty</th><th>Threshold</th><th>Status</th></tr>
  {% for e in equipment %}
  <tr class="{{ 'low' if e.low_stock else '' }}">
    <td>{{ e.name }}</td><td>{{ e.quantity }}</td><td>{{ e.threshold }}</td>
    <td>{{ 'LOW STOCK' if e.low_stock else 'OK' }}</td>
  </tr>
  {% endfor %}
</table>

<form method="post" action="/add">
  <h3>Add Equipment</h3>
  Name: <input name="name" required><br>
  Quantity: <input name="quantity" type="number" required><br>
  Threshold: <input name="threshold" type="number" value="2"><br>
  <button type="submit">Add</button>
</form>

<form method="post" action="/issue">
  <h3>Issue</h3>
  Name: <input name="name" required><br>
  Quantity: <input name="quantity" type="number" value="1"><br>
  Person: <input name="person"><br>
  <button type="submit">Issue</button>
</form>

<form method="post" action="/return">
  <h3>Return</h3>
  Name: <input name="name" required><br>
  Quantity: <input name="quantity" type="number" value="1"><br>
  Person: <input name="person"><br>
  <button type="submit">Return</button>
</form>
"""


@app.route("/")
def index():
    r = requests.get(f"{API_URL}/equipment")
    equipment = r.json() if r.ok else []
    return render_template_string(
        PAGE,
        equipment=equipment,
        message=request.args.get("message"),
        error=request.args.get("error"),
    )


@app.route("/add", methods=["POST"])
def add():
    payload = {
        "name": request.form["name"],
        "quantity": request.form["quantity"],
        "threshold": request.form.get("threshold", 2),
    }
    r = requests.post(f"{API_URL}/equipment", json=payload)
    return _redirect_with_result(r)


@app.route("/issue", methods=["POST"])
def issue():
    name = request.form["name"]
    payload = {"quantity": request.form.get("quantity", 1), "person": request.form.get("person")}
    r = requests.post(f"{API_URL}/equipment/{name}/issue", json=payload)
    return _redirect_with_result(r)


@app.route("/return", methods=["POST"])
def return_item():
    name = request.form["name"]
    payload = {"quantity": request.form.get("quantity", 1), "person": request.form.get("person")}
    r = requests.post(f"{API_URL}/equipment/{name}/return", json=payload)
    return _redirect_with_result(r)


def _redirect_with_result(r):
    data = r.json()
    if r.ok:
        msg = data.get("message", "Done")
        if "warning" in data:
            msg += " \u2014 " + data["warning"]
        return redirect(url_for("index", message=msg))
    return redirect(url_for("index", message=data.get("error", "Request failed"), error=1))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
