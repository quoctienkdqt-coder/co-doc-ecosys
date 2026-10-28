import urllib.parse
import local_stream_server
"""
Ứng dụng Desktop Trích xuất Chứng từ Khai báo C/O eCoSys (Bộ Công Thương)
Giao diện Bố cục Bản Gốc Chuẩn Mực - Nâng Cấp Thiết Kế Hiện Đại, Nổi Bật (PyQt6)
Tích hợp Gemini 3.8 Flash, Cổng APIZ, Trợ lý AI Copilot & Khóa Cứng Đơn Vị KILOGRAM
"""

import sys
import os
import json
import base64
import mimetypes
import traceback
import re
from typing import List, Optional

import fitz  # PyMuPDF

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QFileDialog, QHeaderView, QTableWidget, QTableWidgetItem, QListWidget, QListWidgetItem,
    QTabWidget, QTextEdit, QProgressBar, QSplitter, QGroupBox, QLabel, QLineEdit,
    QComboBox, QCheckBox, QPushButton, QMessageBox, QFrame, QScrollArea, QDialog, QTextBrowser
)
from PyQt6.QtGui import QFont, QIcon, QColor, QPixmap, QImage

from co_schema import CODeclarationData, GoodItem
from gemini_extractor import extract_co_data_from_files, ask_co_advisor

CONFIG_FILE = "settings.json"


