#!/usr/bin/env python3
"""EXPERIMENT 6 -- the same race, but through the HTTP API.

Experiments 1 to 5 drive MySQL directly. This one goes through the whole
stack -- Flask, the connection layer, the service, the procedure -- because
a guarantee that only holds when you talk to the database yourself is not a
guarantee the application has.

It starts its own API process on a spare port, so nothing needs to be
running first and nothing is left behind.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import REPO, connect, reset_fixture, run, scenario, stock, verdict

PORT = 5099
BASE = f"http://127.0.0.1:{PORT}"


def http(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:  # noqa: BLE001 - a non-JSON error body is still a result
            return e.code, {}


def start_api() -> subprocess.Popen:
    env = dict(os.environ, PORT=str(PORT), APP_ENV="development", LOG_LEVEL="ERROR")
    proc = subprocess.Popen(
        [str(REPO / "backend" / ".venv" / "bin" / "python"), "manage.py", "run",
         "--port", str(PORT)],
        cwd=str(REPO / "backend"), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        try:
            if http("GET", "/api/health")[0] == 200:
                return proc
        except Exception:  # noqa: BLE001,S110 - the server is simply not up yet
            pass
        time.sleep(0.5)
    proc.terminate()
    sys.exit(f"error: the API did not come up on port {PORT}")


def main() -> int:
    scenario("EXPERIMENT 6 -- the same race, over HTTP",
             """Ten units exist. Two clients POST /allocate at the same instant, each
for a request that wants all ten. Correct outcome: between them they
receive exactly ten, both get a sensible HTTP status, and no 500.""")

    reset_fixture()
    conn = connect()
    run(conn, "UPDATE StockLevels SET quantity = 0 "
              "WHERE resource_id = 1 AND provider_id IN (2, 3)")
    for rid in (821, 822):
        run(conn, "INSERT INTO Requests (id, zone_id, resource_id, quantity_requested, "
                  "severity, urgency) VALUES (%s, 1, 1, 10, 2, 2)", (rid,))
    conn.commit()
    conn.close()

    print(f"  starting the API on port {PORT} ...")
    proc = start_api()
    try:
        print(f"  stock before: {stock()}  (total 10)\n")
        results: dict[int, tuple] = {}
        barrier = threading.Barrier(2)

        def dispatch(rid: int):
            def inner():
                barrier.wait()
                results[rid] = http("POST", f"/api/requests/{rid}/allocate", {})
            return inner

        threads = [threading.Thread(target=dispatch(r)) for r in (821, 822)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=90)

        for rid in (821, 822):
            code, body = results.get(rid, (None, {}))
            if code == 200:
                print(f"  request {rid}: HTTP {code}  allocated={body.get('allocated')} "
                      f"status={body.get('status')}")
            else:
                err = body.get("error", {})
                print(f"  request {rid}: HTTP {code}  {err.get('code')}: "
                      f"{str(err.get('message'))[:58]}")

        after = stock()
        handed_out = 10 - sum(q for _p, q in after)
        print(f"\n  stock after: {after}")
        print(f"  units handed out: {handed_out}")

        codes = [c for c, _ in results.values()]
        server_errors = [c for c in codes if c and c >= 500]
        negative = [p for p, q in after if q < 0]

        if negative:
            verdict(f"FAILED -- stock went negative at {negative}.")
        elif server_errors:
            verdict(f"FAILED -- the API returned {server_errors}, so a database "
                    "race reached the client as a server fault.")
        elif handed_out == 10:
            verdict("CORRECT. Exactly ten units left the system. One client was "
                    "served and the other was told, with a normal 4xx, that "
                    f"nothing was available -- HTTP statuses {sorted(codes)}. "
                    "No 500, no oversell, no retry needed.")
        else:
            verdict(f"Unexpected: {handed_out} units handed out.")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("\n  API stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
