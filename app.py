import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "tracker.db"
DEFAULT_THRESHOLD = 2


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS equipment (
            name        TEXT PRIMARY KEY,
            quantity    INTEGER NOT NULL CHECK (quantity >= 0),
            threshold   INTEGER NOT NULL DEFAULT 2
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL REFERENCES equipment(name),
            action      TEXT NOT NULL CHECK (action IN ('issue', 'return')),
            quantity    INTEGER NOT NULL CHECK (quantity > 0),
            person      TEXT,
            ts          TEXT NOT NULL
        );
        """
    )
    conn.commit()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cmd_add(conn, args):
    try:
        conn.execute(
            "INSERT INTO equipment (name, quantity, threshold) VALUES (?, ?, ?)",
            (args.name, args.quantity, args.threshold),
        )
        conn.commit()
        print(f"Added '{args.name}': qty={args.quantity}, threshold={args.threshold}")
    except sqlite3.IntegrityError:
        print(f"Error: '{args.name}' already exists. Use 'restock' to add quantity.", file=sys.stderr)
        sys.exit(1)


def cmd_restock(conn, args):
    cur = conn.execute("UPDATE equipment SET quantity = quantity + ? WHERE name = ?", (args.quantity, args.name))
    if cur.rowcount == 0:
        print(f"Error: '{args.name}' not found.", file=sys.stderr)
        sys.exit(1)
    conn.commit()
    print(f"Restocked '{args.name}' by {args.quantity}")


def cmd_issue(conn, args):
    row = conn.execute("SELECT quantity, threshold FROM equipment WHERE name = ?", (args.name,)).fetchone()
    if row is None:
        print(f"Error: '{args.name}' not found.", file=sys.stderr)
        sys.exit(1)
    if row["quantity"] < args.quantity:
        print(f"Error: insufficient stock for '{args.name}' (have {row['quantity']}, need {args.quantity}).", file=sys.stderr)
        sys.exit(1)

    new_qty = row["quantity"] - args.quantity
    conn.execute("UPDATE equipment SET quantity = ? WHERE name = ?", (new_qty, args.name))
    conn.execute(
        "INSERT INTO transactions (name, action, quantity, person, ts) VALUES (?, 'issue', ?, ?, ?)",
        (args.name, args.quantity, args.person, now_iso()),
    )
    conn.commit()
    print(f"Issued {args.quantity}x '{args.name}' to {args.person or 'unspecified'}. Remaining: {new_qty}")

    if new_qty < row["threshold"]:
        print(f"WARNING: '{args.name}' stock ({new_qty}) is below threshold ({row['threshold']}).")


def cmd_return(conn, args):
    row = conn.execute("SELECT quantity FROM equipment WHERE name = ?", (args.name,)).fetchone()
    if row is None:
        print(f"Error: '{args.name}' not found.", file=sys.stderr)
        sys.exit(1)

    new_qty = row["quantity"] + args.quantity
    conn.execute("UPDATE equipment SET quantity = ? WHERE name = ?", (new_qty, args.name))
    conn.execute(
        "INSERT INTO transactions (name, action, quantity, person, ts) VALUES (?, 'return', ?, ?, ?)",
        (args.name, args.quantity, args.person, now_iso()),
    )
    conn.commit()
    print(f"Returned {args.quantity}x '{args.name}' from {args.person or 'unspecified'}. Available: {new_qty}")


def cmd_list(conn, args):
    rows = conn.execute("SELECT name, quantity, threshold FROM equipment ORDER BY name").fetchall()
    if not rows:
        print("No equipment registered.")
        return

    name_w = max(len("Equipment"), *(len(r["name"]) for r in rows))
    print(f"{'Equipment':<{name_w}}  {'Qty':>5}  {'Threshold':>9}  Status")
    print("-" * (name_w + 28))
    for r in rows:
        status = "LOW STOCK" if r["quantity"] < r["threshold"] else "OK"
        print(f"{r['name']:<{name_w}}  {r['quantity']:>5}  {r['threshold']:>9}  {status}")


def cmd_history(conn, args):
    q = "SELECT ts, name, action, quantity, person FROM transactions"
    params = ()
    if args.name:
        q += " WHERE name = ?"
        params = (args.name,)
    q += " ORDER BY id DESC LIMIT ?"
    params = params + (args.limit,)

    rows = conn.execute(q, params).fetchall()
    if not rows:
        print("No transactions recorded.")
        return
    for r in rows:
        who = f" ({r['person']})" if r["person"] else ""
        print(f"[{r['ts']}] {r['action']:<6} {r['quantity']:>3}x {r['name']}{who}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tracker", description="Sports Equipment Tracker")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("add", help="Register new equipment")
    a.add_argument("name")
    a.add_argument("--quantity", type=int, required=True)
    a.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    a.set_defaults(func=cmd_add)

    r = sub.add_parser("restock", help="Increase quantity of existing equipment")
    r.add_argument("name")
    r.add_argument("--quantity", type=int, required=True)
    r.set_defaults(func=cmd_restock)

    i = sub.add_parser("issue", help="Issue equipment to a borrower")
    i.add_argument("name")
    i.add_argument("--quantity", type=int, default=1)
    i.add_argument("--person", default=None)
    i.set_defaults(func=cmd_issue)

    rt = sub.add_parser("return", help="Record a return")
    rt.add_argument("name")
    rt.add_argument("--quantity", type=int, default=1)
    rt.add_argument("--person", default=None)
    rt.set_defaults(func=cmd_return)

    l = sub.add_parser("list", help="Show current availability")
    l.set_defaults(func=cmd_list)

    h = sub.add_parser("history", help="Show transaction history")
    h.add_argument("name", nargs="?", default=None)
    h.add_argument("--limit", type=int, default=20)
    h.set_defaults(func=cmd_history)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    conn = get_conn()
    init_db(conn)
    try:
        args.func(conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
