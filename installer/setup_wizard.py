"""
TRÌNH CÀI ĐẶT PHẦN MỀM: XUẤT NHẬP KHẨU & THỦY SẢN TOÀN DIỆN v3.0
(eCoSys C/O & Đối Chiếu SC Cảng Cá)
Thiết kế bằng PyQt6 - Giao diện Fluent hiện đại, tự giải nén, tạo Desktop Shortcut chuẩn xác.
"""

import os
import sys
import zipfile
import subprocess
import shutil

# Ensure standard outputs handle UTF-8
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QCheckBox, QProgressBar,
    QFileDialog, QMessageBox, QFrame, QWidget
)
from PyQt6.QtGui import QIcon, QFont, QPixmap, QColor


def get_bundle_zip_path():
    if getattr(sys, 'frozen', False):
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    zip_path = os.path.join(base_dir, "app_bundle.zip")
    if not os.path.exists(zip_path):
        zip_path = os.path.join(os.path.dirname(base_dir), "app_bundle.zip")
    return zip_path


APP_EXE_NAME = "XNK_eCoSys_SC.exe"
SHORTCUT_NAMES = ["XNK & Thủy Sản Toàn Diện.lnk", "XNK - eCoSys & Thuy San SC.lnk"]
# Dữ liệu người dùng trong thư mục cài đặt: giữ nguyên khi cập nhật
KEEP_ON_UPDATE = {"cache", "KetQua_DoiChieu", "backups_update", "settings.json"}
CREATE_NO_WINDOW = 0x08000000


