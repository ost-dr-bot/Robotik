#!/usr/bin/env python3
## @file app.py
#  @brief Web GUI backend for the ESP32 UDP link.
#
#  @details
#  Built entirely on top of core/udp_core.py -- this file only wires
#  that core to a browser:
#  @code
#      ESP32 --UDP--> UdpClient --callback--> SSE broadcast --> browser (Chart.js)
#      browser --fetch POST--> Flask routes --> UdpClient.send_*() --UDP--> ESP32
#  @endcode

from __future__ import annotations

import argparse
import json
import queue
import sys
import threading
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

# Make the shared core importable regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
from udp_core import UdpClient, TelemetryBatch, load_config  # noqa: E402

## The Flask application instance.
app = Flask(__name__)

## The single UdpClient instance driving this GUI; assigned in main().
client: UdpClient  # set in main()

# -- SSE fan-out -----------------------------------------------------------
# Every connected browser tab gets its own Queue. The telemetry callback
# (called from the UDP receiver thread) pushes a JSON-ready dict onto every
# subscriber queue. Each SSE request thread just drains its own queue.

## @brief List of per-tab subscriber queues used to fan telemetry out over SSE.
#  @details Guarded by #_subscribers_lock.
_subscribers: list[queue.Queue] = []
## Lock protecting #_subscribers.
_subscribers_lock = threading.Lock()


def _subscribe() -> queue.Queue:
    """!
    @brief Register a new SSE subscriber (called once per browser tab
           connecting to /events).
    @return A fresh bounded Queue that will receive broadcast payloads.
    """
    q: queue.Queue = queue.Queue(maxsize=100)
    with _subscribers_lock:
        _subscribers.append(q)
    return q


def _unsubscribe(q: queue.Queue) -> None:
    """!
    @brief Remove a subscriber queue, e.g. when its SSE connection closes.
    @param q The queue previously returned by _subscribe().
    """
    with _subscribers_lock:
        if q in _subscribers:
            _subscribers.remove(q)


def _broadcast(payload: dict) -> None:
    """!
    @brief Push a JSON-ready payload onto every currently subscribed queue.
    @details If a subscriber's queue is full (a slow/backgrounded tab), the
             oldest queued item is dropped in favor of the newest one, so
             the UI always shows current data instead of falling further
             and further behind.
    @param payload The telemetry payload to broadcast (see _on_telemetry()).
    """
    with _subscribers_lock:
        subs = list(_subscribers)
    for q in subs:
        try:
            q.put_nowait(payload)
        except queue.Full:
            # Slow consumer (e.g. backgrounded tab): drop oldest, keep latest.
            try:
                q.get_nowait()
                q.put_nowait(payload)
            except queue.Empty:
                pass


def _on_telemetry(batch: TelemetryBatch) -> None:
    """!
    @brief UdpClient telemetry callback: converts a TelemetryBatch into
           a JSON-serializable dict and broadcasts it to all SSE subscribers.
    @details Called from the UDP receiver thread -- keep this fast and
             non-blocking.
    @param batch The just-received TelemetryBatch.
    """
    payload = {
        "seq": batch.seq,
        "safety_samples": [
            {"t_us": s.timestamp_us, "safety_level": s.safety_level}
            for s in batch.safety_samples
        ],
        "control_samples": [
            {
                "t_us": c.timestamp_us,
                "enc_A_pos": c.enc_A_pos,
                "enc_B_pos": c.enc_B_pos,
            }
            for c in batch.control_samples
        ],
        "steps": [
            {
                "step_type": st.step_type,
                "step_id": st.step_id,
                "duration_ms": st.duration_ms,
            }
            for st in batch.steps
        ],
        "stats": {
            "total_packets": client.stats.total_packets,
            "total_samples": client.stats.total_samples,
            "dropped_packets": client.stats.dropped_packets,
        },
    }
    _broadcast(payload)


# -- routes ------------------------------------------------------------

