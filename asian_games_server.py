#!/usr/bin/env python3
"""
Asian Games 2026 Live Schedule & Results Proxy Server
Provides direct REST endpoints and serves the schedule dashboard.
"""

import http.server
import socketserver
import urllib.request
import urllib.parse
import zlib
import json
import os
import sys

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, "asian_games_data.json")
BACKEND_BASE = "https://back.results.asiangames2026.org"

def fetch_upstream(path):
    url = f"{BACKEND_BASE}{path}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read()
        chars = raw.decode("utf-8")
        byte_arr = bytes([ord(c) for c in chars])
        decomp = zlib.decompress(byte_arr)
        return json.loads(decomp)

class AsianGamesHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/" or parsed.path == "/index.html":
            self.path = "/asian_games_schedule.html"
            return super().do_GET()

        if parsed.path == "/api/schedule":
            date = qs.get("date", ["2026-09-23"])[0]
            cached_data = self.get_cached_day(date)
            if cached_data is not None:
                self.send_json_response(cached_data)
                return
            try:
                data = fetch_upstream(f"/s/AG2026/en/ALL/schedule/day/{date}")
                self.send_json_response(data)
            except Exception as e:
                self.send_json_response({"error": str(e)}, status=502)
            return

        if parsed.path == "/api/medals":
            org = qs.get("org", ["IND"])[0]
            try:
                data = fetch_upstream(f"/s/AG2026/en/ALL/medals/org/{org}")
                self.send_json_response(data)
            except Exception as e:
                cached_data = self.get_cached_medals()
                if cached_data is not None:
                    self.send_json_response(cached_data)
                else:
                    self.send_json_response({"error": str(e)}, status=502)
        if parsed.path == "/api/medals/standings":
            try:
                data = fetch_upstream("/s/AG2026/en/ALL/medals/standings")
                self.send_json_response(data)
            except Exception as e:
                try:
                    if os.path.exists(CACHE_FILE):
                        with open(CACHE_FILE, "r") as f:
                            cached = json.load(f)
                        self.send_json_response(cached.get("medal_standings", []))
                        return
                except Exception:
                    pass
                self.send_json_response({"error": str(e)}, status=502)
            return

        if parsed.path == "/api/bundle":
            try:
                if os.path.exists(CACHE_FILE):
                    with open(CACHE_FILE, "r") as f:
                        bundle = json.load(f)
                    self.send_json_response(bundle)
                else:
                    self.send_json_response({"error": "Cache file not found"}, status=404)
            except Exception as e:
                self.send_json_response({"error": str(e)}, status=500)
            return

        return super().do_GET()

    def get_cached_day(self, date):
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r") as f:
                    cached = json.load(f)
                return cached.get("schedule", {}).get(date)
        except Exception:
            return None
        return None

    def get_cached_medals(self):
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r") as f:
                    cached = json.load(f)
                return cached.get("medals", [])
        except Exception:
            return None
        return None

    def send_json_response(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    port = PORT
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    # Allow port reuse
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), AsianGamesHandler) as httpd:
        print(f"================================================================")
        print(f" Asian Games 2026 Schedule & Results Dashboard")
        print(f" URL: http://localhost:{port}")
        print(f" API Endpoint: http://localhost:{port}/api/schedule?date=2026-09-23")
        print(f" Medals Endpoint: http://localhost:{port}/api/medals?org=IND")
        print(f"================================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
