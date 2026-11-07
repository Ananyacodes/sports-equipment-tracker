#!/usr/bin/env bash
# Loads demo data into a running Sports Equipment Tracker UI (http://localhost:8080).
# Uses -4 to avoid IPv6 "Connection reset by peer" issues some Podman setups hit on `localhost`.
set -e

BASE="http://127.0.0.1:8080"

echo "Adding equipment..."
curl -4 -s -X POST "$BASE/add" -d name="football gloves"   -d quantity=5 -d threshold=2  > /dev/null
curl -4 -s -X POST "$BASE/add" -d name="cricket bat"        -d quantity=8 -d threshold=3  > /dev/null
curl -4 -s -X POST "$BASE/add" -d name="basketball"         -d quantity=6 -d threshold=2  > /dev/null
curl -4 -s -X POST "$BASE/add" -d name="badminton racket"   -d quantity=4 -d threshold=2  > /dev/null
curl -4 -s -X POST "$BASE/add" -d name="hockey stick"       -d quantity=3 -d threshold=4  > /dev/null

echo "Issuing equipment (some will cross the low-stock threshold)..."
curl -4 -s -X POST "$BASE/issue" -d name="cricket bat"      -d quantity=6 -d person=Rahul  > /dev/null
curl -4 -s -X POST "$BASE/issue" -d name="basketball"       -d quantity=2 -d person=Priya  > /dev/null
curl -4 -s -X POST "$BASE/issue" -d name="badminton racket" -d quantity=3 -d person=Rahul  > /dev/null
curl -4 -s -X POST "$BASE/issue" -d name="football gloves"  -d quantity=4 -d person=Sneha  > /dev/null

echo "Recording a return..."
curl -4 -s -X POST "$BASE/return" -d name="cricket bat"     -d quantity=1 -d person=Rahul  > /dev/null
curl -4 -s -X POST "$BASE/return" -d name="football gloves" -d quantity=3 -d person=Sneha  > /dev/null

echo "Done. Open $BASE to view the table."
