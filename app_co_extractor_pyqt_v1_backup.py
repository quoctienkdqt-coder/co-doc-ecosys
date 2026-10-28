"""
Ứng dụng Desktop Trích xuất Chứng từ Khai báo C/O eCoSys (Bộ Công Thương)
Giao diện Windows 11 Fluent Design System (PyQt-Fluent-Widgets & PyQt6)
Tích hợp Gemini 3.8 Flash, APIZ Gateway & Trợ lý AI Copilot Nghiệp vụ C/O
"""

import sys
import os
import json
import base64
import mimetypes
import traceback
import re
from typing import List

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFileDialog, QHeaderView, QTableWidgetItem, QListWidgetItem,
    QStackedWidget, QLabel, QFrame, QTextEdit
)
from PyQt6.QtGui import QFont, QIcon, QColor, QDesktopServices

from qfluentwidgets import (
    FluentWindow, MSFluentWindow, NavigationInterface, NavigationItemPosition, FluentIcon,
    setTheme, Theme, setThemeColor,
    TitleLabel, SubtitleLabel, BodyLabel, CaptionLabel, StrongBodyLabel,
    CardWidget, ElevatedCardWidget, SimpleCardWidget,
    PrimaryPushButton, PushButton, ToolButton, TransparentToolButton,
    LineEdit, SearchLineEdit, PasswordLineEdit, TextEdit, PlainTextEdit,
    ComboBox, CheckBox, SwitchButton, ProgressBar, ProgressRing,
    TableWidget, ListWidget, SmoothScrollArea, ScrollArea,
    InfoBar, InfoBarPosition, MessageBox, SegmentedWidget, Pivot
)

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


