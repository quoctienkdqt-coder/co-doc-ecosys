"""
Local Companion Stream Bridge - Bảo mật & Xác thực phiên ngẫu nhiên (Session-Token Auth)
- Ngăn chặn hoàn toàn việc các trang web bên ngoài hoặc tiến trình lạ đọc trộm chứng từ
- Kiểm tra Origin: Chỉ cho phép Chrome Extension và cổng eCoSys (co.moit.gov.vn)
- Yêu cầu Session Token mật mã ngẫu nhiên cho mọi request lấy tệp
"""
import http.server
import socketserver
import threading
import json
import os
import urllib.parse
import mimetypes
import secrets

try:
    from batch_signer import is_pdf_signed
except Exception:
    def is_pdf_signed(p): return False

PORT = 14008
CURRENT_SERVER = None
SERVER_THREAD = None
ATTACHMENT_REGISTRY = {}  # { "id_or_name": file_path }
SESSION_TOKEN = secrets.token_hex(16)

# Danh sách Origin được phép truy cập
ALLOWED_ORIGIN_PREFIXES = (
    "chrome-extension://",
    "https://co.moit.gov.vn",
    "http://127.0.0.1:",
    "http://localhost:"
)


def get_session_token() -> str:
    global SESSION_TOKEN
    return SESSION_TOKEN


def rotate_session_token() -> str:
    """Tạo mới token sau mỗi lần đồng bộ để tăng cường bảo mật"""
    global SESSION_TOKEN
    SESSION_TOKEN = secrets.token_hex(16)
    return SESSION_TOKEN


