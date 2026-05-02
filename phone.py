#!/usr/bin/env python3
"""
Webhook receiver for the phone detector.

Listens for POSTed JSON events from detect_phone.py, then runs a CLI
program once per event. The event JSON is passed to the CLI as:
  - the first argument (a single JSON string), AND
  - via stdin (same JSON string)
so your CLI can read whichever is easier.

Usage:
    python3 phone_event_receiver.py --port 9000 --cmd /path/to/your-cli
    python3 phone_event_receiver.py --port 9000 --cmd "your-cli --flag"

The detector on the Pi then runs:
    python3 detect_phone.py --camera 0 \
        --webhook http://<this-machine-tailscale-ip>:9000/event
"""

import argparse
import json
import logging
import shlex
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def make_handler(cmd_tokens, log):
    class Handler(BaseHTTPRequestHandler):
        # silence the default per-request access log; we log our own
        def log_message(self, fmt, *args):
            return

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b""
            try:
                event = json.loads(raw.decode("utf-8"))
            except Exception as e:
                log.warning("bad JSON from %s: %s", self.client_address[0], e)
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error":"bad json"}')
                return

            event_str = json.dumps(event)
            log.info("event: %s", event_str)

            # Run the CLI: pass JSON as final arg AND on stdin.
            try:
                result = subprocess.run(
                    cmd_tokens + [event_str],
                    input=event_str,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    log.warning("cli rc=%d stderr=%s",
                                result.returncode, result.stderr.strip())
                elif result.stdout.strip():
                    log.info("cli out: %s", result.stdout.strip())
            except FileNotFoundError:
                log.error("CLI not found: %s", cmd_tokens[0])
            except subprocess.TimeoutExpired:
                log.warning("CLI timed out")
            except Exception as e:
                log.exception("CLI run failed: %s", e)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def do_GET(self):
            # health check
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"phone-event-receiver alive\n")

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0",
                    help="Bind address. 0.0.0.0 listens on all interfaces "
                         "(including Tailscale). Default: 0.0.0.0")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--cmd", required=True,
                    help="CLI command to run per event. Quoted if it has args.")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log = logging.getLogger("receiver")

    cmd_tokens = shlex.split(args.cmd)
    log.info("CLI on each event: %s", cmd_tokens)
    log.info("listening on http://%s:%d/event", args.host, args.port)

    server = ThreadingHTTPServer((args.host, args.port),
                                 make_handler(cmd_tokens, log))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()