def load_settings() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_settings(settings: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Lỗi lưu cấu hình: {e}")


# ========================================================
# 1. DROP LIST WIDGET HỖ TRỢ KÉO THẢ TỆP CHỨNG TỪ
# ========================================================
class DropListWidget(QListWidget):
    """QListWidget hỗ trợ kéo thả file tài liệu trực tiếp với checkbox chọn file cho AI đọc"""
    file_dropped_signal = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                files.append(file_path)
        if files:
            self.file_dropped_signal.emit(files)
            event.acceptProposedAction()


# ========================================================
# 2. WORKERS CHẠY NGẦM KHÔNG CHẶN GIAO DIỆN (QTHREAD)
# ========================================================
class ExtractionWorker(QThread):
    finished_signal = pyqtSignal(object, str)  # (co_data, error_msg)
    progress_signal = pyqtSignal(int, str)

    def __init__(self, api_key: str, file_paths: List[str], target_form: str = "EUR.1",
                 api_source: str = "official", api_base_url: str = "", model_name: str = ""):
        super().__init__()
        self.api_key = api_key
        self.file_paths = file_paths
        self.target_form = target_form
        self.api_source = api_source
        self.api_base_url = api_base_url
        self.model_name = model_name

    def run(self):
        try:
            def cb(pct, msg):
                self.progress_signal.emit(pct, msg)

            m_target = self.model_name or ("gemini-3.8-flash" if self.api_source == "apiz" else "gemini-3.8-flash")
            cb(10, f"Đang kết nối AI ({m_target})...")

            base_url = self.api_base_url.strip() if self.api_base_url else ""
            if (self.api_source == "apiz" or self.api_key.startswith("sk-")) and not base_url:
                base_url = "https://api.apiz.vn/v1"

            res = extract_co_data_from_files(
                api_key=self.api_key,
                file_paths=self.file_paths,
                target_form=self.target_form,
                api_source=self.api_source,
                api_base_url=base_url,
                model_name=m_target,
                progress_cb=cb
            )
            co_data = res[0] if isinstance(res, tuple) else res

            cb(95, "Đang chuẩn hóa dữ liệu, khóa đơn vị KILOGRAM...")
            cb(100, "Hoàn tất trích xuất thành công 100%!")
            self.finished_signal.emit(co_data, "")
        except Exception as e:
            traceback.print_exc()
            self.finished_signal.emit(None, str(e))


class ChatbotWorker(QThread):
    reply_signal = pyqtSignal(str, str)  # (reply_text, error_msg)

    def __init__(self, api_key: str, question: str, history: List[dict] = None,
                 api_source: str = "official", api_base_url: str = "", model_name: str = ""):
        super().__init__()
        self.api_key = api_key
        self.question = question
        self.history = history or []
        self.api_source = api_source
        self.api_base_url = api_base_url
        self.model_name = model_name

    def run(self):
        try:
            base_url = self.api_base_url.strip() if self.api_base_url else ""
            if (self.api_source == "apiz" or self.api_key.startswith("sk-")) and not base_url:
                base_url = "https://api.apiz.vn/v1"

            m_target = self.model_name or ("gemini-3.8-flash" if self.api_source == "apiz" else "gemini-3.8-flash")
            ans = ask_co_advisor(
                api_key=self.api_key,
                question=self.question,
                history=self.history,
                api_source=self.api_source,
                api_base_url=base_url,
                model_name=m_target
            )
            self.reply_signal.emit(ans, "")
        except Exception as e:
            self.reply_signal.emit("", str(e))


# ========================================================
# HỘP THOẠI HƯỚNG DẪN SỬ DỤNG CHO NGƯỜI MỚI BẮT ĐẦU
# ========================================================
# ========================================================
# HỘP THOẠI HƯỚNG DẪN ĐẶT TÊN CHỨNG TỪ (CUỘN MƯỢT MÀ, KHÔNG TRÀN MÀN HÌNH)
# ========================================================
class AttachmentNamingGuideDialog(QDialog):
    """Cửa sổ hướng dẫn quy tắc đặt tên chứng từ eCoSys với khung cuộn chuẩn tỷ lệ màn hình"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 Hướng Dẫn Đặt Tên Chứng Từ & Vị Trí Đính Kèm eCoSys")
        self.resize(880, 620)
        self.setMinimumSize(740, 500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # 1. Header Banner
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0078d4, stop:1 #0284c7);
                border-radius: 8px;
                padding: 12px 18px;
            }
            QLabel { color: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; }
        """)
        b_lay = QVBoxLayout(banner)
        b_lay.setContentsMargins(0, 0, 0, 0)
        b_lay.setSpacing(3)
        t = QLabel("📋 QUY TẮC ĐẶT TÊN CHỨNG TỪ ĐỂ ĐÍNH KÈM CHÍNH XÁC 100% LÊN ECOSYS")
        t.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        b_lay.addWidget(t)
        sub = QLabel("Extension v2.8.0 sẽ quét từ khóa trong tên file để tự động gán vào đúng ô quy định")
        sub.setStyleSheet("font-size: 12px; color: #e0f2fe;")
        b_lay.addWidget(sub)
        layout.addWidget(banner)

        # 2. Khung cuộn nội dung chi tiết
        browser = QTextBrowser()
        browser.setStyleSheet("""
            QTextBrowser {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 14px 18px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                color: #1e293b;
                line-height: 1.6;
            }
        """)

        html = """
        <style>
            .rule-card {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-left: 4px solid #0078d4;
                border-radius: 6px;
                padding: 10px 14px;
                margin-bottom: 12px;
            }
            .rule-title {
                font-size: 13.5px;
                font-weight: bold;
                color: #0f172a;
                margin-bottom: 4px;
            }
            .keyword-tag {
                background: #e0f2fe;
                color: #0284c7;
                font-weight: 600;
                padding: 2px 7px;
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
            .ecosys-pos {
                background: #f0fdf4;
                color: #166534;
                font-weight: 600;
                padding: 2px 7px;
                border-radius: 4px;
                font-size: 12px;
            }
            .example-box {
                color: #475569;
                font-size: 12px;
                margin-top: 4px;
            }
            .warning-card {
                background: #fffbeb;
                border: 1px solid #fde68a;
                border-radius: 8px;
                padding: 12px 16px;
                margin-top: 14px;
            }
            .author-card {
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 10px 16px;
                margin-top: 10px;
                font-size: 12px;
                color: #334155;
            }
        </style>

        <div class="rule-card" style="border-left-color: #0284c7;">
            <div class="rule-title">1️⃣ Bảng kê chi phí / BOM / Phụ lục theo Thông tư 05:</div>
            <div>• Từ khóa nhận diện: <span class="keyword-tag">bang ke</span>, <span class="keyword-tag">bangke</span>, <span class="keyword-tag">bom</span>, <span class="keyword-tag">phuluc</span></div>
            <div class="example-box">📁 Ví dụ: <code>bang ke WO_HL.pdf</code>, <code>bang_ke_chi_phi.pdf</code>, <code>BOM_EUR1.pdf</code></div>
            <div>• Vị trí tự động đính kèm: <span class="ecosys-pos">Dòng 1 bảng Document Proving (Bảng phụ lục TT 05)</span></div>
        </div>

        <div class="rule-card" style="border-left-color: #16a34a;">
            <div class="rule-title">2️⃣ Vận tải đơn (Bill of Lading - B/L / Sea Waybill):</div>
            <div>• Từ khóa nhận diện: <span class="keyword-tag">bill</span>, <span class="keyword-tag">bl</span>, <span class="keyword-tag">vandon</span>, <span class="keyword-tag">waybill</span></div>
            <div class="example-box">📁 Ví dụ: <code>bill.pdf</code>, <code>bill_tau.pdf</code>, <code>BL_Sea.pdf</code></div>
            <div>• Vị trí tự động đính kèm: <span class="ecosys-pos">Mục 21, 22 (TRANSPORT_INFO / Tài liệu vận tải đính kèm)</span></div>
        </div>

        <div class="rule-card" style="border-left-color: #7c3aed;">
            <div class="rule-title">3️⃣ Hóa đơn thương mại / Đơn đề nghị cấp C/O:</div>
            <div>• Từ khóa nhận diện: <span class="keyword-tag">inv</span>, <span class="keyword-tag">invoice</span>, <span class="keyword-tag">don</span>, <span class="keyword-tag">denghi</span></div>
            <div class="example-box">📁 Ví dụ: <code>don CO,inv.pdf</code>, <code>Commercial_Invoice.pdf</code>, <code>Invoice_HV60625.pdf</code></div>
            <div>• Vị trí tự động đính kèm: <span class="ecosys-pos">Mục 24 (Invoice attached) hoặc Dòng 4 bảng Document Proving</span></div>
        </div>

        <div class="rule-card" style="border-left-color: #ea580c;">
            <div class="rule-title">4️⃣ Hóa đơn VAT mua nguyên phụ liệu trong nước:</div>
            <div>• Từ khóa nhận diện: <span class="keyword-tag">vat</span> HOẶC <b>chính là SỐ HÓA ĐƠN</b></div>
            <div class="example-box">📁 Ví dụ: <code>00000457.pdf</code>, <code>vat_00000457.pdf</code>, <code>HD_457.pdf</code></div>
            <div>• Vị trí tự động đính kèm: <span class="ecosys-pos">Tự động gắn chính xác vào dòng Hóa đơn VAT tương ứng tại Mục 29, 30</span></div>
        </div>

        <div class="rule-card" style="border-left-color: #0891b2;">
            <div class="rule-title">5️⃣ Quy trình sản xuất ra sản phẩm:</div>
            <div>• Từ khóa nhận diện: <span class="keyword-tag">quytrinh</span>, <span class="keyword-tag">sanxuat</span>, <span class="keyword-tag">process</span></div>
            <div class="example-box">📁 Ví dụ: <code>quy trinh san xuat.pdf</code>, <code>process_fish.pdf</code></div>
            <div>• Vị trí tự động đính kèm: <span class="ecosys-pos">Dòng 2 bảng Document Proving (Bản mô tả quy trình sản xuất)</span></div>
        </div>

        <div class="rule-card" style="border-left-color: #4f46e5;">
            <div class="rule-title">6️⃣ Tờ khai hải quan nhập khẩu nguyên vật liệu:</div>
            <div>• Từ khóa nhận diện: <span class="keyword-tag">nhap</span> HOẶC <b>chính là SỐ TỜ KHAI</b></div>
            <div class="example-box">📁 Ví dụ: <code>TK_Nhap_1056789.pdf</code>, <code>1056789.pdf</code></div>
            <div>• Vị trí tự động đính kèm: <span class="ecosys-pos">Tự động gắn chính xác vào dòng Tờ khai NK tương ứng tại Mục 27, 28</span></div>
        </div>

        <div class="rule-card" style="border-left-color: #be185d;">
            <div class="rule-title">7️⃣ Tờ khai hải quan xuất khẩu sản phẩm:</div>
            <div>• Từ khóa nhận diện: <span class="keyword-tag">to khai xuat</span>, <span class="keyword-tag">tk_xuat</span>, <span class="keyword-tag">xuatkhau</span></div>
            <div class="example-box">📁 Ví dụ: <code>to khai xuat.pdf</code>, <code>TK_Xuat_235602.pdf</code></div>
            <div>• Vị trí tự động đính kèm: <span class="ecosys-pos">Mục 25 (Export declaration attached)</span></div>
        </div>

        <div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 6px; padding: 10px 14px; margin-top: 10px;">
            <b style="color: #166534;">💡 Mẹo tiện ích:</b> Bạn chỉ cần nhấn nút <b>"📁 Gom & Chuẩn hóa thư mục chứng từ"</b> tại Tab 4, phần mềm sẽ tự động quét, đổi tên toàn bộ file thành dạng chuẩn <code>01_BangKe...</code>, <code>02_Bill...</code> chỉ trong 1 giây!
        </div>

        <div class="warning-card">
            <b style="color: #92400e; font-size: 13px;">⚠️ CHÚ Ý QUAN TRỌNG VỀ TRÍ TUỆ NHÂN TẠO (AI):</b><br/>
            <span style="color: #78350f;">Trí tuệ nhân tạo (AI Gemini 3.8 Flash) chỉ mang tính chất <b>tham khảo và hỗ trợ nghiệp vụ</b>. Mọi quyết định, phê duyệt và kết quả kiểm tra cuối cùng <b>hoàn toàn do con người</b> rà soát trước khi nộp hồ sơ chính thức lên cơ quan chức năng.</span>
        </div>

        <div class="author-card">
            © <b>BẢN QUYỀN PHẦN MỀM VÀ PHÁT TRIỂN BỞI:</b> <b style="color: #0078d4;">Ngô Quốc Tiến</b> • Hotline / Zalo: <b style="color: #ea580c;">0905387808</b>
        </div>
        """
        browser.setHtml(html)
        layout.addWidget(browser, stretch=1)

        # 3. Nút Đóng
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_close = QPushButton("✅ Đã hiểu & Đóng")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                font-weight: bold;
                padding: 8px 24px;
                border-radius: 6px;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0067b8;
            }
        """)
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)

class UserGuideDialog(QDialog):
    """Cửa sổ hướng dẫn sử dụng toàn diện từ bước thêm chứng từ, AI đọc đến điền web eCoSys"""

    COMMON_CSS = """
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 13px;
            color: #1e293b;
            line-height: 1.6;
            background-color: #ffffff;
            margin: 0;
            padding: 16px 20px;
        }
        h2 {
            color: #0078d4;
            font-size: 16px;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 6px;
            margin-top: 4px;
            margin-bottom: 12px;
        }
        h3 {
            color: #0f172a;
            font-size: 13.5px;
            margin-top: 14px;
            margin-bottom: 6px;
        }
        h4 {
            color: #0369a1;
            font-size: 13px;
            margin-top: 8px;
            margin-bottom: 4px;
        }
        .card {
            background-color: #f8fafc;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 12px;
        }
        .card-highlight {
            background-color: #f0fdf4;
            border: 1px solid #86efac;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 12px;
        }
        .card-info {
            background-color: #f0f9ff;
            border: 1px solid #7dd3fc;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 12px;
        }
        .card-warn {
            background-color: #fffbeb;
            border: 1px solid #fde68a;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 12px;
        }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
        }
        .badge-blue { background-color: #e0f2fe; color: #0284c7; }
        .badge-green { background-color: #dcfce7; color: #166534; }
        .badge-purple { background-color: #f3e8ff; color: #7e22ce; }
        .badge-orange { background-color: #ffedd5; color: #c2410c; }
        .step-badge {
            background-color: #0078d4;
            color: #ffffff;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 12px;
            margin-right: 6px;
        }
        ul, ol {
            margin-top: 4px;
            margin-bottom: 8px;
            padding-left: 20px;
        }
        li {
            margin-bottom: 5px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
        }
        th {
            background-color: #f1f5f9;
            color: #1e293b;
            text-align: left;
            padding: 8px 10px;
            border: 1px solid #cbd5e1;
            font-size: 12px;
        }
        td {
            padding: 8px 10px;
            border: 1px solid #e2e8f0;
            font-size: 12px;
        }
        b {
            color: #0f172a;
        }
        code {
            background-color: #f1f5f9;
            color: #0369a1;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: Consolas, monospace;
            font-size: 12px;
            border: 1px solid #e2e8f0;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📖 Sổ Tay Hướng Dẫn Sử Dụng - eCoSys C/O AI (Gemini 3.8 Flash)")
        self.resize(980, 720)
        self.setMinimumSize(840, 600)
        # Khởi chạy Local Companion Stream Bridge siêu tốc cho chứng từ
        local_stream_server.start_local_stream_server()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Banner
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0078d4, stop:1 #0284c7);
                border-radius: 8px;
            }
            QLabel {
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
        banner_layout = QVBoxLayout(banner)
        banner_layout.setContentsMargins(16, 12, 16, 12)
        banner_layout.setSpacing(4)

        lbl_title = QLabel("📖 CẨM NANG HƯỚNG DẪN VẬN HÀNH eCoSys C/O AI")
        lbl_title.setStyleSheet("font-size: 17px; font-weight: bold; color: #ffffff;")
        banner_layout.addWidget(lbl_title)

        lbl_sub = QLabel("Quy trình thêm chứng từ, cơ chế AI Gemini 3.8 Flash đọc hiểu và các bước tự động điền form C/O trên eCoSys")
        lbl_sub.setStyleSheet("font-size: 12.5px; color: #e0f2fe;")
        banner_layout.addWidget(lbl_sub)

        layout.addWidget(banner)

        # Khung khuyến cáo pháp lý AI & Bản quyền tác giả
        disclaimer_banner = QFrame()
        disclaimer_banner.setStyleSheet("""
            QFrame {
                background-color: #fffbeb;
                border: 1px solid #fde68a;
                border-radius: 6px;
                padding: 9px 14px;
            }
            QLabel {
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
        db_lay = QVBoxLayout(disclaimer_banner)
        db_lay.setContentsMargins(0, 0, 0, 0)
        db_lay.setSpacing(3)
        lbl_ai_w = QLabel("⚠️ <b>CHÚ Ý QUAN TRỌNG VỀ AI:</b> AI chỉ mang tính tham khảo, mọi quyết định và kết quả đều do con người.")
        lbl_ai_w.setStyleSheet("color: #92400e; font-size: 12.5px;")
        db_lay.addWidget(lbl_ai_w)
        lbl_author = QLabel("© <b>Bản quyền phần mềm & Phát triển bởi:</b> Ngô Quốc Tiến • Hotline/Zalo: <b>0905387808</b>")
        lbl_author.setStyleSheet("color: #1e3a8a; font-size: 12px;")
        db_lay.addWidget(lbl_author)
        layout.addWidget(disclaimer_banner)

        # Tab Widget cho các chủ đề hướng dẫn
        guide_tabs = QTabWidget()
        guide_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                background: #ffffff;
                border-radius: 6px;
                top: -1px;
            }
            QTabBar::tab {
                background: #f1f5f9;
                color: #475569;
                padding: 9px 18px;
                margin-right: 3px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
                font-size: 12.5px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-top: 3px solid #0078d4;
                color: #0078d4;
            }
        """)

        # Tab 1: Bắt đầu nhanh (5 bước)
        guide_tabs.addTab(self.create_tab_quickstart(), "🚀 1. Quy trình 5 bước")

        # Tab 2: Thêm chứng từ & AI đọc thế nào
        guide_tabs.addTab(self.create_tab_documents_ai(), "📁 2. Chứng từ & Cách AI đọc")

        # Tab 3: Chuẩn hóa dữ liệu & Khóa Kg
        guide_tabs.addTab(self.create_tab_standards(), "⚙️ 3. Chuẩn hóa & Khóa KILOGRAM")

        # Tab 4: Tự động điền eCoSys (Extension)
        guide_tabs.addTab(self.create_tab_extension(), "🌐 4. Điền Web eCoSys (Extension)")

        # Tab 5: Trợ lý Copilot & Phím tắt
        guide_tabs.addTab(self.create_tab_tips_copilot(), "🤖 5. Trợ lý Copilot & Phím tắt")

        # Tab 6: Nghiệp vụ SC & Hồ sơ IUU
        guide_tabs.addTab(self.create_tab_sc_iuu(), "⚓ 6. Nghiệp vụ SC & Hồ sơ IUU")

        layout.addWidget(guide_tabs, stretch=1)

        # Footer Button
        footer_layout = QHBoxLayout()
        footer_tip = QLabel("💡 Mẹo: Bạn có thể nhấn phím <b>F1</b> bất kỳ lúc nào để mở lại cẩm nang này.")
        footer_tip.setStyleSheet("color: #64748b; font-size: 12px;")
        footer_layout.addWidget(footer_tip)
        footer_layout.addStretch()

        btn_update = QPushButton("🔄 Cập nhật GitHub")
        btn_update.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #0369a1;
                font-weight: 600;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 12.5px;
                border: 1px solid #cbd5e1;
            }
            QPushButton:hover {
                background-color: #e0f2fe;
            }
        """)
        btn_update.clicked.connect(self.open_github_updater)
        footer_layout.addWidget(btn_update)

        btn_close = QPushButton("✅ Đã hiểu & Bắt đầu làm việc")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                font-weight: bold;
                padding: 8px 24px;
                border-radius: 6px;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0067b8;
            }
        """)
        btn_close.clicked.connect(self.accept)
        footer_layout.addWidget(btn_close)

        layout.addLayout(footer_layout)

    def open_github_updater(self):
        try:
            from github_updater import GitHubUpdateDialog
            dlg = GitHubUpdateDialog(self)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi cập nhật", f"Không thể mở trình cập nhật: {e}")

    def _make_browser(self, html_content: str) -> QTextBrowser:
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(f"<html><head><style>{self.COMMON_CSS}</style></head><body>{html_content}</body></html>")
        browser.setStyleSheet("border: none; background-color: #ffffff;")
        return browser

    def create_tab_quickstart(self) -> QTextBrowser:
        content = """
        <h2>🚀 Quy Trình 5 Bước Vận Hành Dành Cho Người Mới Bắt Đầu</h2>
        <div class="card-info">
            <b>Sơ đồ tóm tắt quy trình hoàn tất 1 bộ hồ sơ C/O:</b><br/>
            <code style="font-size: 12.5px; color: #0369a1;">
            [1. Cấu hình & Chọn Mẫu C/O] ➔ [2. Nạp Chứng từ PDF/Ảnh] ➔ [3. AI Đọc & Trích xuất] ➔ [4. Kiểm tra Dữ liệu] ➔ [5. Điền eCoSys (Extension)]
            </code>
        </div>

        <div class="card">
            <h3><span class="step-badge">1</span> Bước 1: Cấu hình API và Chọn Mẫu C/O</h3>
            <ul>
                <li><b>Nguồn API:</b> Phần mềm hỗ trợ cả <b>Google Gemini Official</b> (dán key bắt đầu bằng <code>AIzaSy...</code>) hoặc <b>APIZ Vietnam Gateway</b> (dán key bắt đầu bằng <code>sk-...</code> với Base URL <code>https://api.apiz.vn/v1</code>). Phần mềm tự động nhận diện tiền tố key.</li>
                <li><b>Model AI:</b> Hệ thống đã khóa cố định <code>gemini-3.8-flash</code> - thế hệ AI thị giác đa phương thức (Multimodal Vision) tốc độ cao và chuẩn xác nhất.</li>
                <li><b>Mẫu C/O:</b> Chọn đúng Form C/O dự kiến xin cấp (ví dụ: EUR.1 cho Châu Âu, Form D cho ASEAN, Form E cho Trung Quốc, AK/VK cho Hàn Quốc, CPTPP...).</li>
            </ul>
        </div>

        <div class="card">
            <h3><span class="step-badge">2</span> Bước 2: Thêm Chứng từ Hồ sơ vào Phần mềm</h3>
            <ul>
                <li>Kéo thả trực tiếp các tệp chứng từ (PDF hoặc Ảnh PNG/JPG) vào khung danh sách bên trái hoặc nhấn nút <b>➕ Thêm...</b></li>
                <li>Tích chọn <code>[x]</code> cho những file bạn muốn AI phân tích (xem chi tiết tại Tab 2).</li>
                <li>Có thể dùng nút chọn nhanh <b>🎯 Chỉ Đơn + Inv</b> (lấy nhanh thông tin chính) hoặc <b>☑️ AI đọc hết</b> (đối chiếu toàn diện mọi chứng từ).</li>
            </ul>
        </div>

        <div class="card">
            <h3><span class="step-badge">3</span> Bước 3: Kích hoạt Trích xuất Dữ liệu bằng AI</h3>
            <ul>
                <li>Nhấn nút màu xanh đậm <b>⚡ BẮT ĐẦU TRÍCH XUẤT BẰNG AI</b> ở cột bên trái.</li>
                <li>AI Gemini 3.8 Flash sẽ quét qua từng trang của các chứng từ đã tích chọn, trích xuất hơn 30 trường dữ liệu theo chuẩn eCoSys (Doanh nghiệp, Vận tải, Danh sách hàng hóa, Tờ khai nhập, Hóa đơn VAT).</li>
                <li>Thời gian xử lý trung bình từ 3 - 8 giây tùy số lượng trang tài liệu.</li>
            </ul>
        </div>

        <div class="card">
            <h3><span class="step-badge">4</span> Bước 4: Kiểm tra và Hiệu chỉnh Dữ liệu</h3>
            <ul>
                <li>Kiểm tra thông tin trên các Tab làm việc (Tab 1: Doanh nghiệp, Tab 2: Vận tải, Tab 3: Hàng hóa, Tab 4: Tệp đính kèm).</li>
                <li>Cột <b>Đơn vị tính</b> tại Tab 3 đã được khóa cứng chuẩn <code>KILOGRAM</code> theo quy định eCoSys.</li>
                <li>Các số Tờ khai nhập và Hóa đơn VAT tại Tab 2 đã được tự động bóc tách thành từng dòng riêng kèm ngày tương ứng.</li>
                <li>Có thể chuyển sang <b>Tab 7 (Xem trước chứng từ)</b> để lật từng trang đối chiếu với hồ sơ gốc.</li>
            </ul>
        </div>

        <div class="card-highlight">
            <h3><span class="step-badge">5</span> Bước 5: Sao chép JSON và Tự động Điền lên Web eCoSys</h3>
            <ul>
                <li>Nhấn nút xanh nổi bật <b>📋 SAO CHÉP JSON (DÁN VÀO EXTENSION)</b> ở góc trên bên phải.</li>
                <li>Mở trình duyệt Chrome đã cài tiện ích <b>eCoSys C/O Form Auto-filler v2.6.0</b> ➔ Đăng nhập <code>ecosys.gov.vn</code> ➔ Vào trang Khai báo C/O điện tử.</li>
                <li>Nhấp vào biểu tượng Extension ➔ Nhấn <code>Ctrl + V</code> để dán dữ liệu JSON ➔ Bấm <b>"Điền toàn bộ hồ sơ"</b>. Form khai báo trên web sẽ được điền hoàn tất trong 2 giây!</li>
            </ul>
        </div>
        """
        return self._make_browser(content)

    def create_tab_documents_ai(self) -> QTextBrowser:
        content = """
        <h2>📁 Danh Mục Chứng Từ & Cơ Chế AI Gemini 3.8 Flash Đọc Hiểu</h2>

        <div class="card-info">
            <b>💡 Nguyên tắc cơ bản:</b> Bộ chứng từ đính kèm được quy định chặt chẽ trong <i>Đơn đề nghị cấp C/O (Mẫu 04)</i> theo Thông tư 05/2018/TT-BCT của Bộ Công Thương. AI đọc trực tiếp file PDF/ảnh gốc để trích xuất số liệu chuẩn xác nhất.
        </div>

        <h3>1. Danh mục các chứng từ trong bộ hồ sơ xin cấp C/O</h3>
        <table>
            <tr>
                <th style="width: 25%;">Loại chứng từ</th>
                <th style="width: 48%;">Mục đích & Dữ liệu AI sẽ trích xuất</th>
                <th style="width: 27%;">Vị trí Slot eCoSys</th>
            </tr>
            <tr>
                <td><b>Đơn đề nghị cấp C/O (Mẫu 04)</b></td>
                <td>Thông tin người xuất khẩu, người nhập khẩu, số Invoice, danh mục chứng từ đính kèm theo đơn.</td>
                <td><span class="badge badge-blue">Slot 1: Đơn đề nghị</span></td>
            </tr>
            <tr>
                <td><b>Hóa đơn thương mại (Invoice)</b></td>
                <td>Số HĐ, ngày lập, danh mục mặt hàng, đơn giá, tổng tiền, điều kiện giao hàng (Incoterms: FOB, CIF...).</td>
                <td><span class="badge badge-blue">Slot 2: Hóa đơn TM</span></td>
            </tr>
            <tr>
                <td><b>Tờ khai hải quan xuất khẩu</b></td>
                <td>Số tờ khai xuất khẩu, ngày đăng ký hải quan, mã phân loại kiểm tra (luồng xanh/vàng/đỏ).</td>
                <td><span class="badge badge-blue">Slot 3: Tờ khai XK</span></td>
            </tr>
            <tr>
                <td><b>Vận đơn (B/L / Sea Waybill / AWB)</b></td>
                <td>Số vận đơn B/L, ngày phát hành, tên tàu, số chuyến, cảng bốc hàng (POL), cảng dỡ hàng (POD).</td>
                <td><span class="badge badge-blue">Slot 4: Vận đơn</span></td>
            </tr>
            <tr>
                <td><b>Bảng kê hàm lượng / Chi phí BOM</b></td>
                <td>Tỷ lệ nguyên liệu nội địa, nguyên liệu nhập khẩu, chi phí nhân công, tiêu chí xuất xứ (WO, CTC, RVC...).</td>
                <td><span class="badge badge-blue">Slot 5: Bảng kê chi phí</span></td>
            </tr>
            <tr>
                <td><b>Tờ khai hải quan nhập khẩu NVL</b></td>
                <td>Các số tờ khai nhập khẩu nguyên vật liệu đầu vào và ngày tờ khai tương ứng cấu thành sản phẩm.</td>
                <td><span class="badge badge-blue">Slot 6: Tờ khai NK</span></td>
            </tr>
            <tr>
                <td><b>Hóa đơn GTGT (VAT) mua NVL</b></td>
                <td>Các số hóa đơn GTGT mua nguyên phụ liệu nội địa kèm ngày lập hóa đơn tương ứng.</td>
                <td><span class="badge badge-blue">Slot 7: Hóa đơn VAT</span></td>
            </tr>
            <tr>
                <td><b>Quy trình sản xuất / Bản giải trình</b></td>
                <td>Mô tả các công đoạn chế biến, gia công đáp ứng quy tắc xuất xứ cụ thể mặt hàng (PSR).</td>
                <td><span class="badge badge-blue">Slot 8: Quy trình SX</span></td>
            </tr>
        </table>

        <h3>2. Cơ chế AI đọc: Ý nghĩa ô tích [x] vs [ ]</h3>
        <div class="card">
            <ul>
                <li><b style="color: #0078d4;">[x] Tệp được tích chọn:</b> File này sẽ được chuyển thành ảnh độ phân giải cao và nạp trực tiếp vào mô hình <b>Gemini 3.8 Flash Vision</b> để trích xuất dữ liệu, nhận diện bảng số liệu và văn bản.</li>
                <li><b style="color: #64748b;">[ ] Tệp bỏ tích:</b> File này <i>KHÔNG</i> gửi lên AI (giúp tiết kiệm token và tăng tốc độ xử lý), nhưng vẫn được giữ trong danh sách hồ sơ để đính kèm lên cổng eCoSys sau này.</li>
            </ul>
        </div>

        <h3>3. Hai nút chọn nhanh bộ lọc AI</h3>
        <div class="card">
            <ul>
                <li><b>🎯 Nút "Chỉ Đơn + Inv":</b> Hệ thống chỉ tích chọn 2 tệp cốt lõi là <i>Đơn đề nghị Mẫu 04</i> và <i>Commercial Invoice</i>. Phù hợp khi bạn cần trích xuất siêu tốc (2-3 giây) thông tin người xuất/nhập khẩu và danh sách hàng hóa.</li>
                <li><b>☑️ Nút "AI đọc hết":</b> Tích chọn toàn bộ các file trong danh sách. AI sẽ thực hiện đối chiếu chéo (Cross-check) toàn diện giữa Đơn, Invoice, B/L, Bảng kê BOM và Tờ khai xuất để điền trọn vẹn mọi trường dữ liệu.</li>
            </ul>
        </div>

        <h3>4. Xem trước chứng từ đối chiếu (Tab 7)</h3>
        <div class="card-highlight">
            <ul>
                <li>Nhấp chuột vào bất kỳ tên file nào trong danh sách bên trái, hệ thống sẽ tự động chuyển sang <b>Tab 7 (Xem trước Chứng từ)</b> và hiển thị trang đầu tiên của file đó.</li>
                <li>Sử dụng các nút <b>◀ Trang trước</b>, <b>Trang sau ▶</b>, hoặc các nút phóng to <b>🔍+</b>, thu nhỏ <b>🔍-</b> để soi rõ mã HS, số hóa đơn, con dấu xác nhận.</li>
            </ul>
        </div>
        """
        return self._make_browser(content)

    def create_tab_standards(self) -> QTextBrowser:
        content = """
        <h2>⚙️ Chuẩn Hóa Dữ Liệu Theo Quy Định eCoSys Bộ Công Thương</h2>

        <div class="card-highlight">
            <h3>🛡️ 1. Khóa Cứng Đơn Vị Tính KILOGRAM Chuẩn Hóa</h3>
            <p><b>Quy định eCoSys:</b> Hệ thống dịch vụ công eCoSys của Bộ Công Thương yêu cầu đơn vị tính số lượng/trọng lượng đối với phần lớn các mẫu C/O ưu đãi (EUR.1, D, E, AK, VK, CPTPP...) phải thống nhất là <b>KILOGRAM</b> (hoặc KGM).</p>
            <p><b>Giải pháp trong phần mềm:</b> Cột "Đơn vị tính" trong bảng Danh sách hàng hóa (Tab 3) đã được <b>khóa cứng cố định là KILOGRAM</b>. Bất kể trên hóa đơn gốc ghi là KG, KGS, Kilogram, kgs... khi trích xuất vào form đều được quy chuẩn hóa tự động, triệt tiêu hoàn toàn lỗi lệch đơn vị khi nộp hồ sơ.</p>
        </div>

        <div class="card">
            <h3>🚢 2. Bảng Đa Dòng Tờ Khai Nhập Khẩu Nguyên Liệu (Tab 2)</h3>
            <p><b>Thực tế nghiệp vụ:</b> Trong bảng kê BOM, một sản phẩm xuất khẩu thường được sản xuất từ nhiều nguyên vật liệu nhập khẩu thuộc nhiều tờ khai hải quan khác nhau.</p>
            <p><b>Cách thể hiện trên Web eCoSys:</b> Mỗi tờ khai nhập khẩu được yêu cầu nhập thành <b>1 dòng riêng biệt</b> gồm <i>Số tờ khai</i> và <i>Ngày tờ khai</i> (định dạng dd/MM/yyyy).</p>
            <p><b>Hỗ trợ của phần mềm:</b></p>
            <ul>
                <li>AI tự động bóc tách từng số tờ khai nhập kèm ngày tương ứng thành từng hàng độc lập trong bảng tại Tab 2.</li>
                <li>Hỗ trợ các nút <b>➕ Thêm dòng</b> và <b>➖ Xóa dòng</b> để người dùng bổ sung hoặc xóa bớt nhanh chóng.</li>
            </ul>
        </div>

        <div class="card">
            <h3>🧾 3. Bảng Đa Dòng Hóa Đơn VAT Mua Nguyên Liệu Nội Địa (Tab 2)</h3>
            <p><b>Thực tế nghiệp vụ:</b> Tương tự tờ khai nhập, doanh nghiệp có thể mua nguyên phụ liệu trong nước từ nhiều Hóa đơn GTGT (VAT) khác nhau, mỗi hóa đơn có thể có nhiều dòng hàng.</p>
            <p><b>Cách thể hiện trên Web eCoSys:</b> Mỗi hóa đơn GTGT sẽ được thể hiện thành <b>1 dòng riêng</b> gồm <i>Số hóa đơn</i> và <i>Ngày hóa đơn</i> (định dạng dd/MM/yyyy).</p>
            <p><b>Hỗ trợ của phần mềm:</b> Tự động nhận diện và phân tách mỗi hóa đơn VAT thành 1 dòng tương ứng kèm ngày, khớp chuẩn 100% với giao diện nhập liệu của hệ thống eCoSys.</p>
        </div>

        <div class="card-info">
            <h3>📎 4. Phân Loại 10 Slot Tệp Đính Kèm Tự Động (Tab 4)</h3>
            <p>Tại Tab 4, phần mềm cung cấp nút <b>🔍 Tự động nhận diện loại chứng từ</b>. Thuật toán thông minh sẽ đọc nội dung văn bản bên trong từng file (nhận diện từ khóa chuyên môn như "COMMERCIAL INVOICE", "BILL OF LADING", "ĐƠN ĐỀ NGHỊ", "TỜ KHAI", "BẢNG KÊ", "HÓA ĐƠN GIÁ TRỊ GIA TĂNG"...) để gán đúng từng file vào 10 vị trí upload của Bộ Công Thương mà không cần người dùng phải đổi tên file thủ công.</p>
        </div>
        """
        return self._make_browser(content)

    def create_tab_extension(self) -> QTextBrowser:
        content = """
        <h2>🌐 Tự Động Điền Dữ Liệu Lên Cổng eCoSys Bằng Extension Chrome</h2>

        <div class="card-info">
            <b>Tiện ích eCoSys C/O Form Auto-filler v2.6.0:</b> Được thiết kế chuyên biệt để đồng bộ dữ liệu JSON từ phần mềm Desktop sang biểu mẫu web trên <code>https://ecosys.gov.vn</code> một cách an toàn, nhanh chóng và chính xác tuyệt đối.
        </div>

        <h3>Quy trình 4 bước điền web siêu tốc:</h3>

        <div class="card">
            <h4><span class="step-badge">1</span> Bước 1: Sao chép dữ liệu JSON</h4>
            <p>Sau khi AI trích xuất xong và bạn đã kiểm tra qua các Tab, nhấp vào nút màu xanh đậm ở góc trên bên phải:</p>
            <p><b>📋 SAO CHÉP JSON (DÁN VÀO EXTENSION)</b></p>
            <p>Toàn bộ thông tin từ Tab 1 (Doanh nghiệp), Tab 2 (Vận tải, Tờ khai nhập, HĐ VAT) và Tab 3 (Danh sách hàng hóa) sẽ được tự động tổng hợp thành cấu trúc JSON chuẩn và lưu vào bộ nhớ tạm (Clipboard).</p>
        </div>

        <div class="card">
            <h4><span class="step-badge">2</span> Bước 2: Đăng nhập Cổng eCoSys</h4>
            <p>Mở trình duyệt Google Chrome (hoặc Edge, Cốc Cốc) ➔ Truy cập địa chỉ <code>https://ecosys.gov.vn</code> ➔ Đăng nhập bằng tài khoản doanh nghiệp của bạn.</p>
        </div>

        <div class="card">
            <h4><span class="step-badge">3</span> Bước 3: Mở Form Khai Báo C/O Điện Tử</h4>
            <p>Vào menu <b>Khai báo C/O điện tử</b> ➔ Chọn Form C/O tương ứng với hồ sơ (ví dụ: Mẫu EUR.1) ➔ Bấm nút <b>"Tạo mới"</b> hoặc <b>"Thêm hồ sơ"</b>.</p>
        </div>

        <div class="card-highlight">
            <h4><span class="step-badge">4</span> Bước 4: Dán JSON và Điền Tự Động</h4>
            <ul>
                <li>Nhấp chuột vào biểu tượng <b>eCoSys Auto-filler</b> trên thanh công cụ tiện ích của Chrome (góc trên bên phải trình duyệt).</li>
                <li>Bấm phím <code>Ctrl + V</code> để dán chuỗi JSON đã sao chép từ phần mềm.</li>
                <li>Bấm nút màu xanh <b>"🚀 Điền toàn bộ hồ sơ"</b>.</li>
            </ul>
            <p><b>Kết quả:</b> Toàn bộ thông tin từ Doanh nghiệp, Vận tải, Danh sách hàng hóa, Bảng tờ khai nhập, Bảng hóa đơn VAT sẽ được tự động điền vào các ô trên web trong <b>2 giây</b> mà không cần gõ thủ công từng chữ!</p>
        </div>

        <div class="card-warn">
            <b>⚠️ Lưu ý quan trọng:</b>
            <ul>
                <li>Nếu trình duyệt chưa cài Extension, hãy vào thư mục <code>ecosys_chrome_extension</code> trong thư mục dự án ➔ Mở <code>chrome://extensions</code> ➔ Bật "Chế độ dành cho nhà phát triển" ➔ Chọn "Tải tiện ích đã giải nén".</li>
                <li>Sau khi extension điền tự động, hãy rà soát lại 1 lượt trên web trước khi cắm USB Token để ký số và nộp hồ sơ.</li>
            </ul>
        </div>
        """
        return self._make_browser(content)

    def create_tab_tips_copilot(self) -> QTextBrowser:
        content = """
        <h2>🤖 Trợ Lý AI Copilot Nghiệp Vụ & Phím Tắt Tiện Ích</h2>

        <div class="card">
            <h3>🤖 1. Trợ Lý AI Copilot Nghiệp Vụ C/O (Tab 6)</h3>
            <p>Khi gặp các tình huống nghiệp vụ phức tạp hoặc quy định mới, bạn hãy chuyển sang <b>Tab 6 (Trợ lý AI Copilot)</b> để được hỗ trợ 24/7 trực tiếp:</p>
            <ul>
                <li><b>Tư vấn tiêu chí xuất xứ:</b> Giải thích và hướng dẫn xác định WO (Xuất xứ thuần túy), CTC (Chuyển đổi mã HS ở cấp 2 số CC, 4 số CTH, 6 số CTSH), RVC 40% (Hàm lượng giá trị khu vực), De Minimis (Tỷ lệ không đáp ứng CTC).</li>
                <li><b>Quy tắc vận chuyển trực tiếp:</b> Giải thích quy định hàng hóa đi qua nước thứ ba (Singapore, Hong Kong, Malaysia) cần chứng từ gì để không làm mất xuất xứ (chứng từ lưu kho hải quan, vận đơn suốt qua cảnh).</li>
                <li><b>Xử lý hồ sơ bị từ chối:</b> Nhập lý do cán bộ Bộ Công Thương từ chối để AI gợi ý cách giải trình, bổ sung tài liệu chính xác nhất.</li>
                <li><b>Khắc phục lỗi Chữ ký số USB Token:</b> Hướng dẫn khắc phục lỗi không nhận Token ký số Bit4id, SafeNet, Viettel-CA, VNPT-CA khi ký nộp hồ sơ trên eCoSys.</li>
            </ul>
        </div>

        <div class="card-info">
            <h3>⌨️ 2. Bảng Phím Tắt Nhanh</h3>
            <table>
                <tr>
                    <th style="width: 25%;">Phím tắt</th>
                    <th style="width: 75%;">Chức năng</th>
                </tr>
                <tr>
                    <td><code>F1</code></td>
                    <td>Mở sổ tay Cẩm nang Hướng dẫn Sử dụng này bất cứ lúc nào.</td>
                </tr>
                <tr>
                    <td><code>Ctrl + C</code></td>
                    <td>Sao chép nhanh nội dung ô nhập liệu hoặc ô JSON.</td>
                </tr>
                <tr>
                    <td><code>Ctrl + V</code></td>
                    <td>Dán nhanh API Key hoặc dữ liệu vào ô nhập.</td>
                </tr>
                <tr>
                    <td><code>Enter</code> (tại Chatbot)</td>
                    <td>Gửi câu hỏi nghiệp vụ tới Trợ lý AI Copilot.</td>
                </tr>
            </table>
        </div>

        <div class="card">
            <h3>💡 3. Các Mẹo Nhỏ Tiết Kiệm Thời Gian</h3>
            <ul>
                <li><b>Nút 🧪 Nạp dữ liệu mẫu:</b> Nhấn nút này ở góc trên để nạp ngay bộ dữ liệu thử nghiệm đầy đủ từ <code>sample_data.json</code> giúp làm quen với toàn bộ giao diện và luồng dữ liệu.</li>
                <li><b>Nút 👁️ Hiện/Ẩn API Key:</b> Bấm biểu tượng con mắt cạnh ô API Key để kiểm tra lại chuỗi khóa bí mật đã nhập.</li>
                <li><b>Phân biệt Key API:</b>
                    <ul>
                        <li>Nếu key bắt đầu bằng <code>AIzaSy...</code>: Chọn nguồn <b>Google Gemini Official</b>.</li>
                        <li>Nếu key bắt đầu bằng <code>sk-...</code>: Chọn nguồn <b>APIZ Vietnam Gateway</b> (Base URL <code>https://api.apiz.vn/v1</code>). Phần mềm tự động nhận diện khi bạn dán key.</li>
                    </ul>
                </li>
            </ul>
        </div>
        """
        return self._make_browser(content)

    def create_tab_sc_iuu(self) -> QTextBrowser:
        content = """
        <h2>⚓ Nghiệp Vụ Đối Chiếu SC Cảng Cá & Thẩm Định Hồ Sơ IUU Thủy Sản</h2>

        <div class="card-info">
            <b>💡 Mục đích nghiệp vụ:</b> Thẩm định và đối chiếu tính hợp pháp của nguyên liệu thủy sản khai thác giữa <b>Bản scan Giấy xác nhận SC gốc (Mẫu 01 Cảng cá)</b> và <b>File Excel xuất từ Phần mềm sản xuất (PMSX - Phụ lục 02a)</b> nhằm chống khai thác IUU và phục vụ cấp Giấy chứng nhận xuất xứ C/O Mẫu EUR.1 xuất khẩu.
        </div>

        <h3>1. Quy trình đối chiếu tự động 3 bước</h3>
        <div class="card">
            <ol>
                <li><b>Bước 1:</b> Chọn file PDF Scan SC gốc (hoặc thư mục chứa toàn bộ các file SC cần đối chiếu) và chọn file Excel XNNL từ PMSX.</li>
                <li><b>Bước 2:</b> Bấm <b>🚀 BẮT ĐẦU ĐỐI CHIẾU & XỬ LÝ TỰ ĐỘNG</b>. AI Gemini 3.8 Flash Vision và engine RapidOCR sẽ quét bóc tách toàn bộ danh sách tàu cá trên Giấy SC gốc, so khớp với từng dòng tàu trong Excel.</li>
                <li><b>Bước 3:</b> Xem 5 Thẻ KPI thống kê số liệu và bấm mở <b>Báo Cáo Đối Chiếu (.xlsx)</b> hoặc <b>File XNNL Chuẩn Hóa (.xlsx)</b>.</li>
            </ol>
        </div>

        <h3>2. Các lỗi sai lệch thường gặp và cách xử lý</h3>
        <div class="card">
            <ul>
                <li><b style="color: #b91c1c;">Sai tên Chủ tàu / Thuyền trưởng:</b> Thường do tàu được mua bán chuyển nhượng nhưng chưa sang tên giấy phép, hoặc chủ tàu thuê thuyền trưởng khác điều khiển. Phần mềm tự động đề xuất sửa tên theo SC gốc để nộp hồ sơ.</li>
                <li><b style="color: #b91c1c;">Sai số Giấy phép khai thác (GPKTTS) hoặc hết hạn:</b> Giấy phép khai thác phải còn hiệu lực trong suốt thời gian chuyến biển. Nếu sai lệch, cần kiểm tra lại ngày cấp gia hạn tại Chi cục Thủy sản.</li>
                <li><b style="color: #b45309;">Trùng tàu và cùng ngày lên cá:</b> Nếu 1 tàu cập cảng/lên cá cùng ngày và phát sinh nhiều dòng hàng trên PMSX, phần mềm tự động bật quy tắc <b>Gộp lượng (Aggregation Rule)</b> để cộng dồn khối lượng thành 1 dòng duy nhất theo chuẩn quy định.</li>
            </ul>
        </div>

        <div class="card-highlight">
            <h3>🔗 3. Mối liên kết giữa SC và Khai báo C/O eCoSys</h3>
            <p>Sau khi đã đối chiếu SC và tạo ra File XNNL chuẩn hóa, số liệu khối lượng và giá trị này sẽ được đưa vào <b>Bảng kê chi phí BOM (Mục 5)</b> và <b>Hóa đơn VAT (Mục 7)</b> tại Phân hệ Khai báo C/O eCoSys để xin cấp C/O Mẫu EUR.1 với tiêu chí <b>WO (Xuất xứ thuần túy)</b>.</p>
        </div>
        """
        return self._make_browser(content)


# ========================================================
# 3. ỨNG DỤNG CHÍNH: BỐ CỤC BẢN GỐC NÂNG CẤP HIỆN ĐẠI
# ========================================================
class COExtractorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("eCoSys AI - Trợ lý Trích xuất Chứng từ Khai báo C/O (Bộ Công Thương) • Gemini 3.8 Flash")
        self.resize(1360, 850)
        self.setMinimumSize(1080, 700)

        self.selected_files = []
        self.current_co_data = CODeclarationData()
        self.worker: Optional[ExtractionWorker] = None
        self.chat_worker: Optional[ChatbotWorker] = None
        self.chat_history: List[dict] = []

        # Tích hợp PDF Inspector
        self.inspector_doc: Optional[fitz.Document] = None
        self.inspector_page = 0
        self.inspector_zoom = 1.0

        # Khởi chạy Local Companion Stream Bridge siêu tốc cho chứng từ
        local_stream_server.start_local_stream_server()
        self.init_ui()
        self.load_saved_config()

    def init_ui(self):
        # STYLESHEET HIỆN ĐẠI, NỔI BẬT VÀ SANG TRỌNG (Windows 11 Fluent Aesthetic)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f1f5f9;
            }
            QLabel {
                font-family: 'Segoe UI', Arial, sans-serif;
                color: #1e293b;
                font-size: 13px;
            }
            QGroupBox {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 14px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #0078d4;
            }
            QLineEdit, QComboBox, QTextEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: #ffffff;
                selection-background-color: #0078d4;
                font-family: 'Segoe UI', Arial;
                font-size: 12.5px;
                color: #0f172a;
            }
            QLineEdit:hover, QComboBox:hover, QTextEdit:hover {
                border: 1px solid #94a3b8;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 2px solid #0078d4;
                background-color: #ffffff;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: 600;
                font-size: 12.5px;
                color: #334155;
                font-family: 'Segoe UI', Arial;
            }
            QPushButton:hover {
                background-color: #f8fafc;
                border-color: #94a3b8;
                color: #0f172a;
            }
            QPushButton#btn_extract {
                background-color: #0078d4;
                color: #ffffff;
                font-weight: bold;
                border: none;
                font-size: 13.5px;
                padding: 11px 18px;
                border-radius: 6px;
            }
            QPushButton#btn_extract:hover {
                background-color: #0067b8;
            }
            QPushButton#btn_extract:disabled {
                background-color: #94a3b8;
            }
            QPushButton#btn_copy_json {
                background-color: #107c41;
                color: #ffffff;
                font-weight: bold;
                border: none;
                font-size: 13px;
                padding: 8px 18px;
                border-radius: 6px;
            }
            QPushButton#btn_copy_json:hover {
                background-color: #0b6a37;
            }
            QTableWidget {
                border: 1px solid #cbd5e1;
                gridline-color: #e2e8f0;
                background-color: #ffffff;
                alternate-background-color: #f8fafc;
                border-radius: 6px;
                font-size: 12px;
                selection-background-color: #e0f2fe;
                selection-color: #0369a1;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #1e293b;
                font-weight: bold;
                border: 1px solid #e2e8f0;
                padding: 6px 8px;
                font-size: 12px;
            }
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                background: #ffffff;
                border-radius: 8px;
                top: -1px;
            }
            QTabBar::tab {
                background: #e2e8f0;
                color: #475569;
                padding: 9px 18px;
                margin-right: 3px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
                font-size: 12.5px;
            }
            QTabBar::tab:hover {
                background: #cbd5e1;
                color: #0f172a;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-top: 3px solid #0078d4;
                color: #0078d4;
                font-weight: bold;
            }
            QListWidget {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background: #ffffff;
                font-size: 12px;
            }
            QScrollBar:vertical {
                border: none;
                background: #f1f5f9;
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                min-height: 25px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # ========================================================
        # CỘT TRÁI: ĐIỀU KHIỂN & CHỨNG TỪ ĐẦU VÀO (~330px gọn gàng)
        # ========================================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # 1. Chọn Mẫu C/O Khai Báo (Bộ Công Thương)
        form_group = QGroupBox("1. Mẫu C/O Khai báo")
        form_layout = QVBoxLayout(form_group)
        form_layout.setContentsMargins(10, 8, 10, 8)
        form_layout.setSpacing(6)

        self.combo_form = QComboBox()
        self.combo_form.setStyleSheet("font-weight: bold; font-size: 13px; padding: 6px 10px; color: #0078d4;")
        self.combo_form.addItems([
            "EUR.1 (Việt Nam - EU)",
            "D (ASEAN - ATIGA)",
            "E (ASEAN - Trung Quốc)",
            "AK (ASEAN - Hàn Quốc)",
            "VK (Việt Nam - Hàn Quốc)",
            "VJ (Việt Nam - Nhật Bản)",
            "AJ (ASEAN - Nhật Bản)",
            "CPTPP (Hiệp định CPTPP)",
            "AANZ (ASEAN - Úc - New Zealand)",
            "B (Không ưu đãi - Thị trường chung)"
        ])
        form_layout.addWidget(self.combo_form)
        left_layout.addWidget(form_group)

        # Các thuộc tính lưu cấu hình AI ngầm (gắn parent=self và hide() để KHÔNG BAO GIỜ bị tạo thành cửa sổ taskbar thừa)
        self.combo_api_source = QComboBox(self)
        self.combo_api_source.addItem("Google Gemini Official", "official")
        self.combo_api_source.addItem("APIZ Vietnam Gateway", "apiz")
        self.combo_api_source.hide()
        self.input_api_key = QLineEdit(self)
        self.input_api_key.hide()
        self.input_base_url = QLineEdit("https://api.apiz.vn/v1", self)
        self.input_base_url.hide()
        self.lbl_base_url = QLabel("Base URL:", self)
        self.lbl_base_url.hide()
        self.combo_model = QComboBox(self)
        self.combo_model.addItem("gemini-3.8-flash")
        self.combo_model.hide()

        # 2. Danh sách chứng từ đính kèm (DropListWidget)
        docs_group = QGroupBox("2. Chứng từ đính kèm (PDF / Ảnh)")
        docs_layout = QVBoxLayout(docs_group)
        docs_layout.setSpacing(6)

        doc_hint = QLabel("💡 Kéo thả file vào đây. Tích [x] để AI đọc dữ liệu:")
        doc_hint.setStyleSheet("color: #0369a1; font-size: 11.5px; background: #e0f2fe; padding: 6px 10px; border-radius: 4px;")
        docs_layout.addWidget(doc_hint)

        self.list_files = DropListWidget()
        self.list_files.file_dropped_signal.connect(self.add_dropped_files)
        self.list_files.itemChanged.connect(lambda: self.update_file_status_label())
        self.list_files.itemClicked.connect(self.on_file_item_clicked)
        docs_layout.addWidget(self.list_files)

        # Thanh nút thao tác tệp
        btn_files_layout = QHBoxLayout()
        btn_add_files = QPushButton("➕ Thêm...")
        btn_add_files.clicked.connect(self.choose_files)
        btn_remove_file = QPushButton("➖ Xóa chọn")
        btn_remove_file.clicked.connect(self.remove_selected_file)
        btn_clear_files = QPushButton("🗑️ Xóa hết")
        btn_clear_files.clicked.connect(self.clear_all_files)

        btn_files_layout.addWidget(btn_add_files)
        btn_files_layout.addWidget(btn_remove_file)
        btn_files_layout.addWidget(btn_clear_files)
        docs_layout.addLayout(btn_files_layout)

        # Thanh chọn nhanh bộ lọc AI
        ai_sel_layout = QHBoxLayout()
        btn_select_core = QPushButton("🎯 Chỉ Đơn + Inv")
        btn_select_core.setToolTip("Chỉ tích chọn Đơn C/O và Invoice để AI đọc")
        btn_select_core.clicked.connect(self.select_only_core_files)

        btn_select_all = QPushButton("☑️ AI đọc hết")
        btn_select_all.setToolTip("Tích chọn tất cả các file cho AI phân tích")
        btn_select_all.clicked.connect(self.select_all_ai_files)

        ai_sel_layout.addWidget(btn_select_core)
        ai_sel_layout.addWidget(btn_select_all)
        docs_layout.addLayout(ai_sel_layout)

        left_layout.addWidget(docs_group)

        # 3. Nút Kích hoạt Trích xuất AI Nổi bật
        self.btn_extract = QPushButton("⚡ BẮT ĐẦU TRÍCH XUẤT BẰNG AI")
        self.btn_extract.setObjectName("btn_extract")
        self.btn_extract.clicked.connect(self.start_extraction)
        left_layout.addWidget(self.btn_extract)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximum(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(6)
        left_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Sẵn sàng trích xuất hồ sơ.")
        self.lbl_status.setStyleSheet("color: #475569; font-style: italic; font-size: 11.5px;")
        left_layout.addWidget(self.lbl_status)

        left_layout.addStretch()
        left_widget.setMinimumWidth(320)
        left_widget.setMaximumWidth(380)
        splitter.addWidget(left_widget)

        # ========================================================
        # CỘT PHẢI: TOÀN BỘ KHÔNG GIAN DÀNH CHO TAB DỮ LIỆU & COPILOT
        # ========================================================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        # Tiêu đề bảng điều khiển gọn gàng & Nút Sao chép JSON nổi bật góc trên
        header_layout = QHBoxLayout()
        title_label = QLabel("DỮ LIỆU HỒ SƠ KHAI BÁO C/O (eCoSys)")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #0078d4;")
        header_layout.addWidget(title_label)

        lbl_badge_unit = QLabel("🛡️ Đơn vị: KILOGRAM (Đã khóa chuẩn)")
        lbl_badge_unit.setStyleSheet("background: #dcfce7; color: #166534; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11.5px;")
        header_layout.addWidget(lbl_badge_unit)

        header_layout.addStretch()

        btn_load_sample = QPushButton("🧪 Nạp dữ liệu mẫu")
        btn_load_sample.clicked.connect(self.load_sample_data)
        header_layout.addWidget(btn_load_sample)

        self.btn_copy_json_top = QPushButton("📋 SAO CHÉP JSON (DÁN VÀO EXTENSION)")
        self.btn_copy_json_top.setObjectName("btn_copy_json")
        self.btn_copy_json_top.clicked.connect(self.copy_json_to_clipboard)
        header_layout.addWidget(self.btn_copy_json_top)

        right_layout.addLayout(header_layout)

        # Tab Widget cho các nhóm thông tin (Chiếm 100% chiều cao còn lại)
        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs)

        # Tab 1: Doanh nghiệp & Địa điểm
        self.tab_general = QWidget()
        self.setup_tab_general()
        self.tabs.addTab(self.tab_general, "🏢 1. Doanh nghiệp & Địa điểm")

        # Tab 2: Vận tải & Hóa đơn (Multi-row Tờ khai nhập & Hóa đơn VAT)
        self.tab_transport = QWidget()
        self.setup_tab_transport()
        self.tabs.addTab(self.tab_transport, "🚢 2. Vận tải & Hóa đơn")

        # Tab 3: Danh sách hàng hóa
        self.tab_goods = QWidget()
        self.setup_tab_goods()
        self.tabs.addTab(self.tab_goods, "📦 3. Danh sách hàng hóa")

        # Tab 4: Tệp đính kèm (10 Slot eCoSys)
        self.tab_attachments = QWidget()
        self.setup_tab_attachments()
        self.tabs.addTab(self.tab_attachments, "📎 4. Tệp đính kèm (10 Slot eCoSys)")

        # Tab 5: Xuất JSON cho Extension
        self.tab_json = QWidget()
        self.setup_tab_json()
        self.tabs.addTab(self.tab_json, "💾 5. Xuất JSON (Extension)")

        # Tab 6: Trợ lý AI Copilot nghiệp vụ C/O & eCoSys
        self.tab_copilot = QWidget()
        self.setup_tab_copilot()
        self.tabs.addTab(self.tab_copilot, "🤖 6. Trợ lý AI Copilot")

        # Tab 7: Xem trước tài liệu PDF / Ảnh đối chiếu
        self.tab_inspector = QWidget()
        self.setup_tab_inspector()
        self.tabs.addTab(self.tab_inspector, "👁️ 7. Xem trước Chứng từ")

        self.tabs.currentChanged.connect(self.on_tab_changed)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

    # ----------------------------------------------------
    # TAB 1: DOANH NGHIỆP & ĐỊA ĐIỂM
    # ----------------------------------------------------
    def setup_tab_general(self):
        scroll = QScrollArea(self.tab_general)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Exporter (Người xuất khẩu)
        box_exp = QGroupBox("Người xuất khẩu (Exporter - Box 1)")
        form_exp = QFormLayout(box_exp)
        self.txt_exp_name_en = QLineEdit()
        self.txt_exp_name_vn = QLineEdit()
        self.txt_exp_tax = QLineEdit()
        self.txt_exp_addr1 = QLineEdit()
        self.txt_exp_addr2 = QLineEdit()

        form_exp.addRow("Tên Exporter (Tiếng Anh):", self.txt_exp_name_en)
        form_exp.addRow("Tên Exporter (Tiếng Việt):", self.txt_exp_name_vn)
        form_exp.addRow("Mã số thuế:", self.txt_exp_tax)
        form_exp.addRow("Địa chỉ dòng 1:", self.txt_exp_addr1)
        form_exp.addRow("Địa chỉ dòng 2:", self.txt_exp_addr2)
        layout.addWidget(box_exp)

        # Consignee (Người nhập khẩu)
        box_imp = QGroupBox("Người nhận hàng / Nhập khẩu (Consignee - Box 2)")
        form_imp = QFormLayout(box_imp)
        self.txt_imp_name = QLineEdit()
        self.txt_imp_addr1 = QLineEdit()
        self.txt_imp_addr2 = QLineEdit()

        form_imp.addRow("Tên Consignee (Tiếng Anh):", self.txt_imp_name)
        form_imp.addRow("Địa chỉ dòng 1:", self.txt_imp_addr1)
        form_imp.addRow("Địa chỉ dòng 2:", self.txt_imp_addr2)
        layout.addWidget(box_imp)

        # Metadata
        box_meta = QGroupBox("Cơ quan & Địa điểm cấp C/O")
        form_meta = QFormLayout(box_meta)
        self.txt_authority = QLineEdit()
        self.txt_country = QLineEdit()
        self.txt_place = QLineEdit()

        form_meta.addRow("Phòng Quản lý XNK cấp:", self.txt_authority)
        form_meta.addRow("Nước nhập khẩu (Importing Country):", self.txt_country)
        form_meta.addRow("Nơi khai báo (Tỉnh/Thành phố):", self.txt_place)
        layout.addWidget(box_meta)

        # Manufacturer (Nhà sản xuất - Mục 25, 26)
        box_manu = QGroupBox("Nhà sản xuất (Manufacturer - Mục 25, 26)")
        form_manu = QFormLayout(box_manu)
        self.txt_manu_name = QLineEdit()
        self.txt_manu_addr1 = QLineEdit()
        self.txt_manu_addr2 = QLineEdit()

        form_manu.addRow("Tên nhà sản xuất (Tiếng Anh):", self.txt_manu_name)
        form_manu.addRow("Địa chỉ dòng 1:", self.txt_manu_addr1)
        form_manu.addRow("Địa chỉ dòng 2:", self.txt_manu_addr2)
        layout.addWidget(box_manu)

        layout.addStretch()
        scroll.setWidget(content)

        outer = QVBoxLayout(self.tab_general)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ----------------------------------------------------
    # TAB 2: VẬN TẢI & HÓA ĐƠN (MULTI-ROW IMPORT DECLARATIONS & VAT INVOICES)
    # ----------------------------------------------------
    def setup_tab_transport(self):
        scroll = QScrollArea(self.tab_transport)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Vận tải
        box_trans = QGroupBox("Chi tiết hành trình & Vận tải (Box 3)")
        form_trans = QFormLayout(box_trans)
        self.txt_trans_type = QLineEdit()
        self.txt_trans_type.setText("Đường biển")
        self.txt_vessel = QLineEdit()
        self.txt_pol = QLineEdit()
        self.txt_pod = QLineEdit()
        self.txt_dep_date = QLineEdit()
        self.txt_bill = QLineEdit()

        form_trans.addRow("Phương thức vận tải:", self.txt_trans_type)
        form_trans.addRow("Tên tàu / Chuyến bay:", self.txt_vessel)
        form_trans.addRow("Cảng bốc hàng (Port of Loading):", self.txt_pol)
        form_trans.addRow("Cảng dỡ hàng (Port of Discharge):", self.txt_pod)
        form_trans.addRow("Ngày tàu chạy (DD/MM/YYYY):", self.txt_dep_date)
        form_trans.addRow("Số Vận đơn (B/L No):", self.txt_bill)
        layout.addWidget(box_trans)

        # Hóa đơn thương mại & Tờ khai hải quan xuất khẩu
        box_inv = QGroupBox("Hóa đơn thương mại & Tờ khai Hải quan XK")
        form_inv = QFormLayout(box_inv)
        self.txt_inv_no = QLineEdit()
        self.txt_inv_date = QLineEdit()
        self.txt_inv_curr = QLineEdit()
        self.txt_inv_curr.setText("USD - Dollar Mỹ")
        self.txt_fob_total = QLineEdit()
        self.txt_customs_no = QLineEdit()
        self.txt_customs_date = QLineEdit()
        self.txt_remarks = QLineEdit()

        retro_row = QHBoxLayout()
        self.chk_issued_retro = QCheckBox("Tích chọn 'Issued Retrospectively' (C/O cấp sau)")
        self.chk_issued_retro.setStyleSheet("color: #d93025; font-weight: bold;")
        self.txt_retro_reason = QLineEdit()
        self.txt_retro_reason.setPlaceholderText("Lý do cấp sau (VD: tàu delay, đổi cảng)...")
        retro_row.addWidget(self.chk_issued_retro)
        retro_row.addWidget(self.txt_retro_reason)

        form_inv.addRow("Số Hóa đơn (Invoice No):", self.txt_inv_no)
        form_inv.addRow("Ngày Hóa đơn (DD/MM/YYYY):", self.txt_inv_date)
        form_inv.addRow("Đồng tiền thanh toán:", self.txt_inv_curr)
        form_inv.addRow("Tổng trị giá FOB:", self.txt_fob_total)
        form_inv.addRow("Số tờ khai Hải quan XK:", self.txt_customs_no)
        form_inv.addRow("Ngày tờ khai Hải quan XK:", self.txt_customs_date)
        form_inv.addRow("Ghi chú (Remarks):", self.txt_remarks)
        form_inv.addRow("C/O Cấp sau:", retro_row)
        layout.addWidget(box_inv)

        # BẢNG TỜ KHAI HẢI QUAN NHẬP KHẨU (MULTI-ROW - MỤC 27, 28)
        box_imp_decl = QGroupBox("Tờ khai Hải quan nhập khẩu nguyên liệu (Mục 27, 28 - Nhiều dòng)")
        imp_lay = QVBoxLayout(box_imp_decl)
        imp_tools = QHBoxLayout()
        lbl_imp_hint = QLabel("💡 Mỗi tờ khai nhập là 1 dòng kèm ngày tương ứng:")
        lbl_imp_hint.setStyleSheet("color: #64748b; font-size: 11.5px;")
        imp_tools.addWidget(lbl_imp_hint)
        imp_tools.addStretch()

        btn_add_imp = QPushButton("➕ Thêm tờ khai nhập")
        btn_add_imp.clicked.connect(self.add_import_declaration_row)
        btn_del_imp = QPushButton("➖ Xóa dòng chọn")
        btn_del_imp.clicked.connect(self.delete_import_declaration_row)
        imp_tools.addWidget(btn_add_imp)
        imp_tools.addWidget(btn_del_imp)
        imp_lay.addLayout(imp_tools)

        self.table_import_decls = QTableWidget()
        self.table_import_decls.setColumnCount(2)
        self.table_import_decls.setHorizontalHeaderLabels(["Số Tờ Khai HQ Nhập Khẩu", "Ngày Tờ Khai (DD/MM/YYYY)"])
        self.table_import_decls.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_import_decls.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_import_decls.setFixedHeight(110)
        imp_lay.addWidget(self.table_import_decls)
        layout.addWidget(box_imp_decl)

        # BẢNG HÓA ĐƠN VAT MUA NGUYÊN LIỆU (MULTI-ROW - MỤC 29, 30)
        box_vat_inv = QGroupBox("Hóa đơn VAT mua nguyên liệu trong nước (Mục 29, 30 - Nhiều dòng)")
        vat_lay = QVBoxLayout(box_vat_inv)
        vat_tools = QHBoxLayout()
        lbl_vat_hint = QLabel("💡 Mỗi hóa đơn VAT là 1 dòng kèm ngày tương ứng:")
        lbl_vat_hint.setStyleSheet("color: #64748b; font-size: 11.5px;")
        vat_tools.addWidget(lbl_vat_hint)
        vat_tools.addStretch()

        btn_add_vat = QPushButton("➕ Thêm hóa đơn VAT")
        btn_add_vat.clicked.connect(self.add_vat_invoice_row)
        btn_del_vat = QPushButton("➖ Xóa dòng chọn")
        btn_del_vat.clicked.connect(self.delete_vat_invoice_row)
        vat_tools.addWidget(btn_add_vat)
        vat_tools.addWidget(btn_del_vat)
        vat_lay.addLayout(vat_tools)

        self.table_vat_invoices = QTableWidget()
        self.table_vat_invoices.setColumnCount(2)
        self.table_vat_invoices.setHorizontalHeaderLabels(["Số Hóa Đơn VAT Mua NVL", "Ngày Hóa Đơn VAT (DD/MM/YYYY)"])
        self.table_vat_invoices.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_vat_invoices.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_vat_invoices.setFixedHeight(110)
        vat_lay.addWidget(self.table_vat_invoices)
        layout.addWidget(box_vat_inv)

        layout.addStretch()
        scroll.setWidget(content)

        outer = QVBoxLayout(self.tab_transport)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def add_import_declaration_row(self, no: str = "", dt: str = ""):
        r = self.table_import_decls.rowCount()
        self.table_import_decls.insertRow(r)
        self.table_import_decls.setItem(r, 0, QTableWidgetItem(no))
        self.table_import_decls.setItem(r, 1, QTableWidgetItem(dt))

    def delete_import_declaration_row(self):
        r = self.table_import_decls.currentRow()
        if r >= 0:
            self.table_import_decls.removeRow(r)

    def add_vat_invoice_row(self, no: str = "", dt: str = ""):
        r = self.table_vat_invoices.rowCount()
        self.table_vat_invoices.insertRow(r)
        self.table_vat_invoices.setItem(r, 0, QTableWidgetItem(no))
        self.table_vat_invoices.setItem(r, 1, QTableWidgetItem(dt))

    def delete_vat_invoice_row(self):
        r = self.table_vat_invoices.currentRow()
        if r >= 0:
            self.table_vat_invoices.removeRow(r)

    # ----------------------------------------------------
    # TAB 3: DANH SÁCH HÀNG HÓA (KHÓA CỨNG KILOGRAM)
    # ----------------------------------------------------
    def setup_tab_goods(self):
        layout = QVBoxLayout(self.tab_goods)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Toolbar
        btn_layout = QHBoxLayout()
        btn_add_row = QPushButton("➕ Thêm dòng hàng")
        btn_add_row.clicked.connect(self.add_table_row)
        btn_del_row = QPushButton("➖ Xóa dòng chọn")
        btn_del_row.clicked.connect(self.delete_table_row)
        btn_recalc = QPushButton("🔄 Tính lại tổng FOB")
        btn_recalc.clicked.connect(self.recalculate_totals)

        btn_layout.addWidget(btn_add_row)
        btn_layout.addWidget(btn_del_row)
        btn_layout.addWidget(btn_recalc)
        btn_layout.addStretch()

        self.lbl_goods_count = QLabel("Tổng số: 0 mặt hàng")
        self.lbl_goods_count.setStyleSheet("font-weight: bold; color: #0078d4;")
        btn_layout.addWidget(self.lbl_goods_count)

        layout.addLayout(btn_layout)

        # Table
        self.table_goods = QTableWidget()
        headers = [
            "Mã HS XK (8 số)", "Mã HS NK (6 số)", "Mô tả hàng hóa", "Tiêu chí xuất xứ",
            "Số lượng (NW)", "ĐVT (Khóa KILOGRAM)", "Gross Wt (GW)", "ĐVT GW",
            "Số kiện", "Loại kiện", "Trị giá FOB", "Tiền tệ",
            "Ký hiệu kiện", "Số Hóa đơn", "Ngày Hóa đơn"
        ]
        self.table_goods.setColumnCount(len(headers))
        self.table_goods.setHorizontalHeaderLabels(headers)
        self.table_goods.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_goods.setAlternatingRowColors(True)
        layout.addWidget(self.table_goods)

    def add_table_row(self):
        r = self.table_goods.rowCount()
        self.table_goods.insertRow(r)
        defaults = [
            "0901.11.10", "0901.11", "Cà phê Robusta nhân sống", "WO",
            "1000", "KILOGRAM", "1050", "KILOGRAM",
            "100", "CARTON", "3500.00", "USD - Dollar Mỹ",
            "NO MARK", "", ""
        ]
        for col, val in enumerate(defaults):
            self.table_goods.setItem(r, col, QTableWidgetItem(val))
        self.lbl_goods_count.setText(f"Tổng số: {self.table_goods.rowCount()} mặt hàng")

    def delete_table_row(self):
        r = self.table_goods.currentRow()
        if r >= 0:
            self.table_goods.removeRow(r)
            self.lbl_goods_count.setText(f"Tổng số: {self.table_goods.rowCount()} mặt hàng")

    def recalculate_totals(self):
        total_fob = 0.0
        for r in range(self.table_goods.rowCount()):
            it = self.table_goods.item(r, 10)
            if it and it.text().strip():
                try:
                    total_fob += float(it.text().replace(",", "").strip())
                except:
                    pass
        self.txt_fob_total.setText(f"{total_fob:.2f}")

    # ----------------------------------------------------
    # TAB 4: TỆP ĐÍNH KÈM (10 VỊ TRÍ UPLOAD ECOSYS)
    # ----------------------------------------------------
    def setup_tab_attachments(self):
        layout = QVBoxLayout(self.tab_attachments)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        info_box = QGroupBox("Cấu hình Tự động Đính kèm & Upload File lên eCoSys")
        info_layout = QVBoxLayout(info_box)

        self.chk_include_base64 = QCheckBox("Tự động đóng gói Base64 các tệp được chọn vào JSON (Extension sẽ tự động upload lên web)")
        self.chk_include_base64.setChecked(True)
        self.chk_include_base64.setStyleSheet("font-weight: bold; color: #0078d4; font-size: 13px;")
        info_layout.addWidget(self.chk_include_base64)

        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel("<b>Phương thức gán tệp HĐ VAT & Tờ khai nhập:</b>"))
        self.combo_matching_mode = QComboBox()
        self.combo_matching_mode.addItem("🔢 Khớp theo Số HĐ / Số Tờ khai trong tên tệp (Khuyên dùng)", "by_number")
        self.combo_matching_mode.addItem("➡️ Gán tuần tự theo thứ tự dòng 1, 2, 3... (Dự phòng)", "by_order")
        row_mode.addWidget(self.combo_matching_mode, stretch=1)
        info_layout.addLayout(row_mode)

        desc_lbl = QLabel(
            "💡 Khuyên dùng: Nếu có nhiều Hóa đơn VAT hoặc Tờ khai nhập, chỉ cần đặt tên file chứa số (ví dụ: HD_00000083.pdf, TK_10582231.pdf), "
            "Extension sẽ tự động đính chính xác vào đúng dòng số đó trên web eCoSys. Nếu tên file không có số, hệ thống sẽ tự động dùng phương án dự phòng (gán tuần tự dòng 1, 2...)."
        )
        desc_lbl.setStyleSheet("color: #475569; font-size: 11.5px;")
        desc_lbl.setWordWrap(True)
        info_layout.addWidget(desc_lbl)
        layout.addWidget(info_box)

        # Toolbar
        tools_layout = QHBoxLayout()
        btn_add_att = QPushButton("➕ Thêm tệp chứng từ...")
        btn_add_att.clicked.connect(self.add_attachment_files)
        btn_del_att = QPushButton("➖ Bỏ tệp khỏi danh sách")
        btn_del_att.clicked.connect(self.delete_attachment_file)
        btn_auto_detect = QPushButton("🔍 Tự động nhận diện loại chứng từ (PyMuPDF)")
        btn_auto_detect.clicked.connect(self.auto_detect_attachment_types)

        btn_organize_folder = QPushButton("📁 Gom & Chuẩn hóa thư mục chứng từ...")
        btn_organize_folder.setStyleSheet("font-weight: bold; color: #1e40af; background-color: #dbeafe; border: 1px solid #93c5fd; padding: 4px 10px; border-radius: 4px;")
        btn_organize_folder.clicked.connect(self.organize_attachment_folder)

        tools_layout.addWidget(btn_add_att)
        tools_layout.addWidget(btn_del_att)
        tools_layout.addWidget(btn_auto_detect)
        tools_layout.addWidget(btn_organize_folder)
        btn_guide_naming = QPushButton("💡 Hướng dẫn đặt tên chứng từ")
        btn_guide_naming.setStyleSheet("font-weight: bold; color: #047857; background-color: #d1fae5; border: 1px solid #6ee7b7; padding: 4px 10px; border-radius: 4px;")
        btn_guide_naming.clicked.connect(self.show_attachment_naming_guide)
        tools_layout.addWidget(btn_guide_naming)
        tools_layout.addStretch()
        layout.addLayout(tools_layout)

        # Table
        self.table_attachments = QTableWidget()
        headers = ["Nạp", "Tên tệp", "Vị trí tải lên eCoSys (Dropbox)", "Kích thước", "Đường dẫn gốc"]
        self.table_attachments.setColumnCount(len(headers))
        self.table_attachments.setHorizontalHeaderLabels(headers)
        self.table_attachments.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_attachments.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_attachments.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table_attachments.setAlternatingRowColors(True)
        layout.addWidget(self.table_attachments)

    def add_attachment_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn tệp chứng từ đính kèm (PDF, Ảnh...)",
            "",
            "Chứng từ (*.pdf *.png *.jpg *.jpeg *.bmp);;Tất cả tệp (*.*)"
        )
        if files:
            for f in files:
                ftype = self.detect_file_type_from_content(f)
                self.add_attachment_row(f, ftype, checked=True)

    def delete_attachment_file(self):
        r = self.table_attachments.currentRow()
        if r >= 0:
            self.table_attachments.removeRow(r)

    def add_attachment_row(self, file_path: str, file_type: str = "TAILIEUCHUNGMINH", checked: bool = True):
        if not os.path.exists(file_path):
            return

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        size_str = f"{round(file_size / 1024, 1)} KB" if file_size < 1024 * 1024 else f"{round(file_size / (1024*1024), 2)} MB"

        row = self.table_attachments.rowCount()
        self.table_attachments.insertRow(row)

        chk_item = QTableWidgetItem()
        chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk_item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.table_attachments.setItem(row, 0, chk_item)

        name_item = QTableWidgetItem(file_name)
        name_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self.table_attachments.setItem(row, 1, name_item)

        combo_type = QComboBox()
        types = [
            ("ToKhaiXuatKhau", "Tờ khai hải quan xuất khẩu (Mục 25, 26)"),
            ("Invoice_attached_Doc", "Hóa đơn thương mại (Invoice Attached)"),
            ("VanDon", "Vận tải đơn / B/L (TRANSPORT_INFO)"),
            ("HoaDonVAT", "Hóa đơn VAT mua nguyên liệu trong nước (Mục 29, 30)"),
            ("ToKhaiHQNK_Document", "Tờ khai hải quan nhập khẩu nguyên liệu (Mục 27, 28)"),
            ("BangKeChiPhi", "Bảng kê chi phí / Hàm lượng (DOCUMENT_PROVING)"),
            ("QuyTrinhSanXuat", "Bản mô tả quy trình sản xuất (DOCUMENT_PROVING)"),
            ("TAILIEUCHUNGMINH", "Đơn đề nghị cấp C/O & Tài liệu khác (DOCUMENT_PROVING)"),
            ("HopDongMuaBan", "Hợp đồng mua bán (DOCUMENT_PROVING)"),
            ("GiayPhepXuatKhau", "Giấy phép xuất khẩu (DOCUMENT_PROVING)")
        ]
        for val, label in types:
            combo_type.addItem(f"{label} [{val}]", val)

        for i in range(combo_type.count()):
            if combo_type.itemData(i) == file_type:
                combo_type.setCurrentIndex(i)
                break
        self.table_attachments.setCellWidget(row, 2, combo_type)

        size_item = QTableWidgetItem(size_str)
        size_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table_attachments.setItem(row, 3, size_item)

        path_item = QTableWidgetItem(file_path)
        path_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self.table_attachments.setItem(row, 4, path_item)

    def detect_file_type_from_content(self, file_path: str) -> str:
        if not file_path or not os.path.exists(file_path):
            return "TAILIEUCHUNGMINH"

        fn = os.path.basename(file_path).lower()

        # 1. Nhận diện cực nhanh từ tên tệp (0ms - không làm chậm UI)
        if any(k in fn for k in ["inv", "invoice"]):
            return "Invoice_attached_Doc"
        if any(k in fn for k in ["bill", "bl", "van_don", "vandon"]):
            return "VanDon"
        if any(k in fn for k in ["vat", "gtgt"]):
            return "HoaDonVAT"
        if any(k in fn for k in ["to_khai", "tokhai", "customs", "tkhq"]):
            if any(nk in fn for nk in ["nhap", "nk", "import"]):
                return "ToKhaiHQNK_Document"
            return "ToKhaiXuatKhau"
        if any(k in fn for k in ["bang_ke", "bangke", "bom"]):
            return "BangKeChiPhi"
        if any(k in fn for k in ["quy_trinh", "quytrinh", "process"]):
            return "QuyTrinhSanXuat"
        if any(k in fn for k in ["don", "denghi", "form04"]):
            return "TAILIEUCHUNGMINH"

        # 2. Nếu tên tệp không rõ ràng, chỉ đọc trang đầu tiên của PDF
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            try:
                doc = fitz.open(file_path)
                if len(doc) > 0:
                    first_page_text = (doc[0].get_text() or "").upper()
                    txt_clean = re.sub(r'\s+', ' ', first_page_text)

                    if any(k in txt_clean for k in ["COMMERCIAL INVOICE", "HOÁ ĐƠN THƯƠNG MẠI", "HÓA ĐƠN THƯƠNG MẠI", "PROFORMA INVOICE"]):
                        if not any(v in txt_clean for v in ["HOÁ ĐƠN GIÁ TRỊ GIA TĂNG", "HÓA ĐƠN GIÁ TRỊ GIA TĂNG", "HÓA ĐƠN VAT"]):
                            return "Invoice_attached_Doc"

                    if any(k in txt_clean for k in ["BILL OF LADING", "OCEAN BILL", "WAYBILL", "SEAWAY BILL", "AIR WAYBILL"]):
                        return "VanDon"

                    if any(k in txt_clean for k in ["GIÁ TRỊ GIA TĂNG", "GIA TRI GIA TANG", "HOÁ ĐƠN GTGT", "HÓA ĐƠN GTGT", "HOÁ ĐƠN VAT"]):
                        return "HoaDonVAT"

                    if any(k in txt_clean for k in ["TỜ KHAI HẢI QUAN", "TO KHAI HAI QUAN", "CUSTOMS DECLARATION"]):
                        if any(nk in txt_clean for nk in ["NHẬP KHẨU", "NHAP KHAU", "NHẬP NGUYÊN LIỆU"]):
                            return "ToKhaiHQNK_Document"
                        return "ToKhaiXuatKhau"

                    if any(k in txt_clean for k in ["BẢNG KÊ", "BANG KE", "TIÊU CHÍ XUẤT XỨ", "HÀM LƯỢNG GIÁ TRỊ", "RVC", "CTC", "BOM"]):
                        return "BangKeChiPhi"

                    if any(k in txt_clean for k in ["QUY TRÌNH SẢN XUẤT", "QUY TRINH SAN XUAT", "MANUFACTURING PROCESS"]):
                        return "QuyTrinhSanXuat"
            except Exception:
                pass

        return "TAILIEUCHUNGMINH"

    def auto_detect_attachment_types(self):
        count = 0
        for r in range(self.table_attachments.rowCount()):
            path_item = self.table_attachments.item(r, 4)
            if path_item and path_item.text():
                detected = self.detect_file_type_from_content(path_item.text())
                combo = self.table_attachments.cellWidget(r, 2)
                if combo:
                    for i in range(combo.count()):
                        if combo.itemData(i) == detected:
                            combo.setCurrentIndex(i)
                            count += 1
                            break
        QMessageBox.information(self, "Hoàn tất", f"Đã tự động phân loại {count} tệp chứng từ dựa vào NỘI DUNG THỰC TẾ và tên tệp!")

    # ----------------------------------------------------
    # TAB 5: XUẤT JSON (CHO EXTENSION)
    # ----------------------------------------------------
    def setup_tab_json(self):
        layout = QVBoxLayout(self.tab_json)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        bar_layout = QHBoxLayout()
        btn_copy_json = QPushButton("📋 SAO CHÉP JSON (DÁN VÀO EXTENSION)")
        btn_copy_json.setObjectName("btn_copy_json")
        btn_copy_json.clicked.connect(self.copy_json_to_clipboard)

        btn_save_json = QPushButton("💾 Lưu file JSON...")
        btn_save_json.clicked.connect(self.save_json_file)

        btn_refresh_json = QPushButton("🔄 Đồng bộ dữ liệu vào JSON")
        btn_refresh_json.clicked.connect(self.refresh_json_from_inputs)

        bar_layout.addWidget(btn_copy_json)
        bar_layout.addWidget(btn_save_json)
        bar_layout.addWidget(btn_refresh_json)
        bar_layout.addStretch()
        layout.addLayout(bar_layout)

        info_lbl = QLabel("✅ Dữ liệu JSON chuẩn eCoSys. Bạn chỉ cần bấm 'Sao chép JSON', sau đó mở web eCoSys và bấm 'Dán từ Clipboard & Điền Ngay'.")
        info_lbl.setStyleSheet("color: #166534; font-weight: 600; font-size: 12px;")
        layout.addWidget(info_lbl)

        self.txt_json_view = QTextEdit()
        self.txt_json_view.setFont(QFont("Consolas", 10))
        self.txt_json_view.setStyleSheet("background: #0f172a; color: #38bdf8; border-radius: 6px;")
        layout.addWidget(self.txt_json_view)

    # ----------------------------------------------------
    # TAB 6: TRỢ LÝ AI COPILOT CHUYÊN GIA C/O & ECOSYS 24/7
    # ----------------------------------------------------
    def setup_tab_copilot(self):
        layout = QVBoxLayout(self.tab_copilot)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header gợi ý câu hỏi
        hint_card = QFrame()
        hint_card.setStyleSheet("QFrame { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px; }")
        h_lay = QVBoxLayout(hint_card)
        h_lay.setContentsMargins(6, 6, 6, 6)
        h_lay.setSpacing(4)

        lbl_c_title = QLabel("🤖 TRỢ LÝ AI COPILOT (GEMINI 3.8 FLASH) • HỎI ĐÁP NGHIỆP VỤ & SỬA LỖI ECOSYS")
        lbl_c_title.setStyleSheet("font-weight: bold; color: #0078d4; font-size: 13px;")
        h_lay.addWidget(lbl_c_title)

        chips_row = QHBoxLayout()
        chips = [
            ("🇪🇺 Form EUR.1 (EVFTA)", "Giải thích quy tắc xuất xứ Form EUR.1 và hồ sơ chứng minh."),
            ("⚖️ WO vs CTC vs RVC", "Phân biệt tiêu chí WO, CTC (CC, CTH, CTSH) và RVC."),
            ("📋 BOM & HĐ VAT", "Hướng dẫn lập Bảng kê khai nguyên phụ liệu (BOM) và đối soát hóa đơn VAT."),
            ("🔌 Lỗi Token Ký số", "Cách sửa lỗi Plugin ký số MOITSignPlugin không tìm thấy USB Token."),
            ("🔍 Soát lỗi hồ sơ này", "SCAN_CURRENT_FORM")
        ]
        for title, p in chips:
            b = QPushButton(title)
            b.setStyleSheet("padding: 4px 8px; font-size: 11.5px;")
            b.clicked.connect(lambda ch, prompt_val=p: self.on_copilot_quick_ask(prompt_val))
            chips_row.addWidget(b)
        chips_row.addStretch()
        h_lay.addLayout(chips_row)
        layout.addWidget(hint_card)

        # Chat history
        self.txt_chat_history = QTextEdit()
        self.txt_chat_history.setReadOnly(True)
        self.txt_chat_history.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px; line-height: 1.5;")
        layout.addWidget(self.txt_chat_history)

        # Chat input
        chat_input_row = QHBoxLayout()
        self.input_chat = QLineEdit()
        self.input_chat.setPlaceholderText("Nhập câu hỏi nghiệp vụ hoặc hỏi cách xử lý lỗi eCoSys...")
        self.input_chat.returnPressed.connect(self.send_copilot_message)
        chat_input_row.addWidget(self.input_chat)

        self.btn_chat_send = QPushButton("Gửi Câu Hỏi")
        self.btn_chat_send.setStyleSheet("background-color: #0078d4; color: white; font-weight: bold;")
        self.btn_chat_send.clicked.connect(self.send_copilot_message)
        chat_input_row.addWidget(self.btn_chat_send)

        layout.addLayout(chat_input_row)

        self.append_ai_chat_message(
            "Xin chào! Tôi là **Trợ lý AI Copilot Nghiệp vụ C/O & eCoSys** (Gemini 3.8 Flash).\n"
            "Tôi sẵn sàng giải đáp thắc mắc về tiêu chí xuất xứ (WO, CTC, RVC), hướng dẫn lập bảng kê BOM và xử lý các lỗi kỹ thuật khi ký số trên eCoSys!"
        )

    def on_copilot_quick_ask(self, prompt: str):
        if prompt == "SCAN_CURRENT_FORM":
            data = self.collect_data_from_inputs()
            data_no_att = {k: v for k, v in data.items() if k != "attachments"}
            q = (
                f"Hãy rà soát tính hợp lệ của bộ hồ sơ C/O này:\n"
                f"{json.dumps(data_no_att, ensure_ascii=False, indent=2)}\n\n"
                f"Chỉ ra các điểm cần lưu ý về Mẫu C/O, Nước nhập khẩu, Mã HS, Tiêu chí xuất xứ và Tờ khai/HĐ VAT mua NVL."
            )
            self.input_chat.setText(q)
            self.send_copilot_message()
        else:
            self.input_chat.setText(prompt)
            self.send_copilot_message()

    def send_copilot_message(self):
        text = self.input_chat.text().strip()
        if not text:
            return

        api_key = self.input_api_key.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Chưa có API Key", "Vui lòng nhập API Key ở cột trái trước khi hỏi đáp AI.")
            return

        self.input_chat.clear()
        self.append_user_chat_message(text)
        self.btn_chat_send.setEnabled(False)
        self.lbl_status.setText("🤖 Copilot đang phân tích câu hỏi...")

        m_name = self.combo_model.currentData() or ("gemini-3.8-flash" if self.combo_api_source.currentData() == "apiz" else "gemini-3.8-flash")
        self.chat_worker = ChatbotWorker(
            api_key=api_key,
            question=text,
            history=self.chat_history,
            api_source=self.combo_api_source.currentData(),
            api_base_url=self.input_base_url.text().strip(),
            model_name=m_name
        )
        self.chat_worker.reply_signal.connect(self.on_copilot_reply)
        self.chat_worker.start()

    def on_copilot_reply(self, ans: str, err: str):
        self.btn_chat_send.setEnabled(True)
        self.lbl_status.setText("Sẵn sàng.")
        if err:
            self.append_ai_chat_message(f"❌ Đã xảy ra lỗi: {err}")
        else:
            self.append_ai_chat_message(ans)

    def append_user_chat_message(self, text: str):
        self.chat_history.append({"role": "user", "text": text})
        self.txt_chat_history.append(f"<p style='color: #0078d4; font-weight: bold;'>👤 Bạn:</p><p style='margin-left: 10px; color: #0f172a;'>{text}</p><hr style='border: none; border-top: 1px dashed #cbd5e1;'>")

    def append_ai_chat_message(self, markdown_text: str):
        self.chat_history.append({"role": "model", "text": markdown_text})
        # Chuyển đổi markdown cơ bản sang HTML trực quan
        html = markdown_text.replace("\n", "<br>")
        html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html)
        self.txt_chat_history.append(f"<p style='color: #107c41; font-weight: bold;'>🤖 AI Copilot (Gemini 3.8 Flash):</p><div style='margin-left: 10px; color: #1e293b; line-height: 1.5;'>{html}</div><hr style='border: none; border-top: 1px solid #e2e8f0;'>")

    # ----------------------------------------------------
    # TAB 7: XEM TRƯỚC CHỨNG TỪ (PDF/ẢNH ĐỐI SOÁT)
    # ----------------------------------------------------
    def setup_tab_inspector(self):
        layout = QVBoxLayout(self.tab_inspector)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        bar = QHBoxLayout()
        btn_prev = QPushButton("◀ Trang trước")
        btn_prev.clicked.connect(self.inspector_prev_page)
        btn_next = QPushButton("Trang tiếp ▶")
        btn_next.clicked.connect(self.inspector_next_page)

        self.lbl_insp_page = QLabel("Trang: 0 / 0")
        self.lbl_insp_page.setStyleSheet("font-weight: bold;")

        btn_zoom_out = QPushButton("➖ Thu nhỏ")
        btn_zoom_out.clicked.connect(self.inspector_zoom_out)
        btn_zoom_in = QPushButton("➕ Phóng to")
        btn_zoom_in.clicked.connect(self.inspector_zoom_in)

        self.lbl_insp_file = QLabel("Chưa chọn file")
        self.lbl_insp_file.setStyleSheet("color: #0078d4; font-weight: bold;")

        bar.addWidget(btn_prev)
        bar.addWidget(self.lbl_insp_page)
        bar.addWidget(btn_next)
        bar.addSpacing(12)
        bar.addWidget(btn_zoom_out)
        bar.addWidget(btn_zoom_in)
        bar.addStretch()
        bar.addWidget(self.lbl_insp_file)
        layout.addLayout(bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.lbl_insp_image = QLabel()
        self.lbl_insp_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_insp_image.setStyleSheet("background: #f8fafc; padding: 10px;")
        scroll.setWidget(self.lbl_insp_image)
        layout.addWidget(scroll)

    def load_file_into_inspector(self, path: str):
        if not path or not os.path.exists(path):
            return
        self.lbl_insp_file.setText(os.path.basename(path))
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            try:
                if self.inspector_doc:
                    self.inspector_doc.close()
                self.inspector_doc = fitz.open(path)
                self.inspector_page = 0
                self.render_inspector_page()
            except Exception as e:
                self.lbl_insp_image.setText(f"Lỗi đọc PDF: {e}")
        elif ext in [".png", ".jpg", ".jpeg", ".bmp"]:
            self.inspector_doc = None
            pix = QPixmap(path)
            if not pix.isNull():
                self.lbl_insp_page.setText("Trang: 1 / 1")
                scaled = pix.scaled(int(pix.width() * self.inspector_zoom), int(pix.height() * self.inspector_zoom),
                                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.lbl_insp_image.setPixmap(scaled)

    def render_inspector_page(self):
        if not self.inspector_doc or len(self.inspector_doc) == 0:
            return
        total = len(self.inspector_doc)
        self.lbl_insp_page.setText(f"Trang: {self.inspector_page + 1} / {total}")
        page = self.inspector_doc[self.inspector_page]
        scale = max(0.6, min(1.8, self.inspector_zoom))
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat)
        qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
        pix = None
        self.lbl_insp_image.setPixmap(QPixmap.fromImage(qimg))

    def inspector_prev_page(self):
        if self.inspector_doc and self.inspector_page > 0:
            self.inspector_page -= 1
            self.render_inspector_page()

    def inspector_next_page(self):
        if self.inspector_doc and self.inspector_page < len(self.inspector_doc) - 1:
            self.inspector_page += 1
            self.render_inspector_page()

    def inspector_zoom_in(self):
        self.inspector_zoom = min(2.5, self.inspector_zoom + 0.2)
        if self.inspector_doc: self.render_inspector_page()

    def inspector_zoom_out(self):
        self.inspector_zoom = max(0.5, self.inspector_zoom - 0.2)
        if self.inspector_doc: self.render_inspector_page()

    # ----------------------------------------------------
    # QUẢN LÝ TỆP ĐẦU VÀO & SỰ KIỆN GIAO DIỆN
    # ----------------------------------------------------
    def toggle_api_key_visibility(self):
        if self.input_api_key.echoMode() == QLineEdit.EchoMode.Password:
            self.input_api_key.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.input_api_key.setEchoMode(QLineEdit.EchoMode.Password)

    def on_api_source_changed(self, idx: int):
        is_apiz = self.combo_api_source.currentData() == "apiz"
        # TUYỆT ĐỐI KHÔNG GỌI setVisible trên lbl_base_url hay input_base_url để tránh biến thành 2 cửa sổ thừa nổi trên taskbar!
        self.combo_model.clear()
        if is_apiz:
            if not self.input_base_url.text().strip():
                self.input_base_url.setText("https://api.apiz.vn/v1")
            self.combo_model.addItem("gemini-3.8-flash (Cổng APIZ Vietnam)", "gemini-3.8-flash")
        else:
            self.input_base_url.setText("")  # XÓA TRẮNG ĐỂ KHÔNG BỊ TRÁO NHẦM SANG APIZ!
            self.combo_model.addItem("gemini-3.8-flash (Google Official Flagship)", "gemini-3.8-flash")
            self.combo_model.addItem("gemini-2.5-flash (Google 2.5)", "gemini-3.8-flash")
            self.combo_model.addItem("gemini-2.0-flash (Tốc độ cao)", "gemini-2.0-flash")
            self.combo_model.addItem("gemini-1.5-flash (Ổn định)", "gemini-1.5-flash")

    def on_api_key_changed(self, text: str):
        t = text.strip()
        if t.startswith("AIzaSy"):
            for i in range(self.combo_api_source.count()):
                if self.combo_api_source.itemData(i) == "official":
                    self.combo_api_source.setCurrentIndex(i)
                    break
            self.input_base_url.setText("")
        elif t.startswith("sk-"):
            for i in range(self.combo_api_source.count()):
                if self.combo_api_source.itemData(i) == "apiz":
                    self.combo_api_source.setCurrentIndex(i)
                    break
            if not self.input_base_url.text().strip():
                self.input_base_url.setText("https://api.apiz.vn/v1")

    def choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn chứng từ xuất khẩu (Đơn C/O, Invoice, B/L, Bảng kê, Tờ khai)",
            "",
            "Tài liệu C/O (*.pdf *.png *.jpg *.jpeg *.bmp);;Tất cả tệp (*.*)"
        )
        if files:
            self.add_dropped_files(files)

    def add_dropped_files(self, file_paths: list):
        for p in file_paths:
            if p not in self.selected_files:
                self.selected_files.append(p)
                it = QListWidgetItem(os.path.basename(p))
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                # Tự động tích nếu là Đơn C/O hoặc Invoice
                is_core = self.is_core_ai_file(p)
                it.setCheckState(Qt.CheckState.Checked if is_core else Qt.CheckState.Checked)
                it.setData(Qt.ItemDataRole.UserRole, p)
                self.list_files.addItem(it)

        self.update_file_status_label()
        self.populate_attachments_from_files(self.selected_files)

    def is_core_ai_file(self, filename: str) -> bool:
        fn = filename.lower()
        return any(k in fn for k in ["don", "inv", "invoice", "hoa_don", "denghi", "bill", "van_don"])

    def on_file_item_clicked(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.load_file_into_inspector(path)

    def remove_selected_file(self):
        row = self.list_files.currentRow()
        if row >= 0:
            it = self.list_files.takeItem(row)
            p = it.data(Qt.ItemDataRole.UserRole)
            if p in self.selected_files:
                self.selected_files.remove(p)
            self.update_file_status_label()
            self.populate_attachments_from_files(self.selected_files)

    def clear_all_files(self):
        self.list_files.clear()
        self.selected_files.clear()
        self.update_file_status_label()
        self.table_attachments.setRowCount(0)

    def select_only_core_files(self):
        for i in range(self.list_files.count()):
            it = self.list_files.item(i)
            p = it.data(Qt.ItemDataRole.UserRole)
            is_core = self.is_core_ai_file(p)
            it.setCheckState(Qt.CheckState.Checked if is_core else Qt.CheckState.Unchecked)
        self.update_file_status_label()

    def select_all_ai_files(self):
        for i in range(self.list_files.count()):
            self.list_files.item(i).setCheckState(Qt.CheckState.Checked)
        self.update_file_status_label()

    def update_file_status_label(self):
        total = self.list_files.count()
        checked = sum(1 for i in range(total) if self.list_files.item(i).checkState() == Qt.CheckState.Checked)
        self.lbl_status.setText(f"Đã chọn {checked}/{total} tệp cho AI Gemini 3.8 Flash đọc.")

    def populate_attachments_from_files(self, file_paths: list):
        self.table_attachments.setRowCount(0)
        for p in file_paths:
            ftype = self.detect_file_type_from_content(p)
            self.add_attachment_row(p, ftype, checked=True)

    # ----------------------------------------------------
    # BẮT ĐẦU TRÍCH XUẤT AI (GEMINI 3.8 FLASH)
    # ----------------------------------------------------
    def start_extraction(self):
        api_key = self.input_api_key.text().strip()
        if not api_key:
            cfg = load_settings()
            api_key = cfg.get("api_key", "").strip()
            if api_key:
                self.input_api_key.setText(api_key)
                if cfg.get("api_source"):
                    idx = self.combo_api_source.findData(cfg["api_source"])
                    if idx >= 0:
                        self.combo_api_source.setCurrentIndex(idx)
                if cfg.get("api_base_url"):
                    self.input_base_url.setText(cfg["api_base_url"])

        if not api_key:
            QMessageBox.warning(self, "Chưa có API Key", "Vui lòng vào menu '⚙️ Cài đặt API Chung' để nhập API Key trước khi trích xuất.")
            return

        ai_files = []
        for i in range(self.list_files.count()):
            it = self.list_files.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                ai_files.append(it.data(Qt.ItemDataRole.UserRole))

        if not ai_files:
            QMessageBox.warning(self, "Chưa chọn tệp cho AI", "Vui lòng tích chọn [x] ít nhất 1 tệp chứng từ để AI phân tích.")
            return

        target_form = self.combo_form.currentText().split()[0]

        self.btn_extract.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_status.setText("⚡ AI Gemini 3.8 Flash đang phân tích toàn bộ chứng từ...")

        self.save_current_config()

        m_name = self.combo_model.currentData() or ("gemini-3.8-flash" if self.combo_api_source.currentData() == "apiz" else "gemini-3.8-flash")
        self.worker = ExtractionWorker(
            api_key=api_key,
            file_paths=ai_files,
            target_form=target_form,
            api_source=self.combo_api_source.currentData(),
            api_base_url=self.input_base_url.text().strip(),
            model_name=m_name
        )
        self.worker.progress_signal.connect(lambda pct, msg: self.lbl_status.setText(f"⚡ [{pct}%] {msg}"))
        self.worker.finished_signal.connect(self.on_extraction_finished)
        self.worker.start()

    def on_extraction_finished(self, co_data: Optional[CODeclarationData], error: str):
        self.btn_extract.setEnabled(True)
        self.progress_bar.setVisible(False)

        if error:
            self.lbl_status.setText(f"❌ Lỗi: {error}")
            QMessageBox.critical(self, "Lỗi trích xuất AI", f"Không thể trích xuất hồ sơ: {error}")
            return

        self.lbl_status.setText("✅ Trích xuất thành công 100% bằng Gemini 3.8 Flash!")
        self.current_co_data = co_data
        self.populate_inputs_from_data(co_data)
        self.refresh_json_from_inputs()

        QMessageBox.information(
            self,
            "Trích xuất thành công",
            "AI Gemini 3.8 Flash đã tổng hợp toàn bộ thông tin C/O và chuẩn hóa đơn vị KILOGRAM!\n"
            "Bạn hãy kiểm tra các tab dữ liệu và bấm 'Sao chép JSON' để điền lên eCoSys."
        )

    # ----------------------------------------------------
    # ĐIỀN DỮ LIỆU TỪ CODeclarationData VÀO FORM
    # ----------------------------------------------------
    def populate_inputs_from_data(self, data: CODeclarationData):
        if not data:
            return

        # Mẫu C/O
        if getattr(data, "coType", None):
            ct = str(data.coType).strip().upper()
            for idx in range(self.combo_form.count()):
                if ct in self.combo_form.itemText(idx).upper():
                    self.combo_form.setCurrentIndex(idx)
                    break

        # 1. Doanh nghiệp
        self.txt_exp_name_en.setText(data.from_ExporterBusinessName or "")
        self.txt_exp_name_vn.setText(data.from_ExporterBusinessNameVN or "")
        self.txt_exp_tax.setText(data.taxCode or "")
        self.txt_exp_addr1.setText(data.from_AddressLine1 or "")
        self.txt_exp_addr2.setText(data.from_Addressline2 or "")

        self.txt_imp_name.setText(data.to_ConsigneeName or "")
        self.txt_imp_addr1.setText(data.to_Addressline1 or "")
        self.txt_imp_addr2.setText(data.to_Addressline2 or "")

        self.txt_authority.setText(data.issuing_Authority or "")
        self.txt_country.setText(data.importing_Country or "")
        self.txt_place.setText(data.declarationPlace or "")

        self.txt_manu_name.setText(data.manu_Name or "")
        self.txt_manu_addr1.setText(data.manu_AddressLine1 or "")
        self.txt_manu_addr2.setText(data.manu_AddressLine2 or "")

        # 2. Vận tải & Hóa đơn
        self.txt_trans_type.setText(data.route_TransportationType or "Đường biển")
        self.txt_vessel.setText(data.route_TransportName or "")
        self.txt_pol.setText(data.route_PortOfLoading or "")
        self.txt_pod.setText(data.route_PortOfDischange or "")
        self.txt_dep_date.setText(data.route_DepartureDepartureDate or "")
        self.txt_bill.setText(data.bill or "")

        self.txt_inv_no.setText(data.invoiceNumber or "")
        self.txt_inv_date.setText(data.invoiceDate or "")
        self.txt_inv_curr.setText(data.currency or "USD - Dollar Mỹ")
        self.txt_fob_total.setText(str(data.goods_Total_FobValue or 0.0))
        self.txt_customs_no.setText(data.declarationNumbers or "")
        self.txt_customs_date.setText(data.declarationDates or "")
        self.txt_remarks.setText(data.remarks or "")

        self.chk_issued_retro.setChecked(bool(data.isIssuedRetroactively))
        self.txt_retro_reason.setText(data.issuedRetroactivelyReason or "tàu delay")

        # 3. Tờ khai nhập (Multi-row)
        self.table_import_decls.setRowCount(0)
        raw_imp_list = getattr(data, "importDeclarationList", []) or []
        for item in raw_imp_list:
            no = item.get("declarationNumber", "") if isinstance(item, dict) else getattr(item, "declarationNumber", "")
            dt = item.get("declarationDate", "") if isinstance(item, dict) else getattr(item, "declarationDate", "")
            self.add_import_declaration_row(str(no), str(dt))

        # 4. Hóa đơn VAT (Multi-row)
        self.table_vat_invoices.setRowCount(0)
        raw_vat_list = getattr(data, "invoiceVATList", []) or []
        for item in raw_vat_list:
            no = item.get("declarationNumber", "") if isinstance(item, dict) else getattr(item, "declarationNumber", "")
            dt = item.get("declarationDate", "") if isinstance(item, dict) else getattr(item, "declarationDate", "")
            self.add_vat_invoice_row(str(no), str(dt))

        # 5. Danh mục hàng hóa (Khóa cứng KILOGRAM)
        self.table_goods.setRowCount(0)
        items = data.goodItems or []
        for it in items:
            r = self.table_goods.rowCount()
            self.table_goods.insertRow(r)
            vals = [
                it.exportingHsCode or "",
                it.importingHsCode or "",
                it.goodsDescription or "",
                it.originCriterion or "WO",
                str(it.quantity if it.quantity is not None else ""),
                "KILOGRAM",  # Khóa cứng KILOGRAM
                str(it.grossWeight if it.grossWeight is not None else ""),
                "KILOGRAM",  # Khóa cứng KILOGRAM
                str(it.packageQuantity if it.packageQuantity is not None else ""),
                it.packageUnit or "CARTON",
                str(it.value if it.value is not None else ""),
                it.currency or "USD - Dollar Mỹ",
                it.markAndNumberOnPackage or "NO MARK",
                it.invoiceNumber or "",
                it.invoiceDate or ""
            ]
            for col, v in enumerate(vals):
                self.table_goods.setItem(r, col, QTableWidgetItem(str(v)))

        self.lbl_goods_count.setText(f"Tổng số: {self.table_goods.rowCount()} mặt hàng")

    # ----------------------------------------------------
    # TẬP HỢP DỮ LIỆU ĐỂ XUẤT JSON ECOSYS
    # ----------------------------------------------------
    def collect_data_from_inputs(self, include_full_base64: bool = False) -> dict:
        target_form = self.combo_form.currentText().split()[0]

        # Tờ khai nhập (Multi-row)
        imp_list = []
        raw_imp_nos, raw_imp_dates = [], []
        for r in range(self.table_import_decls.rowCount()):
            no_item = self.table_import_decls.item(r, 0)
            dt_item = self.table_import_decls.item(r, 1)
            no = no_item.text().strip() if no_item else ""
            dt = dt_item.text().strip() if dt_item else ""
            if no or dt:
                imp_list.append({"declarationNumber": no, "declarationDate": dt})
                if no: raw_imp_nos.append(no)
                if dt: raw_imp_dates.append(dt)

        # Hóa đơn VAT (Multi-row)
        vat_list = []
        raw_vat_nos, raw_vat_dates = [], []
        for r in range(self.table_vat_invoices.rowCount()):
            no_item = self.table_vat_invoices.item(r, 0)
            dt_item = self.table_vat_invoices.item(r, 1)
            no = no_item.text().strip() if no_item else ""
            dt = dt_item.text().strip() if dt_item else ""
            if no or dt:
                vat_list.append({"declarationNumber": no, "declarationDate": dt})
                if no: raw_vat_nos.append(no)
                if dt: raw_vat_dates.append(dt)

        # Bảng hàng hóa
        good_items = []
        for r in range(self.table_goods.rowCount()):
            def get_t(c):
                it = self.table_goods.item(r, c)
                return it.text().strip() if it else ""

            def get_f(c):
                t = get_t(c).replace(",", "")
                try: return float(t) if t else None
                except: return None

            def get_i(c):
                t = get_t(c).replace(",", "")
                try: return int(t) if t else None
                except: return None

            good_items.append({
                "exportingHsCode": get_t(0),
                "importingHsCode": get_t(1),
                "goodsDescription": get_t(2),
                "originCriterion": get_t(3) or "WO",
                "countryOfOrigin": "VN",
                "quantity": get_f(4),
                "quantityUnit": "KILOGRAM",  # Khóa cứng KILOGRAM
                "grossWeight": get_f(6),
                "grossWeightUnit": "KILOGRAM",  # Khóa cứng KILOGRAM
                "packageQuantity": get_i(8),
                "packageUnit": get_t(9) or "CARTON",
                "value": get_f(10),
                "currency": get_t(11) or "USD - Dollar Mỹ",
                "markAndNumberOnPackage": get_t(12) or "NO MARK",
                "invoiceNumber": get_t(13),
                "invoiceDate": get_t(14)
            })

        data = {
            "form": target_form,
            "issuing_Authority": self.txt_authority.text().strip(),
            "importing_Country": self.txt_country.text().strip(),
            "declarationPlace": self.txt_place.text().strip(),
            "taxCode": self.txt_exp_tax.text().strip(),
            "maSoDN": self.txt_exp_tax.text().strip(),
            "from_ExporterBusinessName": self.txt_exp_name_en.text().strip(),
            "from_ExporterBusinessNameVN": self.txt_exp_name_vn.text().strip(),
            "from_AddressLine1": self.txt_exp_addr1.text().strip(),
            "from_Addressline2": self.txt_exp_addr2.text().strip(),
            "to_ConsigneeName": self.txt_imp_name.text().strip(),
            "to_Addressline1": self.txt_imp_addr1.text().strip(),
            "to_Addressline2": self.txt_imp_addr2.text().strip(),
            "manu_Name": self.txt_manu_name.text().strip(),
            "manu_AddressLine1": self.txt_manu_addr1.text().strip(),
            "manu_AddressLine2": self.txt_manu_addr2.text().strip(),
            "importDeclarationList": imp_list,
            "importDeclarationNumbers": ", ".join(raw_imp_nos),
            "importDeclarationDates": ", ".join(raw_imp_dates),
            "invoiceVATList": vat_list,
            "invoiceVATNumbers": ", ".join(raw_vat_nos),
            "invoiceVATDates": ", ".join(raw_vat_dates),
            "route_TransportationType": self.txt_trans_type.text().strip(),
            "route_TransportName": self.txt_vessel.text().strip(),
            "route_PortOfLoading": self.txt_pol.text().strip(),
            "route_PortOfDischange": self.txt_pod.text().strip(),
            "route_PortOfDestination": self.txt_pod.text().strip(),
            "route_DepartureDepartureDate": self.txt_dep_date.text().strip(),
            "bill": self.txt_bill.text().strip(),
            "invoiceNumber": self.txt_inv_no.text().strip(),
            "invoiceDate": self.txt_inv_date.text().strip(),
            "currency": self.txt_inv_curr.text().strip(),
            "goods_Total_FobValue": float(self.txt_fob_total.text().replace(",", "").strip() or 0.0) if self.txt_fob_total.text().strip() else 0.0,
            "declarationNumbers": self.txt_customs_no.text().strip(),
            "declarationDates": self.txt_customs_date.text().strip(),
            "remarks": self.txt_remarks.text().strip(),
            "isIssuedRetroactively": self.chk_issued_retro.isChecked(),
            "issuedRetroactivelyReason": self.txt_retro_reason.text().strip(),
            "goodItems": good_items
        }

        matching_mode = self.combo_matching_mode.currentData() if hasattr(self, 'combo_matching_mode') else "by_number"
        data["attachmentMatchingMode"] = matching_mode

        # Thu thập attachments (Hỗ trợ Local Stream Bridge & Offline Base64)
        attachments = []
        vat_idx = 0
        imp_idx = 0
        for r in range(self.table_attachments.rowCount()):
            chk = self.table_attachments.item(r, 0)
            if chk and chk.checkState() == Qt.CheckState.Checked:
                fn = self.table_attachments.item(r, 1).text().strip()
                combo = self.table_attachments.cellWidget(r, 2)
                ftype = combo.currentData() if combo else "TAILIEUCHUNGMINH"
                path_item = self.table_attachments.item(r, 4)
                fpath = path_item.text().strip() if path_item else ""

                if fpath and os.path.exists(fpath):
                    try:
                        f_size = os.path.getsize(fpath)
                        mime, _ = mimetypes.guess_type(fpath)
                        mime = mime or "application/pdf"

                        # Đăng ký tệp vào Local Stream Server nội bộ (phục vụ truyền stream siêu tốc)
                        local_stream_server.register_attachment_file(fn, fpath)
                        port = local_stream_server.PORT or 14008
                        stream_url = f"http://127.0.0.1:{port}/file?key={urllib.parse.quote(fn)}"

                        if include_full_base64:
                            with open(fpath, "rb") as fb:
                                b_data = fb.read()
                            b64 = base64.b64encode(b_data).decode("utf-8")
                        else:
                            b64 = ""

                        # Tự động tìm số liên kết (Số HĐ hoặc Số tờ khai) từ tên file
                        linked_no = ""
                        nums = re.findall(r'\d+', fn)
                        target_row = 0
                        if ftype == "HoaDonVAT":
                            target_row = vat_idx
                            vat_idx += 1
                            for vat in vat_list:
                                v_no = vat.get("declarationNumber", "")
                                if v_no and any(n in v_no or v_no in n or n.lstrip('0') == v_no.lstrip('0') for n in nums):
                                    linked_no = v_no
                                    break
                        elif ftype in ["ToKhaiHQNK_Document", "ToKhaiXuatKhau"]:
                            target_row = imp_idx
                            imp_idx += 1
                            for imp in imp_list:
                                i_no = imp.get("declarationNumber", "")
                                if i_no and any(n in i_no or i_no in n or n.lstrip('0') == i_no.lstrip('0') for n in nums):
                                    linked_no = i_no
                                    break

                        attachments.append({
                            "fileName": fn,
                            "fileType": ftype,
                            "fileSize": f_size,
                            "mimeType": mime,
                            "streamUrl": stream_url,
                            "base64": b64,
                            "linkedNumber": linked_no,
                            "targetRow": target_row
                        })
                    except Exception as ex:
                        print(f"[File Error] {fpath}: {ex}")

        data["attachments"] = attachments
        return data

    def refresh_json_from_inputs(self):
        # Nạp JSON tóm tắt cho giao diện để tránh treo/đơ ứng dụng khi có file lớn
        data = self.collect_data_from_inputs(include_full_base64=False)
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        self.txt_json_view.setText(json_str)

    def on_tab_changed(self, index: int):
        if index == 4:  # Tab JSON
            self.refresh_json_from_inputs()

    def copy_json_to_clipboard(self):
        # Sử dụng Local Companion Stream Bridge: JSON siêu nhẹ ~5KB, sao chép trong 0.001s, KHÔNG GIẬT LAG
        data = self.collect_data_from_inputs(include_full_base64=False)
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        if not json_str:
            QMessageBox.warning(self, "Chưa có dữ liệu", "Vui lòng nhập liệu hoặc trích xuất trước khi sao chép.")
            return

        cb = QApplication.clipboard()
        cb.setText(json_str)
        att_count = len(data.get("attachments", []))
        port = local_stream_server.PORT or 14008
        QMessageBox.information(
            self,
            "Đã sao chép JSON Siêu Tốc",
            f"⚡ ĐÃ SAO CHÉP DỮ LIỆU C/O VÀO CLIPBOARD!\n\n"
            f"• Số chứng từ đính kèm: {att_count} tệp\n"
            f"• Kích thước JSON: ~{len(json_str)/1024:.1f} KB (Siêu nhẹ, 0% giật lag)\n"
            f"• Cổng Stream nội bộ: http://127.0.0.1:{port}\n\n"
            f"👉 Bây giờ bạn chỉ việc mở web eCoSys và bấm 'Dán từ Clipboard & Điền Ngay' trên tiện ích!"
        )

    def show_attachment_naming_guide(self):
        """Mở cửa sổ hướng dẫn đặt tên chứng từ dạng hộp thoại cuộn hiện đại (không tràn màn hình)"""
        dlg = AttachmentNamingGuideDialog(self)
        dlg.exec()

    def organize_attachment_folder(self):
        """Tự động gom và đổi tên toàn bộ file chứng từ vào một thư mục chuẩn hóa theo số thứ tự eCoSys"""
        data = self.collect_data_from_inputs(include_full_base64=False)
        attachments = data.get("attachments", [])
        if not attachments:
            QMessageBox.warning(self, "Chưa có chứng từ", "Vui lòng thêm tệp chứng từ vào bảng trước khi gom thư mục.")
            return

        inv_no = data.get("invoiceNumber", "ChungTu") or "ChungTu"
        inv_no = re.sub(r'[^\w\-]', '_', inv_no)
        target_dir = os.path.join(os.path.expanduser("~"), "Documents", f"BoChungTu_CO_{inv_no}")
        os.makedirs(target_dir, exist_ok=True)

        copied_count = 0
        type_prefix_map = {
            "ToKhaiXuatKhau": "01_ToKhaiXuatKhau",
            "HoaDonVAT": "02_HoaDonVAT",
            "ToKhaiHQNK_Document": "03_ToKhaiHQNK",
            "Invoice_attached_Doc": "04_HoaDonThuongMai",
            "VanDon": "05_VanDon_BL",
            "BangKeChiPhi": "06_BangKeChiPhi_BOM",
            "QuyTrinhSanXuat": "07_QuyTrinhSanXuat",
            "TAILIEUCHUNGMINH": "08_DonDeNghi_ChungTuKhac"
        }

        vat_row = 1
        imp_row = 1
        for r in range(self.table_attachments.rowCount()):
            chk = self.table_attachments.item(r, 0)
            if chk and chk.checkState() == Qt.CheckState.Checked:
                path_item = self.table_attachments.item(r, 4)
                fpath = path_item.text().strip() if path_item else ""
                combo = self.table_attachments.cellWidget(r, 2)
                ftype = combo.currentData() if combo else "TAILIEUCHUNGMINH"

                if fpath and os.path.exists(fpath):
                    prefix = type_prefix_map.get(ftype, "09_ChungTu")
                    if ftype == "HoaDonVAT":
                        new_name = f"{prefix}_Dong{vat_row}_{os.path.basename(fpath)}"
                        vat_row += 1
                    elif ftype == "ToKhaiHQNK_Document":
                        new_name = f"{prefix}_Dong{imp_row}_{os.path.basename(fpath)}"
                        imp_row += 1
                    else:
                        new_name = f"{prefix}_{os.path.basename(fpath)}"

                    dst_path = os.path.join(target_dir, new_name)
                    try:
                        shutil.copy2(fpath, dst_path)
                        copied_count += 1
                    except Exception as e:
                        print("Lỗi copy:", e)

        QApplication.clipboard().setText(target_dir)
        try:
            os.startfile(target_dir)
        except Exception:
            pass

        QMessageBox.information(
            self,
            "Đã gom thư mục chứng từ",
            f"✅ ĐÃ GOM VÀ CHUẨN HÓA {copied_count} TỆP VÀO THƯ MỤC:\n{target_dir}\n\n"
            f"• Toàn bộ file đã được đánh số thứ tự (01, 02, 03...) theo đúng từng mục trên eCoSys.\n"
            f"• Đường dẫn thư mục đã được lưu vào Clipboard!\n"
            f"• Bạn có thể kéo thả trực tiếp file từ thư mục này vào ô upload trên web eCoSys!"
        )

    def save_json_file(self):
        # Thu thập đầy đủ 100% dữ liệu Base64 để tệp JSON lưu ra có thể nạp thẳng vào Extension
        data = self.collect_data_from_inputs(include_full_base64=True)
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        if not json_str:
            QMessageBox.warning(self, "Chưa có dữ liệu", "Vui lòng nhập liệu hoặc trích xuất trước khi lưu file.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Lưu file JSON eCoSys", "ho_so_co.json", "JSON (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(json_str)
            QMessageBox.information(self, "Thành công", f"Đã lưu tệp JSON đầy đủ chứng từ (kèm Base64) tại:\n{path}")

    def load_saved_config(self):
        cfg = load_settings()
        if "api_key" in cfg:
            self.input_api_key.setText(cfg["api_key"])
        if "api_source" in cfg:
            src = cfg["api_source"]
            for i in range(self.combo_api_source.count()):
                if self.combo_api_source.itemData(i) == src:
                    self.combo_api_source.setCurrentIndex(i)
                    break
        if "api_base_url" in cfg and cfg["api_base_url"]:
            self.input_base_url.setText(cfg["api_base_url"])
        elif self.combo_api_source.currentData() == "apiz":
            self.input_base_url.setText("https://api.apiz.vn/v1")
        self.on_api_source_changed(self.combo_api_source.currentIndex())
        if "target_form" in cfg:
            idx = self.combo_form.findText(cfg["target_form"], Qt.MatchFlag.MatchStartsWith)
            if idx >= 0:
                self.combo_form.setCurrentIndex(idx)

    def save_current_config(self):
        m_name = self.combo_model.currentData() or ("gemini-3.8-flash" if self.combo_api_source.currentData() == "apiz" else "gemini-3.8-flash")
        cfg = {
            "api_key": self.input_api_key.text().strip(),
            "api_source": self.combo_api_source.currentData(),
            "api_base_url": self.input_base_url.text().strip(),
            "model_name": m_name,
            "target_form": self.combo_form.currentText().split()[0]
        }
        save_settings(cfg)

    def load_sample_data(self):
        if os.path.exists("sample_data.json"):
            try:
                with open("sample_data.json", "r", encoding="utf-8") as f:
                    d = json.load(f)
                co_data = CODeclarationData(**d)
                self.populate_inputs_from_data(co_data)
                self.refresh_json_from_inputs()
                QMessageBox.information(self, "Đã nạp mẫu", "Đã nạp dữ liệu mẫu từ sample_data.json thành công!")
            except Exception as e:
                QMessageBox.warning(self, "Lỗi nạp mẫu", f"Không thể đọc sample_data.json: {e}")
        else:
            QMessageBox.warning(self, "Thiếu tệp", "Không tìm thấy tệp sample_data.json.")

    def show_user_guide_dialog(self):
        """Mở cửa sổ hướng dẫn sử dụng toàn diện từ thêm chứng từ, AI đọc đến điền web eCoSys"""
        dlg = UserGuideDialog(self)
        dlg.exec()

    def keyPressEvent(self, event):
        """Bắt phím F1 để mở nhanh hướng dẫn sử dụng"""
        if event.key() == Qt.Key.Key_F1:
            self.show_user_guide_dialog()
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            try:
                self.worker.terminate()
            except Exception:
                pass
        if hasattr(self, 'chat_worker') and self.chat_worker and self.chat_worker.isRunning():
            try:
                self.chat_worker.terminate()
            except Exception:
                pass
        event.accept()
        QApplication.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = COExtractorApp()
    w.show()
    sys.exit(app.exec())
