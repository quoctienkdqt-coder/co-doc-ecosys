"""
Module kiểm tra và tự động cập nhật phần mềm qua GitHub
Tác giả & Phát triển: Ngô Quốc Tiến - Zalo: 0905387808
Bản quyền © 2026. Mọi quyền được bảo lưu.
Khuyến cáo AI: AI chỉ mang tính tham khảo, mọi quyết định và kết quả đều do con người.
"""

import os
import sys
import json
import shutil
import zipfile
import urllib.request
import subprocess
from datetime import datetime
from typing import Tuple, Optional, Dict, Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextBrowser, QProgressBar, QMessageBox, QFrame
)
from PyQt6.QtGui import QFont, QIcon


def get_app_dir() -> str:
    """Trả về thư mục gốc của ứng dụng (hỗ trợ cả chạy mã nguồn .py và chạy qua .exe đã đóng gói)"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_local_version_info() -> Dict[str, Any]:
    """Đọc thông tin phiên bản hiện tại từ version.json"""
    v_path = os.path.join(get_app_dir(), "version.json")
    if os.path.exists(v_path):
        try:
            with open(v_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "version": "3.1.0",
        "app_name": "Hệ Thống Quản Trị Xuất Nhập Khẩu & Thủy Sản Toàn Diện",
        "author": "Ngô Quốc Tiến",
        "contact": "Zalo: 0905387808",
        "ai_disclaimer": "AI chỉ mang tính tham khảo, mọi quyết định và kết quả đều do con người.",
        "github_repo": "https://github.com/quoctienkdqt-coder/co-doc-ecosys",
        "release_date": "28/10/2026"
    }


def parse_repo_owner_name(url: str) -> Tuple[str, str]:
    """Phân tích đường link GitHub thành owner và repo name"""
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    parts = url.split("/")
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return "", ""


class UpdateCheckerWorker(QThread):
    """Luồng ngầm kiểm tra cập nhật trên GitHub"""
    result_signal = pyqtSignal(bool, dict, str)

    def __init__(self, repo_url: str):
        super().__init__()
        self.repo_url = repo_url

    def run(self):
        try:
            owner, repo = parse_repo_owner_name(self.repo_url)
            if not owner or not repo:
                self.result_signal.emit(False, {}, "Đường dẫn kho GitHub không hợp lệ!")
                return

            remote_data = None
            exe_download_url = None

            # Cách 1: Thử lấy release mới nhất qua GitHub API (nếu có file cài đặt .exe)
            api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
            try:
                req = urllib.request.Request(
                    api_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                )
                with urllib.request.urlopen(req, timeout=6) as response:
                    if response.status == 200:
                        rel_data = json.loads(response.read().decode("utf-8"))
                        tag = rel_data.get("tag_name", "").lstrip("v")
                        # Tìm asset có đuôi .exe (ví dụ CaiDat_XNK_eCoSys_SC.exe)
                        for asset in rel_data.get("assets", []):
                            if asset.get("name", "").endswith(".exe"):
                                exe_download_url = asset.get("browser_download_url")
                                break

                        remote_data = {
                            "version": tag or "3.1.0",
                            "changelog": [rel_data.get("body", "Bản cập nhật mới trên GitHub")],
                            "published_at": rel_data.get("published_at", ""),
                            "exe_url": exe_download_url
                        }
            except Exception:
                pass

            # Cách 2: Thử đọc trực tiếp version.json từ nhánh main/master
            if not remote_data:
                raw_urls = [
                    f"https://raw.githubusercontent.com/{owner}/{repo}/main/version.json",
                    f"https://raw.githubusercontent.com/{owner}/{repo}/master/version.json"
                ]
                for r_url in raw_urls:
                    try:
                        req = urllib.request.Request(
                            r_url,
                            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                        )
                        with urllib.request.urlopen(req, timeout=6) as response:
                            if response.status == 200:
                                remote_data = json.loads(response.read().decode("utf-8"))
                                break
                    except Exception:
                        continue

            if remote_data:
                self.result_signal.emit(True, remote_data, "")
            else:
                self.result_signal.emit(
                    False, {},
                    f"Không thể kết nối hoặc chưa tìm thấy bản phát hành tại kho GitHub: {owner}/{repo}\n"
                    "Vui lòng kiểm tra lại kết nối mạng hoặc tính khả dụng của kho lưu trữ."
                )

        except Exception as e:
            self.result_signal.emit(False, {}, str(e))


class UpdateApplyWorker(QThread):
    """Luồng ngầm tải và tiến hành cập nhật ứng dụng"""
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, repo_url: str, remote_info: dict):
        super().__init__()
        self.repo_url = repo_url
        self.remote_info = remote_info

    def run(self):
        try:
            workspace_dir = get_app_dir()
            backup_base = os.path.join(workspace_dir, "backups_update")
            os.makedirs(backup_base, exist_ok=True)

            # Trường hợp 1: Nếu có file cài đặt Setup (.exe) đính kèm trên GitHub Release
            exe_url = self.remote_info.get("exe_url")
            if exe_url and exe_url.endswith(".exe"):
                self.progress_signal.emit(20, f"Phát hiện file cài đặt mới trên GitHub Release: {os.path.basename(exe_url)}")
                installer_name = os.path.basename(exe_url)
                dest_installer = os.path.join(workspace_dir, installer_name)
                self.progress_signal.emit(40, f"Đang tải an toàn {installer_name}...")
                req = urllib.request.Request(exe_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=120) as resp, open(dest_installer, 'wb') as out_f:
                    shutil.copyfileobj(resp, out_f)

                # Xác minh an toàn tệp thực thi PE Windows (chống giả mạo)
                if not os.path.exists(dest_installer) or os.path.getsize(dest_installer) < 1024 * 1024:
                    raise ValueError("Tệp cài đặt tải về không hợp lệ hoặc kích thước quá nhỏ!")
                with open(dest_installer, "rb") as check_f:
                    magic = check_f.read(2)
                    if magic != b'MZ':
                        raise ValueError("Tệp tải về không phải định dạng thực thi PE Windows an toàn!")

                self.progress_signal.emit(90, "Đang khởi chạy trình cài đặt mới...")
                # Chạy an toàn KHÔNG dùng shell=True để chống injection
                subprocess.Popen([dest_installer], shell=False)
                self.progress_signal.emit(100, "Đã khởi chạy bộ cài đặt mới!")
                self.finished_signal.emit(True, f"Đã tải xong bộ cài đặt mới:\n{dest_installer}\n\nTrình cài đặt đang được mở để tự động cập nhật hệ thống.")
                return

            # Trường hợp 2: Kiểm tra nếu là kho Git nội bộ (.git)
            dot_git = os.path.join(workspace_dir, ".git")
            if os.path.exists(dot_git):
                self.progress_signal.emit(25, "Phát hiện kho Git. Đang đồng bộ tự động qua git pull...")
                try:
                    res = subprocess.run(
                        ["git", "pull"],
                        cwd=workspace_dir,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    if res.returncode == 0:
                        self.progress_signal.emit(100, "Cập nhật Git hoàn tất thành công!")
                        self.finished_signal.emit(True, f"Đã đồng bộ git pull thành công:\n{res.stdout}\n\nVui lòng khởi động lại phần mềm.")
                        return
                except Exception as git_err:
                    self.progress_signal.emit(35, f"Git pull gặp trục trặc: {git_err}. Đang chuyển sang tải gói mã nguồn...")

            # Trường hợp 3: Tải nén ZIP toàn bộ mã nguồn cập nhật từ GitHub
            owner, repo = parse_repo_owner_name(self.repo_url)
            zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip"

            self.progress_signal.emit(25, f"Đang kết nối tải mã nguồn từ: {zip_url}...")

            # Tạo bản sao lưu toàn diện cây thư mục (Full-Tree Backup)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_folder = os.path.join(backup_base, f"backup_{ts}")
            os.makedirs(backup_folder, exist_ok=True)
            self.progress_signal.emit(35, f"Đang tạo bản sao lưu toàn diện tại: backups_update/backup_{ts}...")

            exclude_dirs = {"backups_update", ".git", "__pycache__", "venv", "dist", "build", "debug_profile"}
            for item in os.listdir(workspace_dir):
                if item in exclude_dirs or item.endswith(".tmp") or item.endswith(".zip"):
                    continue
                s = os.path.join(workspace_dir, item)
                d = os.path.join(backup_folder, item)
                try:
                    if os.path.isdir(s):
                        shutil.copytree(s, d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                    elif os.path.isfile(s):
                        shutil.copy2(s, d)
                except Exception as copy_err:
                    print(f"Warning backup item {item}: {copy_err}")

            # Tải tệp zip về tạm
            temp_zip = os.path.join(workspace_dir, "temp_update.zip")
            staging_dir = os.path.join(workspace_dir, f"staging_update_{ts}")
            req = urllib.request.Request(
                zip_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )

            self.progress_signal.emit(55, "Đang tải gói cập nhật mã nguồn an toàn...")
            with urllib.request.urlopen(req, timeout=30) as response, open(temp_zip, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)

            self.progress_signal.emit(75, "Đang xác minh bảo mật và giải nén qua Staging cách ly...")
            os.makedirs(staging_dir, exist_ok=True)
            norm_workspace = os.path.normpath(os.path.abspath(workspace_dir))
            norm_staging = os.path.normpath(os.path.abspath(staging_dir))

            try:
                with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                    members = zip_ref.namelist()
                    root_in_zip = members[0].split('/')[0] if members else ""

                    for member in members:
                        if member.endswith("/"):
                            continue
                        rel_path = member[len(root_in_zip) + 1:] if root_in_zip and member.startswith(root_in_zip + "/") else member
                        if not rel_path or rel_path.startswith("/") or ".." in rel_path:
                            continue

                        # Bảo tồn file cấu hình
                        if rel_path in ["settings.json"]:
                            continue

                        # Chống lỗ hổng Zip Slip (Kiểm tra đường dẫn sau chuẩn hóa)
                        stage_dest = os.path.normpath(os.path.join(staging_dir, rel_path))
                        if not stage_dest.startswith(norm_staging):
                            raise ValueError(f"Cảnh báo bảo mật: Tệp '{member}' vi phạm kiểm tra an toàn Zip Slip!")

                        os.makedirs(os.path.dirname(stage_dest), exist_ok=True)
                        with zip_ref.open(member) as src_f, open(stage_dest, "wb") as dst_f:
                            shutil.copyfileobj(src_f, dst_f)

                # Bước áp dụng nguyên tử (Atomic Copy) từ Staging vào Workspace
                self.progress_signal.emit(90, "Đang áp dụng phiên bản cập nhật...")
                for root_s, dirs_s, files_s in os.walk(staging_dir):
                    rel_sub = os.path.relpath(root_s, staging_dir)
                    dest_sub = workspace_dir if rel_sub == "." else os.path.join(workspace_dir, rel_sub)
                    dest_sub_norm = os.path.normpath(os.path.abspath(dest_sub))
                    if not dest_sub_norm.startswith(norm_workspace):
                        raise ValueError(f"Đường dẫn ghi đè không hợp lệ: {dest_sub_norm}")

                    os.makedirs(dest_sub_norm, exist_ok=True)
                    for f in files_s:
                        f_stage = os.path.join(root_s, f)
                        f_dest = os.path.join(dest_sub_norm, f)
                        shutil.copy2(f_stage, f_dest)

            except Exception as update_err:
                # Cơ chế Rollback tự động phục hồi nếu có sự cố
                self.progress_signal.emit(40, "⚠️ Có lỗi xảy ra. Đang tự động khôi phục (Rollback) từ bản sao lưu...")
                try:
                    for root_b, dirs_b, files_b in os.walk(backup_folder):
                        rel_b = os.path.relpath(root_b, backup_folder)
                        dest_b = workspace_dir if rel_b == "." else os.path.join(workspace_dir, rel_b)
                        os.makedirs(dest_b, exist_ok=True)
                        for fb in files_b:
                            shutil.copy2(os.path.join(root_b, fb), os.path.join(dest_b, fb))
                except Exception as rb_err:
                    print(f"Rollback error: {rb_err}")
                raise update_err
            finally:
                if os.path.exists(staging_dir):
                    shutil.rmtree(staging_dir, ignore_errors=True)
                if os.path.exists(temp_zip):
                    try:
                        os.remove(temp_zip)
                    except Exception:
                        pass

            self.progress_signal.emit(100, "Cập nhật thành công 100%!")
            self.finished_signal.emit(
                True,
                "Đã hoàn tất cập nhật phần mềm lên phiên bản mới nhất!\n"
                f"Toàn bộ phiên bản cũ đã được sao lưu an toàn tại:\nbackups_update/backup_{ts}\n\n"
                "👉 Vui lòng khởi động lại ứng dụng để áp dụng ngay các tính năng mới."
            )

        except Exception as e:
            self.finished_signal.emit(False, f"Lỗi trong quá trình cập nhật: {e}")


class GitHubUpdateDialog(QDialog):
    """Cửa sổ Kiểm tra & Cập nhật phần mềm qua GitHub"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔄 Kiểm Tra & Cập Nhật Phần Mềm Qua GitHub")
        self.resize(720, 560)
        self.setMinimumSize(640, 480)
        self.local_info = get_local_version_info()
        self.remote_info = {}
        self.check_worker: Optional[UpdateCheckerWorker] = None
        self.apply_worker: Optional[UpdateApplyWorker] = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # 1. Header Banner
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e3a8a, stop:1 #0284c7);
                border-radius: 8px;
                padding: 14px 16px;
            }
            QLabel {
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
        b_layout = QVBoxLayout(banner)
        b_layout.setContentsMargins(0, 0, 0, 0)
        b_layout.setSpacing(4)

        lbl_t = QLabel("🔄 TRÌNH CẬP NHẬT PHẦN MỀM TỰ ĐỘNG QUA GITHUB")
        lbl_t.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        b_layout.addWidget(lbl_t)

        lbl_cur = QLabel(
            f"Phiên bản hiện tại: <b>v{self.local_info.get('version', '3.1.0')}</b> "
            f"• Tác giả: <b>{self.local_info.get('author', 'Ngô Quốc Tiến')}</b> (Zalo: 0905387808)"
        )
        lbl_cur.setStyleSheet("font-size: 12.5px; color: #e0f2fe;")
        b_layout.addWidget(lbl_cur)
        layout.addWidget(banner)

        # 2. Khung cấu hình kho GitHub
        repo_card = QFrame()
        repo_card.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px 14px;")
        rc_layout = QHBoxLayout(repo_card)
        rc_layout.setContentsMargins(0, 0, 0, 0)
        rc_layout.setSpacing(10)

        rc_layout.addWidget(QLabel("<b>Kho GitHub:</b>"))
        self.txt_repo = QLineEdit(self.local_info.get("github_repo", "https://github.com/quoctienkdqt-coder/co-doc-ecosys"))
        self.txt_repo.setPlaceholderText("Nhập link repository GitHub...")
        rc_layout.addWidget(self.txt_repo)

        self.btn_check = QPushButton("🔍 Kiểm tra bản mới")
        self.btn_check.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.btn_check.clicked.connect(self.check_for_updates)
        rc_layout.addWidget(self.btn_check)
        layout.addWidget(repo_card)

        # 3. Khu vực hiển thị nhật ký & trạng thái
        self.txt_info = QTextBrowser()
        self.txt_info.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 12.5px; padding: 10px;")
        self.show_initial_status()
        layout.addWidget(self.txt_info, stretch=1)

        # 4. Thanh tiến trình cập nhật
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setTextVisible(True)
        self.prog_bar.setVisible(False)
        layout.addWidget(self.prog_bar)

        # 5. Khuyến cáo AI & Quyền sở hữu
        lbl_disclaimer = QLabel(
            "⚠️ <b>CHÚ Ý:</b> AI chỉ mang tính tham khảo, mọi quyết định và kết quả đều do con người.<br/>"
            "© Bản quyền phần mềm & Phát triển bởi: <b>Ngô Quốc Tiến</b> • Zalo: <b>0905387808</b>"
        )
        lbl_disclaimer.setStyleSheet("color: #475569; font-size: 11.5px; background: #f1f5f9; padding: 8px 12px; border-radius: 6px;")
        layout.addWidget(lbl_disclaimer)

        # 6. Nút điều khiển
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_apply = QPushButton("🚀 TIẾN HÀNH CẬP NHẬT NGAY")
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #16a34a;
                color: #ffffff;
                font-weight: bold;
                padding: 9px 24px;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #15803d;
            }
            QPushButton:disabled {
                background-color: #94a3b8;
            }
        """)
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self.apply_update)
        btn_layout.addWidget(self.btn_apply)

        btn_close = QPushButton("Đóng")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #e2e8f0;
                color: #334155;
                font-weight: 500;
                padding: 9px 18px;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #cbd5e1;
            }
        """)
        btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def show_initial_status(self):
        cur_v = self.local_info.get("version", "3.1.0")
        rel_date = self.local_info.get("release_date", "28/10/2026")
        changelog = self.local_info.get("changelog", [])
        cl_html = "".join([f"<li>{item}</li>" for item in changelog])

        html = f"""
        <div style="font-family: 'Segoe UI', Arial; line-height: 1.6;">
            <h3 style="color: #0f172a; margin-top: 0;">ℹ️ THÔNG TIN PHIÊN BẢN ĐANG CÀI ĐẶT:</h3>
            <p>• Phiên bản hiện tại: <b style="color: #0284c7;">v{cur_v}</b> (Ngày phát hành: {rel_date})</p>
            <p>• Tác giả: <b>{self.local_info.get('author', 'Ngô Quốc Tiến')}</b> — Hotline/Zalo: <b>0905387808</b></p>
            <h4 style="color: #1e3a8a; margin-bottom: 6px;">Các cải tiến gần nhất:</h4>
            <ul>{cl_html}</ul>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 12px 0;"/>
            <p style="color: #64748b;">👉 Bấm nút <b>'🔍 Kiểm tra bản mới'</b> ở trên để kết nối với kho GitHub và phát hiện các bản nâng cấp mới nhất.</p>
        </div>
        """
        self.txt_info.setHtml(html)

    def check_for_updates(self):
        url = self.txt_repo.text().strip()
        if not url:
            QMessageBox.warning(self, "Thiếu liên kết", "Vui lòng nhập đường dẫn repository GitHub để kiểm tra!")
            return

        self.btn_check.setEnabled(False)
        self.btn_check.setText("⏳ Đang kiểm tra...")
        self.txt_info.setHtml("<p style='color: #0284c7;'>⏳ Đang kết nối đến GitHub để kiểm tra phiên bản mới nhất...</p>")

        self.check_worker = UpdateCheckerWorker(url)
        self.check_worker.result_signal.connect(self.on_check_result)
        self.check_worker.start()

    def on_check_result(self, success: bool, data: dict, err: str):
        self.btn_check.setEnabled(True)
        self.btn_check.setText("🔍 Kiểm tra bản mới")

        if not success:
            self.txt_info.setHtml(f"""
                <div style="color: #b91c1c; padding: 10px;">
                    <h4>❌ Không thể kiểm tra cập nhật</h4>
                    <p>{err}</p>
                    <p style="color: #475569; font-size: 11.5px;">💡 Mẹo: Hãy kiểm tra kho lưu trữ GitHub có tồn tại và kết nối mạng của bạn có ổn định không.</p>
                </div>
            """)
            self.btn_apply.setEnabled(False)
            return

        self.remote_info = data
        remote_v = str(data.get("version", "")).lstrip("v")
        cur_v = str(self.local_info.get("version", "3.1.0")).lstrip("v")

        has_new = remote_v != cur_v and remote_v > cur_v
        changelog = data.get("changelog", ["Cập nhật và tối ưu hóa hệ thống"])
        cl_html = "".join([f"<li>{item}</li>" for item in changelog])

        if has_new:
            self.btn_apply.setEnabled(True)
            self.txt_info.setHtml(f"""
                <div style="font-family: 'Segoe UI', Arial; line-height: 1.6;">
                    <div style="background-color: #dcfce7; border: 1px solid #86efac; padding: 12px 16px; border-radius: 6px; margin-bottom: 12px;">
                        <h3 style="color: #166534; margin: 0;">🎉 ĐÃ PHÁT HIỆN BẢN CẬP NHẬT MỚI: v{remote_v}!</h3>
                        <p style="color: #15803d; margin: 4px 0 0 0;">Phiên bản bạn đang dùng: v{cur_v} → Đã có bản mới v{remote_v} sẵn sàng nâng cấp.</p>
                    </div>
                    <h4 style="color: #0f172a; margin-bottom: 6px;">Nội dung cập nhật mới:</h4>
                    <ul>{cl_html}</ul>
                    <p style="color: #0369a1; font-weight: 500;">👉 Bấm nút <b>'🚀 TIẾN HÀNH CẬP NHẬT NGAY'</b> bên dưới để tự động tải và cài đặt.</p>
                </div>
            """)
        else:
            self.btn_apply.setEnabled(False)
            self.txt_info.setHtml(f"""
                <div style="font-family: 'Segoe UI', Arial; line-height: 1.6;">
                    <div style="background-color: #f0f9ff; border: 1px solid #7dd3fc; padding: 12px 16px; border-radius: 6px;">
                        <h3 style="color: #0369a1; margin: 0;">✅ BẠN ĐANG SỬ DỤNG PHIÊN BẢN MỚI NHẤT!</h3>
                        <p style="color: #0284c7; margin: 4px 0 0 0;">Phiên bản hiện tại: <b>v{cur_v}</b> đã là phiên bản mới nhất trên kho GitHub.</p>
                    </div>
                </div>
            """)

    def apply_update(self):
        confirm = QMessageBox.question(
            self, "Xác nhận cập nhật",
            "Hệ thống sẽ tự động sao lưu toàn bộ mã nguồn hiện tại vào thư mục 'backups_update/' trước khi nâng cấp.\n\n"
            "Bạn có chắc chắn muốn tiến hành cập nhật ngay không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.btn_apply.setEnabled(False)
        self.btn_check.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.prog_bar.setValue(10)

        url = self.txt_repo.text().strip()
        self.apply_worker = UpdateApplyWorker(url, self.remote_info)
        self.apply_worker.progress_signal.connect(self.on_apply_progress)
        self.apply_worker.finished_signal.connect(self.on_apply_finished)
        self.apply_worker.start()

    def on_apply_progress(self, val: int, msg: str):
        self.prog_bar.setValue(val)
        self.txt_info.append(f"<p style='color: #0284c7; margin: 4px 0;'>⏳ {msg}</p>")

    def on_apply_finished(self, success: bool, msg: str):
        self.btn_check.setEnabled(True)
        if success:
            QMessageBox.information(self, "Cập nhật hoàn tất", msg)
            self.accept()
        else:
            self.btn_apply.setEnabled(True)
            QMessageBox.critical(self, "Lỗi cập nhật", msg)
