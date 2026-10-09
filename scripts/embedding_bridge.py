"""
Local OpenAI-compatible embeddings server for RAG. Runs the model on CPU with
fastembed, so no third-party key or per-call cost is involved.

    pip install fastembed
    python scripts/embedding_bridge.py            # listens on 127.0.0.1:8789

Point the app at it with EMBEDDING_BASE_URL=http://127.0.0.1:8789/v1.
Env: EMBEDDING_MODEL_NAME, PORT, EMBEDDING_API_KEY (optional bearer token).
"""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from fastembed import TextEmbedding

MODEL = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
KEY = os.getenv("EMBEDDING_API_KEY", "")
model = TextEmbedding(MODEL)


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/v1/embeddings":
            return self._send(404, {"error": "not found"})
        if KEY and self.headers.get("Authorization") != f"Bearer {KEY}":
            return self._send(401, {"error": "unauthorized"})
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            texts = [req["input"]] if isinstance(req["input"], str) else list(req["input"])
        except (ValueError, KeyError, TypeError):
            return self._send(400, {"error": "expected JSON with 'input'"})
        # Small internal batches keep ONNX peak memory low on a shared VPS.
        vectors = model.embed(texts, batch_size=4)
        data = [{"object": "embedding", "index": i, "embedding": v.tolist()} for i, v in enumerate(vectors)]
        self._send(200, {"object": "list", "model": MODEL, "data": data})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8789"))
    print(f"Embedding bridge ready on 127.0.0.1:{port} ({MODEL})", flush=True)
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
