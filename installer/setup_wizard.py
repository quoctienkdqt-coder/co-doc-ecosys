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

            self.progress_signal.emit(5, "Đang chuẩn bị thư mục cài đặt...")
            os.makedirs(self.install_dir, exist_ok=True)

            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                file_list = zf.infolist()
                total_files = len(file_list)
                if total_files == 0:
                    self.finished_signal.emit(False, "Gói cài đặt rỗng.")
                    return

                for idx, member in enumerate(file_list):
                    zf.extract(member, self.install_dir)
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
        self.setWindowTitle("Cài Đặt Phần Mềm - XNK & Thủy Sản Toàn Diện v3.0")
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
        self.default_install_dir = os.path.join(local_app_data, "Programs", "XNK_eCoSys_SC")
        self.installed_exe_path = None

        self.init_ui()

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

        lbl_sub = QLabel("Phiên bản v3.0 • Khai báo C/O eCoSys & Đối chiếu SC Cảng cá (IUU)")
        lbl_sub.setStyleSheet("font-size: 12.5px; color: #bae6fd; background: transparent; border: none;")
        banner_text_col.addWidget(lbl_sub)

        banner_layout.addLayout(banner_text_col, stretch=1)

        # Version Pill Badge
        lbl_badge = QLabel("v3.0 Official")
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

        lbl_intro = QLabel(
            "Trình cài đặt sẽ thiết lập toàn bộ hệ thống vào máy tính của bạn.\n"
            "Phần mềm chạy hoàn toàn độc lập, không yêu cầu cài đặt Python hay thư viện nào khác."
        )
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

        self.btn_install = QPushButton("🚀 Cài Đặt Ngay")
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

        self.btn_install.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.btn_install.setText("⏳ Đang cài đặt...")
        self.prog_bar.setVisible(True)
        self.prog_bar.setValue(5)

        self.worker = InstallWorker(
            zip_path=zip_path,
            install_dir=install_dir,
            create_desktop=self.chk_desktop.isChecked(),
            create_start=self.chk_start.isChecked()
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

            QMessageBox.information(
                self, "Cài Đặt Thành Công",
                "Chúc mừng! Phần mềm XNK & Thủy Sản Toàn Diện v3.0 đã được cài đặt thành công.\n\n"
                "Biểu tượng đã được tạo ngoài màn hình Desktop."
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