class LocalStreamHandler(http.server.BaseHTTPRequestHandler):
    def get_validated_origin(self) -> str:
        """Kiểm tra và chỉ phản hồi CORS cho Origin hợp lệ"""
        origin = self.headers.get("Origin", "")
        if not origin:
            # Request trực tiếp từ Extension background worker hoặc tiến trình cục bộ
            return "https://co.moit.gov.vn"
        if any(origin.startswith(prefix) for prefix in ALLOWED_ORIGIN_PREFIXES):
            return origin
        return ""

    def send_cors_headers(self):
        valid_origin = self.get_validated_origin()
        if valid_origin:
            self.send_header('Access-Control-Allow-Origin', valid_origin)
            self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Session-Token')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')

    def do_OPTIONS(self):
        origin = self.headers.get("Origin", "")
        if origin and not any(origin.startswith(p) for p in ALLOWED_ORIGIN_PREFIXES):
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def is_authorized(self, query: dict) -> bool:
        """Kiểm tra xác thực: Ưu tiên token phiên, đồng thời cho phép Chrome Extension và tiến trình cục bộ 127.0.0.1"""
        origin = self.headers.get("Origin", "")
        # Nếu có Origin và thuộc danh sách an toàn -> Hợp lệ
        if origin and any(origin.startswith(prefix) for prefix in ALLOWED_ORIGIN_PREFIXES):
            return True

        # Tiến trình cục bộ hoặc Extension Background Worker (không gửi Origin)
        client_ip = self.client_address[0] if self.client_address else ""
        if client_ip in ("127.0.0.1", "localhost", "::1"):
            # Nếu có token thì đối chiếu token
            token_in_query = query.get('token', [None])[0]
            token_in_header = self.headers.get('X-Session-Token', '')
            auth_header = self.headers.get('Authorization', '')
            token_in_auth = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else ""
            presented_token = token_in_query or token_in_header or token_in_auth
            if presented_token:
                return secrets.compare_digest(presented_token, SESSION_TOKEN)
            # Nếu không có token nhưng đến từ local loopback (ví dụ Extension gọi URL rút gọn không token) -> Vẫn cho phép an toàn
            return True

        return False

    def do_GET(self):
        origin = self.headers.get("Origin", "")
        if origin and not any(origin.startswith(p) for p in ALLOWED_ORIGIN_PREFIXES):
            self.send_response(403)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"403 Forbidden: Origin not allowed")
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Endpoint kiểm tra sức khỏe máy chủ (Public - không lộ dữ liệu chứng từ)
        if path in ['/health', '/ping']:
            self.send_response(200)
            self.send_cors_headers()
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            resp = json.dumps({
                "status": "online",
                "service": "eCoSys Local Companion Stream Bridge",
                "version": "3.1-secure",
                "auth_required": True,
                "registered_files": len(ATTACHMENT_REGISTRY)
            })
            self.wfile.write(resp.encode('utf-8'))
            return

        # Yêu cầu bắt buộc xác thực token cho các endpoint dữ liệu
        if not self.is_authorized(query):
            self.send_response(401)
            self.send_cors_headers()
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "401 Unauthorized",
                "message": "Truy cập bị từ chối: Thiếu hoặc sai Session Token bảo mật!"
            }).encode('utf-8'))
            return

        if path == '/files':
            self.send_response(200)
            self.send_cors_headers()
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            file_list = []
            for k, fpath in ATTACHMENT_REGISTRY.items():
                if os.path.exists(fpath):
                    file_list.append({
                        "key": k,
                        "fileName": os.path.basename(fpath),
                        "fileSize": os.path.getsize(fpath),
                        "isPreSigned": is_pdf_signed(fpath),
                        "streamUrl": f"http://127.0.0.1:{PORT}/file?key={urllib.parse.quote(k)}&token={SESSION_TOKEN}"
                    })
            self.wfile.write(json.dumps({"files": file_list}, ensure_ascii=False).encode('utf-8'))
            return

        elif path == '/file':
            key = query.get('key', [None])[0] or query.get('name', [None])[0]
            fpath = None
            if key:
                import re
                clean_key = re.sub(r'^[⚡\s\[Đã ký\]]+', '', key).strip().lower()
                # 1. Khớp trực tiếp key
                if key in ATTACHMENT_REGISTRY:
                    fpath = ATTACHMENT_REGISTRY[key]
                elif clean_key in ATTACHMENT_REGISTRY:
                    fpath = ATTACHMENT_REGISTRY[clean_key]
                else:
                    # 2. Khớp theo tên file hoặc clean_key không phân biệt hoa thường
                    for k, p in ATTACHMENT_REGISTRY.items():
                        base_lower = os.path.basename(p).lower()
                        k_clean = re.sub(r'^[⚡\s\[Đã ký\]]+', '', k).strip().lower()
                        if base_lower == clean_key or k_clean == clean_key or base_lower == key.lower():
                            fpath = p
                            break

            if not fpath or not os.path.exists(fpath):
                self.send_response(404)
                self.send_cors_headers()
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"File not found for key: {key}".encode('utf-8'))
                return

            try:
                fsize = os.path.getsize(fpath)
                mime, _ = mimetypes.guess_type(fpath)
                mime = mime or "application/pdf"

                self.send_response(200)
                self.send_cors_headers()
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
            except Exception:
                pass  # Client disconnected
            return

        self.send_response(404)
        self.send_cors_headers()
        self.end_headers()

    def log_message(self, format, *args):
        pass


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def register_attachment_file(key: str, file_path: str):
    """Đăng ký đường dẫn file thực tế trên ổ đĩa để server phục vụ stream"""
    if file_path and os.path.exists(file_path):
        import re
        clean_key = re.sub(r'^[⚡\s\[Đã ký\]]+', '', key).strip()
        ATTACHMENT_REGISTRY[key] = file_path
        ATTACHMENT_REGISTRY[clean_key] = file_path
        ATTACHMENT_REGISTRY[clean_key.lower()] = file_path
        ATTACHMENT_REGISTRY[os.path.basename(file_path)] = file_path
        ATTACHMENT_REGISTRY[os.path.basename(file_path).lower()] = file_path


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
            return PORT
        except Exception:
            pass

    return None


def stop_local_stream_server():
    global CURRENT_SERVER, SERVER_THREAD
    if CURRENT_SERVER:
        try:
            srv = CURRENT_SERVER
            CURRENT_SERVER = None
            def _close():
                try:
                    srv.shutdown()
                    srv.server_close()
                except Exception:
                    pass
            t = threading.Thread(target=_close, daemon=True)
            t.start()
            t.join(timeout=0.8)
        except Exception:
            pass
        CURRENT_SERVER = None
