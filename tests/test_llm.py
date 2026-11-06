"""Tests for the OpenAI-compatible tidy-up call, against a local stub server."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from screenshot_to_text.llm import LlmError, tidy_text


class StubEndpoint(BaseHTTPRequestHandler):
    last_model = ""
    last_auth = ""
    last_path = ""

    def do_POST(self):  # noqa: N802
        StubEndpoint.last_path = self.path
        StubEndpoint.last_auth = self.headers.get("Authorization", "")
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if not self.path.endswith("/chat/completions"):
            self.send_response(404)
            self.end_headers()
            return
        reply = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": "CLEANED: " + body["messages"][-1]["content"][:20]
                        }
                    }
                ]
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(reply)
        StubEndpoint.last_model = body["model"]

    def log_message(self, *args):  # silence test server logs
        pass


@pytest.fixture(scope="module")
def stub_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubEndpoint)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    server.shutdown()


def test_sends_messages_and_parses_reply(stub_url):
    result = tidy_text("hello world this is OCR", api_base=stub_url, model="test-model")
    assert result.startswith("CLEANED: hello world this")
    assert StubEndpoint.last_model == "test-model"
    assert StubEndpoint.last_path.endswith("/v1/chat/completions")
    assert StubEndpoint.last_auth == ""  # no key sent, Ollama-style


def test_blank_text_skips_the_call(stub_url):
    model_before = StubEndpoint.last_model
    assert tidy_text("   ", api_base=stub_url) == "   "
    assert StubEndpoint.last_model == model_before  # no request was made


def test_unreachable_endpoint_raises_friendly_error():
    with pytest.raises(LlmError, match="Is the server running"):
        tidy_text("text", api_base="http://127.0.0.1:1/v1", timeout=1)
