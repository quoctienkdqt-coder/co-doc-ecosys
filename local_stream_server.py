import http.server
import socketserver
import threading
import json
import os
import urllib.parse
import mimetypes

PORT = 14008
CURRENT_SERVER = None
SERVER_THREAD = None
ATTACHMENT_REGISTRY = {}  # { "id_or_name": file_path }

class LocalStreamHandler(http.server.BaseHTTPRequestHandler):
    def end_headers(self):
        # Allow CORS from eCoSys and Chrome Extension
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ['/health', '/ping']:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            resp = json.dumps({
                "status": "online",
                "service": "eCoSys Local Companion Stream Bridge",
                "version": "3.0",
                "registered_files": len(ATTACHMENT_REGISTRY)
            })
            self.wfile.write(resp.encode('utf-8'))
            return

        elif path == '/files':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            file_list = []
            for k, fpath in ATTACHMENT_REGISTRY.items():
                if os.path.exists(fpath):
                    file_list.append({
                        "key": k,
                        "fileName": os.path.basename(fpath),
                        "fileSize": os.path.getsize(fpath),
                        "streamUrl": f"http://127.0.0.1:{PORT}/file?key={urllib.parse.quote(k)}"
                    })
            self.wfile.write(json.dumps({"files": file_list}, ensure_ascii=False).encode('utf-8'))
            return

        elif path == '/file':
            key = query.get('key', [None])[0] or query.get('name', [None])[0]
            fpath = None
            if key and key in ATTACHMENT_REGISTRY:
                fpath = ATTACHMENT_REGISTRY[key]
            elif key:
                # Tìm theo tên file
                for k, p in ATTACHMENT_REGISTRY.items():
                    if os.path.basename(p).lower() == key.lower() or k.lower() == key.lower():
                        fpath = p
                        break

            if not fpath or not os.path.exists(fpath):
                self.send_response(404)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"File not found for key: {key}".encode('utf-8'))
                return

            try:
                fsize = os.path.getsize(fpath)
                mime, _ = mimetypes.guess_type(fpath)
                mime = mime or "application/pdf"

                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(fsize))
                self.send_header('Content-Disposition', f'inline; filename="{os.path.basename(fpath)}"')
                self.end_headers()

                # Stream file in 64KB chunks
                with open(fpath, 'rb') as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            except Exception as e:
                pass  # Client disconnected
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        # Mute logging to console to keep output clean
        pass

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

def register_attachment_file(key: str, file_path: str):
    """Đăng ký đường dẫn file thực tế trên ổ đĩa để server phục vụ stream"""
    if file_path and os.path.exists(file_path):
        ATTACHMENT_REGISTRY[key] = file_path
        ATTACHMENT_REGISTRY[os.path.basename(file_path)] = file_path

def clear_attachment_registry():
    ATTACHMENT_REGISTRY.clear()

def start_local_stream_server():
    global CURRENT_SERVER, SERVER_THREAD, PORT
    if CURRENT_SERVER is not None:
        return PORT

    for p in [14008, 14009, 14010]:
        try:
            PORT = p
            server = ReusableTCPServer(('127.0.0.1', PORT), LocalStreamHandler)
            CURRENT_SERVER = server
            SERVER_THREAD = threading.Thread(target=server.serve_forever, daemon=True)
            SERVER_THREAD.start()
            print(f"[LocalStreamServer] Started Local Companion Stream Bridge at http://127.0.0.1:{PORT}")
            return PORT
        except Exception as e:
            print(f"[LocalStreamServer] Port {p} busy ({e}), trying next...")

    print("[LocalStreamServer] Unable to bind to any port for LocalStreamServer!")
    return None

def stop_local_stream_server():
    global CURRENT_SERVER
    if CURRENT_SERVER:
        try:
            CURRENT_SERVER.shutdown()
            CURRENT_SERVER.server_close()
        except Exception:
            pass
        CURRENT_SERVER = None