@app.route("/")
def index():
    """!
    @brief Render the dashboard page.
    @return The rendered index.html, with the (possibly hostname-and-resolved-IP)
            ESP32 address and port passed in for display.
    """
    display_host = client.esp32_host
    if client.dest and client.dest[0] != client.esp32_host:
        display_host = f"{client.esp32_host} ({client.dest[0]})"
    return render_template("index.html", esp32_host=display_host, esp32_port=client.dest[1])


@app.route("/events")
def events():
    """!
    @brief SSE endpoint: streams telemetry batches to the browser, one
           `data:` line (JSON-encoded) per batch.
    @return A streaming Flask Response with mimetype `text/event-stream`.
    """

    def stream():
        """! @brief Generator that yields SSE-formatted telemetry payloads
                    for a single subscriber, until its connection closes. """
        q = _subscribe()
        try:
            while True:
                payload = q.get()  # blocks until next batch
                yield f"data: {json.dumps(payload)}\n\n"
        finally:
            _unsubscribe(q)

    return Response(stream(), mimetype="text/event-stream")


@app.route("/api/command/safety", methods=["POST"])
def cmd_safety():
    """!
    @brief POST /api/command/safety - trigger a safety event.
    @details Expects JSON body `{"event": <int>}`.
    @return JSON `{"ok": true, "sent": {"event": <int>}}`.
    """
    body = request.get_json(force=True)
    event = int(body["event"])
    client.send_safety(event)
    return jsonify({"ok": True, "sent": {"event": event}})


@app.route("/api/command/wait", methods=["POST"])
def cmd_wait():
    """!
    @brief POST /api/command/wait - queue a wait sequencer step.
    @details Expects JSON body `{"duration_ms": <int>}`.
    @return JSON `{"ok": true, "sent": {"duration_ms": <int>}}`.
    """
    body = request.get_json(force=True)
    duration_ms = int(body["duration_ms"])
    client.send_wait(duration_ms)
    return jsonify({"ok": True, "sent": {"duration_ms": duration_ms}})


@app.route("/api/command/remove_step", methods=["POST"])
def cmd_remove_step():
    """!
    @brief POST /api/command/remove_step - remove a queued sequencer step.
    @details Expects JSON body `{"step_id": <int>}`.
    @return JSON `{"ok": true, "sent": {"step_id": <int>}}`.
    """
    body = request.get_json(force=True)
    step_id = int(body["step_id"])
    client.send_remove_step(step_id)
    return jsonify({"ok": True, "sent": {"step_id": step_id}})


def main():
    """!
    @brief Entry point: parse CLI args (falling back to esp32_config.json),
           start the UdpClient, and run the Flask dev server until
           interrupted.
    """
    global client

    parser = argparse.ArgumentParser(description="Web GUI for the ESP32 UDP telemetry link")
    parser.add_argument(
        "esp32_host",
        nargs="?",
        default=None,
        help="IP address or hostname of the ESP32. If omitted, read from esp32_config.json.",
    )
    parser.add_argument(
        "--port", type=int, default=None, help="ESP32 UDP port (default: 3333, or config file)"
    )
    parser.add_argument("--http-port", type=int, default=8081, help="Web GUI HTTP port (default: 8080)")
    parser.add_argument("--config", default=None, help="Path to esp32_config.json (default: auto-search)")
    args = parser.parse_args()

    config = load_config(args.config)
    esp32_host = args.esp32_host or config.get("esp32_host")
    esp32_port = args.port if args.port is not None else config.get("esp32_port", 3333)

    if not esp32_host:
        parser.error(
            "No ESP32 host given and none found in a config file. Either pass it as an "
            "argument, or create esp32_config.json (see esp32_config.json.example)."
        )

    client = UdpClient(esp32_host, port=esp32_port)
    client.on_telemetry(_on_telemetry)
    client.start()
    print(f"Connected to ESP32 at {esp32_host}:{esp32_port} (resolved: {client.dest})")
    print(f"Open http://localhost:{args.http_port} in a browser")

    try:
        app.run(host="127.0.0.1", port=args.http_port, threaded=True)
    finally:
        client.stop()


if __name__ == "__main__":
    main()
