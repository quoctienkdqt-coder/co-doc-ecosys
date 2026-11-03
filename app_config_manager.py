"""
Quản lý Cấu hình Tập trung & Bảo mật (Centralized Secure Config Manager)
Đảm bảo API Key được lưu an toàn trong %APPDATA%, không bao giờ bị lưu trong mã nguồn hoặc gói ZIP
"""
import os
import json

APP_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "XNK_eCoSys_SC")
SECURE_SETTINGS_FILE = os.path.join(APP_DATA_DIR, "settings.json")
LOCAL_TEMPLATE_SETTINGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

DEFAULT_SETTINGS = {
    "api_key": "",
    "api_source": "apiz",
    "api_base_url": "https://api.apiz.vn/v1",
    "model_name": "gemini-3.8-flash",
    "target_form": "EUR.1"
}


def get_secure_settings_path() -> str:
    if not os.path.exists(APP_DATA_DIR):
        os.makedirs(APP_DATA_DIR, exist_ok=True)
    return SECURE_SETTINGS_FILE


def load_secure_settings() -> dict:
    """
    Tải cấu hình an toàn:
    1. Ưu tiên đọc từ %APPDATA%/XNK_eCoSys_SC/settings.json (bảo mật người dùng)
    2. Đọc từ biến môi trường APIZ_API_KEY / GEMINI_API_KEY nếu có
    3. Fallback đọc từ file settings.json cục bộ
    """
    settings = DEFAULT_SETTINGS.copy()
    secure_path = get_secure_settings_path()

    loaded = False
    if os.path.exists(secure_path):
        try:
            with open(secure_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                settings.update(data)
                loaded = True
        except Exception:
            pass

    # Nếu chưa có trong AppData, đọc từ file cục bộ (chuyển tiếp một lần)
    if not loaded and os.path.exists(LOCAL_TEMPLATE_SETTINGS):
        try:
            with open(LOCAL_TEMPLATE_SETTINGS, "r", encoding="utf-8") as f:
                data = json.load(f)
                settings.update(data)
                # Tự động di chuyển vào AppData bảo mật
                save_secure_settings(settings)
        except Exception:
            pass

    # Đọc từ biến môi trường nếu key đang trống
    if not settings.get("api_key"):
        env_key = os.environ.get("APIZ_API_KEY") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if env_key:
            settings["api_key"] = env_key

    return settings


def save_secure_settings(settings: dict) -> bool:
    """
    Lưu cấu hình người dùng vào %APPDATA%, bảo vệ tuyệt đối không bao giờ lộ API Key ra file ZIP hoặc Git.
    """
    secure_path = get_secure_settings_path()
    try:
        with open(secure_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

        # File settings.json trong thư mục dự án CHỈ LƯU TEMPLATE TRỐNG API KEY
        sanitized_template = settings.copy()
        sanitized_template["api_key"] = ""
        try:
            with open(LOCAL_TEMPLATE_SETTINGS, "w", encoding="utf-8") as f:
                json.dump(sanitized_template, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        return True
    except Exception as e:
        print(f"Lỗi lưu cấu hình bảo mật: {e}")
        return False
