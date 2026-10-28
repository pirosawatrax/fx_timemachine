import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fxtm.providers import http_get
from fxtm.ticks import ProviderError


class _Handler(BaseHTTPRequestHandler):
    hits = {}

    def log_message(self, *args):
        pass

    def do_GET(self):
        n = self.hits[self.path] = self.hits.get(self.path, 0) + 1
        if self.path == "/ok":
            code, body = 200, b"data"
        elif self.path == "/quiet":
            code, body = 200, b""  # an hour without ticks: a real, valid answer
        elif self.path == "/missing":
            code, body = 404, b"no"
        elif self.path == "/challenge":
            code, body = 202, b""  # bot protection: NOT an empty hour
        elif self.path == "/busy":
            code, body = 503, b"busy"
        elif self.path == "/flaky":
            code, body = (503, b"busy") if n <= 2 else (200, b"data")
        else:
            code, body = 403, b"no"
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class HttpGetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def get(self, path, retries=3):
        return http_get(self.base + path, timeout=5, retries=retries, sleep=lambda s: None)

    def test_ok_and_quiet_hour(self):
        self.assertEqual(self.get("/ok"), b"data")
        self.assertEqual(self.get("/quiet"), b"")

    def test_404_means_no_such_file(self):
        self.assertIsNone(self.get("/missing"))

    def test_202_challenge_is_an_error_not_an_empty_hour(self):
        with self.assertRaises(ProviderError) as ctx:
            self.get("/challenge")
        self.assertIn("bot-protection", str(ctx.exception))
        self.assertEqual(_Handler.hits["/challenge"], 3)  # retried

    def test_server_trouble_and_refusal(self):
        with self.assertRaises(ProviderError) as ctx:
            self.get("/busy")
        self.assertIn("503", str(ctx.exception))
        with self.assertRaises(ProviderError) as ctx:
            self.get("/other")
        self.assertIn("refused", str(ctx.exception))

    def test_retry_recovers_from_a_flaky_server(self):
        self.assertEqual(self.get("/flaky"), b"data")

    def test_connection_failure_message_has_a_hint(self):
        with self.assertRaises(ProviderError) as ctx:
            http_get("http://127.0.0.1:1/x", timeout=1, retries=2, sleep=lambda s: None)
        self.assertIn("own data files", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
