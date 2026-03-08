#!/usr/bin/env python3
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR.parent / "results"
ANNOTATIONS_PATH = BASE_DIR / "annotations.json"
HOST = "127.0.0.1"
PORT = 8765

HTML = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Study Review</title>
  <style>
    :root {
      --bg: #f6f4ef;
      --card: #fffdf8;
      --ink: #222;
      --muted: #666;
      --accent: #0b6e4f;
      --border: #ddd4c7;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: radial-gradient(circle at 10% 10%, #fff, var(--bg));
      color: var(--ink);
    }
    .wrap {
      max-width: 1200px;
      margin: 24px auto;
      padding: 0 16px;
    }
    .toolbar, .panel {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
      margin-bottom: 12px;
    }
    .toolbar {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }
    button {
      border: 1px solid #bbb;
      background: #fff;
      color: #222;
      border-radius: 6px;
      padding: 7px 10px;
      cursor: pointer;
    }
    button.primary {
      border-color: var(--accent);
      color: #fff;
      background: var(--accent);
    }
    button:disabled { opacity: 0.5; cursor: default; }
    .meta {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      font-size: 14px;
    }
    .label { color: var(--muted); }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      margin: 0;
      background: #f3f3f3;
      border: 1px solid #e1e1e1;
      border-radius: 8px;
      padding: 10px;
      max-height: 420px;
      overflow: auto;
      font-family: Menlo, Monaco, monospace;
      font-size: 13px;
    }
    textarea {
      width: 100%;
      min-height: 140px;
      resize: vertical;
      border: 1px solid #c9c9c9;
      border-radius: 8px;
      padding: 10px;
      font-family: ui-sans-serif, -apple-system, sans-serif;
    }
    .status { color: var(--muted); font-size: 13px; }
    @media (max-width: 860px) {
      .meta { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"toolbar\">
      <button id=\"prevBtn\">Prev</button>
      <button id=\"nextBtn\">Next</button>
      <button id=\"saveBtn\" class=\"primary\">Save Annotation</button>
      <button id=\"saveNextBtn\">Save + Next</button>
      <span id=\"position\" class=\"status\"></span>
      <span id=\"status\" class=\"status\"></span>
    </div>

    <div class=\"panel meta\">
      <div><span class=\"label\">Result file:</span> <span id=\"resultFile\"></span></div>
      <div><span class=\"label\">Model:</span> <span id=\"model\"></span></div>
      <div><span class=\"label\">Timestamp:</span> <span id=\"timestamp\"></span></div>
      <div><span class=\"label\">Entry ID:</span> <span id=\"entryId\"></span></div>
    </div>

    <div class=\"panel\">
      <div class=\"label\">Study prompt</div>
      <pre id=\"prompt\"></pre>
    </div>

    <div class=\"panel\">
      <div class=\"label\">Generated code / response</div>
      <pre id=\"generated\"></pre>
    </div>

    <div class=\"panel\">
      <div class=\"label\">Audit output</div>
      <pre id=\"audit\"></pre>
    </div>

    <div class=\"panel\">
      <div class=\"label\">Your annotation</div>
      <textarea id=\"comment\" placeholder=\"Add review notes for this generation...\"></textarea>
    </div>
  </div>

  <script>
    let entries = [];
    let annotations = {};
    let idx = 0;

    const byId = (id) => document.getElementById(id);
    const statusEl = byId('status');

    function setStatus(msg) {
      statusEl.textContent = msg || '';
    }

    function escapeMaybe(value) {
      return value == null ? '' : String(value);
    }

    function render() {
      if (!entries.length) {
        setStatus('No entries found in /results.');
        byId('position').textContent = '0 / 0';
        return;
      }
      const e = entries[idx];
      byId('position').textContent = `${idx + 1} / ${entries.length}`;
      byId('resultFile').textContent = e.result_file;
      byId('model').textContent = e.model;
      byId('timestamp').textContent = e.timestamp;
      byId('entryId').textContent = e.entry_id;
      byId('prompt').textContent = escapeMaybe(e.prompt);
      byId('generated').textContent = escapeMaybe(e.generated);
      byId('audit').textContent = escapeMaybe(e.audit);
      byId('comment').value = (annotations[e.entry_id] && annotations[e.entry_id].comment) || '';
      byId('prevBtn').disabled = idx <= 0;
      byId('nextBtn').disabled = idx >= entries.length - 1;
    }

    async function loadData() {
      const [entriesRes, annRes] = await Promise.all([
        fetch('/api/entries'),
        fetch('/api/annotations')
      ]);
      entries = (await entriesRes.json()).entries || [];
      annotations = (await annRes.json()).annotations || {};
      render();
    }

    async function saveAnnotation() {
      if (!entries.length) return;
      const e = entries[idx];
      const payload = {
        entry_id: e.entry_id,
        result_file: e.result_file,
        model: e.model,
        timestamp: e.timestamp,
        comment: byId('comment').value
      };
      const res = await fetch('/api/annotations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        setStatus('Save failed.');
        return false;
      }
      const data = await res.json();
      annotations = data.annotations || annotations;
      setStatus('Saved.');
      return true;
    }

    byId('prevBtn').addEventListener('click', () => {
      if (idx > 0) idx -= 1;
      render();
    });

    byId('nextBtn').addEventListener('click', () => {
      if (idx < entries.length - 1) idx += 1;
      render();
    });

    byId('saveBtn').addEventListener('click', async () => {
      await saveAnnotation();
    });

    byId('saveNextBtn').addEventListener('click', async () => {
      const ok = await saveAnnotation();
      if (ok && idx < entries.length - 1) {
        idx += 1;
        render();
      }
    });

    loadData().catch((e) => {
      console.error(e);
      setStatus('Failed to load data.');
    });
  </script>
</body>
</html>
"""


def load_entries():
    entries = []
    if not RESULTS_DIR.exists():
        return entries

    for result_path in sorted(RESULTS_DIR.glob("*.json")):
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        generated = data.get("generated", {})
        audits = data.get("audits", {})
        models = data.get("models") or sorted(generated.keys())

        for model in models:
            if model not in generated:
                continue
            entry_id = f"{result_path.name}::{model}"
            entries.append(
                {
                    "entry_id": entry_id,
                    "result_file": result_path.name,
                    "timestamp": data.get("timestamp", ""),
                    "prompt": data.get("prompt", ""),
                    "audit_prompt": data.get("audit_prompt", ""),
                    "model": model,
                    "generated": generated.get(model, ""),
                    "audit": audits.get(model, ""),
                }
            )

    return entries


def load_annotations():
    if not ANNOTATIONS_PATH.exists():
        return {}
    try:
        data = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_annotations(annotations):
    ANNOTATIONS_PATH.write_text(json.dumps(annotations, indent=2), encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(HTML)
            return

        if parsed.path == "/api/entries":
            entries = load_entries()
            self._send_json({"entries": entries})
            return

        if parsed.path == "/api/annotations":
            self._send_json({"annotations": load_annotations()})
            return

        self._send_json({"error": "Not found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/annotations":
            self._send_json({"error": "Not found"}, status=404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._send_json({"error": "Invalid JSON"}, status=400)
            return

        entry_id = payload.get("entry_id")
        if not entry_id:
            self._send_json({"error": "entry_id is required"}, status=400)
            return

        annotations = load_annotations()
        annotations[entry_id] = {
            "result_file": payload.get("result_file", ""),
            "model": payload.get("model", ""),
            "timestamp": payload.get("timestamp", ""),
            "comment": payload.get("comment", ""),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        save_annotations(annotations)
        self._send_json({"ok": True, "annotations": annotations})

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    print(f"Review app: http://{HOST}:{PORT}")
    print(f"Reading results from: {RESULTS_DIR}")
    print(f"Saving annotations to: {ANNOTATIONS_PATH}")
    server = HTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
