"""
FIM92 Tracking Web Viewer - Local HTTP Server
Serves viewer.html and proxies tracking_data.json from the build directory.

Usage:
    python server.py
    Then open http://localhost:8080 in your browser.
"""
import http.server
import os
import sys

PORT = 8080

# Resolve paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
BUILD_DIR = os.path.join(PROJECT_DIR, "build", "Release")

class TrackingHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SCRIPT_DIR, **kwargs)

    def do_GET(self):
        # Strip query string for path matching
        path = self.path.split('?')[0]

        if path == '/' or path == '/index.html':
            self.path = '/viewer.html'
            return super().do_GET()

        if path == '/tracking_data.json':
            json_path = os.path.join(BUILD_DIR, "tracking_data.json")
            if os.path.exists(json_path):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'no-cache, no-store')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                with open(json_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"error":"tracking_data.json not found"}')
            return

        return super().do_GET()

    def log_message(self, format, *args):
        # Suppress noisy polling logs
        if 'tracking_data.json' not in str(args):
            super().log_message(format, *args)


if __name__ == '__main__':
    print(f"FIM92 Tracking Web Viewer")
    print(f"  Web dir:   {SCRIPT_DIR}")
    print(f"  Build dir: {BUILD_DIR}")
    print(f"  URL:       http://localhost:{PORT}")
    print(f"  Press Ctrl+C to stop.\n")

    with http.server.HTTPServer(('', PORT), TrackingHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
