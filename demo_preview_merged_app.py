"""
BẢN DEMO XEM TRƯỚC: HỆ THỐNG QUẢN TRỊ XUẤT NHẬP KHẨU & HỒ SƠ THỦY SẢN TOÀN DIỆN
Gộp 2 nghiệp vụ:
  1. Khai báo C/O eCoSys (Bộ Công Thương) • Gemini 3.8 Flash
  2. Đối chiếu SC & XNNL Cảng Cá (Dự án Chị Nguyên) • IUU Marine

LƯU Ý: Đây là bản demo giao diện độc lập để người dùng xem trước và duyệt thiết kế.
Bản gốc của cả 2 dự án được bảo toàn nguyên vẹn 100%.
"""

import sys
import os

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QCheckBox, QProgressBar,
    QStackedWidget, QFrame, QTextEdit, QScrollArea, QFileDialog
)
from PyQt6.QtGui import QFont, QIcon, QColor


class UnifiedSuiteDemoApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bộ Phần Mềm Quản Trị Xuất Nhập Khẩu & Hồ Sơ Thủy Sản (eCoSys C/O & Đối Chiếu SC)")
        self.resize(1400, 880)
        self.setMinimumSize(1100, 720)

        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f1f5f9;
            }
            QLabel {
                font-family: 'Segoe UI', Arial, sans-serif;
                color: #1e293b;
            }
            QLineEdit, QComboBox, QTextEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: #ffffff;
                font-size: 12.5px;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 2px solid #0078d4;
            }
            QPushButton {
                font-family: 'Segoe UI', Arial, sans-serif;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
                font-size: 12.5px;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ========================================================
        # THANH ĐIỀU HƯỚNG BÊN TRÁI (SIDEBAR NAVIGATION - FLUENT STYLE)
        # ========================================================
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(240)
        self.sidebar.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border-right: 1px solid #1e293b;
            }
            QLabel {
                color: #f8fafc;
            }
        """)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(8)

        # Brand / Logo Header
        app_title = QLabel("🚢 XNK & LOGISTICS")
        app_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        sidebar_layout.addWidget(app_title)

        app_sub = QLabel("Bộ Phần Mềm Hợp Nhất 2 Trong 1")
        app_sub.setStyleSheet("font-size: 11px; color: #94a3b8; margin-bottom: 12px;")
        sidebar_layout.addWidget(app_sub)

        # Navigation Buttons
        self.btn_nav_co = self.create_nav_button("📋  Khai báo C/O eCoSys", active=True)
        self.btn_nav_co.clicked.connect(lambda: self.switch_page(0))
        sidebar_layout.addWidget(self.btn_nav_co)

        self.btn_nav_sc = self.create_nav_button("⚓  Đối chiếu SC & XNNL", active=False)
        self.btn_nav_sc.clicked.connect(lambda: self.switch_page(1))
        sidebar_layout.addWidget(self.btn_nav_sc)

        self.btn_nav_settings = self.create_nav_button("⚙️  Cài đặt API Dùng Chung", active=False)
        self.btn_nav_settings.clicked.connect(lambda: self.switch_page(2))
        sidebar_layout.addWidget(self.btn_nav_settings)

        sidebar_layout.addStretch()

        # Footer info
        lbl_version = QLabel("Phiên bản Hợp Nhất v3.0\nKhóa cứng: Gemini 3.8 Flash")
        lbl_version.setStyleSheet("font-size: 11px; color: #64748b; line-height: 1.4;")
        sidebar_layout.addWidget(lbl_version)

        main_layout.addWidget(self.sidebar)

        # ========================================================
        # KHU VỰC NỘI DUNG CHÍNH (STACKED WIDGET)
        # ========================================================
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, stretch=1)

        # Trang 0: Phân hệ C/O eCoSys
        self.page_co = self.create_co_module_preview()
        self.stack.addWidget(self.page_co)

        # Trang 1: Phân hệ Đối chiếu SC (Chị Nguyên)
        self.page_sc = self.create_sc_module_preview()
        self.stack.addWidget(self.page_sc)

        # Trang 2: Phân hệ Cài đặt API dùng chung
        self.page_settings = self.create_settings_module_preview()
        self.stack.addWidget(self.page_settings)

    def create_nav_button(self, text: str, active: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(44)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_nav_button_style(btn, active)
        return btn

    def apply_nav_button_style(self, btn: QPushButton, active: bool):
        if active:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: #ffffff;
                    text-align: left;
                    padding-left: 14px;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: bold;
                    border: none;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #cbd5e1;
                    text-align: left;
                    padding-left: 14px;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: 500;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #1e293b;
                    color: #ffffff;
                }
            """)

    def switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
        self.apply_nav_button_style(self.btn_nav_co, active=(index == 0))
        self.apply_nav_button_style(self.btn_nav_sc, active=(index == 1))
        self.apply_nav_button_style(self.btn_nav_settings, active=(index == 2))

    # --------------------------------------------------------
    # MÔ PHỎNG PHÂN HỆ 1: C/O ECOSYS
    # --------------------------------------------------------
    def create_co_module_preview(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header bar
        hdr = QHBoxLayout()
        title = QLabel("📋 PHÂN HỆ 1: TRÍCH XUẤT CHỨNG TỪ KHAI BÁO C/O (eCoSys Bộ Công Thương)")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0284c7;")
        hdr.addWidget(title)

        badge = QLabel("🛡️ Đơn vị: KILOGRAM (Đã khóa)")
        badge.setStyleSheet("background: #dcfce7; color: #166534; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11.5px;")
        hdr.addWidget(badge)

        hdr.addStretch()

        btn_copy = QPushButton("📋 SAO CHÉP JSON (DÁN VÀO EXTENSION)")
        btn_copy.setStyleSheet("background: #107c41; color: white; font-weight: bold; padding: 8px 16px;")
        hdr.addWidget(btn_copy)
        layout.addLayout(hdr)

        # Body split demo
        body = QHBoxLayout()
        left_demo = QFrame()
        left_demo.setFixedWidth(320)
        left_demo.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px;")
        left_l = QVBoxLayout(left_demo)
        left_l.addWidget(QLabel("<b>1. Chứng từ đính kèm (Mẫu 04)</b>"))
        left_l.addWidget(QLabel("✓ Đơn đề nghị cấp C/O\n✓ Commercial Invoice\n✓ Tờ khai hải quan XK\n✓ Vận đơn (Bill of Lading)\n✓ Bảng kê BOM / Chi phí NVL"))
        left_l.addStretch()
        btn_run_co = QPushButton("⚡ BẮT ĐẦU TRÍCH XUẤT BẰNG AI")
        btn_run_co.setStyleSheet("background: #0078d4; color: white; font-weight: bold; padding: 10px;")
        left_l.addWidget(btn_run_co)
        body.addWidget(left_demo)

        right_demo = QFrame()
        right_demo.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px;")
        right_l = QVBoxLayout(right_demo)
        right_l.addWidget(QLabel("<b>2. Không gian làm việc 7 Tab (Khai báo eCoSys)</b>"))
        right_l.addWidget(QLabel("Tab 1: Doanh nghiệp & Địa điểm | Tab 2: Vận tải & Hóa đơn (Đa dòng Tờ khai nhập & VAT) | Tab 3: Hàng hóa (Khóa KILOGRAM) | Tab 4: 10 Slot đính kèm | Tab 5: JSON | Tab 6: Copilot AI | Tab 7: Xem trước chứng từ"))
        right_l.addWidget(QTextEdit("Dữ liệu C/O hiện tại sẵn sàng đồng bộ 100% vào phân hệ này mà không làm mất bất kỳ cấu hình hay phím tắt nào."))
        body.addWidget(right_demo, stretch=1)

        layout.addLayout(body, stretch=1)
        return widget

    # --------------------------------------------------------
    # MÔ PHỎNG PHÂN HỆ 2: ĐỐI CHIẾU SC (DỰ ÁN CHỊ NGUYÊN)
    # --------------------------------------------------------
    def create_sc_module_preview(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header bar
        hdr = QHBoxLayout()
        title = QLabel("⚓ PHÂN HỆ 2: ĐỐI CHIẾU HỒ SƠ XÁC NHẬN NGUYÊN LIỆU (XNNL & SC GỐC CẢNG CÁ)")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e3a8a;")
        hdr.addWidget(title)

        badge = QLabel("🐟 Hồ sơ IUU & Chuẩn hóa PMSX")
        badge.setStyleSheet("background: #e0f2fe; color: #0369a1; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11.5px;")
        hdr.addWidget(badge)
        hdr.addStretch()
        layout.addLayout(hdr)

        # Box 1: Chọn Tệp Đầu Vào (Scan SC + Excel PMSX + Thư mục lưu)
        in_box = QFrame()
        in_box.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px;")
        in_grid = QGridLayout(in_box)
        in_grid.setSpacing(8)

        in_grid.addWidget(QLabel("<b>Bản Scan SC Gốc (PDF / Folder):</b>"), 0, 0)
        entry_sc = QLineEdit("00180 2026 SC  GL TQ HL.pdf (Hoặc thư mục chứa nhiều file SC)")
        in_grid.addWidget(entry_sc, 0, 1)
        btn_sc = QPushButton("Chọn File(s)...")
        in_grid.addWidget(btn_sc, 0, 2)

        in_grid.addWidget(QLabel("<b>File Excel XNNL (PMSX):</b>"), 1, 0)
        entry_excel = QLineEdit("XKNL_26260EUR_1.xlsx")
        in_grid.addWidget(entry_excel, 1, 1)
        btn_ex = QPushButton("Chọn Excel...")
        in_grid.addWidget(btn_ex, 1, 2)

        in_grid.addWidget(QLabel("<b>Thư mục xuất kết quả:</b>"), 2, 0)
        entry_out = QLineEdit("KetQua_DoiChieu/")
        in_grid.addWidget(entry_out, 2, 1)
        btn_out = QPushButton("Chọn Thư Mục...")
        in_grid.addWidget(btn_out, 2, 2)

        layout.addWidget(in_box)

        # Box 2: Tùy chọn & Nút Bắt đầu đối chiếu
        opt_box = QFrame()
        opt_box.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px;")
        opt_layout = QHBoxLayout(opt_box)

        chk_ai = QCheckBox("🤖 Bóc tách bằng AI Vision (Gemini 3.8 Flash)")
        chk_ai.setChecked(True)
        opt_layout.addWidget(chk_ai)

        chk_merge = QCheckBox("🔄 Tự động gộp lượng (Cùng tàu + Cùng ngày)")
        chk_merge.setChecked(True)
        opt_layout.addWidget(chk_merge)

        chk_correct = QCheckBox("✏️ Tự động sửa Chủ tàu & GPKTTS theo SC gốc")
        chk_correct.setChecked(True)
        opt_layout.addWidget(chk_correct)

        opt_layout.addStretch()

        btn_run_sc = QPushButton("🚀 BẮT ĐẦU ĐỐI CHIẾU & XỬ LÝ TỰ ĐỘNG")
        btn_run_sc.setStyleSheet("background: #1e40af; color: white; font-weight: bold; padding: 10px 22px; font-size: 13.5px;")
        opt_layout.addWidget(btn_run_sc)

        layout.addWidget(opt_box)

        # Box 3: 5 Thẻ KPI Thống Kê Số Liệu Trực Quan
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(10)

        cards = [
            ("TÀU SC GỐC", "27", "#1e3a8a"),
            ("TÀU EXCEL", "27", "#334155"),
            ("KHỚP 100%", "24", "#15803d"),
            ("SAI LỆCH CẦN SỬA", "3", "#b91c1c"),
            ("ĐÃ GỘP LƯỢNG", "2", "#b45309"),
        ]
        for title, val, col in cards:
            card = QFrame()
            card.setStyleSheet(f"background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px;")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(6, 6, 6, 6)
            cl.setSpacing(2)
            lbl_t = QLabel(title)
            lbl_t.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748b;")
            lbl_t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(lbl_t)
            lbl_v = QLabel(val)
            lbl_v.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {col};")
            lbl_v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(lbl_v)
            kpi_layout.addWidget(card)

        layout.addLayout(kpi_layout)

        # Box 4: Thanh nút kết quả nổi bật
        exp_box = QFrame()
        exp_box.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px 12px;")
        exp_l = QHBoxLayout(exp_box)
        exp_l.addWidget(QLabel("<b>📁 KẾT QUẢ ĐÃ XUẤT:</b>"))
        btn_open_rep = QPushButton("📊 Mở Báo Cáo Đối Chiếu (.xlsx)")
        btn_open_rep.setStyleSheet("background: #15803d; color: white; font-weight: bold;")
        exp_l.addWidget(btn_open_rep)

        btn_open_fixed = QPushButton("📑 Mở File XNNL Chuẩn Hóa (.xlsx)")
        btn_open_fixed.setStyleSheet("background: #0284c7; color: white; font-weight: bold;")
        exp_l.addWidget(btn_open_fixed)

        btn_open_fol = QPushButton("📂 Mở Thư Mục Kết Quả")
        btn_open_fol.setStyleSheet("background: #475569; color: white; font-weight: bold;")
        exp_l.addWidget(btn_open_fol)
        layout.addWidget(exp_box)

        # Box 5: Nhật ký xử lý
        log_box = QTextEdit()
        log_box.setReadOnly(True)
        log_box.setStyleSheet("background: #0f172a; color: #38bdf8; font-family: Consolas, monospace; font-size: 11.5px; border-radius: 6px; padding: 8px;")
        log_box.setText(
            "[10:30:15] Bắt đầu quá trình đối chiếu tự động...\n"
            "[10:30:16] Đã quét xong Giấy xác nhận SC gốc: 00180/2026/SC-GL-TQ-HL -> Tìm thấy 27 tàu cá.\n"
            "[10:30:17] Đã đọc dữ liệu Excel (Phụ lục 02a): Tìm thấy 27 dòng dữ liệu tàu.\n"
            "[10:30:18] Đã tự động gộp lượng cho 2 lượt tàu trùng ngày lên cá.\n"
            "[10:30:19] PHÁT HIỆN 3 SAI LỆCH:\n"
            "   * Tàu BĐ-99013-TS: Tên chủ tàu Excel là 'Dương Thị Xí', trong khi SC gốc ghi 'Võ Văn Lưu'.\n"
            "   * Tàu KH-91234-TS: Sai ngày hết hạn GPKTTS (SC gốc: 15/12/2026, Excel: 10/12/2026).\n"
            "   * Tàu PY-95678-TS: Chênh lệch khối lượng 50.0 kg.\n"
            "[10:30:20] Đã xuất xong Báo cáo đối chiếu và File XNNL chuẩn hóa thành công!"
        )
        layout.addWidget(log_box, stretch=1)

        return widget

    # --------------------------------------------------------
    # MÔ PHỎNG PHÂN HỆ 3: CÀI ĐẶT API DÙNG CHUNG
    # --------------------------------------------------------
    def create_settings_module_preview(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("⚙️ CÀI ĐẶT HỆ THỐNG & TÀI KHOẢN AI DÙNG CHUNG")
        title.setStyleSheet("font-size: 17px; font-weight: bold; color: #0f172a;")
        layout.addWidget(title)

        sub = QLabel("Chỉ cần cấu hình API Key 1 lần duy nhất, cả 2 phân hệ (Khai báo C/O eCoSys và Đối chiếu SC) đều được kích hoạt tự động!")
        sub.setStyleSheet("font-size: 13px; color: #475569;")
        layout.addWidget(sub)

        card = QFrame()
        card.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 18px;")
        grid = QGridLayout(card)
        grid.setSpacing(12)

        grid.addWidget(QLabel("<b>Nguồn API:</b>"), 0, 0)
        combo_source = QComboBox()
        combo_source.addItems(["APIZ Vietnam Gateway (Khuyên dùng)", "Google Gemini Official"])
        grid.addWidget(combo_source, 0, 1)

        grid.addWidget(QLabel("<b>API Key:</b>"), 1, 0)
        entry_key = QLineEdit("sk-k5K6****************************************")
        entry_key.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addWidget(entry_key, 1, 1)

        grid.addWidget(QLabel("<b>Base URL:</b>"), 2, 0)
        entry_base = QLineEdit("https://api.apiz.vn/v1")
        grid.addWidget(entry_base, 2, 1)

        grid.addWidget(QLabel("<b>Mô hình AI:</b>"), 3, 0)
        entry_model = QLineEdit("gemini-3.8-flash (Cố định tốc độ cao nhất)")
        entry_model.setEnabled(False)
        grid.addWidget(entry_model, 3, 1)

        btn_save = QPushButton("💾 Lưu Cấu Hình Cho Toàn Bộ Ứng Dụng")
        btn_save.setStyleSheet("background: #0078d4; color: white; font-weight: bold; padding: 10px 20px;")
        grid.addWidget(btn_save, 4, 1, Qt.AlignmentFlag.AlignRight)

        layout.addWidget(card)
        layout.addStretch()
        return widget


if __name__ == "__main__":
    app = QApplication(sys.argv)
    demo = UnifiedSuiteDemoApp()
    demo.show()
    sys.exit(app.exec())
