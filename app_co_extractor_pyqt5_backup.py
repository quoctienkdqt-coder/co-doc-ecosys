"""
Ứng dụng Desktop Trích xuất Chứng từ Khai báo C/O eCoSys (Bộ Công Thương)
Giao diện PyQt5 với AI Gemini Structured Outputs
"""

import sys
import os
import json
import base64
import mimetypes
import traceback
import re
from typing import List

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QFileDialog, QMessageBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit, QProgressBar,
    QSplitter, QGroupBox, QFormLayout, QHeaderView, QListWidget, QListWidgetItem,
    QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QColor

from co_schema import CODeclarationData, GoodItem
from gemini_extractor import extract_co_data_from_files

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
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Lỗi lưu cấu hình: {e}")


class ExtractionWorker(QThread):
    finished_signal = pyqtSignal(object, str)
    error_signal = pyqtSignal(str)

    def __init__(self, api_key: str, file_paths: List[str], target_form: str, model_name: str):
        super().__init__()
        self.api_key = api_key
        self.file_paths = file_paths
        self.target_form = target_form
        self.model_name = model_name

    def run(self):
        try:
            co_data, raw_json = extract_co_data_from_files(
                api_key=self.api_key,
                file_paths=self.file_paths,
                target_form=self.target_form,
                model_name=self.model_name
            )
            self.finished_signal.emit(co_data, raw_json)
        except Exception as e:
            self.error_signal.emit(f"{str(e)}\n\nChi tiết:\n{traceback.format_exc()}")


class DropListWidget(QListWidget):
    """QListWidget hỗ trợ kéo thả file tài liệu trực tiếp"""
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


class COExtractorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("eCoSys AI - Trợ lý Trích xuất Chứng từ Khai báo C/O (Bộ Công Thương)")
        self.resize(1280, 820)
        self.setMinimumSize(1024, 680)

        self.selected_files = []
        self.current_co_data = CODeclarationData()
        self.worker = None

        self.init_ui()
        self.load_saved_config()

    def init_ui(self):
        # Thiết lập style giao diện hiện đại, trực quan
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f4f6f9;
            }
            QLabel {
                font-family: 'Segoe UI', Arial, sans-serif;
                color: #2c3e50;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #dcdfe6;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 14px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
                color: #1a73e8;
            }
            QLineEdit, QComboBox, QTextEdit {
                border: 1px solid #cfd4dc;
                border-radius: 5px;
                padding: 6px 8px;
                background-color: #ffffff;
                selection-background-color: #1a73e8;
                font-family: 'Segoe UI', Arial;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 1.5px solid #1a73e8;
            }
            QPushButton {
                background-color: #f1f3f4;
                border: 1px solid #dadce0;
                border-radius: 5px;
                padding: 7px 14px;
                font-weight: 500;
                font-family: 'Segoe UI', Arial;
            }
            QPushButton:hover {
                background-color: #e8eaed;
            }
            QPushButton#btn_primary {
                background-color: #1a73e8;
                color: white;
                font-weight: bold;
                border: none;
                font-size: 13px;
                padding: 10px 18px;
            }
            QPushButton#btn_primary:hover {
                background-color: #1557b0;
            }
            QPushButton#btn_copy {
                background-color: #0f9d58;
                color: white;
                font-weight: bold;
                border: none;
                padding: 8px 16px;
            }
            QPushButton#btn_copy:hover {
                background-color: #0b8043;
            }
            QTableWidget {
                border: 1px solid #dcdfe6;
                gridline-color: #e8eaed;
                background-color: #ffffff;
                alternate-background-color: #f8f9fa;
            }
            QHeaderView::section {
                background-color: #edf2f7;
                color: #2d3748;
                font-weight: bold;
                border: 1px solid #dcdfe6;
                padding: 5px;
            }
            QTabWidget::pane {
                border: 1px solid #dcdfe6;
                background: white;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #e9ecef;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 2px solid #1a73e8;
                color: #1a73e8;
                font-weight: bold;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # ==========================================
        # CỘT TRÁI: ĐIỀU KHIỂN & CHỨNG TỪ ĐẦU VÀO
        # ==========================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # 1. Cấu hình AI & API Key
        config_group = QGroupBox("1. Cấu hình AI Gemini")
        config_form = QFormLayout(config_group)
        config_form.setSpacing(8)

        self.input_api_key = QLineEdit()
        self.input_api_key.setEchoMode(QLineEdit.Password)
        self.input_api_key.setPlaceholderText("Dán API Key từ Google AI Studio...")
        
        btn_show_key = QPushButton("👁️")
        btn_show_key.setFixedWidth(36)
        btn_show_key.setToolTip("Hiện / Ẩn API Key")
        btn_show_key.clicked.connect(self.toggle_api_key_visibility)

        key_layout = QHBoxLayout()
        key_layout.addWidget(self.input_api_key)
        key_layout.addWidget(btn_show_key)
        config_form.addRow("API Key:", key_layout)

        self.combo_model = QComboBox()
        self.combo_model.setEditable(True)
        self.combo_model.addItems([
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-1.5-flash",
            "gemini-3.8-flash"
        ])
        config_form.addRow("Model AI:", self.combo_model)

        self.combo_form = QComboBox()
        self.combo_form.addItems([
            "E (ASEAN - Trung Quốc)",
            "D (ASEAN - ATIGA)",
            "AK (ASEAN - Hàn Quốc)",
            "AJ (ASEAN - Nhật Bản)",
            "EUR.1 (Việt Nam - EU)",
            "CPTPP (Hiệp định CPTPP)",
            "VJ (Việt Nam - Nhật Bản)",
            "VK (Việt Nam - Hàn Quốc)",
            "VC (Việt Nam - Chile)",
            "S (Việt Nam - Lào)",
            "AANZ (ASEAN - Úc - New Zealand)",
            "VN-EAEU (Việt Nam - Liên minh Kinh tế Á Âu)"
        ])
        config_form.addRow("Mẫu C/O:", self.combo_form)

        left_layout.addWidget(config_group)

        # 2. Danh sách chứng từ đính kèm
        docs_group = QGroupBox("2. Chứng từ đính kèm (PDF / Ảnh)")
        docs_layout = QVBoxLayout(docs_group)

        doc_hint = QLabel("💡 Kéo thả file chứng từ vào đây:\n- Tích [x] để AI đọc dữ liệu (Đơn C/O + Invoice)\n- Bỏ tích [ ] file chỉ dùng đính kèm (Tờ khai, B/L...)")
        doc_hint.setStyleSheet("color: #1e3a8a; font-size: 11px; background: #eff6ff; padding: 6px; border-radius: 4px;")
        docs_layout.addWidget(doc_hint)

        self.list_files = DropListWidget()
        self.list_files.file_dropped_signal.connect(self.add_dropped_files)
        self.list_files.itemChanged.connect(lambda: self.update_file_status_label())
        docs_layout.addWidget(self.list_files)

        # Thanh nút thao tác file
        btn_files_layout = QHBoxLayout()
        btn_add_files = QPushButton("➕ Thêm file...")
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
        btn_select_core = QPushButton("🎯 Chỉ AI đọc Đơn C/O + Inv")
        btn_select_core.setToolTip("Tự động tích chọn chỉ Đơn đề nghị C/O và Hóa đơn để AI đọc")
        btn_select_core.clicked.connect(self.select_only_core_files)

        btn_select_all = QPushButton("☑️ AI đọc hết")
        btn_select_all.setToolTip("Tích chọn tất cả các file cho AI phân tích")
        btn_select_all.clicked.connect(self.select_all_ai_files)

        ai_sel_layout.addWidget(btn_select_core)
        ai_sel_layout.addWidget(btn_select_all)
        docs_layout.addLayout(ai_sel_layout)

        left_layout.addWidget(docs_group)

        # 3. Nút Kích hoạt Trích xuất AI
        self.btn_extract = QPushButton("⚡ BẮT ĐẦU TRÍCH XUẤT BẰNG AI")
        self.btn_extract.setObjectName("btn_primary")
        self.btn_extract.clicked.connect(self.start_extraction)
        left_layout.addWidget(self.btn_extract)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximum(0)  # Chế độ chạy liên tục (indeterminate)
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Sẵn sàng")
        self.lbl_status.setStyleSheet("color: #495057; font-style: italic;")
        left_layout.addWidget(self.lbl_status)

        left_layout.addStretch()
        left_widget.setMinimumWidth(340)
        splitter.addWidget(left_widget)

        # ==========================================
        # CỘT PHẢI: XEM TRƯỚC & CHỈNH SỬA DỮ LIỆU C/O
        # ==========================================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Tiêu đề bảng điều khiển
        header_layout = QHBoxLayout()
        title_label = QLabel("DỮ LIỆU HỒ SƠ KHAI BÁO C/O")
        title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #1a73e8;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        btn_load_sample = QPushButton("🧪 Nạp dữ liệu mẫu (Test)")
        btn_load_sample.setToolTip("Nạp file sample_data.json để thử nghiệm tính năng")
        btn_load_sample.clicked.connect(self.load_sample_data)
        header_layout.addWidget(btn_load_sample)

        right_layout.addLayout(header_layout)

        # Tab Widget cho các nhóm thông tin
        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs)

        # Tab 1: Thông tin chung & Doanh nghiệp
        self.tab_general = QWidget()
        self.setup_tab_general()
        self.tabs.addTab(self.tab_general, "🏢 1. Thông tin chung & Doanh nghiệp")

        # Tab 2: Vận chuyển & Hóa đơn
        self.tab_transport = QWidget()
        self.setup_tab_transport()
        self.tabs.addTab(self.tab_transport, "🚢 2. Vận tải & Hóa đơn")

        # Tab 3: Danh sách hàng hóa
        self.tab_goods = QWidget()
        self.setup_tab_goods()
        self.tabs.addTab(self.tab_goods, "📦 3. Danh sách hàng hóa")

        # Tab 4: Tệp đính kèm (Attachments)
        self.tab_attachments = QWidget()
        self.setup_tab_attachments()
        self.tabs.addTab(self.tab_attachments, "📎 4. Tệp đính kèm (Attachments)")

        # Tab 5: Xuất JSON cho Extension
        self.tab_json = QWidget()
        self.setup_tab_json()
        self.tabs.addTab(self.tab_json, "💾 5. Xuất JSON (Cho Extension)")

        # Lắng nghe sự kiện chuyển tab để tự động đồng bộ sang tab JSON
        self.tabs.currentChanged.connect(self.on_tab_changed)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

    def setup_tab_general(self):
        layout = QVBoxLayout(self.tab_general)

        # Exporter
        box_exp = QGroupBox("Người xuất khẩu (Exporter)")
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

        # Consignee
        box_imp = QGroupBox("Người nhận hàng / Nhập khẩu (Consignee)")
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
        form_meta.addRow("Mã nước nhập khẩu (ISO):", self.txt_country)
        form_meta.addRow("Nơi khai báo (Tỉnh/Thành phố):", self.txt_place)
        layout.addWidget(box_meta)

        # Manufacturer (Nhà sản xuất - Mục 25, 26)
        box_manu = QGroupBox("Nhà sản xuất (Manufacturer - Mục 25, 26)")
        form_manu = QFormLayout(box_manu)
        self.txt_manu_name = QLineEdit()
        self.txt_manu_name.setPlaceholderText("Tên nhà sản xuất (Mục 25)...")
        self.txt_manu_addr1 = QLineEdit()
        self.txt_manu_addr1.setPlaceholderText("Địa chỉ dòng 1 (Mục 26)...")
        self.txt_manu_addr2 = QLineEdit()
        self.txt_manu_addr2.setPlaceholderText("Địa chỉ dòng 2...")

        form_manu.addRow("Tên nhà sản xuất (Tiếng Anh):", self.txt_manu_name)
        form_manu.addRow("Địa chỉ dòng 1:", self.txt_manu_addr1)
        form_manu.addRow("Địa chỉ dòng 2:", self.txt_manu_addr2)
        layout.addWidget(box_manu)

        layout.addStretch()

    def setup_tab_transport(self):
        layout = QVBoxLayout(self.tab_transport)

        # Transport
        box_trans = QGroupBox("Chi tiết hành trình & Vận tải")
        form_trans = QFormLayout(box_trans)
        self.txt_trans_type = QLineEdit()
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

        # Invoice & Customs
        box_inv = QGroupBox("Hóa đơn thương mại & Tờ khai Hải quan")
        form_inv = QFormLayout(box_inv)
        self.txt_inv_no = QLineEdit()
        self.txt_inv_date = QLineEdit()
        self.txt_inv_curr = QLineEdit()
        self.txt_fob_total = QLineEdit()
        self.txt_customs_no = QLineEdit()
        self.txt_customs_date = QLineEdit()
        self.txt_remarks = QLineEdit()
        self.chk_issued_retro = QCheckBox("Tích chọn 'Issued Retrospectively' (C/O cấp sau)")
        self.chk_issued_retro.setStyleSheet("color: #d93025; font-weight: bold;")
        self.txt_retro_reason = QLineEdit()
        self.txt_retro_reason.setPlaceholderText("Lý do xin cấp sau (nếu có)...")

        form_inv.addRow("Số Hóa đơn (Invoice No):", self.txt_inv_no)
        form_inv.addRow("Ngày Hóa đơn (DD/MM/YYYY):", self.txt_inv_date)
        form_inv.addRow("Đồng tiền thanh toán:", self.txt_inv_curr)
        form_inv.addRow("Tổng trị giá FOB:", self.txt_fob_total)
        form_inv.addRow("Số tờ khai Hải quan:", self.txt_customs_no)
        form_inv.addRow("Ngày tờ khai Hải quan:", self.txt_customs_date)
        form_inv.addRow("Ghi chú (Remarks):", self.txt_remarks)
        form_inv.addRow("C/O Cấp sau:", self.chk_issued_retro)
        form_inv.addRow("Lý do cấp sau:", self.txt_retro_reason)
        layout.addWidget(box_inv)

        # Nguyên liệu đầu vào (Tờ khai nhập khẩu / Hóa đơn VAT - Mục 27, 28, 29, 30)
        box_mat = QGroupBox("Nguyên liệu đầu vào (Tờ khai nhập khẩu / Hóa đơn VAT)")
        form_mat = QFormLayout(box_mat)
        self.txt_import_decl_no = QLineEdit()
        self.txt_import_decl_no.setPlaceholderText("Dùng khi nguyên liệu nhập khẩu (Mục 27)...")
        self.txt_import_decl_date = QLineEdit()
        self.txt_import_decl_date.setPlaceholderText("DD/MM/YYYY (Mục 28)...")
        self.txt_vat_invoice_no = QLineEdit()
        self.txt_vat_invoice_no.setPlaceholderText("Dùng khi nguyên liệu mua trong nước (Mục 29)...")
        self.txt_vat_invoice_date = QLineEdit()
        self.txt_vat_invoice_date.setPlaceholderText("DD/MM/YYYY (Mục 30)...")

        form_mat.addRow("Số Tờ khai HQ nhập khẩu (TKN):", self.txt_import_decl_no)
        form_mat.addRow("Ngày Tờ khai HQ nhập khẩu:", self.txt_import_decl_date)
        form_mat.addRow("Số Hóa đơn VAT mua nguyên liệu:", self.txt_vat_invoice_no)
        form_mat.addRow("Ngày Hóa đơn VAT mua nguyên liệu:", self.txt_vat_invoice_date)
        layout.addWidget(box_mat)

        layout.addStretch()

    def setup_tab_goods(self):
        layout = QVBoxLayout(self.tab_goods)

        # Tool buttons
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
        layout.addLayout(btn_layout)

        # Table
        self.table_goods = QTableWidget()
        headers = [
            "Mã HS XK (8 số)", "Mã HS NK (6 số)", "Mô tả hàng hóa", "Tiêu chí xuất xứ",
            "Số lượng (NW)", "ĐVT", "Gross Wt (GW)", "Số kiện (21)", "Loại kiện (22)",
            "Trị giá FOB (20)", "Tiền tệ", "Ký hiệu kiện", "Số Hóa đơn (23)", "Ngày Hóa đơn (24)"
        ]
        self.table_goods.setColumnCount(len(headers))
        self.table_goods.setHorizontalHeaderLabels(headers)
        self.table_goods.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_goods.setAlternatingRowColors(True)
        layout.addWidget(self.table_goods)

    def setup_tab_attachments(self):
        layout = QVBoxLayout(self.tab_attachments)

        info_box = QGroupBox("Cấu hình Tự động Đính kèm & Upload File lên eCoSys")
        info_layout = QVBoxLayout(info_box)

        self.chk_include_base64 = QCheckBox("Tự động đóng gói Base64 các tệp được chọn vào JSON (Extension sẽ tự động upload lên web)")
        self.chk_include_base64.setChecked(True)
        self.chk_include_base64.setStyleSheet("font-weight: bold; color: #1a73e8; font-size: 13px;")
        info_layout.addWidget(self.chk_include_base64)

        desc_lbl = QLabel(
            "💡 Cơ chế hoạt động: Toàn bộ file PDF/Ảnh chứng từ được chuyển thành chuỗi nhị phân Base64 đưa vào JSON.\n"
            "Khi bấm 'Điền tự động' trên Extension, Extension sẽ tái tạo lại đúng từng byte của file gốc và nạp thẳng lên hệ thống eCoSys Bộ Công Thương.\n"
            "Cơ quan Hải quan / Bộ Công Thương mở file trên hệ thống eCoSys vẫn đọc đầy đủ 100% như tải file thủ công."
        )
        desc_lbl.setStyleSheet("color: #475569; font-size: 12px; line-height: 1.4;")
        desc_lbl.setWordWrap(True)
        info_layout.addWidget(desc_lbl)
        layout.addWidget(info_box)

        # Toolbar
        tools_layout = QHBoxLayout()
        btn_add_att = QPushButton("➕ Thêm tệp chứng từ...")
        btn_add_att.clicked.connect(self.add_attachment_files)
        btn_del_att = QPushButton("➖ Bỏ tệp khỏi danh sách")
        btn_del_att.clicked.connect(self.delete_attachment_file)
        btn_auto_detect = QPushButton("🔍 Tự động nhận diện loại chứng từ")
        btn_auto_detect.clicked.connect(self.auto_detect_attachment_types)

        tools_layout.addWidget(btn_add_att)
        tools_layout.addWidget(btn_del_att)
        tools_layout.addWidget(btn_auto_detect)
        tools_layout.addStretch()
        layout.addLayout(tools_layout)

        # Table of attachments
        self.table_attachments = QTableWidget()
        headers = ["Nạp", "Tên tệp", "Vị trí tải lên eCoSys (Dropbox)", "Kích thước", "Đường dẫn gốc"]
        self.table_attachments.setColumnCount(len(headers))
        self.table_attachments.setHorizontalHeaderLabels(headers)
        self.table_attachments.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_attachments.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_attachments.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table_attachments.setAlternatingRowColors(True)
        layout.addWidget(self.table_attachments)

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

    def detect_file_type_from_content(self, file_path: str) -> str:
        """
        Nhận diện loại chứng từ eCoSys dựa vào NỘI DUNG THỰC TẾ BÊN TRONG TỆP (PyMuPDF).
        Nếu không đọc được văn bản (ảnh quét/file mã hóa), tự động rơi về nhận diện theo tên tệp.
        """
        if not file_path or not os.path.exists(file_path):
            return "TAILIEUCHUNGMINH"

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            try:
                import fitz
                doc = fitz.open(file_path)
                full_text = ""
                # Quét tối đa 4 trang đầu của tài liệu
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

            except Exception as e:
                pass

        # Rơi về nhận diện theo tên file nếu không trích xuất được từ nội dung
        return self.detect_file_type_from_name(os.path.basename(file_path))

    def detect_file_type_from_name(self, filename: str) -> str:
        fn = filename.lower().replace("-", "_").replace(" ", "_")
        raw_clean = filename.lower().replace(" ", "").replace("_", "").replace("-", "")

        # 1. Hợp đồng mua bán
        if any(k in fn or k in raw_clean for k in ["hop_dong", "hopdong", "contract"]):
            return "HopDongMuaBan"

        # 2. Giấy phép xuất khẩu
        if any(k in fn or k in raw_clean for k in ["giayphep", "giay_phep", "license"]):
            return "GiayPhepXuatKhau"

        # 3. Bản mô tả quy trình sản xuất
        if any(k in fn or k in raw_clean for k in ["quytrinh", "quy_trinh", "sanxuat", "san_xuat", "process", "production"]):
            return "QuyTrinhSanXuat"

        # 4. Bảng kê chi phí / hàm lượng RVC / CTC / BOM
        if any(k in fn or k in raw_clean for k in ["bang_ke", "bangke", "cost", "rvc", "ctc", "bom", "tieu_chi", "tieuchi", "hamluong", "ham_luong"]):
            return "BangKeChiPhi"

        # 5. Vận đơn / B/L / AWB / Seaway bill
        if any(k in fn or k in raw_clean for k in ["bill", "bl", "b_l", "van_don", "vandon", "airway", "awb", "sur", "seaway", "booking"]):
            return "VanDon"

        # 6. Tờ khai hải quan
        if any(k in fn or k in raw_clean for k in ["tokhai_xk", "tokhaixk", "tkhq_xk", "tokhai", "to_khai", "tkhq", "customs", "declaration", "haiquan"]):
            if any(nk in fn or nk in raw_clean for nk in ["nhap", "nk", "import", "nguyenlieu"]):
                return "ToKhaiHQNK_Document"
            return "ToKhaiXuatKhau"

        # 7. Hóa đơn thương mại (Commercial Invoice)
        if any(k in fn or k in raw_clean for k in ["commercial_invoice", "commercialinvoice", "inv", "commercial", "invoice"]):
            if any(v in fn or v in raw_clean for v in ["vat", "gtgt", "noidia"]):
                return "HoaDonVAT"
            return "Invoice_attached_Doc"

        # 8. Hóa đơn GTGT / VAT mua bán nguyên liệu trong nước
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
        QMessageBox.information(self, "Hoàn tất", f"Đã tự động phân loại {count} tệp chứng từ dựa vào NỘI DUNG THỰC TẾ và tên tệp!")

    def add_attachment_row(self, file_path: str, file_type: str = "TAILIEUCHUNGMINH", checked: bool = True):
        if not os.path.exists(file_path):
            return

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        size_str = f"{round(file_size / 1024, 1)} KB" if file_size < 1024 * 1024 else f"{round(file_size / (1024*1024), 2)} MB"

        row = self.table_attachments.rowCount()
        self.table_attachments.insertRow(row)

        chk_item = QTableWidgetItem()
        chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        chk_item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.table_attachments.setItem(row, 0, chk_item)

        name_item = QTableWidgetItem(file_name)
        name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
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
        size_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        size_item.setTextAlignment(Qt.AlignCenter)
        self.table_attachments.setItem(row, 3, size_item)

        path_item = QTableWidgetItem(file_path)
        path_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.table_attachments.setItem(row, 4, path_item)

    def populate_attachments_from_files(self, file_paths: list, allowed_types: list = None):
        self.table_attachments.setRowCount(0)
        for p in file_paths:
            ftype = self.detect_file_type_from_content(p)
            # Nếu có danh mục chứng từ từ Đơn đề nghị, chỉ tích nạp những loại được đánh dấu
            is_checked = True
            if allowed_types and len(allowed_types) > 0:
                is_checked = (
                    ftype in allowed_types or
                    (ftype == "Invoice_attached_Doc" and ("HoaDonVAT" in allowed_types or "Invoice_attached_Doc" in allowed_types)) or
                    (ftype == "HoaDonVAT" and ("HoaDonVAT" in allowed_types or "Invoice_attached_Doc" in allowed_types)) or
                    (ftype == "TAILIEUCHUNGMINH" and "TAILIEUCHUNGMINH" in allowed_types)
                )
            self.add_attachment_row(p, ftype, checked=is_checked)

    def setup_tab_json(self):
        layout = QVBoxLayout(self.tab_json)

        bar_layout = QHBoxLayout()
        btn_copy_json = QPushButton("📋 SAO CHÉP JSON (DÁN VÀO EXTENSION)")
        btn_copy_json.setObjectName("btn_copy")
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

        info_lbl = QLabel("Dữ liệu JSON chuẩn theo eCoSys. Bạn chỉ cần bấm 'Sao chép JSON', sau đó mở web eCoSys và bấm 'Dán & Điền' trên Extension.")
        info_lbl.setStyleSheet("color: #2e7d32; font-weight: 500;")
        layout.addWidget(info_lbl)

        self.txt_json_view = QTextEdit()
        self.txt_json_view.setFont(QFont("Consolas", 10))
        layout.addWidget(self.txt_json_view)

    # ==========================================
    # CÁC HÀM XỬ LÝ CHỨC NĂNG (LOGIC)
    # ==========================================
    def toggle_api_key_visibility(self):
        if self.input_api_key.echoMode() == QLineEdit.Password:
            self.input_api_key.setEchoMode(QLineEdit.Normal)
        else:
            self.input_api_key.setEchoMode(QLineEdit.Password)

    def load_saved_config(self):
        cfg = load_settings()
        if "api_key" in cfg:
            self.input_api_key.setText(cfg["api_key"])
        if "model_name" in cfg:
            self.combo_model.setCurrentText(cfg["model_name"])
        if "target_form" in cfg:
            idx = self.combo_form.findText(cfg["target_form"], Qt.MatchStartsWith)
            if idx >= 0:
                self.combo_form.setCurrentIndex(idx)

    def save_current_config(self):
        cfg = {
            "api_key": self.input_api_key.text().strip(),
            "model_name": self.combo_model.currentText().strip(),
            "target_form": self.combo_form.currentText().split()[0]
        }
        save_settings(cfg)

    def is_core_ai_file(self, filename: str) -> bool:
        fn = filename.lower().replace("-", "_").replace(" ", "_")
        raw = filename.lower().replace(" ", "").replace("_", "").replace("-", "")
        # Đơn đề nghị cấp C/O (Mẫu 04)
        if any(k in fn or k in raw for k in ["don", "denghi", "de_nghi", "mau04", "mau_04", "application", "co_form", "form_co"]):
            return True
        # Hóa đơn thương mại (Commercial Invoice)
        if any(k in fn or k in raw for k in ["invoice", "inv", "hoadon", "hoa_don", "commercial"]):
            return True
        return False

    def choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn chứng từ xuất khẩu (Invoice, Packing List, Tờ khai, B/L...)",
            "",
            "Tất cả chứng từ (*.pdf *.png *.jpg *.jpeg *.webp);;PDF Files (*.pdf);;Images (*.png *.jpg *.jpeg *.webp)"
        )
        if files:
            self.add_files_to_list(files)

    def add_dropped_files(self, files: list):
        self.add_files_to_list(files)

    def add_files_to_list(self, files: list):
        for f in files:
            if f not in self.selected_files:
                self.selected_files.append(f)
                is_core = self.is_core_ai_file(os.path.basename(f))
                tag = "🤖 [AI ĐỌC]" if is_core else "📎 [ĐÍNH KÈM]"
                size_kb = max(1, os.path.getsize(f) // 1024)

                item = QListWidgetItem(f"{tag} {os.path.basename(f)} ({size_kb} KB)")
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if is_core else Qt.Unchecked)

                if is_core:
                    item.setToolTip(f"{f}\n👉 Tệp nguồn cốt lõi (Đơn C/O hoặc Invoice) được gửi cho AI đọc dữ liệu.")
                else:
                    item.setToolTip(f"{f}\n👉 Tệp đính kèm bổ sung (Chỉ đóng gói nạp lên eCoSys, AI không đọc để tiết kiệm token/thời gian).")

                self.list_files.addItem(item)
        self.update_file_status_label()

    def update_file_status_label(self):
        total = len(self.selected_files)
        ai_count = 0
        for i in range(self.list_files.count()):
            if self.list_files.item(i).checkState() == Qt.Checked:
                ai_count += 1
        self.lbl_status.setText(f"Đã chọn {total} file ({ai_count} file [x] gửi AI đọc).")

    def select_only_core_files(self):
        for i in range(self.list_files.count()):
            f = self.selected_files[i]
            is_core = self.is_core_ai_file(os.path.basename(f))
            self.list_files.item(i).setCheckState(Qt.Checked if is_core else Qt.Unchecked)
        self.update_file_status_label()

    def select_all_ai_files(self):
        for i in range(self.list_files.count()):
            self.list_files.item(i).setCheckState(Qt.Checked)
        self.update_file_status_label()

    def remove_selected_file(self):
        row = self.list_files.currentRow()
        if row >= 0:
            self.list_files.takeItem(row)
            if row < len(self.selected_files):
                self.selected_files.pop(row)
        self.update_file_status_label()

    def clear_all_files(self):
        self.list_files.clear()
        self.selected_files.clear()
        self.lbl_status.setText("Đã xóa hết file.")

    def start_extraction(self):
        api_key = self.input_api_key.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Thiếu API Key", "Vui lòng nhập Google Gemini API Key.")
            self.input_api_key.setFocus()
            return

        if not self.selected_files:
            QMessageBox.warning(self, "Chưa chọn file", "Vui lòng chọn ít nhất 1 file chứng từ (PDF hoặc ảnh).")
            return

        # Lọc các file được tích chọn cho AI đọc
        ai_files = []
        for i in range(self.list_files.count()):
            item = self.list_files.item(i)
            if item.checkState() == Qt.Checked:
                ai_files.append(self.selected_files[i])

        if not ai_files:
            # Nếu chưa tích file nào, tự động chọn các file cốt lõi
            ai_files = [f for f in self.selected_files if self.is_core_ai_file(os.path.basename(f))]
            if not ai_files:
                ai_files = self.selected_files[:2]
            for i in range(self.list_files.count()):
                if self.selected_files[i] in ai_files:
                    self.list_files.item(i).setCheckState(Qt.Checked)

        self.save_current_config()

        target_form = self.combo_form.currentText().split()[0]
        model_name = self.combo_model.currentText().strip()

        # Cập nhật UI trạng thái
        self.btn_extract.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_status.setText(f"⏳ Đang gửi {len(ai_files)} file cốt lõi để AI phân tích...")

        # Khởi chạy Worker Thread CHỈ VỚI AI_FILES (tiết kiệm token & tăng tốc độ)
        self.worker = ExtractionWorker(
            api_key=api_key,
            file_paths=ai_files,
            target_form=target_form,
            model_name=model_name
        )
        self.worker.finished_signal.connect(self.on_extraction_success)
        self.worker.error_signal.connect(self.on_extraction_error)
        self.worker.start()

    def on_extraction_success(self, co_data: CODeclarationData, raw_json: str):
        self.btn_extract.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_status.setText("✅ Trích xuất thành công 100%!")
        
        self.current_co_data = co_data
        self.populate_inputs_from_data(co_data)
        allowed_docs = getattr(co_data, "deNghiHoSoDinhKem", []) or []
        self.populate_attachments_from_files(self.selected_files, allowed_types=allowed_docs)
        self.tabs.setCurrentIndex(0)
        QMessageBox.information(self, "Thành công", "AI đã trích xuất hoàn tất dữ liệu chứng từ!\nBạn có thể kiểm tra và chỉnh sửa ở các tab bên phải.")

    def on_extraction_error(self, err_msg: str):
        self.btn_extract.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_status.setText("❌ Lỗi trích xuất!")
        QMessageBox.critical(self, "Lỗi phân tích chứng từ", f"Không thể trích xuất dữ liệu:\n{err_msg}")

    def populate_inputs_from_data(self, data: CODeclarationData):
        # Tab 1: Exporter & Consignee
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

        # Tab 2: Transport & Invoice
        self.txt_trans_type.setText(data.route_TransportationType or "Đường biển")
        self.txt_vessel.setText(data.route_TransportName or "")
        self.txt_pol.setText(data.route_PortOfLoading or "")
        self.txt_pod.setText(data.route_PortOfDischange or "")
        self.txt_dep_date.setText(data.route_DepartureDepartureDate or "")
        self.txt_bill.setText(data.bill or "")

        self.txt_inv_no.setText(data.invoiceNumber or "")
        self.txt_inv_date.setText(data.invoiceDate or "")
        self.txt_inv_curr.setText(data.currency or "USD")
        self.txt_fob_total.setText(str(data.goods_Total_FobValue or 0.0))
        self.txt_customs_no.setText(data.declarationNumbers or "")
        self.txt_customs_date.setText(data.declarationDates or "")
        self.txt_remarks.setText(data.remarks or "")
        self.chk_issued_retro.setChecked(bool(data.isIssuedRetroactively))
        self.txt_retro_reason.setText(data.issuedRetroactivelyReason or "")

        # Manufacturer (Nhà sản xuất - Mục 25, 26)
        self.txt_manu_name.setText(data.manu_Name or "")
        self.txt_manu_addr1.setText(data.manu_AddressLine1 or "")
        self.txt_manu_addr2.setText(data.manu_AddressLine2 or "")

        # Nguyên liệu đầu vào (Tờ khai nhập khẩu / Hóa đơn VAT - Mục 27, 28, 29, 30)
        raw_imp_list = getattr(data, "importDeclarationList", []) or []
        imp_nos = []
        imp_dates = []
        for item in raw_imp_list:
            no = item.get("declarationNumber", "") if isinstance(item, dict) else getattr(item, "declarationNumber", "")
            dt = item.get("declarationDate", "") if isinstance(item, dict) else getattr(item, "declarationDate", "")
            if no:
                imp_nos.append(str(no).strip())
            if dt:
                imp_dates.append(str(dt).strip())
        self.txt_import_decl_no.setText(", ".join(imp_nos) if imp_nos else (getattr(data, "importDeclarationNumbers", "") or ""))
        self.txt_import_decl_date.setText(", ".join(imp_dates) if imp_dates else (getattr(data, "importDeclarationDates", "") or ""))

        raw_vat_list = getattr(data, "invoiceVATList", []) or []
        vat_nos = []
        vat_dates = []
        for item in raw_vat_list:
            no = item.get("declarationNumber", "") if isinstance(item, dict) else getattr(item, "declarationNumber", "")
            dt = item.get("declarationDate", "") if isinstance(item, dict) else getattr(item, "declarationDate", "")
            if no:
                vat_nos.append(str(no).strip())
            if dt:
                vat_dates.append(str(dt).strip())
        self.txt_vat_invoice_no.setText(", ".join(vat_nos) if vat_nos else (getattr(data, "invoiceVATNumbers", "") or ""))
        self.txt_vat_invoice_date.setText(", ".join(vat_dates) if vat_dates else (getattr(data, "invoiceVATDates", "") or ""))

        # Tab 3: Table items
        self.table_goods.setRowCount(0)
        raw_goods = getattr(data, "goodItems", []) or []
        for row, item in enumerate(raw_goods):
            self.table_goods.insertRow(row)
            imp_hs = item.importingHsCode or (item.exportingHsCode[:6] if len(item.exportingHsCode) >= 6 else item.exportingHsCode)
            self.set_table_item(row, 0, item.exportingHsCode)
            self.set_table_item(row, 1, imp_hs)
            self.set_table_item(row, 2, item.goodsDescription)
            self.set_table_item(row, 3, item.originCriterion)
            q_unit = "KILOGRAM" if any(k in (item.quantityUnit or "").upper() for k in ["KG", "KILO"]) else (item.quantityUnit or "KILOGRAM")
            self.set_table_item(row, 4, str(item.quantity))
            self.set_table_item(row, 5, q_unit)
            self.set_table_item(row, 6, str(item.grossWeight))
            self.set_table_item(row, 7, str(item.packageQuantity or 1))
            self.set_table_item(row, 8, item.packageUnit or "CARTON")
            self.set_table_item(row, 9, str(item.value))
            self.set_table_item(row, 10, item.currency)
            self.set_table_item(row, 11, item.markAndNumberOnPackage or "NO MARK")
            self.set_table_item(row, 12, item.invoiceNumber or data.invoiceNumber or "")
            self.set_table_item(row, 13, item.invoiceDate or data.invoiceDate or "")

        # Cập nhật Tab 4: JSON
        self.refresh_json_from_inputs()

    def set_table_item(self, row: int, col: int, text: str):
        item = QTableWidgetItem(str(text))
        self.table_goods.setItem(row, col, item)

    def get_table_item(self, row: int, col: int) -> str:
        item = self.table_goods.item(row, col)
        return item.text().strip() if item else ""

    def add_table_row(self):
        row = self.table_goods.rowCount()
        self.table_goods.insertRow(row)
        self.set_table_item(row, 0, "")
        self.set_table_item(row, 1, "")
        self.set_table_item(row, 2, "NEW ITEM")
        self.set_table_item(row, 3, "WO")
        self.set_table_item(row, 4, "1")
        self.set_table_item(row, 5, "KILOGRAM")
        self.set_table_item(row, 6, "1.0")
        self.set_table_item(row, 7, "1")
        self.set_table_item(row, 8, "CARTON")
        self.set_table_item(row, 9, "0.0")
        self.set_table_item(row, 10, "USD - Dollar Mỹ")
        self.set_table_item(row, 11, "NO MARK")
        self.set_table_item(row, 12, self.txt_inv_no.text().strip() if hasattr(self, "txt_inv_no") else "")
        self.set_table_item(row, 13, self.txt_inv_date.text().strip() if hasattr(self, "txt_inv_date") else "")

    def delete_table_row(self):
        row = self.table_goods.currentRow()
        if row >= 0:
            self.table_goods.removeRow(row)

    def recalculate_totals(self):
        total_fob = 0.0
        for r in range(self.table_goods.rowCount()):
            try:
                val = float(self.get_table_item(r, 9) or 0)
                total_fob += val
            except ValueError:
                pass
        self.txt_fob_total.setText(str(round(total_fob, 2)))
        QMessageBox.information(self, "Đã tính lại", f"Tổng trị giá FOB mới: {round(total_fob, 2)}")

    def collect_data_from_inputs(self) -> dict:
        """Gom dữ liệu từ tất cả ô input và bảng để xuất ra dict JSON chuẩn"""
        form_code = self.combo_form.currentText().split()[0]

        # Xử lý danh sách Hóa đơn VAT nguyên liệu trong nước (Mục 29, 30: hỗ trợ nhiều hóa đơn)
        raw_vat_nos = [s.strip() for s in self.txt_vat_invoice_no.text().split(",") if s.strip()]
        raw_vat_dates = [s.strip() for s in self.txt_vat_invoice_date.text().split(",") if s.strip()]
        vat_list = []
        for idx, no in enumerate(raw_vat_nos):
            dt = raw_vat_dates[idx] if idx < len(raw_vat_dates) else ""
            vat_list.append({"declarationNumber": no, "declarationDate": dt})

        # Xử lý danh sách Tờ khai HQ nhập khẩu nguyên liệu (Mục 27, 28: hỗ trợ nhiều tờ khai)
        raw_imp_nos = [s.strip() for s in self.txt_import_decl_no.text().split(",") if s.strip()]
        raw_imp_dates = [s.strip() for s in self.txt_import_decl_date.text().split(",") if s.strip()]
        imp_list = []
        for idx, no in enumerate(raw_imp_nos):
            dt = raw_imp_dates[idx] if idx < len(raw_imp_dates) else ""
            imp_list.append({"declarationNumber": no, "declarationDate": dt})

        items = []
        for r in range(self.table_goods.rowCount()):
            hs_exp = self.get_table_item(r, 0)
            hs_imp = self.get_table_item(r, 1) or (hs_exp[:6] if len(hs_exp) >= 6 else hs_exp)
            desc = self.get_table_item(r, 2)
            criterion = self.get_table_item(r, 3)
            try:
                qty = float(self.get_table_item(r, 4) or 0)
            except ValueError:
                qty = 0.0
            qty_unit = self.get_table_item(r, 5)
            try:
                gw = float(self.get_table_item(r, 6) or 0)
            except ValueError:
                gw = 0.0
            try:
                pkg_qty = int(self.get_table_item(r, 7) or 1)
            except ValueError:
                pkg_qty = 1
            pkg_unit = self.get_table_item(r, 8)
            try:
                val = float(self.get_table_item(r, 9) or 0)
            except ValueError:
                val = 0.0
            curr = self.get_table_item(r, 10)
            mark = self.get_table_item(r, 11) or "NO MARK"
            inv_no = self.get_table_item(r, 12) or self.txt_inv_no.text().strip()
            inv_dt = self.get_table_item(r, 13) or self.txt_inv_date.text().strip()

            clean_qty_unit = "KILOGRAM" if any(k in qty_unit.upper() for k in ["KG", "KILO"]) else qty_unit
            item = {
                "exportingHsCode": hs_exp,
                "importingHsCode": hs_imp,
                "goodsDescription": desc,
                "originCriterion": criterion,
                "countryOfOrigin": "VN",
                "quantity": qty,
                "quantityUnit": clean_qty_unit,
                "markAndNumberOnPackage": mark,
                "packageQuantity": pkg_qty,
                "packageUnit": pkg_unit,
                "grossWeight": gw,
                "grossWeightUnit": "KGM",
                "value": val,
                "currency": curr,
                "invoiceNumber": inv_no,
                "invoiceDate": inv_dt
            }
            items.append(item)

        try:
            fob_val = float(self.txt_fob_total.text().strip() or 0)
        except ValueError:
            fob_val = 0.0

        data = {
            "form": form_code,
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
            "currency": self.txt_inv_curr.text().strip() or "USD",
            "goods_Total_FobValue": fob_val,
            "declarationNumbers": self.txt_customs_no.text().strip(),
            "declarationDates": self.txt_customs_date.text().strip(),
            "remarks": self.txt_remarks.text().strip(),
            "isIssuedRetroactively": self.chk_issued_retro.isChecked(),
            "issuedRetroactivelyReason": self.txt_retro_reason.text().strip(),
            "goodItems": items
        }

        # Thu thập danh sách tệp đính kèm (mã hóa Base64)
        attachments = []
        if hasattr(self, "chk_include_base64") and self.chk_include_base64.isChecked() and hasattr(self, "table_attachments"):
            for r in range(self.table_attachments.rowCount()):
                chk = self.table_attachments.item(r, 0)
                if chk and chk.checkState() == Qt.Checked:
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
                            print(f"Lỗi đọc file đính kèm {fpath}: {ex}")

        data["attachments"] = attachments
        return data

    def refresh_json_from_inputs(self):
        data = self.collect_data_from_inputs()
        self.full_json_str = json.dumps(data, indent=2, ensure_ascii=False)

        # Tạo bản preview rút gọn cho giao diện để tránh đơ app nếu file quá nặng
        try:
            preview_data = json.loads(self.full_json_str)
            if "attachments" in preview_data and isinstance(preview_data["attachments"], list):
                for att in preview_data["attachments"]:
                    if "base64" in att and len(att["base64"]) > 80:
                        kb = round(len(att["base64"]) * 0.75 / 1024, 1)
                        att["base64"] = f"[Base64 ~{kb} KB - Sẽ được sao chép/xuất đầy đủ khi bấm nút]"
            display_json = json.dumps(preview_data, indent=2, ensure_ascii=False)
        except Exception:
            display_json = self.full_json_str

        self.txt_json_view.setPlainText(display_json)

    def on_tab_changed(self, index: int):
        # Khi người dùng chuyển sang Tab 5 (JSON), tự động update dữ liệu mới nhất
        if index == 4:
            self.refresh_json_from_inputs()

    def copy_json_to_clipboard(self):
        self.refresh_json_from_inputs()
        json_text = getattr(self, "full_json_str", "").strip() or self.txt_json_view.toPlainText().strip()
        if not json_text:
            QMessageBox.warning(self, "Chưa có dữ liệu", "Không có dữ liệu JSON để sao chép.")
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(json_text)
        QMessageBox.information(
            self,
            "Đã sao chép vào Clipboard",
            "Đã copy toàn bộ dữ liệu JSON (kèm tệp đính kèm Base64) vào bộ nhớ đệm!\n\n"
            "Bây giờ bạn chỉ cần mở tab https://co.moit.gov.vn/hoSo/KhaiBaoCO trên trình duyệt\n"
            "và bấm nút 'Dán & Điền tự động' trên Extension."
        )

    def save_json_file(self):
        self.refresh_json_from_inputs()
        json_text = getattr(self, "full_json_str", "").strip() or self.txt_json_view.toPlainText().strip()
        if not json_text:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu dữ liệu hồ sơ C/O thành file JSON",
            "ho_so_co.json",
            "JSON Files (*.json)"
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(json_text)
            QMessageBox.information(self, "Đã lưu file", f"Đã lưu thành công tại:\n{file_path}")

    def load_sample_data(self):
        sample_path = "sample_data.json"
        if not os.path.exists(sample_path):
            QMessageBox.warning(self, "Không tìm thấy file", f"Không tìm thấy file {sample_path}")
            return

        with open(sample_path, "r", encoding="utf-8") as f:
            data_dict = json.load(f)

        co_data = CODeclarationData.model_validate(data_dict)
        self.current_co_data = co_data
        self.populate_inputs_from_data(co_data)
        if hasattr(self, "selected_files") and self.selected_files:
            allowed_docs = getattr(co_data, "deNghiHoSoDinhKem", []) or []
            self.populate_attachments_from_files(self.selected_files, allowed_types=allowed_docs)
        QMessageBox.information(self, "Đã nạp dữ liệu mẫu", "Đã nạp thành công bộ hồ sơ mẫu Form E (Xuất khẩu nông sản)!")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    window = COExtractorApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