def get_bundle_version():
    """Số phiên bản của gói cài đặt (đọc version.json đóng kèm bộ cài)."""
    import json
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    for p in (os.path.join(base_dir, "version.json"), os.path.join(os.path.dirname(base_dir), "version.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f).get("version", "")
        except Exception:
            continue
    return ""


def parse_cli_args():
    """--update (chế độ cập nhật tự động) ; --target <thư mục đang cài>"""
    args = sys.argv[1:]
    opts = {"update": "--update" in args, "target": "", "no_shortcuts": "--no-shortcuts" in args}
    if "--target" in args:
        i = args.index("--target")
        if i + 1 < len(args):
            opts["target"] = args[i + 1].strip().strip('"')
    return opts


def _shortcut_target(lnk_path):
    try:
        import win32com.client
        ws = win32com.client.Dispatch("WScript.Shell")
        return ws.CreateShortcut(lnk_path).TargetPath or ""
    except Exception:
        return ""


def find_existing_install_dir():
    """Tìm thư mục đã cài bản cũ qua shortcut ngoài Desktop / Start Menu (người dùng có thể đã cài ở chỗ khác)."""
    for d in get_real_desktop_paths() + get_real_start_menu_paths():
        for name in SHORTCUT_NAMES:
            lnk = os.path.join(d, name)
            if os.path.exists(lnk):
                tgt = _shortcut_target(lnk)
                if tgt and os.path.basename(tgt).lower() == APP_EXE_NAME.lower() and os.path.exists(tgt):
                    return os.path.dirname(tgt)
    return ""


def _app_pids(install_dir):
    """PID các tiến trình XNK_eCoSys_SC.exe chạy từ ĐÚNG thư mục install_dir (không đụng bản ở thư mục khác)."""
    target = os.path.normcase(os.path.abspath(os.path.join(install_dir, APP_EXE_NAME)))
    ps = ("Get-Process -Name 'XNK_eCoSys_SC' -ErrorAction SilentlyContinue | "
          "ForEach-Object { \"$($_.Id)|$($_.Path)\" }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                             creationflags=CREATE_NO_WINDOW, timeout=20).stdout
    except Exception:
        return []
    pids = []
    for line in out.splitlines():
        if "|" in line:
            pid, path = line.split("|", 1)
            if path.strip() and os.path.normcase(os.path.abspath(path.strip())) == target:
                pids.append(pid.strip())
    return pids


def is_app_running(install_dir):
    return bool(_app_pids(install_dir))


def close_running_app(install_dir, timeout=20):
    """Chờ phần mềm (ở thư mục cài đặt này) tự đóng — trình cập nhật đóng app sau khi mở bộ cài;
    quá hạn thì buộc đóng đúng các tiến trình đó."""
    import time
    t0 = time.time()
    while is_app_running(install_dir) and time.time() - t0 < timeout:
        time.sleep(0.7)
    pids = _app_pids(install_dir)
    for pid in pids:
        subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True, creationflags=CREATE_NO_WINDOW)
    if pids:
        time.sleep(1.5)
    return not is_app_running(install_dir)


def move_old_files_to_backup(install_dir, log=print):
    """
    Chuyển file của bản cũ sang backups_update/truoc_cai_dat_<thời gian>/ để bản mới ghi đè sạch sẽ
    (tránh sót file .py cũ do kiểu cập nhật mã nguồn trước đây làm lẫn phiên bản). Giữ nguyên dữ liệu người dùng.
    Chỉ thực hiện khi thư mục đúng là thư mục cài phần mềm (có XNK_eCoSys_SC.exe).
    """
    import time
    if not os.path.exists(os.path.join(install_dir, APP_EXE_NAME)):
        return ""
    backup_root = os.path.join(install_dir, "backups_update")
    os.makedirs(backup_root, exist_ok=True)
    # Chỉ giữ 1 bản sao lưu trước-cài-đặt gần nhất để tiết kiệm dung lượng
    for old in os.listdir(backup_root):
        if old.startswith("truoc_cai_dat_"):
            shutil.rmtree(os.path.join(backup_root, old), ignore_errors=True)
    dest = os.path.join(backup_root, "truoc_cai_dat_" + time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(dest, exist_ok=True)
    for name in os.listdir(install_dir):
        if name in KEEP_ON_UPDATE:
            continue
        src = os.path.join(install_dir, name)
        for attempt in range(6):  # file có thể còn bị khóa vài giây sau khi app đóng
            try:
                shutil.move(src, os.path.join(dest, name))
                break
            except Exception as e:
                if attempt == 5:
                    log(f"Không chuyển được {name}: {e}")
                time.sleep(1)
    return dest


def get_real_desktop_paths():
    """
    Trả về danh sách các thư mục Desktop khả dĩ trên máy Windows (bao gồm cả OneDrive nếu có).
    """
    paths = []
    # 1. Windows API CSIDL_DESKTOPDIRECTORY
    try:
        from win32com.shell import shell, shellcon
        d = shell.SHGetFolderPath(0, shellcon.CSIDL_DESKTOPDIRECTORY, None, 0)
        if d and os.path.isdir(d) and d not in paths:
            paths.append(d)
    except Exception:
        pass

    user_profile = os.environ.get('USERPROFILE', os.path.expanduser('~'))

    # 2. OneDrive Desktop
    one_drive = os.path.join(user_profile, 'OneDrive', 'Desktop')
    if os.path.isdir(one_drive) and one_drive not in paths:
        paths.append(one_drive)

    # 3. Standard User Desktop
    std_desktop = os.path.join(user_profile, 'Desktop')
    if os.path.isdir(std_desktop) and std_desktop not in paths:
        paths.append(std_desktop)

    return paths


def get_real_start_menu_paths():
    """
    Trả về danh sách thư mục Start Menu Programs.
    """
    paths = []
    try:
        from win32com.shell import shell, shellcon
        p = shell.SHGetFolderPath(0, shellcon.CSIDL_PROGRAMS, None, 0)
        if p and os.path.isdir(p) and p not in paths:
            paths.append(p)
    except Exception:
        pass

    app_data = os.environ.get('APPDATA', '')
    if app_data:
        std_p = os.path.join(app_data, 'Microsoft', 'Windows', 'Start Menu', 'Programs')
        if os.path.isdir(std_p) and std_p not in paths:
            paths.append(std_p)

    return paths


def create_windows_shortcut(target_exe, shortcut_path, icon_path=None, description=""):
    """
    Tạo shortcut (.lnk) trên Windows với hỗ trợ Unicode đầy đủ (tiếng Việt có dấu).
    Áp dụng 3 tầng phòng thủ:
    1. IShellLinkW qua pythoncom (Native Windows API, hỗ trợ tiếng Việt tuyệt đối).
    2. PowerShell script qua tệp tạm UTF-8 có BOM.
    3. WScript.Shell với tên không dấu fallback.
    """
    target_dir = os.path.dirname(shortcut_path)
    if not os.path.exists(target_dir):
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception:
            pass

    # 1. Thử dùng IShellLinkW native
    try:
        import pythoncom
        from win32com.shell import shell

        shortcut = pythoncom.CoCreateInstance(
            shell.CLSID_ShellLink,
            None,
            pythoncom.CLSCTX_INPROC_SERVER,
            shell.IID_IShellLink
        )
        shortcut.SetPath(target_exe)
        shortcut.SetWorkingDirectory(os.path.dirname(target_exe))
        if description:
            shortcut.SetDescription(description)
        if icon_path and os.path.exists(icon_path):
            shortcut.SetIconLocation(icon_path, 0)

        persist_file = shortcut.QueryInterface(pythoncom.IID_IPersistFile)
        persist_file.Save(shortcut_path, 0)

        if os.path.exists(shortcut_path):
            return True
    except Exception as e:
        print(f"[Warning] IShellLinkW failed: {e}")

    # 2. Fallback: PowerShell Script với UTF-8 BOM
    try:
        import tempfile
        ps_script = (
            f'$ws = New-Object -COM WScript.Shell\n'
            f'$sc = $ws.CreateShortcut("{shortcut_path}")\n'
            f'$sc.TargetPath = "{target_exe}"\n'
            f'$sc.WorkingDirectory = "{os.path.dirname(target_exe)}"\n'
        )
        if icon_path and os.path.exists(icon_path):
            ps_script += f'$sc.IconLocation = "{icon_path}"\n'
        if description:
            ps_script += f'$sc.Description = "{description}"\n'
        ps_script += '$sc.Save()\n'

        with tempfile.NamedTemporaryFile('w', suffix='.ps1', encoding='utf-8-sig', delete=False) as tf:
            tf.write(ps_script)
            tf_path = tf.name

        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", tf_path],
            check=False,
            creationflags=0x08000000
        )
        try:
            os.remove(tf_path)
        except Exception:
            pass

        if os.path.exists(shortcut_path):
            return True
    except Exception as e:
        print(f"[Warning] PowerShell fallback failed: {e}")

    # 3. Fallback: WScript.Shell với tên không dấu
    try:
        import win32com.client
        ascii_name = "XNK - eCoSys & Thuy San SC.lnk"
        ascii_path = os.path.join(target_dir, ascii_name)
        ws = win32com.client.Dispatch('WScript.Shell')
        sc = ws.CreateShortcut(ascii_path)
        sc.TargetPath = target_exe
        sc.WorkingDirectory = os.path.dirname(target_exe)
        if icon_path and os.path.exists(icon_path):
            sc.IconLocation = icon_path
        sc.Save()
        return os.path.exists(ascii_path)
    except Exception as e:
        print(f"[Error] All shortcut creation methods failed: {e}")
        return False


class InstallWorker(QThread):
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, zip_path: str, install_dir: str, create_desktop: bool, create_start: bool):
        super().__init__()
        self.zip_path = zip_path
        self.install_dir = install_dir
        self.create_desktop = create_desktop
        self.create_start = create_start

    def run(self):
        try:
            if not os.path.exists(self.zip_path):
                self.finished_signal.emit(False, f"Không tìm thấy gói cài đặt: {self.zip_path}")
                return

            self.progress_signal.emit(3, "Đang đóng phần mềm (nếu đang mở) để cập nhật...")
            if is_app_running(self.install_dir) and not close_running_app(self.install_dir):
                self.finished_signal.emit(False, "Phần mềm vẫn đang mở và không thể tự đóng.\n"
                                                 "Vui lòng tắt phần mềm rồi bấm 'Thử Lại'.")
                return

            self.progress_signal.emit(6, "Đang chuẩn bị thư mục cài đặt...")
            os.makedirs(self.install_dir, exist_ok=True)
            backup = move_old_files_to_backup(self.install_dir)
            if backup:
                self.progress_signal.emit(9, f"Đã sao lưu bản cũ vào: {backup}")

            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                file_list = zf.infolist()
                total_files = len(file_list)
                if total_files == 0:
                    self.finished_signal.emit(False, "Gói cài đặt rỗng.")
                    return

                for idx, member in enumerate(file_list):
                    for attempt in range(5):  # ghi đè, thử lại nếu file còn bị khóa
                        try:
                            zf.extract(member, self.install_dir)
                            break
                        except PermissionError:
                            if attempt == 4:
                                raise
                            import time
                            time.sleep(1)
                    pct = int(10 + (idx / total_files) * 80)
                    if idx % 15 == 0 or idx == total_files - 1:
                        self.progress_signal.emit(pct, f"Đang giải nén: {os.path.basename(member.filename)}...")

            self.progress_signal.emit(92, "Đang tạo biểu tượng lối tắt (Desktop Shortcut)...")
            exe_path = os.path.join(self.install_dir, "XNK_eCoSys_SC.exe")
            if not os.path.exists(exe_path):
                # Search if it extracted into a subdirectory
                for root, dirs, files in os.walk(self.install_dir):
                    if "XNK_eCoSys_SC.exe" in files:
                        exe_path = os.path.join(root, "XNK_eCoSys_SC.exe")
                        break

            candidate_icons = [
                os.path.join(os.path.dirname(exe_path), "_internal", "assets", "app_icon.ico"),
                os.path.join(os.path.dirname(exe_path), "assets", "app_icon.ico"),
                exe_path
            ]
            icon_path = exe_path
            for cand in candidate_icons:
                if os.path.exists(cand):
                    icon_path = cand
                    break

            # 1. Desktop Shortcuts
            if self.create_desktop:
                desktop_dirs = get_real_desktop_paths()
                if not desktop_dirs:
                    desktop_dirs = [os.path.join(os.environ.get('USERPROFILE', os.path.expanduser('~')), 'Desktop')]
                for d_dir in desktop_dirs:
                    sc_path = os.path.join(d_dir, "XNK & Thủy Sản Toàn Diện.lnk")
                    create_windows_shortcut(
                        exe_path,
                        sc_path,
                        icon_path,
                        "Hệ Thống Quản Trị C/O eCoSys & Đối Chiếu SC Cảng Cá"
                    )

            # 2. Start Menu Shortcuts
            if self.create_start:
                start_dirs = get_real_start_menu_paths()
                if not start_dirs:
                    app_data = os.environ.get('APPDATA', '')
                    if app_data:
                        start_dirs = [os.path.join(app_data, 'Microsoft', 'Windows', 'Start Menu', 'Programs')]
                for s_dir in start_dirs:
                    sc_start = os.path.join(s_dir, "XNK & Thủy Sản Toàn Diện.lnk")
                    create_windows_shortcut(
                        exe_path,
                        sc_start,
                        icon_path,
                        "Hệ Thống Quản Trị C/O eCoSys & Đối Chiếu SC Cảng Cá"
                    )

            self.progress_signal.emit(100, "Cài đặt thành công 100%!")
            self.finished_signal.emit(True, exe_path)

        except Exception as e:
            self.finished_signal.emit(False, str(e))


class SetupWizard(QDialog):
    def __init__(self):
        super().__init__()
        self.version = get_bundle_version() or "3"
        self.cli = parse_cli_args()
        self.setWindowTitle(f"Cài Đặt Phần Mềm - XNK & Thủy Sản Toàn Diện v{self.version}")
        self.resize(620, 520)
        self.setFixedSize(620, 520)

        # Set Icon if available
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, "assets", "app_icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(base_dir), "assets", "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.icon_path = icon_path

        local_app_data = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        std_dir = os.path.join(local_app_data, "Programs", "XNK_eCoSys_SC")
        # Ưu tiên: thư mục do trình cập nhật truyền vào -> thư mục bản cũ (theo shortcut) -> mặc định
        existing = self.cli["target"] if self.cli["target"] and os.path.isdir(self.cli["target"]) else ""
        existing = existing or find_existing_install_dir()
        if not existing and os.path.exists(os.path.join(std_dir, APP_EXE_NAME)):
            existing = std_dir
        self.is_upgrade = bool(existing)
        self.default_install_dir = existing or std_dir
        self.installed_exe_path = None

        self.init_ui()
        if self.cli["update"] and self.is_upgrade:
            # Mở từ trình cập nhật trong phần mềm: tự cài đè luôn, không cần bấm
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(600, self.start_install)

    def init_ui(self):
        # Global stylesheet scoped carefully so it does NOT corrupt children
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
            }
            #card_dir, #card_opt {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
            #card_dir QLabel, #card_opt QLabel {
                background: transparent;
                border: none;
                color: #1e293b;
            }
            QLineEdit#entry_dir {
                background-color: #f8fafc;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                color: #0f172a;
            }
            QLineEdit#entry_dir:focus {
                border-color: #0284c7;
                background-color: #ffffff;
            }
            QPushButton#btn_browse {
                background-color: #f1f5f9;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 600;
                color: #334155;
            }
            QPushButton#btn_browse:hover {
                background-color: #e2e8f0;
                border-color: #94a3b8;
                color: #0f172a;
            }
            QCheckBox {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                color: #1e293b;
                background: transparent;
                border: none;
                spacing: 8px;
                padding: 3px 0px;
            }
            QProgressBar {
                background-color: #e2e8f0;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #0284c7;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(14)

        # 1. Header Banner
        banner = QFrame()
        banner.setObjectName("header_banner")
        banner.setStyleSheet("""
            #header_banner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:0.6 #0369a1, stop:1 #0284c7);
                border-bottom: 2px solid #38bdf8;
            }
        """)
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(24, 16, 24, 16)
        banner_layout.setSpacing(16)

        # Banner Icon
        lbl_logo = QLabel("🚢")
        lbl_logo.setStyleSheet("font-size: 36px; background: transparent; border: none;")
        banner_layout.addWidget(lbl_logo)

        # Banner Title & Subtitle
        banner_text_col = QVBoxLayout()
        banner_text_col.setSpacing(3)

        lbl_title = QLabel("CÀI ĐẶT HỆ THỐNG XNK & THỦY SẢN TOÀN DIỆN")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff; background: transparent; border: none;")
        banner_text_col.addWidget(lbl_title)

        lbl_sub = QLabel(f"Phiên bản v{self.version} • Khai báo C/O eCoSys & Đối chiếu SC Cảng cá (IUU)")
        lbl_sub.setStyleSheet("font-size: 12.5px; color: #bae6fd; background: transparent; border: none;")
        banner_text_col.addWidget(lbl_sub)

        banner_layout.addLayout(banner_text_col, stretch=1)

        # Version Pill Badge
        lbl_badge = QLabel(f"v{self.version}")
        lbl_badge.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.15);
            color: #ffffff;
            font-size: 11px;
            font-weight: bold;
            padding: 4px 10px;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.3);
        """)
        banner_layout.addWidget(lbl_badge, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(banner)

        # 2. Main Body Container
        body_widget = QWidget()
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(24, 0, 24, 0)
        body_layout.setSpacing(12)

        if self.is_upgrade:
            intro_txt = (f"Đã tìm thấy bản đang cài tại thư mục bên dưới — sẽ CẬP NHẬT GHI ĐÈ lên v{self.version}.\n"
                         "Phần mềm đang mở sẽ được tự đóng; bản cũ được sao lưu, dữ liệu (cache, kết quả) giữ nguyên.")
        else:
            intro_txt = ("Trình cài đặt sẽ thiết lập toàn bộ hệ thống vào máy tính của bạn.\n"
                         "Phần mềm chạy hoàn toàn độc lập, không yêu cầu cài đặt Python hay thư viện nào khác.")
        lbl_intro = QLabel(intro_txt)
        lbl_intro.setStyleSheet("font-size: 12.5px; color: #475569; line-height: 1.4; border: none; background: transparent;")
        body_layout.addWidget(lbl_intro)

        # CARD 1: Thư mục cài đặt
        card_dir = QFrame()
        card_dir.setObjectName("card_dir")
        card_dir_layout = QVBoxLayout(card_dir)
        card_dir_layout.setContentsMargins(16, 12, 16, 12)
        card_dir_layout.setSpacing(8)

        lbl_dir_title = QLabel("📁 <b>Thư mục cài đặt ứng dụng:</b>")
        lbl_dir_title.setStyleSheet("font-size: 13px;")
        card_dir_layout.addWidget(lbl_dir_title)

        row_dir = QHBoxLayout()
        row_dir.setSpacing(8)
        self.entry_dir = QLineEdit(self.default_install_dir)
        self.entry_dir.setObjectName("entry_dir")
        row_dir.addWidget(self.entry_dir, stretch=1)

        btn_browse = QPushButton("Duyệt...")
        btn_browse.setObjectName("btn_browse")
        btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse.clicked.connect(self.browse_dir)
        row_dir.addWidget(btn_browse)
        card_dir_layout.addLayout(row_dir)

        body_layout.addWidget(card_dir)

        # CARD 2: Tùy chọn cài đặt & Khởi chạy
        card_opt = QFrame()
        card_opt.setObjectName("card_opt")
        card_opt_layout = QVBoxLayout(card_opt)
        card_opt_layout.setContentsMargins(16, 12, 16, 12)
        card_opt_layout.setSpacing(6)

        lbl_opt_title = QLabel("⚙️ <b>Tùy chọn tạo lối tắt & khởi chạy:</b>")
        lbl_opt_title.setStyleSheet("font-size: 13px;")
        card_opt_layout.addWidget(lbl_opt_title)

        self.chk_desktop = QCheckBox("Tạo biểu tượng ngoài màn hình Desktop (Desktop Shortcut)")
        self.chk_desktop.setChecked(True)
        self.chk_desktop.setCursor(Qt.CursorShape.PointingHandCursor)
        card_opt_layout.addWidget(self.chk_desktop)

        self.chk_start = QCheckBox("Tạo lối tắt trong Start Menu")
        self.chk_start.setChecked(True)
        self.chk_start.setCursor(Qt.CursorShape.PointingHandCursor)
        card_opt_layout.addWidget(self.chk_start)

        self.chk_launch = QCheckBox("Tự động mở phần mềm ngay sau khi cài đặt hoàn tất")
        self.chk_launch.setChecked(True)
        self.chk_launch.setCursor(Qt.CursorShape.PointingHandCursor)
        card_opt_layout.addWidget(self.chk_launch)

        body_layout.addWidget(card_opt)

        # Progress bar
        self.prog_bar = QProgressBar()
        self.prog_bar.setFixedHeight(8)
        self.prog_bar.setValue(0)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setVisible(False)
        body_layout.addWidget(self.prog_bar)

        self.lbl_status = QLabel("Sẵn sàng bắt đầu cài đặt.")
        self.lbl_status.setStyleSheet("color: #64748b; font-style: italic; font-size: 12px; border: none; background: transparent;")
        body_layout.addWidget(self.lbl_status)

        layout.addWidget(body_widget, stretch=1)

        # 3. Footer Bar
        footer = QHBoxLayout()
        footer.setContentsMargins(24, 0, 24, 0)
        footer.setSpacing(10)
        footer.addStretch()

        self.btn_cancel = QPushButton("Hủy Bỏ")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                color: #0f172a;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        footer.addWidget(self.btn_cancel)

        self.btn_install = QPushButton("🚀 Cập Nhật Ngay" if self.is_upgrade else "🚀 Cài Đặt Ngay")
        self.btn_install.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_install.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 24px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QPushButton:disabled {
                background-color: #94a3b8;
                color: #f1f5f9;
            }
        """)
        self.btn_install.clicked.connect(self.start_install)
        footer.addWidget(self.btn_install)

        layout.addLayout(footer)

    def browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục cài đặt", self.entry_dir.text())
        if d:
            self.entry_dir.setText(d)

    def start_install(self):
        install_dir = self.entry_dir.text().strip()
        if not install_dir:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn thư mục cài đặt!")
            return

        zip_path = get_bundle_zip_path()
        if not os.path.exists(zip_path):
            QMessageBox.critical(self, "Lỗi", f"Không tìm thấy gói tệp nén cài đặt: {zip_path}")
            return

        if not self.cli["update"] and is_app_running(install_dir):
            ans = QMessageBox.question(
                self, "Phần mềm đang mở",
                "Phần mềm XNK & Thủy Sản đang mở. Cần đóng phần mềm để ghi đè bản mới.\n\n"
                "Đóng phần mềm và tiếp tục cập nhật?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
            if ans != QMessageBox.StandardButton.Yes:
                return

        self.btn_install.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.btn_install.setText("⏳ Đang cài đặt...")
        self.prog_bar.setVisible(True)
        self.prog_bar.setValue(5)

        self.worker = InstallWorker(
            zip_path=zip_path,
            install_dir=install_dir,
            create_desktop=self.chk_desktop.isChecked() and not self.cli["no_shortcuts"],
            create_start=self.chk_start.isChecked() and not self.cli["no_shortcuts"]
        )
        self.worker.progress_signal.connect(self.on_progress)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, val: int, msg: str):
        self.prog_bar.setValue(val)
        self.lbl_status.setText(msg)

    def on_finished(self, success: bool, exe_or_err: str):
        if success:
            self.installed_exe_path = exe_or_err
            self.btn_install.setText("✅ Hoàn Tất")
            self.btn_install.setEnabled(True)
            self.btn_install.clicked.disconnect()
            self.btn_install.clicked.connect(self.on_done_clicked)
            self.btn_cancel.setVisible(False)
            self.lbl_status.setText("Cài đặt thành công 100%! Đã tạo biểu tượng ngoài màn hình Desktop.")

            if not self.cli["update"]:
                QMessageBox.information(
                    self, "Cài Đặt Thành Công",
                    f"Phần mềm XNK & Thủy Sản Toàn Diện v{self.version} đã được "
                    f"{'cập nhật' if self.is_upgrade else 'cài đặt'} thành công.\n\n"
                    f"Thư mục: {os.path.dirname(exe_or_err)}"
                )
            if self.chk_launch.isChecked():
                self.launch_installed_app()
                self.accept()
        else:
            self.btn_install.setEnabled(True)
            self.btn_cancel.setEnabled(True)
            self.btn_install.setText("🚀 Thử Lại")
            QMessageBox.critical(self, "Lỗi Cài Đặt", f"Phát sinh lỗi trong quá trình cài đặt:\n{exe_or_err}")

    def on_done_clicked(self):
        if self.chk_launch.isChecked():
            self.launch_installed_app()
        self.accept()

    def launch_installed_app(self):
        if self.installed_exe_path and os.path.exists(self.installed_exe_path):
            try:
                subprocess.Popen([self.installed_exe_path], cwd=os.path.dirname(self.installed_exe_path))
            except Exception as e:
                print(f"Failed to launch: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    wizard = SetupWizard()
    wizard.show()
    sys.exit(app.exec())