def save_settings(data: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Lỗi lưu cài đặt: {e}")


# ========================================================
# BACKGROUND WORKER THREADS (Không bao giờ block UI thread)
# ========================================================
class ExtractionWorker(QThread):
    finished_signal = pyqtSignal(object, str, str)  # (co_data, raw_json, error_message)
    progress_signal = pyqtSignal(str)

    def __init__(self, api_key: str, file_paths: List[str], target_form: str, api_source: str = "official", api_base_url: str = ""):
        super().__init__()
        self.api_key = api_key
        self.file_paths = file_paths
        self.target_form = target_form
        self.api_source = api_source
        self.api_base_url = api_base_url

    def run(self):
        try:
            self.progress_signal.emit("Đang nạp file và kết nối Gemini 3.8 Flash...")
            co_data, raw_json = extract_co_data_from_files(
                api_key=self.api_key,
                file_paths=self.file_paths,
                target_form=self.target_form,
                model_name="gemini-3.8-flash",
                api_source=self.api_source,
                api_base_url=self.api_base_url
            )
            self.finished_signal.emit(co_data, raw_json, "")
        except Exception as e:
            err_trace = traceback.format_exc()
            self.finished_signal.emit(None, "", f"{str(e)}\n{err_trace}")


class ChatbotWorker(QThread):
    reply_signal = pyqtSignal(str, str)  # (reply_text, error_message)

    def __init__(self, api_key: str, question: str, history: List[dict] = None, api_source: str = "official", api_base_url: str = ""):
        super().__init__()
        self.api_key = api_key
        self.question = question
        self.history = history or []
        self.api_source = api_source
        self.api_base_url = api_base_url

    def run(self):
        try:
            ans = ask_co_advisor(
                api_key=self.api_key,
                question=self.question,
                history=self.history,
                api_source=self.api_source,
                api_base_url=self.api_base_url,
                model_name="gemini-3.8-flash"
            )
            self.reply_signal.emit(ans, "")
        except Exception as e:
            self.reply_signal.emit("", str(e))


class TestApiWorker(QThread):
    test_signal = pyqtSignal(bool, str)  # (success, message)

    def __init__(self, api_key: str, api_source: str = "official", api_base_url: str = ""):
        super().__init__()
        self.api_key = api_key
        self.api_source = api_source
        self.api_base_url = api_base_url

    def run(self):
        try:
            ans = ask_co_advisor(
                api_key=self.api_key,
                question="Chào bạn! Kiểm tra kết nối API.",
                api_source=self.api_source,
                api_base_url=self.api_base_url,
                model_name="gemini-3.8-flash"
            )
            if ans:
                self.test_signal.emit(True, "Kết nối thành công tới mô hình Gemini 3.8 Flash!")
            else:
                self.test_signal.emit(False, "Không nhận được phản hồi từ mô hình.")
        except Exception as e:
            self.test_signal.emit(False, str(e))


# ========================================================
# 1. TAB TRÍCH XUẤT C/O (HOME INTERFACE)
# ========================================================
class HomeInterface(QWidget):
    def __init__(self, main_window):
        super().__init__(parent=main_window)
        self.setObjectName("homeInterface")
        self.main_window = main_window

        self.selected_files = []
        self.current_co_data = None

        self.init_ui()

    def init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # Smooth Scroll Area cho toàn bộ trang
        self.scroll_area = SmoothScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        self.layout = QVBoxLayout(container)
        self.layout.setContentsMargins(32, 24, 32, 32)
        self.layout.setSpacing(18)

        # 1. Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        title = TitleLabel("Trích Xuất Hồ Sơ C/O Bằng AI")
        subtitle = CaptionLabel("Tự động đọc Đơn đề nghị Mẫu 04, Vận đơn, Hóa đơn thương mại, Bảng kê BOM & Tờ khai HQ để điền chuẩn eCoSys")
        subtitle.setStyleSheet("color: #64748b; font-size: 13px;")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        self.layout.addLayout(header_layout)

        # 2. Upload Files Card (CardWidget)
        self.setup_upload_card()

        # 3. Action & Progress Card (ElevatedCardWidget)
        self.setup_action_card()

        # 4. Result Tabs Card (CardWidget)
        self.setup_result_card()

        self.scroll_area.setWidget(container)
        outer_layout.addWidget(self.scroll_area)

    def setup_upload_card(self):
        card = CardWidget(self)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        top_row = QHBoxLayout()
        title = SubtitleLabel("📁 Danh Sách Tệp Chứng Từ Xuất Khẩu")
        top_row.addWidget(title)
        top_row.addStretch()

        self.lbl_file_count = CaptionLabel("0 tệp đã chọn")
        self.lbl_file_count.setStyleSheet("color: #0078d4; font-weight: 600;")
        top_row.addWidget(self.lbl_file_count)
        lay.addLayout(top_row)

        # File List Widget
        self.list_files = ListWidget(card)
        self.list_files.setMinimumHeight(110)
        self.list_files.setMaximumHeight(160)
        lay.addWidget(self.list_files)

        # Buttons row
        btn_row = QHBoxLayout()
        self.btn_add_files = PrimaryPushButton(FluentIcon.ADD, "Thêm tệp chứng từ (PDF, Ảnh)...", card)
        self.btn_add_files.clicked.connect(self.choose_files)
        btn_row.addWidget(self.btn_add_files)

        self.btn_del_file = PushButton(FluentIcon.DELETE, "Xóa tệp chọn", card)
        self.btn_del_file.clicked.connect(self.remove_selected_file)
        btn_row.addWidget(self.btn_del_file)

        self.btn_clear_files = PushButton(FluentIcon.BROOM, "Xóa tất cả", card)
        self.btn_clear_files.clicked.connect(self.clear_all_files)
        btn_row.addWidget(self.btn_clear_files)

        btn_row.addStretch()
        lay.addLayout(btn_row)

        self.layout.addWidget(card)

    def setup_action_card(self):
        card = ElevatedCardWidget(self)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(16)

        lbl_form = StrongBodyLabel("Mẫu C/O Cần Khai:", card)
        ctrl_row.addWidget(lbl_form)

        self.combo_form = ComboBox(card)
        forms = [
            "EUR.1 (Hiệp định EVFTA - Thị trường EU)",
            "Form D (Hiệp định ATIGA - Thị trường ASEAN)",
            "Form E (Hiệp định ACFTA - Thị trường Trung Quốc)",
            "Form AK (Hiệp định AKFTA - Hàn Quốc)",
            "Form VK (Hiệp định VKFTA - Hàn Quốc)",
            "Form VJ (Hiệp định VJEPA - Nhật Bản)",
            "Form AJ (Hiệp định AJCEP - Nhật Bản)",
            "Form CPTPP (Hiệp định CPTPP)",
            "Form AANZ (Hiệp định AANZFTA - Úc, New Zealand)",
            "Form B (Không ưu đãi - Thị trường chung)"
        ]
        self.combo_form.addItems(forms)
        self.combo_form.setMinimumWidth(320)
        ctrl_row.addWidget(self.combo_form)

        ctrl_row.addStretch()

        self.btn_extract = PrimaryPushButton(FluentIcon.SEND_FILL, "⚡ TRÍCH XUẤT CHỨNG TỪ BẰNG AI (3.8 FLASH)", card)
        self.btn_extract.setFixedHeight(40)
        self.btn_extract.setStyleSheet("font-weight: bold; font-size: 14px; padding: 0 24px;")
        self.btn_extract.clicked.connect(self.start_extraction)
        ctrl_row.addWidget(self.btn_extract)

        lay.addLayout(ctrl_row)

        # Progress bar
        self.progress_bar = ProgressBar(card)
        self.progress_bar.setVisible(False)
        lay.addWidget(self.progress_bar)

        self.lbl_status = CaptionLabel("Sẵn sàng nạp tệp chứng từ và trích xuất...", card)
        self.lbl_status.setStyleSheet("color: #64748b; font-size: 12px;")
        lay.addWidget(self.lbl_status)

        self.layout.addWidget(card)

    def setup_result_card(self):
        card = CardWidget(self)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.addWidget(SubtitleLabel("📊 Dữ Liệu Khai Báo eCoSys (30 Trường & Tệp Đính Kèm)"))
        header_row.addStretch()
        lay.addLayout(header_row)

        # Segmented Navigation Bar
        self.pivot = SegmentedWidget(card)
        self.stacked_views = QStackedWidget(card)

        # 5 Views
        self.view_parties = self.create_parties_view()
        self.view_transport = self.create_transport_view()
        self.view_goods = self.create_goods_view()
        self.view_attachments = self.create_attachments_view()
        self.view_json = self.create_json_view()

        self.stacked_views.addWidget(self.view_parties)
        self.stacked_views.addWidget(self.view_transport)
        self.stacked_views.addWidget(self.view_goods)
        self.stacked_views.addWidget(self.view_attachments)
        self.stacked_views.addWidget(self.view_json)

        self.pivot.addItem("parties", "🏢 1. Doanh nghiệp (Exporter / Consignee)", onClick=lambda: self.stacked_views.setCurrentIndex(0))
        self.pivot.addItem("transport", "🚢 2. Vận chuyển, Cảng & Hóa đơn", onClick=lambda: self.stacked_views.setCurrentIndex(1))
        self.pivot.addItem("goods", "📦 3. Danh mục hàng hóa (Items)", onClick=lambda: self.stacked_views.setCurrentIndex(2))
        self.pivot.addItem("attachments", "📎 4. Bản Map chứng từ eCoSys", onClick=lambda: self.stacked_views.setCurrentIndex(3))
        self.pivot.addItem("json", "💾 5. JSON eCoSys (Clipboard)", onClick=lambda: self.stacked_views.setCurrentIndex(4))

        self.pivot.setCurrentItem("parties")
        lay.addWidget(self.pivot)
        lay.addWidget(self.stacked_views)

        self.layout.addWidget(card)

    # ----------------------------------------------------
    # VIEW 1: EXPORTER & CONSIGNEE
    # ----------------------------------------------------
    def create_parties_view(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(14)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)

        # Exporter
        grid.addWidget(StrongBodyLabel("Tên DN xuất khẩu (English):"), 0, 0)
        self.txt_exp_name_en = LineEdit()
        self.txt_exp_name_en.setPlaceholderText("VD: NHA TRANG BAY JOINT STOCK COMPANY")
        grid.addWidget(self.txt_exp_name_en, 0, 1)

        grid.addWidget(StrongBodyLabel("Tên DN xuất khẩu (Tiếng Việt):"), 1, 0)
        self.txt_exp_name_vn = LineEdit()
        self.txt_exp_name_vn.setPlaceholderText("VD: CÔNG TY CỔ PHẦN VỊNH NHA TRANG")
        grid.addWidget(self.txt_exp_name_vn, 1, 1)

        grid.addWidget(StrongBodyLabel("Mã số thuế / Mã DN:"), 2, 0)
        self.txt_exp_tax = LineEdit()
        self.txt_exp_tax.setPlaceholderText("VD: 4200722962")
        grid.addWidget(self.txt_exp_tax, 2, 1)

        grid.addWidget(StrongBodyLabel("Địa chỉ DN (Dòng 1 - max 70):"), 3, 0)
        self.txt_exp_addr1 = LineEdit()
        self.txt_exp_addr1.setPlaceholderText("LOT K1, K2, K3 AND A PART OF K4, SUOI DAU INDUSTRIAL ZONE")
        grid.addWidget(self.txt_exp_addr1, 3, 1)

        grid.addWidget(StrongBodyLabel("Địa chỉ DN (Dòng 2):"), 4, 0)
        self.txt_exp_addr2 = LineEdit()
        self.txt_exp_addr2.setPlaceholderText("CAM LAM COMMUNE, KHANH HOA PROVINCE, VIETNAM")
        grid.addWidget(self.txt_exp_addr2, 4, 1)

        # Consignee
        grid.addWidget(StrongBodyLabel("Tên người nhận hàng (Consignee):"), 5, 0)
        self.txt_imp_name = LineEdit()
        self.txt_imp_name.setPlaceholderText("VD: MARISO SEAFOOD LLC")
        grid.addWidget(self.txt_imp_name, 5, 1)

        grid.addWidget(StrongBodyLabel("Địa chỉ nhận hàng (Dòng 1):"), 6, 0)
        self.txt_imp_addr1 = LineEdit()
        self.txt_imp_addr1.setPlaceholderText("VD: VABADUSE PST 8/1, KIVIOLI")
        grid.addWidget(self.txt_imp_addr1, 6, 1)

        grid.addWidget(StrongBodyLabel("Địa chỉ nhận hàng (Dòng 2):"), 7, 0)
        self.txt_imp_addr2 = LineEdit()
        self.txt_imp_addr2.setPlaceholderText("VD: LUGANUSE VALD, ESTONIA 43125")
        grid.addWidget(self.txt_imp_addr2, 7, 1)

        # Meta
        grid.addWidget(StrongBodyLabel("Tổ chức cấp phép:"), 8, 0)
        self.txt_authority = LineEdit()
        self.txt_authority.setPlaceholderText("VD: Sở Công Thương Tỉnh Khánh Hòa")
        grid.addWidget(self.txt_authority, 8, 1)

        grid.addWidget(StrongBodyLabel("Nước nhập khẩu (Chuẩn eCoSys):"), 9, 0)
        self.txt_country = LineEdit()
        self.txt_country.setPlaceholderText("VD: Lithuania (Litva - EU)")
        grid.addWidget(self.txt_country, 9, 1)

        grid.addWidget(StrongBodyLabel("Nơi khai báo:"), 10, 0)
        self.txt_place = LineEdit()
        self.txt_place.setPlaceholderText("VD: Khánh Hòa")
        grid.addWidget(self.txt_place, 10, 1)

        lay.addLayout(grid)
        lay.addStretch()
        return w

    # ----------------------------------------------------
    # VIEW 2: TRANSPORT, INVOICE & CUSTOMS
    # ----------------------------------------------------
    def create_transport_view(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(14)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)

        # Transport
        grid.addWidget(StrongBodyLabel("Phương thức vận chuyển:"), 0, 0)
        self.txt_trans_type = LineEdit()
        self.txt_trans_type.setText("Đường biển")
        grid.addWidget(self.txt_trans_type, 0, 1)

        grid.addWidget(StrongBodyLabel("Tên tàu / Chuyến / Phương tiện:"), 1, 0)
        self.txt_vessel = LineEdit()
        self.txt_vessel.setPlaceholderText("VD: SEASPAN BENEFACTOR 077W")
        grid.addWidget(self.txt_vessel, 1, 1)

        grid.addWidget(StrongBodyLabel("Cảng bốc hàng (VN):"), 2, 0)
        self.txt_pol = LineEdit()
        self.txt_pol.setPlaceholderText("VD: CANG CAT LAI (HCM) / HO CHI MINH")
        grid.addWidget(self.txt_pol, 2, 1)

        grid.addWidget(StrongBodyLabel("Cảng dỡ hàng:"), 3, 0)
        self.txt_pod = LineEdit()
        self.txt_pod.setPlaceholderText("VD: KLAIPEDA, LITHUANIA")
        grid.addWidget(self.txt_pod, 3, 1)

        grid.addWidget(StrongBodyLabel("Ngày khởi hành (DD/MM/YYYY):"), 4, 0)
        self.txt_dep_date = LineEdit()
        self.txt_dep_date.setPlaceholderText("VD: 09/10/2026")
        grid.addWidget(self.txt_dep_date, 4, 1)

        grid.addWidget(StrongBodyLabel("Số Vận đơn (Bill of Lading):"), 5, 0)
        self.txt_bill = LineEdit()
        self.txt_bill.setPlaceholderText("VD: YMJAN490421110")
        grid.addWidget(self.txt_bill, 5, 1)

        # Invoice
        grid.addWidget(StrongBodyLabel("Số hóa đơn thương mại:"), 6, 0)
        self.txt_inv_no = LineEdit()
        self.txt_inv_no.setPlaceholderText("VD: NT60195")
        grid.addWidget(self.txt_inv_no, 6, 1)

        grid.addWidget(StrongBodyLabel("Ngày hóa đơn (DD/MM/YYYY):"), 7, 0)
        self.txt_inv_date = LineEdit()
        self.txt_inv_date.setPlaceholderText("VD: 01/10/2026")
        grid.addWidget(self.txt_inv_date, 7, 1)

        grid.addWidget(StrongBodyLabel("Loại tiền & Tổng FOB:"), 8, 0)
        h_fob = QHBoxLayout()
        self.txt_inv_curr = LineEdit()
        self.txt_inv_curr.setText("USD - Dollar Mỹ")
        self.txt_inv_curr.setFixedWidth(140)
        self.txt_fob_total = LineEdit()
        self.txt_fob_total.setPlaceholderText("Tổng trị giá FOB (VD: 251081.55)")
        h_fob.addWidget(self.txt_inv_curr)
        h_fob.addWidget(self.txt_fob_total)
        grid.addLayout(h_fob, 8, 1)

        # Customs Export
        grid.addWidget(StrongBodyLabel("Số & Ngày Tờ khai XK (Mục 25, 26):"), 9, 0)
        h_exp_decl = QHBoxLayout()
        self.txt_customs_no = LineEdit()
        self.txt_customs_no.setPlaceholderText("Số tờ khai XK (12 số)")
        self.txt_customs_date = LineEdit()
        self.txt_customs_date.setPlaceholderText("Ngày tờ khai XK (DD/MM/YYYY)")
        h_exp_decl.addWidget(self.txt_customs_no)
        h_exp_decl.addWidget(self.txt_customs_date)
        grid.addLayout(h_exp_decl, 9, 1)

        # Retroactive
        grid.addWidget(StrongBodyLabel("C/O cấp sau (Issued Retroactively):"), 10, 0)
        h_retro = QHBoxLayout()
        self.chk_issued_retro = CheckBox("Tích chọn C/O cấp sau")
        self.txt_retro_reason = LineEdit()
        self.txt_retro_reason.setPlaceholderText("Lý do xin cấp sau (VD: tàu delay)")
        self.txt_retro_reason.setText("tàu delay")
        h_retro.addWidget(self.chk_issued_retro)
        h_retro.addWidget(self.txt_retro_reason)
        grid.addLayout(h_retro, 10, 1)

        # Import Declarations (Multi-row)
        grid.addWidget(StrongBodyLabel("Tờ khai HQ nhập khẩu (Mục 27, 28):"), 11, 0)
        h_imp_decl = QHBoxLayout()
        self.txt_import_decl_no = LineEdit()
        self.txt_import_decl_no.setPlaceholderText("Các số tờ khai NK, cách nhau dấu phẩy (VD: 102345678901, 102345678902)")
        self.txt_import_decl_date = LineEdit()
        self.txt_import_decl_date.setPlaceholderText("Các ngày tờ khai NK tương ứng (VD: 15/09/2026, 18/09/2026)")
        h_imp_decl.addWidget(self.txt_import_decl_no)
        h_imp_decl.addWidget(self.txt_import_decl_date)
        grid.addLayout(h_imp_decl, 11, 1)

        # Invoice VAT (Multi-row)
        grid.addWidget(StrongBodyLabel("Hóa đơn VAT mua NL (Mục 29, 30):"), 12, 0)
        h_vat_decl = QHBoxLayout()
        self.txt_vat_invoice_no = LineEdit()
        self.txt_vat_invoice_no.setPlaceholderText("Các số hóa đơn VAT, cách nhau dấu phẩy (VD: 00129, 00130)")
        self.txt_vat_invoice_date = LineEdit()
        self.txt_vat_invoice_date.setPlaceholderText("Các ngày hóa đơn VAT tương ứng (VD: 20/09/2026, 22/09/2026)")
        h_vat_decl.addWidget(self.txt_vat_invoice_no)
        h_vat_decl.addWidget(self.txt_vat_invoice_date)
        grid.addLayout(h_vat_decl, 12, 1)

        # Manufacturer
        grid.addWidget(StrongBodyLabel("Tên & Địa chỉ Nhà sản xuất:"), 13, 0)
        h_manu = QHBoxLayout()
        self.txt_manu_name = LineEdit()
        self.txt_manu_name.setPlaceholderText("Tên nhà sản xuất")
        self.txt_manu_addr1 = LineEdit()
        self.txt_manu_addr1.setPlaceholderText("Địa chỉ nhà sản xuất")
        self.txt_manu_addr2 = LineEdit()
        self.txt_manu_addr2.setPlaceholderText("Địa chỉ dòng 2 (nếu có)")
        h_manu.addWidget(self.txt_manu_name)
        h_manu.addWidget(self.txt_manu_addr1)
        h_manu.addWidget(self.txt_manu_addr2)
        grid.addLayout(h_manu, 13, 1)

        # Remarks
        grid.addWidget(StrongBodyLabel("Ghi chú thêm (Remarks):"), 14, 0)
        self.txt_remarks = LineEdit()
        self.txt_remarks.setPlaceholderText("VD: Ghi chú đặc biệt cho lô hàng (nếu có)")
        grid.addWidget(self.txt_remarks, 14, 1)

        lay.addLayout(grid)
        lay.addStretch()
        return w

    # ----------------------------------------------------
    # VIEW 3: GOODS ITEMS TABLE
    # ----------------------------------------------------
    def create_goods_view(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.addWidget(StrongBodyLabel("Danh mục mặt hàng xuất nhập khẩu (Đơn vị tính chuẩn: KILOGRAM)"))
        top_row.addStretch()
        self.btn_add_good = PrimaryPushButton(FluentIcon.ADD, "Thêm mặt hàng", w)
        self.btn_add_good.clicked.connect(self.add_empty_good_row)
        self.btn_del_good = PushButton(FluentIcon.DELETE, "Xóa mặt hàng", w)
        self.btn_del_good.clicked.connect(self.delete_selected_good_row)
        top_row.addWidget(self.btn_add_good)
        top_row.addWidget(self.btn_del_good)
        lay.addLayout(top_row)

        self.table_goods = TableWidget(w)
        headers = [
            "Mã HS XK", "Mã HS NK", "Mô tả hàng hóa", "Tiêu chí XX",
            "Nước XX", "Số lượng", "ĐVT", "Ký mã hiệu", "Số kiện",
            "Loại kiện", "Trọng lượng GW", "ĐVT GW", "Trị giá FOB", "Tiền tệ",
            "Số HĐ", "Ngày HĐ"
        ]
        self.table_goods.setColumnCount(len(headers))
        self.table_goods.setHorizontalHeaderLabels(headers)
        self.table_goods.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_goods.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_goods.setAlternatingRowColors(True)
        lay.addWidget(self.table_goods)

        return w

    # ----------------------------------------------------
    # VIEW 4: ATTACHMENTS MAPPING TABLE (BẢN MAP VỊ TRÍ)
    # ----------------------------------------------------
    def create_attachments_view(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        info_card = SimpleCardWidget(w)
        info_lay = QVBoxLayout(info_card)
        info_lay.setContentsMargins(16, 12, 16, 12)
        lbl = BodyLabel(
            "📌 BẢN MAP VỊ TRÍ TẢI LÊN ECOSYS: Mỗi tệp được phân loại chính xác theo NỘI DUNG THỰC TẾ và đưa vào ô tải lên tương ứng trên web.\n"
            "Bạn có thể đổi vị trí nạp bằng hộp Dropbox ở Cột 3, hoặc bấm nút bên dưới để AI tự động phân loại lại theo nội dung tệp PDF."
        )
        lbl.setStyleSheet("color: #475569; font-size: 13px; line-height: 1.4;")
        info_lay.addWidget(lbl)
        lay.addWidget(info_card)

        tools = QHBoxLayout()
        self.btn_add_att = PrimaryPushButton(FluentIcon.ADD, "Thêm tệp chứng từ...", w)
        self.btn_add_att.clicked.connect(self.add_attachment_files)
        self.btn_del_att = PushButton(FluentIcon.DELETE, "Bỏ tệp", w)
        self.btn_del_att.clicked.connect(self.delete_attachment_file)
        self.btn_detect_att = PrimaryPushButton(FluentIcon.SEARCH, "🔍 Tự động nhận diện lại loại chứng từ (theo nội dung AI)", w)
        self.btn_detect_att.clicked.connect(self.auto_detect_attachment_types)

        tools.addWidget(self.btn_add_att)
        tools.addWidget(self.btn_del_att)
        tools.addWidget(self.btn_detect_att)
        tools.addStretch()
        lay.addLayout(tools)

        self.table_attachments = TableWidget(w)
        headers = ["Nạp", "Tên tệp", "Vị trí tải lên eCoSys (Dropbox)", "Kích thước", "Đường dẫn gốc"]
        self.table_attachments.setColumnCount(len(headers))
        self.table_attachments.setHorizontalHeaderLabels(headers)
        self.table_attachments.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_attachments.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_attachments.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table_attachments.setAlternatingRowColors(True)
        lay.addWidget(self.table_attachments)

        return w

    # ----------------------------------------------------
    # VIEW 5: JSON ECOSYS
    # ----------------------------------------------------
    def create_json_view(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        bar = QHBoxLayout()
        self.chk_include_base64 = CheckBox("Kèm mã hóa Base64 tệp chứng từ để Extension tự động nạp tệp lên web eCoSys", w)
        self.chk_include_base64.setChecked(True)
        bar.addWidget(self.chk_include_base64)

        bar.addStretch()

        self.btn_copy_json = PrimaryPushButton(FluentIcon.COPY, "📋 SAO CHÉP JSON (DÁN VÀO EXTENSION)", w)
        self.btn_copy_json.setFixedHeight(38)
        self.btn_copy_json.setStyleSheet("font-weight: bold; font-size: 13px; padding: 0 20px;")
        self.btn_copy_json.clicked.connect(self.copy_json_to_clipboard)
        bar.addWidget(self.btn_copy_json)

        lay.addLayout(bar)

        self.txt_json = TextEdit(w)
        self.txt_json.setFont(QFont("Consolas", 10))
        self.txt_json.setPlaceholderText("Dữ liệu JSON eCoSys sẽ tự động cập nhật tại đây sau khi trích xuất...")
        lay.addWidget(self.txt_json)

        return w

    # ----------------------------------------------------
    # THAO TÁC FILE & NHẬN DIỆN CHỨNG TỪ THEO NỘI DUNG (PyMuPDF)
    # ----------------------------------------------------
    def choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn tệp chứng từ (PDF, Ảnh)",
            "",
            "Tệp chứng từ (*.pdf *.png *.jpg *.jpeg *.bmp *.tiff);;Tất cả tệp (*.*)"
        )
        if files:
            for f in files:
                if f not in self.selected_files:
                    self.selected_files.append(f)
                    self.list_files.addItem(f"📄 {os.path.basename(f)}  ({round(os.path.getsize(f)/1024, 1)} KB)")
            self.lbl_file_count.setText(f"{len(self.selected_files)} tệp đã chọn")

    def remove_selected_file(self):
        row = self.list_files.currentRow()
        if row >= 0:
            self.list_files.takeItem(row)
            self.selected_files.pop(row)
            self.lbl_file_count.setText(f"{len(self.selected_files)} tệp đã chọn")

    def clear_all_files(self):
        self.list_files.clear()
        self.selected_files.clear()
        self.lbl_file_count.setText("0 tệp đã chọn")

    def detect_file_type_from_content(self, file_path: str) -> str:
        """
        Nhận diện loại chứng từ eCoSys dựa vào NỘI DUNG THỰC TẾ BÊN TRONG TỆP (PyMuPDF).
        Hỗ trợ đọc cả trang quay ngược 180 độ.
        """
        if not file_path or not os.path.exists(file_path):
            return "TAILIEUCHUNGMINH"

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            try:
                import fitz
                doc = fitz.open(file_path)
                full_text = ""
                for i in range(min(4, len(doc))):
                    page = doc[i]
                    txt = page.get_text() or ""
                    full_text += " " + txt

                txt_clean = re.sub(r'\s+', ' ', full_text.upper())

                # 1. Hóa đơn thương mại (Commercial Invoice)
                if any(k in txt_clean for k in ["COMMERCIAL INVOICE", "HOÁ ĐƠN THƯƠNG MẠI", "HÓA ĐƠN THƯƠNG MẠI", "PROFORMA INVOICE"]):
                    if not any(v in txt_clean for v in ["HOÁ ĐƠN GIÁ TRỊ GIA TĂNG", "HÓA ĐƠN GIÁ TRỊ GIA TĂNG", "HÓA ĐƠN VAT"]):
                        return "Invoice_attached_Doc"

                # 2. Vận tải đơn / Bill of Lading (VanDon / TRANSPORT_INFO)
                if any(k in txt_clean for k in ["BILL OF LADING", "OCEAN BILL", "WAYBILL", "SEAWAY BILL", "AIR WAYBILL", "CARRIER'S RECEIPT"]):
                    return "VanDon"

                # 3. Hóa đơn GTGT / VAT mua nguyên liệu trong nước (Mục 29, 30)
                if any(k in txt_clean for k in ["GIÁ TRỊ GIA TĂNG", "GIA TRI GIA TANG", "HOÁ ĐƠN GTGT", "HÓA ĐƠN GTGT", "HOÁ ĐƠN VAT", "HÓA ĐƠN VAT"]):
                    return "HoaDonVAT"

                # 4. Tờ khai hải quan (Mục 25, 26 hoặc Mục 27, 28)
                if any(k in txt_clean for k in ["TỜ KHAI HẢI QUAN", "TO KHAI HAI QUAN", "CUSTOMS DECLARATION", "CHI CỤC HẢI QUAN"]):
                    if any(nk in txt_clean for nk in ["NHẬP KHẨU", "NHAP KHAU", "NHẬP NGUYÊN LIỆU"]):
                        return "ToKhaiHQNK_Document"
                    return "ToKhaiXuatKhau"

                # 5. Bảng kê chi phí / Hàm lượng (BangKeChiPhi - DOCUMENT_PROVING)
                if any(k in txt_clean for k in ["BẢNG KÊ", "BANG KE", "TIÊU CHÍ XUẤT XỨ", "TIEU CHI XUAT XU", "HÀM LƯỢNG GIÁ TRỊ", "RVC", "CTC", "BOM", "BẢNG TÍNH TOÁN"]):
                    return "BangKeChiPhi"

                # 6. Quy trình sản xuất (QuyTrinhSanXuat - DOCUMENT_PROVING)
                if any(k in txt_clean for k in ["QUY TRÌNH SẢN XUẤT", "QUY TRINH SAN XUAT", "QUY TRÌNH CHẾ BIẾN", "MANUFACTURING PROCESS", "PRODUCTION PROCESS"]):
                    return "QuyTrinhSanXuat"

                # 7. Đơn đề nghị cấp C/O (Mẫu 04)
                if any(k in txt_clean for k in ["ĐƠN ĐỀ NGHỊ CẤP C/O", "DON DE NGHI CAP C/O", "MẪU SỐ 04", "MAU SO 04"]):
                    return "TAILIEUCHUNGMINH"

                # 8. Hợp đồng mua bán (HopDongMuaBan - DOCUMENT_PROVING)
                if any(k in txt_clean for k in ["HỢP ĐỒNG MUA BÁN", "HOP DONG MUA BAN", "CONTRACT", "SALES CONTRACT"]):
                    return "HopDongMuaBan"

                # 9. Giấy phép xuất khẩu (GiayPhepXuatKhau - DOCUMENT_PROVING)
                if any(k in txt_clean for k in ["GIẤY PHÉP XUẤT KHẨU", "GIAY PHEP XUAT KHAU", "EXPORT LICENSE"]):
                    return "GiayPhepXuatKhau"

            except Exception:
                pass

        return self.detect_file_type_from_name(os.path.basename(file_path))

    def detect_file_type_from_name(self, filename: str) -> str:
        fn = filename.lower().replace("-", "_").replace(" ", "_")
        raw_clean = filename.lower().replace(" ", "").replace("_", "").replace("-", "")

        if any(k in fn or k in raw_clean for k in ["hop_dong", "hopdong", "contract"]):
            return "HopDongMuaBan"
        if any(k in fn or k in raw_clean for k in ["giayphep", "giay_phep", "license"]):
            return "GiayPhepXuatKhau"
        if any(k in fn or k in raw_clean for k in ["quytrinh", "quy_trinh", "sanxuat", "san_xuat", "process", "production"]):
            return "QuyTrinhSanXuat"
        if any(k in fn or k in raw_clean for k in ["bang_ke", "bangke", "cost", "rvc", "ctc", "bom", "tieu_chi", "tieuchi", "hamluong", "ham_luong"]):
            return "BangKeChiPhi"
        if any(k in fn or k in raw_clean for k in ["bill", "bl", "b_l", "van_don", "vandon", "airway", "awb", "sur", "seaway", "booking"]):
            return "VanDon"
        if any(k in fn or k in raw_clean for k in ["tokhai_xk", "tokhaixk", "tkhq_xk", "tokhai", "to_khai", "tkhq", "customs", "declaration", "haiquan"]):
            if any(nk in fn or nk in raw_clean for nk in ["nhap", "nk", "import", "nguyenlieu"]):
                return "ToKhaiHQNK_Document"
            return "ToKhaiXuatKhau"
        if any(k in fn or k in raw_clean for k in ["commercial_invoice", "commercialinvoice", "inv", "commercial", "invoice"]):
            if any(v in fn or v in raw_clean for v in ["vat", "gtgt", "noidia"]):
                return "HoaDonVAT"
            return "Invoice_attached_Doc"
        if any(k in fn or k in raw_clean for k in ["vat", "gtgt", "hoa_don_vat", "hoadonvat", "hoadon", "hoa_don"]):
            return "HoaDonVAT"

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
        InfoBar.success(
            title="Nhận diện hoàn tất",
            content=f"Đã tự động phân loại {count} tệp chứng từ dựa trên NỘI DUNG THỰC TẾ và tên tệp!",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3500,
            parent=self
        )

    def add_attachment_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn tệp chứng từ đính kèm (PDF, Ảnh...)",
            "",
            "Chứng từ (*.pdf *.png *.jpg *.jpeg *.doc *.docx *.xls *.xlsx);;Tất cả tệp (*.*)"
        )
        if files:
            for f in files:
                ftype = self.detect_file_type_from_content(f)
                self.add_attachment_row(f, ftype, checked=True)

    def delete_attachment_file(self):
        row = self.table_attachments.currentRow()
        if row >= 0:
            self.table_attachments.removeRow(row)

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

        combo_type = ComboBox()
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

    def populate_attachments_from_files(self, file_paths: list, allowed_types: list = None):
        self.table_attachments.setRowCount(0)
        for p in file_paths:
            ftype = self.detect_file_type_from_content(p)
            is_checked = True
            if allowed_types and len(allowed_types) > 0:
                is_checked = (
                    ftype in allowed_types or
                    (ftype == "Invoice_attached_Doc" and ("HoaDonVAT" in allowed_types or "Invoice_attached_Doc" in allowed_types)) or
                    (ftype == "HoaDonVAT" and ("HoaDonVAT" in allowed_types or "Invoice_attached_Doc" in allowed_types)) or
                    (ftype == "TAILIEUCHUNGMINH" and "TAILIEUCHUNGMINH" in allowed_types)
                )
            self.add_attachment_row(p, ftype, checked=is_checked)

    # ----------------------------------------------------
    # BẮT ĐẦU TRÍCH XUẤT BẰNG AI GEMINI 3.8 FLASH
    # ----------------------------------------------------
    def start_extraction(self):
        settings = load_settings()
        api_key = settings.get("api_key", "").strip()
        api_source = settings.get("api_source", "official")
        api_base_url = settings.get("api_base_url", "")

        if not api_key:
            InfoBar.warning(
                title="Chưa có API Key",
                content="Vui lòng chuyển sang tab 'Cài đặt & API' để nhập API Key Gemini hoặc APIZ trước khi trích xuất.",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self
            )
            return

        if not self.selected_files:
            InfoBar.warning(
                title="Chưa chọn tệp",
                content="Vui lòng thêm ít nhất một tệp chứng từ (Đơn đề nghị, B/L, Invoice...) để AI phân tích.",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3500,
                parent=self
            )
            return

        raw_form = self.combo_form.currentText()
        target_form = raw_form.split("(")[0].strip()

        self.btn_extract.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("⚡ AI Gemini 3.8 Flash đang phân tích toàn bộ chứng từ xuất khẩu...")

        self.worker = ExtractionWorker(
            api_key=api_key,
            file_paths=self.selected_files,
            target_form=target_form,
            api_source=api_source,
            api_base_url=api_base_url
        )
        self.worker.progress_signal.connect(self.lbl_status.setText)
        self.worker.finished_signal.connect(self.on_extraction_finished)
        self.worker.start()

    def on_extraction_finished(self, co_data, raw_json, error_msg):
        self.btn_extract.setEnabled(True)
        self.progress_bar.setVisible(False)

        if error_msg or not co_data:
            self.lbl_status.setText("❌ Lỗi trích xuất chứng từ!")
            InfoBar.error(
                title="Lỗi phân tích chứng từ",
                content=f"Không thể trích xuất dữ liệu: {error_msg[:120]}...",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
            return

        self.lbl_status.setText("✅ Trích xuất thành công 100% bằng Gemini 3.8 Flash!")
        self.current_co_data = co_data
        self.populate_inputs_from_data(co_data)

        allowed_docs = getattr(co_data, "deNghiHoSoDinhKem", []) or []
        self.populate_attachments_from_files(self.selected_files, allowed_types=allowed_docs)

        # Cập nhật JSON
        self.update_json_output()

        InfoBar.success(
            title="Trích xuất thành công",
            content="AI Gemini 3.8 Flash đã tổng hợp hoàn tất 30 trường dữ liệu C/O và phân loại tệp đính kèm!",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3500,
            parent=self
        )

    def populate_inputs_from_data(self, data: CODeclarationData):
        # 0. Mẫu C/O
        if getattr(data, "coType", None):
            ct = str(data.coType).strip().upper()
            for idx in range(self.combo_form.count()):
                item_txt = self.combo_form.itemText(idx).upper()
                if ct in item_txt or (ct.startswith("FORM ") and ct.split(" ")[-1] in item_txt):
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

        # 2. Vận chuyển & Hóa đơn
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

        self.txt_manu_name.setText(data.manu_Name or "")
        self.txt_manu_addr1.setText(data.manu_AddressLine1 or "")
        self.txt_manu_addr2.setText(data.manu_AddressLine2 or "")

        # Import Declarations (Multi-row)
        raw_imp_list = getattr(data, "importDeclarationList", []) or []
        imp_nos, imp_dates = [], []
        for item in raw_imp_list:
            no = item.get("declarationNumber", "") if isinstance(item, dict) else getattr(item, "declarationNumber", "")
            dt = item.get("declarationDate", "") if isinstance(item, dict) else getattr(item, "declarationDate", "")
            if no: imp_nos.append(str(no).strip())
            if dt: imp_dates.append(str(dt).strip())
        self.txt_import_decl_no.setText(", ".join(imp_nos) if imp_nos else (getattr(data, "importDeclarationNumbers", "") or ""))
        self.txt_import_decl_date.setText(", ".join(imp_dates) if imp_dates else (getattr(data, "importDeclarationDates", "") or ""))

        # VAT Invoices (Multi-row)
        raw_vat_list = getattr(data, "invoiceVATList", []) or []
        vat_nos, vat_dates = [], []
        for item in raw_vat_list:
            no = item.get("declarationNumber", "") if isinstance(item, dict) else getattr(item, "declarationNumber", "")
            dt = item.get("declarationDate", "") if isinstance(item, dict) else getattr(item, "declarationDate", "")
            if no: vat_nos.append(str(no).strip())
            if dt: vat_dates.append(str(dt).strip())
        self.txt_vat_invoice_no.setText(", ".join(vat_nos) if vat_nos else (getattr(data, "invoiceVATNumbers", "") or ""))
        self.txt_vat_invoice_date.setText(", ".join(vat_dates) if vat_dates else (getattr(data, "invoiceVATDates", "") or ""))

        # 3. Good items
        self.table_goods.setRowCount(0)
        items = data.goodItems or []
        for item in items:
            self.add_good_item_row(item)

    def add_good_item_row(self, item: GoodItem):
        r = self.table_goods.rowCount()
        self.table_goods.insertRow(r)

        # Cột: HS XK, HS NK, Mô tả, Tiêu chí, Nước XX, Qty, QtyUnit, Mark, PkgQty, PkgUnit, GW, GWUnit, Value, Curr, InvNo, InvDate
        vals = [
            item.exportingHsCode or "",
            item.importingHsCode or "",
            item.goodsDescription or "",
            item.originCriterion or "WO",
            item.countryOfOrigin or "VN",
            str(item.quantity if item.quantity is not None else ""),
            "KILOGRAM",  # Khóa cứng KILOGRAM chuẩn
            item.markAndNumberOnPackage or "NO MARK",
            str(item.packageQuantity if item.packageQuantity is not None else ""),
            item.packageUnit or "CARTON",
            str(item.grossWeight if item.grossWeight is not None else ""),
            "KILOGRAM",  # Khóa cứng KILOGRAM chuẩn
            str(item.value if item.value is not None else ""),
            item.currency or "USD - Dollar Mỹ",
            item.invoiceNumber or "",
            item.invoiceDate or ""
        ]
        for col, val in enumerate(vals):
            table_item = QTableWidgetItem(str(val))
            self.table_goods.setItem(r, col, table_item)

    def add_empty_good_row(self):
        r = self.table_goods.rowCount()
        self.table_goods.insertRow(r)
        defaults = ["03048700", "030487", "Mặt hàng mới", "WO", "VN", "1000", "KILOGRAM", "NO MARK", "100", "CARTON", "1100", "KILOGRAM", "5000", "USD - Dollar Mỹ", "", ""]
        for col, val in enumerate(defaults):
            self.table_goods.setItem(r, col, QTableWidgetItem(val))

    def delete_selected_good_row(self):
        r = self.table_goods.currentRow()
        if r >= 0:
            self.table_goods.removeRow(r)

    def collect_data_from_inputs(self) -> dict:
        raw_form = self.combo_form.currentText()
        target_form = raw_form.split("(")[0].strip()

        # Import Declarations (Multi-row)
        imp_list = []
        raw_imp_nos = [x.strip() for x in self.txt_import_decl_no.text().split(",") if x.strip()]
        raw_imp_dates = [x.strip() for x in self.txt_import_decl_date.text().split(",") if x.strip()]
        for i, no in enumerate(raw_imp_nos):
            dt = raw_imp_dates[i] if i < len(raw_imp_dates) else ""
            imp_list.append({"declarationNumber": no, "declarationDate": dt})

        # Invoice VAT (Multi-row)
        vat_list = []
        raw_vat_nos = [x.strip() for x in self.txt_vat_invoice_no.text().split(",") if x.strip()]
        raw_vat_dates = [x.strip() for x in self.txt_vat_invoice_date.text().split(",") if x.strip()]
        for i, no in enumerate(raw_vat_nos):
            dt = raw_vat_dates[i] if i < len(raw_vat_dates) else ""
            vat_list.append({"declarationNumber": no, "declarationDate": dt})

        # Good items table
        good_items = []
        for r in range(self.table_goods.rowCount()):
            def get_text(c):
                it = self.table_goods.item(r, c)
                return it.text().strip() if it else ""

            def get_float(c):
                t = get_text(c).replace(",", "")
                try: return float(t) if t else None
                except: return None

            def get_int(c):
                t = get_text(c).replace(",", "")
                try: return int(t) if t else None
                except: return None

            good_items.append({
                "exportingHsCode": get_text(0),
                "importingHsCode": get_text(1),
                "goodsDescription": get_text(2),
                "originCriterion": get_text(3) or "WO",
                "countryOfOrigin": get_text(4) or "VN",
                "quantity": get_float(5),
                "quantityUnit": "KILOGRAM",  # Đảm bảo KILOGRAM
                "markAndNumberOnPackage": get_text(7) or "NO MARK",
                "packageQuantity": get_int(8),
                "packageUnit": get_text(9) or "CARTON",
                "grossWeight": get_float(10),
                "grossWeightUnit": "KILOGRAM",  # Đảm bảo KILOGRAM
                "value": get_float(12),
                "currency": get_text(13) or "USD - Dollar Mỹ",
                "invoiceNumber": get_text(14),
                "invoiceDate": get_text(15)
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

        # Thu thập attachments
        attachments = []
        if self.chk_include_base64.isChecked():
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
                            with open(fpath, "rb") as fb:
                                b_data = fb.read()
                            b64 = base64.b64encode(b_data).decode("utf-8")
                            mime, _ = mimetypes.guess_type(fpath)
                            attachments.append({
                                "fileName": fn,
                                "fileType": ftype,
                                "fileSize": len(b_data),
                                "mimeType": mime or "application/pdf",
                                "base64": b64
                            })
                        except Exception as ex:
                            print(f"Lỗi đọc file {fpath}: {ex}")

        data["attachments"] = attachments
        return data

    def update_json_output(self):
        data = self.collect_data_from_inputs()
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        self.txt_json.setText(json_str)

    def copy_json_to_clipboard(self):
        self.update_json_output()
        json_str = self.txt_json.toPlainText()
        if not json_str:
            InfoBar.warning(
                title="Chưa có dữ liệu",
                content="Vui lòng thực hiện trích xuất chứng từ trước khi sao chép JSON.",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        cb = QApplication.clipboard()
        cb.setText(json_str)

        InfoBar.success(
            title="Đã sao chép JSON!",
            content="Dữ liệu JSON eCoSys đã được lưu vào Clipboard. Bạn hãy chuyển sang trình duyệt Chrome và bấm 'Dán từ Clipboard & Điền Ngay'.",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=4000,
            parent=self
        )


# ========================================================
# 2. TAB TRỢ LÝ AI COPILOT (CHATBOT INTERFACE)
# ========================================================
class ChatbotInterface(QWidget):
    def __init__(self, main_window):
        super().__init__(parent=main_window)
        self.setObjectName("chatbotInterface")
        self.main_window = main_window
        self.history = []

        self.init_ui()

    def init_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 24, 32, 24)
        lay.setSpacing(16)

        # Header
        header = QVBoxLayout()
        header.setSpacing(4)
        title = TitleLabel("Trợ Lý AI Nghiệp Vụ & Khai Báo C/O eCoSys")
        subtitle = CaptionLabel("Tư vấn quy tắc xuất xứ WO/CTC/RVC, hiệp định FTA, hướng dẫn sử dụng phần mềm & khắc phục lỗi eCoSys 24/7 (Model 3.8 Flash)")
        subtitle.setStyleSheet("color: #64748b; font-size: 13px;")
        header.addWidget(title)
        header.addWidget(subtitle)
        lay.addLayout(header)

        # Quick Prompts Card
        quick_card = SimpleCardWidget(self)
        quick_lay = QVBoxLayout(quick_card)
        quick_lay.setContentsMargins(16, 10, 16, 10)
        quick_lay.setSpacing(8)

        lbl_quick = CaptionLabel("💡 Câu hỏi nghiệp vụ gợi ý nhanh:")
        lbl_quick.setStyleSheet("font-weight: 600; color: #475569;")
        quick_lay.addWidget(lbl_quick)

        quick_btns = QHBoxLayout()
        quick_btns.setSpacing(10)

        p1 = PushButton("🇪🇺 C/O EUR.1 sang EU")
        p1.clicked.connect(lambda: self.send_quick_question("Hướng dẫn thủ tục và quy tắc xuất xứ để làm C/O Mẫu EUR.1 xuất khẩu sang Liên minh Châu Âu (EU) theo EVFTA?"))
        quick_btns.addWidget(p1)

        p2 = PushButton("🔍 Phân biệt WO, CTC & RVC")
        p2.clicked.connect(lambda: self.send_quick_question("Phân biệt rõ tiêu chí xuất xứ WO, CTC (CC, CTH, CTSH) và RVC kèm ví dụ minh họa?"))
        quick_btns.addWidget(p2)

        p3 = PushButton("📋 Bảng kê chi phí BOM")
        p3.clicked.connect(lambda: self.send_quick_question("Cách chuẩn bị Bảng kê chi phí nguyên phụ liệu BOM và hồ sơ chứng minh xuất xứ trên eCoSys?"))
        quick_btns.addWidget(p3)

        p4 = PushButton("🔑 Lỗi ký số USB Token")
        p4.clicked.connect(lambda: self.send_quick_question("Khắc phục lỗi không ký số được hoặc plugin cổng 14005/14405 báo bận trên eCoSys?"))
        quick_btns.addWidget(p4)

        p5 = PushButton("⚡ Quy trình 3 bước Extension")
        p5.clicked.connect(lambda: self.send_quick_question("Hướng dẫn quy trình 3 bước sử dụng App Desktop và Extension eCoSys AutoFill v2.6.0?"))
        quick_btns.addWidget(p5)

        quick_btns.addStretch()
        quick_lay.addLayout(quick_btns)
        lay.addWidget(quick_card)

        # Chat Scroll Area
        self.chat_scroll = SmoothScrollArea(self)
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setStyleSheet("QScrollArea { border: 1px solid #e2e8f0; border-radius: 8px; background: #f8fafc; }")

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(20, 20, 20, 20)
        self.chat_layout.setSpacing(14)
        self.chat_layout.addStretch()

        self.chat_scroll.setWidget(self.chat_container)
        lay.addWidget(self.chat_scroll, stretch=1)

        # Input Card
        input_card = CardWidget(self)
        in_lay = QVBoxLayout(input_card)
        in_lay.setContentsMargins(14, 12, 14, 12)
        in_lay.setSpacing(10)

        self.txt_input = TextEdit(input_card)
        self.txt_input.setPlaceholderText("Nhập câu hỏi nghiệp vụ C/O hoặc vướng mắc thao tác eCoSys... (Nhấn Enter để gửi, Shift+Enter để xuống dòng)")
        self.txt_input.setFixedHeight(72)
        self.txt_input.setFont(QFont("Segoe UI", 10))
        in_lay.addWidget(self.txt_input)

        bottom_bar = QHBoxLayout()
        self.lbl_chat_status = CaptionLabel("Trợ lý sẵn sàng giải đáp...")
        self.lbl_chat_status.setStyleSheet("color: #64748b; font-size: 12px;")
        bottom_bar.addWidget(self.lbl_chat_status)
        bottom_bar.addStretch()

        self.btn_clear_chat = PushButton(FluentIcon.BROOM, "Làm mới hội thoại", input_card)
        self.btn_clear_chat.clicked.connect(self.clear_conversation)
        bottom_bar.addWidget(self.btn_clear_chat)

        self.btn_send = PrimaryPushButton(FluentIcon.SEND, "Gửi câu hỏi", input_card)
        self.btn_send.setFixedWidth(130)
        self.btn_send.clicked.connect(self.send_message)
        bottom_bar.addWidget(self.btn_send)

        in_lay.addLayout(bottom_bar)
        lay.addWidget(input_card)

        # Gửi lời chào mở đầu
        self.add_ai_message(
            "Xin chào bạn! Tôi là **Trợ lý AI Nghiệp vụ C/O & Khai báo eCoSys** (chạy trên mô hình **Gemini 3.8 Flash**).\n\n"
            "Tôi có thể hỗ trợ bạn:\n"
            "• **Nghiệp vụ xuất xứ:** Xác định mẫu C/O (EUR.1, D, E, AK, VJ, CPTPP...), tiêu chí WO, CTC (CC/CTH/CTSH), RVC, De Minimis.\n"
            "• **Hồ sơ eCoSys:** Hướng dẫn lập Đơn đề nghị Mẫu 04, Bảng kê chi phí BOM, tờ khai HQ nhập khẩu, hóa đơn VAT.\n"
            "• **Thao tác phần mềm:** Hướng dẫn quy trình 3 bước trích xuất AI và tự động điền bằng Extension Chrome v2.6.0.\n\n"
            "Bạn đang cần hỗ trợ nghiệp vụ cho lô hàng nào hôm nay?"
        )

    def add_user_message(self, text: str):
        bubble = CardWidget(self.chat_container)
        bubble.setStyleSheet("CardWidget { background-color: #0078d4; border-radius: 10px; padding: 12px; }")
        lay = QVBoxLayout(bubble)
        lay.setContentsMargins(14, 10, 14, 10)
        lbl = BodyLabel(text, bubble)
        lbl.setStyleSheet("color: white; font-size: 13px; font-weight: 500;")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

        h_wrap = QHBoxLayout()
        h_wrap.addStretch()
        h_wrap.addWidget(bubble, alignment=Qt.AlignmentFlag.AlignRight)

        # Chèn trước stretch cuối cùng
        count = self.chat_layout.count()
        self.chat_layout.insertLayout(count - 1, h_wrap)
        self.scroll_to_bottom()

    def add_ai_message(self, text: str):
        bubble = ElevatedCardWidget(self.chat_container)
        bubble.setStyleSheet("ElevatedCardWidget { background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px; }")
        lay = QVBoxLayout(bubble)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        title_row = QHBoxLayout()
        icon_lbl = CaptionLabel("🤖 TRỢ LÝ AI COPILOT (GEMINI 3.8 FLASH)")
        icon_lbl.setStyleSheet("font-weight: bold; color: #0078d4; font-size: 11px;")
        title_row.addWidget(icon_lbl)
        title_row.addStretch()
        lay.addLayout(title_row)

        lbl = QTextEdit(bubble)
        lbl.setReadOnly(True)
        lbl.setMarkdown(text)
        lbl.setStyleSheet("QTextEdit { border: none; background: transparent; font-size: 13px; color: #1e293b; line-height: 1.5; }")
        lbl.document().adjustSize()
        h = max(70, int(lbl.document().size().height()) + 20)
        lbl.setFixedHeight(h)
        lay.addWidget(lbl)

        h_wrap = QHBoxLayout()
        h_wrap.addWidget(bubble, alignment=Qt.AlignmentFlag.AlignLeft)
        h_wrap.addStretch()

        count = self.chat_layout.count()
        self.chat_layout.insertLayout(count - 1, h_wrap)
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        QApplication.processEvents()
        self.chat_scroll.verticalScrollBar().setValue(self.chat_scroll.verticalScrollBar().maximum())

    def send_quick_question(self, question: str):
        self.txt_input.setText(question)
        self.send_message()

    def send_message(self):
        text = self.txt_input.toPlainText().strip()
        if not text:
            return

        settings = load_settings()
        api_key = settings.get("api_key", "").strip()
        api_source = settings.get("api_source", "official")
        api_base_url = settings.get("api_base_url", "")

        if not api_key:
            InfoBar.warning(
                title="Chưa có API Key",
                content="Vui lòng vào tab 'Cài đặt & API' để lưu API Key Gemini hoặc APIZ trước khi trò chuyện.",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self
            )
            return

        self.add_user_message(text)
        self.txt_input.clear()
        self.history.append({"role": "user", "text": text})

        self.btn_send.setEnabled(False)
        self.lbl_chat_status.setText("⚡ AI Gemini 3.8 Flash đang suy nghĩ và tổng hợp nghiệp vụ...")

        self.chat_worker = ChatbotWorker(
            api_key=api_key,
            question=text,
            history=self.history,
            api_source=api_source,
            api_base_url=api_base_url
        )
        self.chat_worker.reply_signal.connect(self.on_chat_reply)
        self.chat_worker.start()

    def on_chat_reply(self, reply: str, error_msg: str):
        self.btn_send.setEnabled(True)
        self.lbl_chat_status.setText("Trợ lý sẵn sàng giải đáp...")

        if error_msg or not reply:
            self.add_ai_message(f"⚠️ Rất tiếc, đã xảy ra lỗi khi kết nối tới mô hình AI: {error_msg}")
        else:
            self.add_ai_message(reply)
            self.history.append({"role": "model", "text": reply})

    def clear_conversation(self):
        self.history.clear()
        # Xóa các widget trong chat_layout ngoại trừ stretch
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Xóa layout con
                while item.layout().count() > 0:
                    sub = item.layout().takeAt(0)
                    if sub.widget(): sub.widget().deleteLater()

        self.add_ai_message("Đã làm mới cuộc hội thoại! Bạn có thể đặt câu hỏi mới bất kỳ lúc nào.")


# ========================================================
# 3. TAB CÀI ĐẶT & API (SETTINGS INTERFACE)
# ========================================================
class SettingsInterface(QWidget):
    def __init__(self, main_window):
        super().__init__(parent=main_window)
        self.setObjectName("settingsInterface")
        self.main_window = main_window

        self.init_ui()
        self.load_current_settings()

    def init_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 24, 32, 24)
        lay.setSpacing(20)

        # Header
        header = QVBoxLayout()
        header.setSpacing(4)
        title = TitleLabel("Cài Đặt Hệ Thống & Kết Nối API")
        subtitle = CaptionLabel("Cấu hình API Key (Google Gemini / APIZ Gateway) và tùy chỉnh giao diện ứng dụng")
        subtitle.setStyleSheet("color: #64748b; font-size: 13px;")
        header.addWidget(title)
        header.addWidget(subtitle)
        lay.addLayout(header)

        # Card 1: API Configuration
        card_api = ElevatedCardWidget(self)
        api_lay = QVBoxLayout(card_api)
        api_lay.setContentsMargins(22, 18, 22, 18)
        api_lay.setSpacing(14)

        api_lay.addWidget(SubtitleLabel("🔑 Cấu Hình API Key & Mô Hình AI"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)

        # API Key
        grid.addWidget(StrongBodyLabel("API Key:"), 0, 0)
        self.txt_api_key = PasswordLineEdit(card_api)
        self.txt_api_key.setPlaceholderText("Nhập Google Gemini API Key hoặc APIZ Token (VD: AQ.Ab8RN...)")
        grid.addWidget(self.txt_api_key, 0, 1)

        # Nguồn API
        grid.addWidget(StrongBodyLabel("Nguồn dịch vụ API:"), 1, 0)
        self.combo_source = ComboBox(card_api)
        self.combo_source.addItem("Google Gemini Official (ai.google.dev)", "official")
        self.combo_source.addItem("APIZ Vietnam Gateway (apiz.vn)", "apiz")
        self.combo_source.currentIndexChanged.connect(self.on_source_changed)
        grid.addWidget(self.combo_source, 1, 1)

        # APIZ Custom Base URL
        grid.addWidget(StrongBodyLabel("APIZ Base URL:"), 2, 0)
        self.txt_base_url = LineEdit(card_api)
        self.txt_base_url.setPlaceholderText("https://api.apiz.vn/v1 (Để trống nếu dùng Google Official)")
        grid.addWidget(self.txt_base_url, 2, 1)

        # AI Model (Khóa cứng 3.8 Flash)
        grid.addWidget(StrongBodyLabel("Mô hình AI:"), 3, 0)
        self.txt_model = LineEdit(card_api)
        self.txt_model.setText("gemini-3.8-flash")
        self.txt_model.setReadOnly(True)
        self.txt_model.setStyleSheet("color: #0078d4; font-weight: 600; background: #f1f5f9;")
        grid.addWidget(self.txt_model, 3, 1)

        # Default Form
        grid.addWidget(StrongBodyLabel("Mẫu C/O mặc định:"), 4, 0)
        self.combo_default_form = ComboBox(card_api)
        self.combo_default_form.addItems(["EUR.1", "D", "E", "AK", "VK", "VJ", "AJ", "CPTPP", "AANZ", "B"])
        grid.addWidget(self.combo_default_form, 4, 1)

        api_lay.addLayout(grid)

        # Action Buttons
        btn_row = QHBoxLayout()
        self.btn_test_api = PrimaryPushButton(FluentIcon.ACCEPT, "Kiểm tra kết nối API (Model 3.8 Flash)", card_api)
        self.btn_test_api.clicked.connect(self.test_api_connection)
        btn_row.addWidget(self.btn_test_api)

        self.btn_save = PrimaryPushButton(FluentIcon.SAVE, "Lưu cấu hình", card_api)
        self.btn_save.clicked.connect(self.save_user_settings)
        btn_row.addWidget(self.btn_save)

        btn_row.addStretch()
        api_lay.addLayout(btn_row)

        lay.addWidget(card_api)

        # Card 2: Interface Customization
        card_ui = CardWidget(self)
        ui_lay = QVBoxLayout(card_ui)
        ui_lay.setContentsMargins(22, 18, 22, 18)
        ui_lay.setSpacing(14)

        ui_lay.addWidget(SubtitleLabel("🎨 Giao Diện & Hệ Thống"))

        ui_grid = QGridLayout()
        ui_grid.setHorizontalSpacing(16)
        ui_grid.setVerticalSpacing(12)

        ui_grid.addWidget(StrongBodyLabel("Chủ đề ứng dụng:"), 0, 0)
        self.combo_theme = ComboBox(card_ui)
        self.combo_theme.addItems(["Theo hệ thống (Auto)", "Sáng (Light)", "Tối (Dark)"])
        self.combo_theme.currentIndexChanged.connect(self.on_theme_changed)
        ui_grid.addWidget(self.combo_theme, 0, 1)

        ui_grid.addWidget(StrongBodyLabel("Phiên bản phần mềm:"), 1, 0)
        ver_lbl = BodyLabel("v2.6.0 Fluent Design Edition • Tương thích eCoSys Bộ Công Thương")
        ver_lbl.setStyleSheet("color: #64748b; font-weight: 500;")
        ui_grid.addWidget(ver_lbl, 1, 1)

        ui_lay.addLayout(ui_grid)
        lay.addWidget(card_ui)

        lay.addStretch()

    def on_source_changed(self, idx):
        is_apiz = self.combo_source.currentData() == "apiz"
        if is_apiz and not self.txt_base_url.text():
            self.txt_base_url.setText("https://api.apiz.vn/v1")

    def on_theme_changed(self, idx):
        if idx == 1:
            setTheme(Theme.LIGHT)
        elif idx == 2:
            setTheme(Theme.DARK)
        else:
            setTheme(Theme.AUTO)

    def load_current_settings(self):
        st = load_settings()
        self.txt_api_key.setText(st.get("api_key", ""))
        source = st.get("api_source", "official")
        for i in range(self.combo_source.count()):
            if self.combo_source.itemData(i) == source:
                self.combo_source.setCurrentIndex(i)
                break

        self.txt_base_url.setText(st.get("api_base_url", ""))
        self.txt_model.setText("gemini-3.8-flash")

        d_form = st.get("target_form", "EUR.1")
        idx = self.combo_default_form.findText(d_form)
        if idx >= 0: self.combo_default_form.setCurrentIndex(idx)

    def save_user_settings(self):
        st = {
            "api_key": self.txt_api_key.text().strip(),
            "api_source": self.combo_source.currentData(),
            "api_base_url": self.txt_base_url.text().strip(),
            "model_name": "gemini-3.8-flash",
            "target_form": self.combo_default_form.currentText()
        }
        save_settings(st)
        InfoBar.success(
            title="Đã lưu cài đặt",
            content="Cấu hình API Key và tham số đã được lưu vào settings.json thành công!",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )

    def test_api_connection(self):
        api_key = self.txt_api_key.text().strip()
        if not api_key:
            InfoBar.warning(
                title="Chưa nhập API Key",
                content="Vui lòng nhập API Key để kiểm tra kết nối.",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        self.btn_test_api.setEnabled(False)
        self.test_worker = TestApiWorker(
            api_key=api_key,
            api_source=self.combo_source.currentData(),
            api_base_url=self.txt_base_url.text().strip()
        )
        self.test_worker.test_signal.connect(self.on_test_finished)
        self.test_worker.start()

    def on_test_finished(self, success: bool, msg: str):
        self.btn_test_api.setEnabled(True)
        if success:
            InfoBar.success(
                title="Kết nối thành công",
                content=msg,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self
            )
        else:
            InfoBar.error(
                title="Lỗi kết nối API",
                content=f"Không thể kết nối tới Gemini 3.8 Flash: {msg[:120]}...",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )


# ========================================================
# 4. CỬA SỔ CHÍNH FLUENT DESIGN (MAIN WINDOW)
# ========================================================
class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("eCoSys AI C/O Extractor & Copilot - Bộ Công Thương")
        self.resize(1240, 850)
        self.setMinimumSize(1020, 720)

        # Theme accent color
        setThemeColor("#0078D4")  # Windows 11 Fluent Blue

        # Icon
        if os.path.exists("extension/icon48.png"):
            self.setWindowIcon(QIcon("extension/icon48.png"))

        # Setup Sub-interfaces
        self.home_interface = HomeInterface(self)
        self.addSubInterface(self.home_interface, FluentIcon.DOCUMENT, "Khai báo C/O")

        self.chatbot_interface = ChatbotInterface(self)
        self.addSubInterface(self.chatbot_interface, FluentIcon.CHAT, "Trợ lý AI Copilot")

        self.settings_interface = SettingsInterface(self)
        self.addSubInterface(self.settings_interface, FluentIcon.SETTING, "Cài đặt & API", NavigationItemPosition.BOTTOM)

        # Navigation Bar Width
        self.navigationInterface.setExpandWidth(220)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
