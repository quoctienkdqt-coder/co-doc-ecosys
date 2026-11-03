"""
HỆ THỐNG QUẢN TRỊ XUẤT NHẬP KHẨU & HỒ SƠ THỦY SẢN TOÀN DIỆN (UNIFIED SUITE v3.0)
Hợp nhất 2 Phân hệ Nghiệp vụ Trọng yếu:
  1. Khai báo C/O eCoSys (Bộ Công Thương) • Khóa cứng Đơn vị KILOGRAM • Extension v2.6.0
  2. Đối chiếu SC & XNNL Cảng Cá (Dự án Chị Nguyên) • Quét Scan SC • So khớp Excel PMSX • Báo cáo Màu KPI
  3. Trợ lý AI Copilot Đa Nghiệp vụ Song Hành (Gemini 3.8 Flash & Cổng APIZ)

Tính năng nổi bật:
- Menu Sidebar bên trái có thể thu gọn (64px) hoặc mở rộng (240px) để tối đa hóa không gian làm việc.
- Dùng chung 1 cấu hình API Key (Google Official hoặc APIZ Vietnam Gateway).
- Phím tắt tiện ích: Ctrl+B (Thu/Mở Menu), F1 (Cẩm nang Hướng dẫn).
"""

import sys
import re
import os

# Cho phép nạp các file mã nguồn .py cập nhật trực tiếp từ thư mục làm việc (Hỗ trợ Live-Update qua GitHub)
app_exec_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
for _p in [app_exec_dir, os.path.join(app_exec_dir, "co_core"), os.path.join(app_exec_dir, "sc_core")]:
    if _p and os.path.exists(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import json
import subprocess
from datetime import datetime
from typing import List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QCheckBox, QProgressBar,
    QStackedWidget, QFrame, QTextEdit, QTextBrowser, QFileDialog, QMessageBox,
    QSplitter, QHeaderView, QTableWidget, QTableWidgetItem, QTabWidget
)
from PyQt6.QtGui import QFont, QIcon, QColor, QKeySequence, QShortcut
from PyQt6.QtWidgets import QButtonGroup, QSizePolicy

import ui_theme as ui
from ui_theme import apply_app_theme

# Import C/O Module & Gemini Advisor
try:
    from co_core.app_co_extractor import COExtractorApp, UserGuideDialog, load_settings, save_settings, CONFIG_FILE
    from co_core.app_co_extractor import ChatbotWorker as UnifiedCopilotWorker
    from co_core.gemini_extractor import ask_co_advisor
except ImportError:
    from app_co_extractor import COExtractorApp, UserGuideDialog, load_settings, save_settings, CONFIG_FILE
    from app_co_extractor import ChatbotWorker as UnifiedCopilotWorker
    from gemini_extractor import ask_co_advisor

# Import SC Core Engine (Self-contained in sc_core)
from collections import defaultdict
from sc_core.sc_extractor import extract_multiple_sc_documents
from sc_core.excel_processor import load_excel_xnnl, aggregate_and_validate_excel, load_bang_ke_excel
from sc_core.reconciler import (
    reconcile_excel_vs_sc, reconcile_bang_ke_vs_invoices, reconcile_bang_ke_vs_sc,
    reconcile_full_suite, normalize_sc_key, clean_vessel_key, normalize_fish_size,
    strip_vietnamese_accents
)
from sc_core.report_generator import create_reconciliation_excel_report, generate_corrected_excel_xnnl, create_full_suite_excel_report
from sc_core.sc_excel_vs_pdf import reconcile_sc_excel_files_vs_repo
from sc_core.invoice_extractor import extract_invoices_repository, find_invoice_in_repo
from sc_core.ai_extractor import load_ai_config, save_ai_config


# Cột hiển thị cho tab đối chiếu SC Excel <-> SC scan PDF: (khóa, tiêu đề, độ rộng)
SCX_COLUMNS = [
    ("owner", "Chủ tàu / Thuyền trưởng", 170), ("gear", "Ngư cụ", 120), ("licence_no", "Số GPKTTS", 200),
    ("licence_exp", "Hạn GPKTTS", 130), ("catch_area", "Vùng khai thác", 180), ("catch_period", "Thời gian khai thác", 210),
    ("species", "Loài thủy sản", 230), ("landing_date", "Ngày bốc dỡ", 130), ("req_catch_kg", "KL nguyên liệu mua (kg)", 140),
    ("total_catch_kg", "KL khai thác (kg)", 140), ("validity", "Khai thác & bốc dỡ trong hạn GP", 220),
    ("landing_order", "Ngày bốc dỡ sau ngày khai thác", 220),
]


# ========================================================
# 1. WORKER CHẠY NGẦM ĐỐI CHIẾU HỒ SƠ SC & BẢNG KÊ (QTHREAD)
# ========================================================
class SCReconcileWorker(QThread):
    progress_signal = pyqtSignal(int, str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, dict, str)

    def __init__(self, mode: str, sc_sources: List[str], bang_ke_file: str,
                 invoices_dir: str, excel_file: str, out_dir: str,
                 use_ai: bool, api_key: str, api_source: str, api_base_url: str,
                 do_merge: bool, do_correct: bool, sc_excel_files: Optional[List[str]] = None):
        super().__init__()
        self.sc_excel_files = [f for f in (sc_excel_files or []) if f and os.path.exists(f)]
        self.mode = mode  # ALL_IN_ONE (Default unified flow)
        self.sc_sources = sc_sources
        self.bang_ke_file = bang_ke_file
        self.invoices_dir = invoices_dir
        # Nguồn hóa đơn: thư mục hoặc 1/nhiều file PDF (cách nhau bởi ';')
        self.invoice_sources = [p.strip().strip('"') for p in (invoices_dir or "").split(";")
                                if p.strip() and os.path.exists(p.strip().strip('"'))]
        self.excel_file = excel_file
        self.out_dir = out_dir
        self.use_ai = use_ai
        self.api_key = api_key
        self.api_source = api_source
        self.api_base_url = api_base_url
        self.do_merge = do_merge
        self.do_correct = do_correct

    def run(self):
        try:
            self.log_signal.emit("🚀 Bắt đầu quá trình đối chiếu hồ sơ xuất nhập khẩu hợp nhất...")
            os.makedirs(self.out_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prov = "apiz" if (self.api_source == "apiz" or (self.api_key and self.api_key.startswith("sk-"))) else "gemini"

            def prog_cb(pct, msg):
                self.progress_signal.emit(pct, msg)
                self.log_signal.emit(f"[{pct}%] {msg}")

            has_bk = bool(self.bang_ke_file and os.path.exists(self.bang_ke_file))
            has_inv = bool(self.invoice_sources)
            has_xnnl = bool(self.excel_file and os.path.exists(self.excel_file))
            inv_src = self.invoice_sources if len(self.invoice_sources) != 1 else self.invoice_sources[0]

            if has_bk:
                self.log_signal.emit(f"📋 Bảng kê thu mua (TT 05): {os.path.basename(self.bang_ke_file)}")
            if has_inv:
                self.log_signal.emit(f"🧾 Hóa đơn VAT: {', '.join(os.path.basename(p) or p for p in self.invoice_sources)}")
            elif has_bk:
                self.log_signal.emit("⚠️ Chưa có hóa đơn VAT (thư mục 'hoa don' hoặc file PDF hóa đơn) — "
                                     "sẽ KHÔNG có kết quả đối chiếu Bảng kê ↔ Hóa đơn.")
            if self.sc_sources:
                self.log_signal.emit(f"⚓ Nguồn SC gốc: {len(self.sc_sources)} tệp / thư mục")
            if has_xnnl:
                self.log_signal.emit(f"🐟 File Excel XNNL: {os.path.basename(self.excel_file)}")

            if has_bk and has_inv:
                master_res = reconcile_full_suite(
                    bang_ke_file=self.bang_ke_file,
                    invoices_dir=inv_src,
                    sc_sources=self.sc_sources,
                    excel_xnnl_file=self.excel_file if has_xnnl else None,
                    use_ai=self.use_ai,
                    api_key=self.api_key,
                    api_source=self.api_source,
                    api_base_url=self.api_base_url,
                    do_merge=self.do_merge,
                    do_correct=self.do_correct,
                    progress_cb=prog_cb,
                    log_cb=self.log_signal.emit
                )
            else:
                # Chế độ chỉ có XNNL + SC (hoặc thiếu Bảng kê/Hóa đơn)
                prog_cb(20, "Đang quét bóc tách Giấy xác nhận SC gốc...")
                sc_repo, all_sc_records = extract_multiple_sc_documents(
                    self.sc_sources, cache_dir="cache", use_ai=self.use_ai,
                    api_key=self.api_key, provider=prov
                )
                recon_results, summary_stats, merge_logs = [], {}, []
                if has_xnnl:
                    prog_cb(60, "Đang đọc và đối chiếu File Excel XNNL với SC gốc...")
                    ex_meta, raw_records, _ = load_excel_xnnl(self.excel_file)
                    if self.do_merge:
                        agg_records, merge_logs = aggregate_and_validate_excel(raw_records)
                    else:
                        agg_records = raw_records
                    recon_results, summary_stats = reconcile_excel_vs_sc(agg_records, sc_repo)

                bk_meta, bk_records = {}, []
                bk_vs_inv_recons, bk_vs_inv_rows, bk_vs_inv_sum = [], [], {}
                bk_vs_sc_recons, bk_vs_sc_sum = [], {}
                invoices_repo = {}

                if has_bk:
                    bk_meta, bk_records, _, _, _ = load_bang_ke_excel(self.bang_ke_file)
                    if self.sc_sources:
                        bk_vs_sc_recons, bk_vs_sc_sum = reconcile_bang_ke_vs_sc(bk_records, sc_repo)
                    if has_inv:
                        prog_cb(70, "Đang đọc Hóa đơn VAT (bản scan đọc bằng AI)...")
                        invoices_repo = extract_invoices_repository(
                            inv_src, use_ai=self.use_ai, ai_provider=prov, api_key=self.api_key or None,
                            base_url=(self.api_base_url or None) if prov == "apiz" else None,
                            cache_dir="cache", log_cb=self.log_signal.emit)
                        bk_vs_inv_recons, bk_vs_inv_rows, bk_vs_inv_sum = reconcile_bang_ke_vs_invoices(bk_records, invoices_repo)

                master_res = {
                    'dossier_status': "HOÀN TẤT ĐỐI CHIẾU HỒ SƠ",
                    'bang_ke_meta': bk_meta,
                    'bang_ke_records': bk_records,
                    'invoices_repo': invoices_repo,
                    'sc_repo': sc_repo,
                    'all_sc_records': all_sc_records,
                    'bk_vs_invoices': {'recons': bk_vs_inv_recons, 'rows': bk_vs_inv_rows, 'summary': bk_vs_inv_sum},
                    'bk_vs_sc': {'recons': bk_vs_sc_recons, 'summary': bk_vs_sc_sum},
                    'xnnl_vs_sc': {'recons': recon_results, 'summary': summary_stats, 'merge_logs': merge_logs}
                }

            # Cảnh báo rõ khi đọc Bảng kê / Hóa đơn không ra dữ liệu (thay vì im lặng thiếu sheet)
            self.inv_warning = ""
            if has_bk and not master_res.get('bang_ke_records'):
                self.inv_warning = ("Không đọc được dòng nào trong Bảng kê "
                                    f"'{os.path.basename(self.bang_ke_file)}' — kiểm tra lại mẫu bảng kê.")
            elif has_bk and has_inv:
                repo = master_res.get('invoices_repo') or {}
                n_inv = repo.get('count', 0)
                skipped = repo.get('scanned_skipped') or []
                if skipped and not self.use_ai:
                    self.inv_warning = ("Hóa đơn là BẢN SCAN nhưng chưa bật AI — tick ô 'AI đọc SC & hóa đơn scan' "
                                        f"rồi chạy lại ({', '.join(os.path.basename(x) for x in skipped)}).")
                elif n_inv == 0:
                    self.inv_warning = ("Không đọc được số hóa đơn nào từ file hóa đơn"
                                        + (" (AI đọc bản scan bị lỗi — xem Nhật ký)." if skipped else "."))
                else:
                    for fn, st in (repo.get('ai_stats') or {}).items():
                        self.log_signal.emit(
                            f"🤖 {fn}: {st['pages']} trang → đọc {st['invoice_pages']} trang hóa đơn "
                            f"({st['ai_calls']} lượt gọi AI, {st['from_cache']} lấy từ cache), bỏ qua {st['skipped']} trang khác"
                            + (f", {st['errors']} trang lỗi" if st.get('errors') else ""))
                    self.log_signal.emit(f"🧾 Đọc được {n_inv} hóa đơn VAT.")
            elif has_bk and not has_inv:
                self.inv_warning = "Không có hóa đơn VAT nên phần đối chiếu Bảng kê ↔ Hóa đơn để trống."
            if self.inv_warning:
                self.log_signal.emit(f"⚠️ {self.inv_warning}")

            # Đối chiếu SC Excel <-> SC scan PDF
            if self.sc_excel_files:
                self.log_signal.emit("[95%] Đang đối chiếu file SC Excel với bản SC scan PDF...")
                master_res['sc_excel_vs_pdf'] = reconcile_sc_excel_files_vs_repo(
                    self.sc_excel_files, master_res.get('sc_repo', {}), log_cb=self.log_signal.emit)
                for _r in master_res['sc_excel_vs_pdf']:
                    if 'error' in _r:
                        self.log_signal.emit(f"⚠️ {_r['error']}")

            # Xuất DUY NHẤT 1 file báo cáo Excel gồm 4 Sheet chuẩn
            report_name = f"BaoCao_DoiChieu_SC_XNNL_{timestamp}.xlsx"
            report_path = os.path.join(self.out_dir, report_name)
            report_path = create_full_suite_excel_report(report_path, master_res)
            self.log_signal.emit(f"📊 Đã xuất File Báo cáo 4 Sheet chuẩn: {report_path}")

            # Đồng thời cập nhật bản chuẩn trong thư mục lô hàng (nếu có) để tiện mở ngay
            lote_dir = os.path.dirname(self.bang_ke_file or self.excel_file or "")
            if lote_dir and os.path.isdir(lote_dir):
                try:
                    lote_report = os.path.join(lote_dir, "BaoCao_DoiChieu_SC_XNNL.xlsx")
                    create_full_suite_excel_report(lote_report, master_res)
                    self.log_signal.emit(f"📁 Đã lưu bản báo cáo tại thư mục hồ sơ: {lote_report}")
                except Exception:
                    pass

            corrected_path = None
            xnnl_recons = master_res.get('xnnl_vs_sc', {}).get('recons', [])
            if self.do_correct and has_xnnl and xnnl_recons:
                corrected_name = f"XNNL_DaChuanHoa_{timestamp}.xlsx"
                corrected_path = os.path.join(self.out_dir, corrected_name)
                generate_corrected_excel_xnnl(self.excel_file, corrected_path, xnnl_recons)
                self.log_signal.emit(f"📑 Đã tạo File XNNL chuẩn hóa: {corrected_path}")

            prog_cb(100, "Hoàn tất đối chiếu và xuất báo cáo!")
            result_data = {
                "mode": "ALL_IN_ONE",
                "master_res": master_res,
                "report_path": report_path,
                "corrected_path": corrected_path,
                "output_dir": self.out_dir,
                "inv_warning": getattr(self, "inv_warning", "")
            }
            self.finished_signal.emit(True, result_data, "")

        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            self.log_signal.emit(f"❌ LỖI TRONG QUÁ TRÌNH XỬ LÝ: {e}\n{tb_str}")
            self.finished_signal.emit(False, {}, str(e))


# ========================================================
# 2. WIDGET PHÂN HỆ 2: ĐỐI CHIẾU HỒ SƠ SC & BẢNG KÊ (UI GỌN GÀNG, HIỆN ĐẠI)
# ========================================================
class SCReconciliationWidget(QWidget):
    def __init__(self, parent_app):
        super().__init__()
        self.parent_app = parent_app
        self.worker: Optional[SCReconcileWorker] = None
        self.last_report_path = None
        self.last_corrected_path = None
        self.last_out_dir = None

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(12)

        # --------------------------------------------------------
        # TIÊU ĐỀ TRANG
        # --------------------------------------------------------
        self.btn_open_folder = ui.button("📂 Thư mục kết quả", "ghost", tooltip="Mở thư mục KetQua_DoiChieu")
        self.btn_open_folder.clicked.connect(self.open_output_folder)
        layout.addLayout(ui.page_header(
            "Đối chiếu hồ sơ SC & Bảng kê",
            "Chọn thư mục lô hàng — phần mềm tự nhận SC gốc, Bảng kê, Hóa đơn VAT, XNNL và SC Excel rồi đối chiếu 1 lần.",
            [self.btn_open_folder]))

        # --------------------------------------------------------
        # THẺ 1: CHỌN HỒ SƠ + CHẠY
        # --------------------------------------------------------
        ctrl_card = ui.card()
        ctrl_layout = QVBoxLayout(ctrl_card)
        ctrl_layout.setContentsMargins(16, 14, 16, 12)
        ctrl_layout.setSpacing(10)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        self.entry_folder = QLineEdit()
        self.entry_folder.setObjectName("SearchLike")
        self.entry_folder.setPlaceholderText("📁  Đường dẫn thư mục hồ sơ lô hàng (VD: ld.linh)...")
        self.entry_folder.returnPressed.connect(lambda: self.auto_detect_folder(self.entry_folder.text().strip()))
        row1.addWidget(self.entry_folder, stretch=1)

        btn_auto_dir = ui.button("📂 Chọn thư mục lô hàng", "soft")
        btn_auto_dir.clicked.connect(self.browse_auto_dir)
        row1.addWidget(btn_auto_dir)

        btn_sample = ui.button("Nạp mẫu ld.linh", "ghost", tooltip="Nạp nhanh thư mục mẫu ld.linh")
        btn_sample.clicked.connect(self.load_sample_ld_linh)
        row1.addWidget(btn_sample)

        self.btn_toggle_manual = ui.button("⚙ Chọn lẻ từng file ▾", "ghost")
        self.btn_toggle_manual.setCheckable(True)
        self.btn_toggle_manual.toggled.connect(self.toggle_manual_files)
        row1.addWidget(self.btn_toggle_manual)
        ctrl_layout.addLayout(row1)

        # Chip trạng thái từng loại chứng từ (bấm để chọn / đổi file)
        pills_row = QHBoxLayout()
        pills_row.setSpacing(8)
        self.pill_sc = ui.button("", "chip")
        self.pill_sc.clicked.connect(self.browse_sc_files)
        self.pill_bk = ui.button("", "chip")
        self.pill_bk.clicked.connect(self.browse_bang_ke_file)
        self.pill_inv = ui.button("", "chip")
        self.pill_inv.clicked.connect(self.browse_invoices_dir)
        self.pill_xnnl = ui.button("", "chip")
        self.pill_xnnl.clicked.connect(self.browse_excel_file)
        self.pill_scx = ui.button("", "chip")
        self.pill_scx.clicked.connect(self.browse_sc_excel_files)
        for p in (self.pill_sc, self.pill_bk, self.pill_inv, self.pill_xnnl, self.pill_scx):
            p.setMinimumWidth(120)
            pills_row.addWidget(p, stretch=1)
        ctrl_layout.addLayout(pills_row)

        # Khung chọn lẻ từng file (ẩn mặc định)
        self.panel_manual = ui.card("Inset")
        self.panel_manual.setVisible(False)
        grid_in = QGridLayout(self.panel_manual)
        grid_in.setHorizontalSpacing(10)
        grid_in.setVerticalSpacing(8)
        grid_in.setContentsMargins(12, 10, 12, 10)
        grid_in.setColumnStretch(1, 1)

        def lbl(t):
            w = QLabel(t)
            w.setObjectName("Muted")
            return w

        grid_in.addWidget(lbl("SC gốc (PDF / thư mục)"), 0, 0)
        self.entry_sc = QLineEdit()
        self.entry_sc.setPlaceholderText("Các file PDF SC gốc hoặc thư mục chứa SC...")
        self.entry_sc.textChanged.connect(self.refresh_file_pills)
        grid_in.addWidget(self.entry_sc, 0, 1)
        btn_sc_f = ui.button("Chọn file...", size="sm")
        btn_sc_f.clicked.connect(self.browse_sc_files)
        btn_sc_d = ui.button("Thư mục...", size="sm")
        btn_sc_d.clicked.connect(self.browse_sc_dir)
        sc_btn_box = QHBoxLayout()
        sc_btn_box.setSpacing(6)
        sc_btn_box.addWidget(btn_sc_f)
        sc_btn_box.addWidget(btn_sc_d)
        grid_in.addLayout(sc_btn_box, 0, 2)

        grid_in.addWidget(lbl("Bảng kê thu mua (TT 05)"), 1, 0)
        self.entry_bang_ke = QLineEdit()
        self.entry_bang_ke.setPlaceholderText("File Excel Bảng kê thu mua nguyên liệu (bang ke.xlsx)...")
        self.entry_bang_ke.textChanged.connect(self.refresh_file_pills)
        grid_in.addWidget(self.entry_bang_ke, 1, 1)
        btn_bk = ui.button("Chọn file...", size="sm")
        btn_bk.clicked.connect(self.browse_bang_ke_file)
        grid_in.addWidget(btn_bk, 1, 2, Qt.AlignmentFlag.AlignLeft)

        grid_in.addWidget(lbl("Thư mục Hóa đơn VAT"), 2, 0)
        self.entry_invoices = QLineEdit()
        self.entry_invoices.setPlaceholderText("Thư mục chứa các file PDF Hóa đơn VAT điện tử (hoa don/)...")
        self.entry_invoices.textChanged.connect(self.refresh_file_pills)
        grid_in.addWidget(self.entry_invoices, 2, 1)
        btn_inv = ui.button("Thư mục...", size="sm")
        btn_inv.clicked.connect(self.browse_invoices_dir)
        grid_in.addWidget(btn_inv, 2, 2, Qt.AlignmentFlag.AlignLeft)

        grid_in.addWidget(lbl("Excel XNNL (PMSX)"), 3, 0)
        self.entry_excel = QLineEdit()
        self.entry_excel.setPlaceholderText("File Excel XNNL (ví dụ: ~XKNL_26131MRS_1.xlsx)...")
        self.entry_excel.textChanged.connect(self.refresh_file_pills)
        grid_in.addWidget(self.entry_excel, 3, 1)
        btn_ex = ui.button("Chọn file...", size="sm")
        btn_ex.clicked.connect(self.browse_excel_file)
        grid_in.addWidget(btn_ex, 3, 2, Qt.AlignmentFlag.AlignLeft)

        grid_in.addWidget(lbl("Các file SC dạng Excel"), 4, 0)
        self.entry_sc_excel = QLineEdit()
        self.entry_sc_excel.setPlaceholderText("Một hoặc nhiều file SC Excel (cách nhau bởi ;) — tự ghép với SC scan PDF cùng số SC...")
        self.entry_sc_excel.textChanged.connect(self.refresh_file_pills)
        grid_in.addWidget(self.entry_sc_excel, 4, 1)
        btn_scx = ui.button("Thêm file...", size="sm", tooltip="Chọn được nhiều file cùng lúc (giữ Ctrl). Bấm lại để thêm tiếp.")
        btn_scx.clicked.connect(self.browse_sc_excel_files)
        btn_scx_d = ui.button("Thư mục...", size="sm", tooltip="Thêm tất cả file Excel SC trong một thư mục")
        btn_scx_d.clicked.connect(self.browse_sc_excel_dir)
        btn_scx_clr = ui.button("Xóa", "danger", "sm", tooltip="Xóa danh sách file SC Excel")
        btn_scx_clr.clicked.connect(lambda: self.entry_sc_excel.clear())
        scx_btn_box = QHBoxLayout()
        scx_btn_box.setSpacing(6)
        scx_btn_box.addWidget(btn_scx)
        scx_btn_box.addWidget(btn_scx_d)
        scx_btn_box.addWidget(btn_scx_clr)
        grid_in.addLayout(scx_btn_box, 4, 2)
        ctrl_layout.addWidget(self.panel_manual)

        # Đường kẻ mảnh phân tách
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {ui.C['border']}; border: none;")
        ctrl_layout.addWidget(sep)

        # Tùy chọn + nút chạy + mở kết quả
        action_row = QHBoxLayout()
        action_row.setSpacing(14)

        # Giữ combo_mode ẩn để tương thích ngược, luôn ALL_IN_ONE
        self.combo_mode = QComboBox()
        self.combo_mode.addItem("ALL_IN_ONE", "ALL_IN_ONE")
        self.combo_mode.setVisible(False)

        self.chk_ai = QCheckBox("AI đọc SC & hóa đơn scan")
        self.chk_ai.setToolTip("Dùng AI đọc bản scan SC và hóa đơn VAT scan (chỉ đọc trang là hóa đơn, có cache)")
        self.chk_ai.setChecked(True)
        action_row.addWidget(self.chk_ai)
        self.chk_merge = QCheckBox("Gộp tàu trùng ngày")
        self.chk_merge.setChecked(True)
        action_row.addWidget(self.chk_merge)
        self.chk_correct = QCheckBox("Xuất XNNL đã sửa")
        self.chk_correct.setChecked(True)
        action_row.addWidget(self.chk_correct)

        self.lbl_status = QLabel("Sẵn sàng đối chiếu.")
        self.lbl_status.setObjectName("StatusText")
        action_row.addWidget(self.lbl_status, stretch=1)

        self.btn_open_report = ui.button("📊 Mở báo cáo", "soft", tooltip="Mở file báo cáo Excel vừa xuất")
        self.btn_open_report.clicked.connect(self.open_report_file)
        self.btn_open_report.setEnabled(False)
        action_row.addWidget(self.btn_open_report)

        self.btn_open_fixed = ui.button("📑 XNNL đã sửa", "soft", tooltip="Mở file XNNL đã chuẩn hóa")
        self.btn_open_fixed.clicked.connect(self.open_fixed_file)
        self.btn_open_fixed.setEnabled(False)
        action_row.addWidget(self.btn_open_fixed)

        self.btn_run = ui.button("▶  Bắt đầu đối chiếu", "primary", "lg")
        self.btn_run.setMinimumWidth(190)
        self.btn_run.clicked.connect(self.start_reconciliation)
        action_row.addWidget(self.btn_run)
        ctrl_layout.addLayout(action_row)

        self.prog_bar = QProgressBar()
        self.prog_bar.setFixedHeight(4)
        self.prog_bar.setValue(0)
        self.prog_bar.setTextVisible(False)
        ctrl_layout.addWidget(self.prog_bar)
        # Giữ nguyên chiều cao khung điều khiển; khi thiếu chỗ thì bảng kết quả bên dưới co lại (không ép bẹp ô nhập)
        ctrl_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(ctrl_card)

        # --------------------------------------------------------
        # DÃY THẺ KPI
        # --------------------------------------------------------
        kpi_box = QHBoxLayout()
        kpi_box.setSpacing(10)
        self.lbl_kpi_bk = self.create_kpi_card(kpi_box, "Dòng bảng kê", "0", "#2563EB")
        self.lbl_kpi_inv = self.create_kpi_card(kpi_box, "Hóa đơn VAT", "0", "#0891B2")
        self.lbl_kpi_sc = self.create_kpi_card(kpi_box, "Tàu trên SC gốc", "0", "#475569")
        self.lbl_kpi_match = self.create_kpi_card(kpi_box, "Khớp hoàn toàn", "0", "#16A34A")
        self.lbl_kpi_diff = self.create_kpi_card(kpi_box, "Lưu ý & sai lệch", "0", "#DC2626")
        layout.addLayout(kpi_box)

        # --------------------------------------------------------
        # BẢNG KẾT QUẢ (đồng bộ với file báo cáo Excel)
        # --------------------------------------------------------
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(False)
        self.tabs.setUsesScrollButtons(True)

        def tab_page():
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(10, 10, 10, 10)
            lay.setSpacing(8)
            return w, lay

        def prep_table(t: QTableWidget, row_h=46):
            t.setWordWrap(True)
            t.verticalHeader().setVisible(False)
            t.verticalHeader().setDefaultSectionSize(row_h)
            t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            t.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            t.horizontalHeader().setMinimumHeight(40)
            t.setShowGrid(True)

        # TAB 1: Đối chiếu Bảng kê (HĐ VAT vàng & SC gốc xanh) — giống Sheet 2 báo cáo
        self.tab_bk_audit, l_bk = tab_page()
        self.tbl_bk_audit = QTableWidget()
        self.tbl_bk_audit.setColumnCount(16)
        self.tbl_bk_audit.setHorizontalHeaderLabels([
            "STT", "Tên NL", "Size Cá", "Mã HS", "Nơi KT",
            "[HĐ Vàng] Số Lượng (KGS)\n(Excel / HĐ gốc)",
            "[HĐ Vàng] Đơn Giá (VNĐ)\n(Excel / HĐ gốc)",
            "[HĐ Vàng] Tổng Trị Giá (VNĐ)\n(Excel / HĐ gốc)",
            "[HĐ Vàng] Nhà Cung Cấp\n(Excel / HĐ gốc)",
            "[HĐ Vàng] Địa Chỉ NCC\n(Excel / HĐ gốc)",
            "[HĐ Vàng] Số HĐ\n(Excel / HĐ)",
            "[HĐ Vàng] Ngày HĐ\n(Excel / HĐ)",
            "[SC Xanh] Số Giấy SC\n(Excel / SC gốc)",
            "[SC Xanh] Số Đăng Ký Tàu\n(Excel / SC gốc)",
            "[SC Xanh] Chủ Tàu / Thuyền Trưởng\n(Excel / SC gốc)",
            "Kết Luận & Đánh Giá Chi Tiết"
        ])
        prep_table(self.tbl_bk_audit)
        self.tbl_bk_audit.setAlternatingRowColors(False)
        for c_i, w_v in enumerate([46, 80, 75, 70, 70, 185, 145, 165, 210, 230, 105, 115, 165, 175, 185, 280]):
            self.tbl_bk_audit.setColumnWidth(c_i, w_v)
        l_bk.addWidget(self.tbl_bk_audit)
        self.tabs.addTab(self.tab_bk_audit, "Bảng kê ↔ HĐ VAT & SC")
        self.tabs.setTabToolTip(0, "Đối chiếu Bảng kê (HĐ VAT tô vàng ↔ SC gốc tô xanh)")

        # TAB 2: XNNL ↔ SC gốc — giống Sheet 1 báo cáo
        self.tab_xnnl, l_xnnl = tab_page()
        self.tbl_xnnl = QTableWidget()
        self.tbl_xnnl.setColumnCount(12)
        self.tbl_xnnl.setHorizontalHeaderLabels([
            "STT", "Số ĐK Tàu", "Số Giấy SC", "Trạng Thái", "Gộp Lượng?",
            "Tên Chủ Tàu\n(Excel / SC gốc)",
            "Số GPKTTS\n(Excel / SC gốc)",
            "Hạn GP\n(Excel / SC)",
            "Thời Gian KT\n(Excel / SC)",
            "Ngày Lên Cá\n(Excel / SC)",
            "Khối Lượng Mua\n(Excel / SC / Lệch)",
            "Hành Động Khắc Phục Đề Xuất"
        ])
        prep_table(self.tbl_xnnl)
        for c_i, w_v in enumerate([46, 105, 150, 110, 95, 180, 160, 115, 165, 115, 175, 240]):
            self.tbl_xnnl.setColumnWidth(c_i, w_v)
        self.tbl_xnnl.horizontalHeader().setSectionResizeMode(11, QHeaderView.ResizeMode.Stretch)
        l_xnnl.addWidget(self.tbl_xnnl)
        self.tabs.addTab(self.tab_xnnl, "XNNL ↔ SC gốc")
        self.tabs.setTabToolTip(1, "Bảng đối chiếu sai khác XNNL (PMSX) với SC gốc cảng cá")

        # TAB 3: Toàn bộ SC gốc — giống Sheet 4 báo cáo
        self.tab_all_sc, l_all_sc = tab_page()
        self.tbl_all_sc = QTableWidget()
        self.tbl_all_sc.setColumnCount(9)
        self.tbl_all_sc.setHorizontalHeaderLabels([
            "STT", "Số Giấy SC", "Số Đăng Ký Tàu", "Tên Chủ Tàu / Thuyền Trưởng (SC Gốc)",
            "Số Giấy Phép KTTS", "Hạn Giấy Phép", "Thời Gian Khai Thác", "Ngày Lên Cá", "Sản Lượng Xác Nhận (kg)"
        ])
        prep_table(self.tbl_all_sc, 36)
        self.tbl_all_sc.setAlternatingRowColors(True)
        self.tbl_all_sc.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        l_all_sc.addWidget(self.tbl_all_sc)
        self.tabs.addTab(self.tab_all_sc, "Toàn bộ tàu SC gốc")
        self.tabs.setTabToolTip(2, "Toàn bộ tàu đọc được trên SC gốc (có dấu)")

        # TAB 4: SC Excel ↔ SC scan PDF
        self.tab_scx, l_scx = tab_page()
        self.lbl_scx_summary = QLabel("Chưa có dữ liệu. Chọn file SC Excel + SC scan PDF rồi bấm Bắt đầu đối chiếu.")
        self.lbl_scx_summary.setWordWrap(True)
        self.lbl_scx_summary.setObjectName("Muted")
        self.lbl_scx_summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        l_scx.addWidget(self.lbl_scx_summary)
        self.tbl_scx = QTableWidget()
        self.tbl_scx.setColumnCount(len(SCX_COLUMNS) + 5)
        self.tbl_scx.setHorizontalHeaderLabels(["STT", "Số ĐK Tàu", "Số Giấy SC", "Kết quả"]
                                               + [c[1] for c in SCX_COLUMNS] + ["Chi tiết sai lệch"])
        prep_table(self.tbl_scx)
        for c_i, w_v in enumerate([46, 110, 160, 90] + [c[2] for c in SCX_COLUMNS] + [260]):
            self.tbl_scx.setColumnWidth(c_i, w_v)
        l_scx.addWidget(self.tbl_scx)
        self.tabs.addTab(self.tab_scx, "SC Excel ↔ SC PDF")
        self.tabs.setTabToolTip(3, "Đối chiếu file SC dạng Excel với bản SC scan PDF")

        # TAB 5: Nhật ký
        self.tab_log, l_log = tab_page()
        self.txt_log = QTextEdit()
        self.txt_log.setObjectName("LogView")
        self.txt_log.setReadOnly(True)
        l_log.addWidget(self.txt_log)
        self.tabs.addTab(self.tab_log, "Nhật ký xử lý")

        layout.addWidget(self.tabs, stretch=1)
        self.refresh_file_pills()
        ui.smooth_item_views(self)

    @staticmethod
    def _short(s: str, n: int = 26) -> str:
        return s if len(s) <= n else s[:n - 1] + "…"

    def _set_pill_state(self, btn: QPushButton, active: bool, text: Optional[str] = None, tip: str = ""):
        """Chip trạng thái chứng từ: xanh = đã có file, viền đứt = chưa chọn."""
        if text:
            btn.setText(text)
        btn.setToolTip(tip or ("Bấm để đổi file" if active else "Bấm để chọn file"))
        ui.set_prop(btn, "state", "on" if active else "off")

    def toggle_manual_files(self, checked: bool):
        self.panel_manual.setVisible(checked)
        self.btn_toggle_manual.setText("⚙ Ẩn chọn lẻ ▴" if checked else "⚙ Chọn lẻ từng file ▾")

    def refresh_file_pills(self):
        # 1. SC gốc
        raw_sc = self.entry_sc.text().strip()
        if raw_sc:
            parts = [s.strip() for s in raw_sc.split(";") if s.strip()]
            if len(parts) == 1 and os.path.isdir(parts[0]):
                self._set_pill_state(self.pill_sc, True, f"✓ SC gốc · {self._short(os.path.basename(parts[0]), 16)}", parts[0])
            else:
                self._set_pill_state(self.pill_sc, True, f"✓ SC gốc · {len(parts)} file", "\n".join(parts))
        else:
            self._set_pill_state(self.pill_sc, False, "⚓ SC gốc · chưa chọn")

        # 2. Bảng kê
        bk = self.entry_bang_ke.text().strip()
        if bk and os.path.exists(bk):
            self._set_pill_state(self.pill_bk, True, f"✓ Bảng kê · {self._short(os.path.basename(bk), 16)}", bk)
        else:
            self._set_pill_state(self.pill_bk, False, "📋 Bảng kê TT05 · chưa chọn")

        # 3. Hóa đơn VAT
        inv = self.entry_invoices.text().strip()
        inv_parts = [p.strip().strip('"') for p in inv.split(";") if p.strip()]
        inv_files = [p for p in inv_parts if os.path.isfile(p) and p.lower().endswith('.pdf')]
        if inv and os.path.isdir(inv):
            try:
                pdf_cnt = len([f for f in os.listdir(inv) if f.lower().endswith('.pdf')])
            except OSError:
                pdf_cnt = 0
            self._set_pill_state(self.pill_inv, True, f"✓ Hóa đơn VAT · {pdf_cnt} PDF", inv)
        elif inv_files:
            self._set_pill_state(self.pill_inv, True,
                                 f"✓ Hóa đơn VAT · {self._short(os.path.basename(inv_files[0]), 14)}"
                                 + (f" +{len(inv_files) - 1}" if len(inv_files) > 1 else ""), "\n".join(inv_files))
        else:
            self._set_pill_state(self.pill_inv, False, "🧾 Hóa đơn VAT · chưa chọn")

        # 4. Excel XNNL
        ex = self.entry_excel.text().strip()
        if ex and os.path.exists(ex):
            self._set_pill_state(self.pill_xnnl, True, f"✓ XNNL · {self._short(os.path.basename(ex), 18)}", ex)
        else:
            self._set_pill_state(self.pill_xnnl, False, "🐟 Excel XNNL · chưa chọn")

        # 5. SC Excel
        scx = self.get_sc_excel_files() if hasattr(self, 'entry_sc_excel') else []
        if scx:
            self._set_pill_state(self.pill_scx, True, f"✓ SC Excel · {len(scx)} file",
                                 "\n".join(os.path.basename(x) for x in scx) + "\n\nBấm để thêm file")
        else:
            self._set_pill_state(self.pill_scx, False, "📗 SC Excel · chưa chọn",
                                 "Chọn 1 hoặc nhiều file SC Excel để đối chiếu với SC scan PDF")

    def create_kpi_card(self, parent_layout, title: str, val: str, color: str, bg_color: str = "#ffffff") -> QLabel:
        """Thẻ KPI: vạch màu bên trái + nhãn nhỏ + số lớn."""
        card = ui.card("KpiCard")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        l = QHBoxLayout(card)
        l.setContentsMargins(12, 10, 14, 10)
        l.setSpacing(10)

        accent = QFrame()
        accent.setObjectName("KpiAccent")
        accent.setFixedWidth(4)
        accent.setStyleSheet(f"QFrame#KpiAccent {{ background: {color}; }}")
        l.addWidget(accent)

        col = QVBoxLayout()
        col.setSpacing(0)
        lbl_t = QLabel(title)
        lbl_t.setObjectName("Caption")
        col.addWidget(lbl_t)
        lbl_v = QLabel(val)
        lbl_v.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {color};")
        col.addWidget(lbl_v)
        l.addLayout(col, stretch=1)

        parent_layout.addWidget(card, stretch=1)
        return lbl_v

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.txt_log.append(f"[{ts}] {msg}")

    def browse_auto_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục hồ sơ lô hàng xuất khẩu")
        if d:
            self.entry_folder.setText(d)
            self.auto_detect_folder(d)

    def load_sample_ld_linh(self):
        p_ld = os.path.abspath(r"C:/Users/Admin/Desktop/chị Nguyên/ld.linh")
        if os.path.exists(p_ld):
            self.entry_folder.setText(p_ld)
            self.auto_detect_folder(p_ld)
        else:
            QMessageBox.warning(self, "Không tìm thấy", f"Thư mục mẫu không tồn tại: {p_ld}")

    def auto_detect_folder(self, folder_path: str):
        if not os.path.isdir(folder_path):
            return

        self.log(f"🔍 Bắt đầu quét tự động thư mục: {folder_path}")
        sc_files = []
        bang_ke_file = ""
        invoices_dir = ""
        excel_xnnl_file = ""
        sc_excel_found = []
        invoice_pdfs = []  # file PDF hóa đơn đặt lẻ (vd 'hoa don.pdf' gộp nhiều hóa đơn)
        inv_name_re = re.compile(r'(h[oó]a\s*[dđ][oơ]n|hdon|(^|[^a-z])hd([^a-z]|$)|invoice)', re.I)

        for root, dirs, files in os.walk(folder_path):
            # Không quét vào thư mục KetQua_DoiChieu
            if "ketqua_doichieu" in root.lower():
                continue
            for d in dirs:
                if d.lower() in ('hoa don', 'hoa_don', 'invoices', 'hd', 'hóa đơn'):
                    invoices_dir = os.path.join(root, d)
            for f in files:
                if f.startswith('~$') or f.startswith('BaoCao_DoiChieu') or f.startswith('XNNL_DaChuanHoa'):
                    continue
                f_low = f.lower()
                full_p = os.path.join(root, f)
                in_inv_dir = bool(invoices_dir) and os.path.abspath(root).startswith(os.path.abspath(invoices_dir))
                if f_low.endswith('.pdf') and 'sc' in f_low:
                    sc_files.append(full_p)
                elif f_low.endswith('.pdf') and not in_inv_dir and inv_name_re.search(strip_vietnamese_accents(f_low)):
                    invoice_pdfs.append(full_p)
                elif f_low.endswith('.xlsx') and ('bang ke' in f_low or 'bang_ke' in f_low or 'bảng kê' in f_low):
                    bang_ke_file = full_p
                elif f_low.endswith('.xlsx') and ('xknl' in f_low or 'xnnl' in f_low or 'pmsx' in f_low or 'pfi' in f_low):
                    excel_xnnl_file = full_p
                elif f_low.endswith('.xlsx') and re.search(r'(^|[^a-z])sc([^a-z]|$)', f_low):
                    sc_excel_found.append(full_p)

        if not invoices_dir and invoice_pdfs:
            # Không có thư mục 'hoa don' -> dùng (các) file PDF hóa đơn đặt lẻ
            invoices_dir = "; ".join(invoice_pdfs)
            self.log(f"🧾 Không thấy thư mục 'hoa don' — dùng file hóa đơn: {', '.join(os.path.basename(x) for x in invoice_pdfs)}")
        self.entry_sc.setText("; ".join(sc_files) if sc_files else "")
        self.entry_bang_ke.setText(bang_ke_file)
        self.entry_invoices.setText(invoices_dir)
        self.entry_excel.setText(excel_xnnl_file)
        self.entry_sc_excel.setText("; ".join(sc_excel_found))
        self.refresh_file_pills()

        self.lbl_status.setText(f"Đã nạp: {len(sc_files)} SC • Bảng kê • HĐ VAT • XNNL • {len(sc_excel_found)} SC Excel")
        if sc_excel_found:
            self.log(f"📗 SC dạng Excel (sẽ đối chiếu với SC scan PDF): {', '.join(os.path.basename(x) for x in sc_excel_found)}")

    def browse_sc_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn các file Scan SC gốc", "",
            "Tài liệu PDF / Ảnh (*.pdf *.png *.jpg *.jpeg);;Tất cả tệp (*.*)"
        )
        if files:
            self.entry_sc.setText("; ".join(files))

    def _add_sc_excel_paths(self, paths: List[str]):
        """Cộng dồn file SC Excel vào ô nhập (không trùng lặp)."""
        cur = [p.strip().strip('"') for p in self.entry_sc_excel.text().split(";") if p.strip()]
        norm = {os.path.normcase(os.path.abspath(p)) for p in cur}
        for p in paths:
            k = os.path.normcase(os.path.abspath(p))
            if k not in norm:
                cur.append(p)
                norm.add(k)
        self.entry_sc_excel.setText("; ".join(cur))
        self.log(f"📗 Danh sách SC Excel: {len(cur)} file")

    def browse_sc_excel_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn một hoặc nhiều file SC dạng Excel (giữ Ctrl để chọn nhiều)", "",
            "Excel Files (*.xlsx *.xlsm *.xls)")
        if files:
            self._add_sc_excel_paths(files)

    def browse_sc_excel_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa các file SC dạng Excel")
        if not d:
            return
        found = []
        for root, _dirs, files in os.walk(d):
            if "ketqua_doichieu" in root.lower():
                continue
            for f in sorted(files):
                if f.startswith(('~$', 'BaoCao_DoiChieu', 'XNNL_DaChuanHoa')):
                    continue
                if f.lower().endswith(('.xlsx', '.xlsm', '.xls')) and re.search(r'(^|[^a-z])sc([^a-z]|$)', f.lower()):
                    found.append(os.path.join(root, f))
        if not found:
            QMessageBox.information(self, "Không tìm thấy", "Không có file Excel nào có chữ 'SC' trong tên ở thư mục này.")
            return
        self._add_sc_excel_paths(found)

    def get_sc_excel_files(self) -> List[str]:
        """File SC Excel: lấy từ ô riêng + các file .xlsx lỡ chọn chung ở ô SC scan."""
        out = []
        for raw in (self.entry_sc_excel.text(), self.entry_sc.text()):
            for p in raw.split(";"):
                p = p.strip().strip('"')
                bn = os.path.basename(p)
                if bn.startswith(('~$', 'BaoCao_DoiChieu', 'XNNL_DaChuanHoa')):
                    continue
                if p.lower().endswith(('.xlsx', '.xlsm', '.xls')) and os.path.isfile(p) and p not in out:
                    out.append(p)
        return out

    def browse_sc_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa các file Scan SC gốc")
        if d:
            self.entry_sc.setText(d)

    def browse_bang_ke_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Chọn file Bảng kê thu mua theo Thông tư 05", "",
            "Tệp Excel (*.xlsx *.xls);;Tất cả tệp (*.*)"
        )
        if f:
            self.entry_bang_ke.setText(f)

    def browse_invoices_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa các file PDF Hóa đơn điện tử")
        if d:
            self.entry_invoices.setText(d)

    def browse_excel_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Chọn file Excel XNNL từ phần mềm khai thác", "",
            "Tệp Excel (*.xlsx *.xls);;Tất cả tệp (*.*)"
        )
        if f:
            self.entry_excel.setText(f)

    def start_reconciliation(self):
        raw_sc = self.entry_sc.text().strip()
        bang_ke_path = self.entry_bang_ke.text().strip()
        invoices_dir = self.entry_invoices.text().strip()
        excel_path = self.entry_excel.text().strip()
        out_dir = os.path.abspath("KetQua_DoiChieu")

        sc_excel_files = self.get_sc_excel_files()
        if not raw_sc:
            QMessageBox.warning(self, "Thiếu dữ liệu", "Vui lòng chọn thư mục lô hàng hoặc ít nhất 1 file Scan SC gốc!")
            return
        if not bang_ke_path and not excel_path and not sc_excel_files:
            QMessageBox.warning(self, "Thiếu dữ liệu", "Vui lòng chọn file Excel Bảng kê thu mua (TT 05) hoặc file Excel XNNL!")
            return

        if ";" in raw_sc:
            sc_sources = [s.strip() for s in raw_sc.split(";") if s.strip()]
        else:
            sc_sources = [raw_sc] if raw_sc else []
        # Chỉ đưa PDF/ảnh/thư mục vào bộ bóc tách SC scan (loại file Excel)
        sc_sources = [s for s in sc_sources if not s.lower().endswith(('.xlsx', '.xlsm', '.xls'))]
        if not sc_sources:
            QMessageBox.warning(self, "Thiếu dữ liệu", "Chưa có file SC scan (PDF/ảnh). File Excel không thể dùng làm SC scan!")
            return

        cfg = self.parent_app.shared_config
        api_key = cfg.get("api_key", "")
        api_source = cfg.get("api_source", "official")
        api_base_url = cfg.get("api_base_url", "https://api.apiz.vn/v1")

        self.btn_run.setEnabled(False)
        self.btn_run.setText("⏳  Đang đối chiếu...")
        self.tabs.setCurrentWidget(self.tab_log)
        self.prog_bar.setValue(5)
        self.txt_log.clear()

        self.worker = SCReconcileWorker(
            mode="ALL_IN_ONE",
            sc_sources=sc_sources,
            bang_ke_file=bang_ke_path,
            invoices_dir=invoices_dir,
            excel_file=excel_path,
            out_dir=out_dir,
            use_ai=self.chk_ai.isChecked(),
            api_key=api_key,
            api_source=api_source,
            api_base_url=api_base_url,
            do_merge=self.chk_merge.isChecked(),
            do_correct=self.chk_correct.isChecked(),
            sc_excel_files=sc_excel_files
        )
        self.worker.progress_signal.connect(self.on_worker_progress)
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(self.on_worker_finished)
        self.worker.start()

    def on_worker_progress(self, val: int, msg: str):
        self.prog_bar.setValue(val)
        self.lbl_status.setText(msg)

    def on_worker_finished(self, success: bool, res: dict, err: str):
        self.btn_run.setEnabled(True)
        self.btn_run.setText("▶  Bắt đầu đối chiếu")

        if success:
            master_res = res.get("master_res") or {}
            self.last_report_path = res.get("report_path")
            self.last_corrected_path = res.get("corrected_path")
            self.last_out_dir = res.get("output_dir")

            self.btn_open_report.setEnabled(bool(self.last_report_path))
            self.btn_open_fixed.setEnabled(bool(self.last_corrected_path))

            # Tắt vẽ lại trong lúc đổ dữ liệu vào bảng -> hiển thị kết quả nhanh, không giật
            self.setUpdatesEnabled(False)
            try:
                self.populate_results_view(master_res)
            finally:
                self.setUpdatesEnabled(True)

            sx_lines = ""
            for sx in master_res.get('sc_excel_vs_pdf', []):
                if 'error' in sx:
                    sx_lines += f"• ⚠️ {sx['error']}\n"
                else:
                    s = sx['summary']
                    sx_lines += (f"• SC Excel ↔ PDF {sx['excel_info'].get('sc_number', '')}: "
                                 f"{'KHỚP HOÀN TOÀN' if s['all_ok'] else 'CÓ SAI LỆCH'} "
                                 f"(khớp {s['match']}/{s['total_excel']} tàu, lệch {s['mismatch']}, lưu ý {s['warn']}, "
                                 f"chỉ Excel {s['only_excel']}, chỉ PDF {s['only_pdf']})\n")
            if sx_lines:
                sx_lines = "\n" + sx_lines + "\n"
            if res.get("inv_warning"):
                sx_lines += f"\n⚠️ HÓA ĐƠN VAT: {res['inv_warning']}\n"

            QMessageBox.information(
                self, "Hoàn tất đối chiếu",
                f"Đã hoàn thành đối chiếu và xuất báo cáo thành công!\n\n"
                f"• Báo cáo Excel (4 Sheet): {os.path.basename(self.last_report_path or '')}\n"
                f"  1. Bảng Đối Chiếu Sai Khác (XNNL ↔ SC Gốc)\n"
                f"  2. Đối Chiếu Bảng Kê (HĐ VAT Vàng & SC Gốc Xanh)\n"
                f"  3. Tàu Đã Gộp Lượng\n"
                f"  4. Toàn Bộ SC Gốc (Cảng cá)\n"
                f"{sx_lines}\n"
                f"Bạn có thể bấm '📊 Mở Báo Cáo Excel' hoặc xem trực tiếp trên bảng bên dưới."
            )
        else:
            QMessageBox.critical(self, "Lỗi đối chiếu", f"Quá trình đối chiếu phát sinh lỗi:\n{err}")

    def populate_results_view(self, master_res: dict):
        bk_records = master_res.get('bang_ke_records', [])
        invoices_repo = master_res.get('invoices_repo', {})
        sc_repo = master_res.get('sc_repo', {})
        all_sc_records = master_res.get('all_sc_records', [])
        bk_vs_inv = master_res.get('bk_vs_invoices', {})
        bk_vs_sc = master_res.get('bk_vs_sc', {})
        xnnl_vs_sc = master_res.get('xnnl_vs_sc', {})

        # ----------------------------------------------------
        # 1. TAB 1: ĐỐI CHIẾU BẢNG KÊ (PHẦN TÔ VÀNG HĐ VAT & PHẦN TÔ XANH SC GỐC)
        # ----------------------------------------------------
        excel_size_totals = {}
        excel_size_counts = {}
        for r in bk_records:
            hd_no = str(r.get('hd_no', '')).lstrip("0") or "0"
            sz = normalize_fish_size(r.get('spec', ''))
            k = (hd_no, r.get('hd_date', ''), r.get('supplier', ''), sz)
            excel_size_totals[k] = excel_size_totals.get(k, 0.0) + float(r.get('qty', 0.0))
            excel_size_counts[k] = excel_size_counts.get(k, 0) + 1

        sc_matched_map = {}
        for rec in bk_vs_sc.get('recons', []):
            k_sc = (normalize_sc_key(rec.get('sc_no', '')), clean_vessel_key(rec.get('vessel_id', '')))
            sc_matched_map[k_sc] = rec

        sc_vessel_lookup = {}
        seen_sc_v = set()
        for sc_k, sc_bundle in (sc_repo or {}).items():
            sc_num_real = sc_bundle.get('sc_info', {}).get('sc_number', sc_k)
            sck = normalize_sc_key(sc_num_real)
            for v_rec in sc_bundle.get('records', []):
                vk = clean_vessel_key(v_rec.get('vessel_id', ''))
                dedup_k = (sck, vk, v_rec.get('landing_date', ''), v_rec.get('req_catch_kg', 0))
                if dedup_k in seen_sc_v:
                    continue
                seen_sc_v.add(dedup_k)
                if vk not in sc_vessel_lookup:
                    sc_vessel_lookup[vk] = {
                        'sc_number': sc_num_real,
                        'vessel_id': v_rec.get('vessel_id', ''),
                        'owner': v_rec.get('owner', ''),
                        'req_catch_kg': float(v_rec.get('req_catch_kg', 0.0)),
                    }
                else:
                    sc_vessel_lookup[vk]['req_catch_kg'] += float(v_rec.get('req_catch_kg', 0.0))

        self.tbl_bk_audit.setRowCount(len(bk_records))
        bk_perfect_cnt = 0
        bk_issue_cnt = 0

        bg_yellow = QColor("#FFF9E6")
        bg_green = QColor("#EBF5E6")
        bg_err = QColor("#FEE2E2")
        bg_warn = QColor("#FEF9C3")
        bg_ok = QColor("#DCFCE7")

        for r_i, r in enumerate(bk_records):
            row_notes = []
            row_has_err = False
            row_has_warn = False

            hd_no = str(r.get('hd_no', '')).lstrip("0") or "0"
            hd_date = str(r.get('hd_date', '')).strip()
            supplier_bk = str(r.get('supplier', '')).strip()
            address_bk = str(r.get('address', '')).strip()
            spec_bk = str(r.get('spec', '')).strip()
            size_key = normalize_fish_size(spec_bk)

            ex_qty = float(r.get('qty', 0.0))
            ex_price = float(r.get('price', 0.0))
            ex_amt = ex_qty * ex_price

            k_sz = (hd_no, hd_date, supplier_bk, size_key)
            ex_size_sum = excel_size_totals.get(k_sz, ex_qty)
            ex_size_cnt = excel_size_counts.get(k_sz, 1)

            inv = find_invoice_in_repo(invoices_repo, hd_no, supplier_hint=supplier_bk, date_hint=hd_date)
            matched_inv_item = None
            if inv:
                for it in inv.get('items', []):
                    if normalize_fish_size(it.get('item_name', '')) == size_key:
                        matched_inv_item = it
                        break

            inv_qty = float(matched_inv_item['qty']) if matched_inv_item else 0.0
            inv_price = float(matched_inv_item['price']) if matched_inv_item else 0.0
            inv_amt = float(matched_inv_item['amount']) if matched_inv_item else 0.0
            inv_seller = inv.get('seller_name', '-') if inv else 'Không tìm thấy HĐ'
            inv_address = inv.get('seller_address', '-') if inv else '-'
            inv_no_str = inv.get('so_hd', '-') if inv else '-'
            inv_date_str = inv.get('ngay_hd', '-') if inv else '-'

            price_ok = (abs(ex_price - inv_price) < 1.0) if (inv and matched_inv_item) else False
            qty_ok = (ex_size_sum <= inv_qty + 0.1) if (inv and matched_inv_item) else False
            date_ok = (hd_date.replace('-', '/') == inv_date_str.replace('-', '/')) if inv else False

            if not inv:
                row_has_err = True
                row_notes.append(f"Thiếu HĐ {hd_no}")
            else:
                if not price_ok:
                    row_has_err = True
                    row_notes.append(f"Lệch giá ({ex_price:,.0f} != {inv_price:,.0f})")
                if not qty_ok:
                    row_has_err = True
                    row_notes.append(f"Vượt lượng size ({ex_size_sum:,.0f} > {inv_qty:,.0f})")
                if not date_ok:
                    row_has_warn = True
                    row_notes.append(f"Lệch ngày HĐ")

            # Cột 0..4: Thông tin cơ bản
            self.tbl_bk_audit.setItem(r_i, 0, QTableWidgetItem(str(r.get('stt', r_i + 1))))
            self.tbl_bk_audit.setItem(r_i, 1, QTableWidgetItem(str(r.get('material', 'Cá ngừ'))))
            self.tbl_bk_audit.setItem(r_i, 2, QTableWidgetItem(spec_bk))
            self.tbl_bk_audit.setItem(r_i, 3, QTableWidgetItem(str(r.get('hs', '030342'))))
            self.tbl_bk_audit.setItem(r_i, 4, QTableWidgetItem(str(r.get('origin', 'Việt Nam'))))

            # Cột 5..11: Phần Tô Vàng (Excel vs HĐ VAT)
            qty_txt = f"Excel: {ex_qty:,.1f} (Tổng: {ex_size_sum:,.1f})\nHĐ gốc: {inv_qty:,.1f}" if ex_size_cnt > 1 else f"Excel: {ex_qty:,.1f}\nHĐ gốc: {inv_qty:,.1f}"
            yellow_cells = [
                (5, qty_txt, qty_ok),
                (6, f"Excel: {ex_price:,.0f}\nHĐ gốc: {inv_price:,.0f}", price_ok),
                (7, f"Excel: {ex_amt:,.0f}\nHĐ gốc: {inv_amt:,.0f}", True),
                (8, f"Excel: {supplier_bk}\nHĐ gốc: {inv_seller}", bool(inv)),
                (9, f"Excel: {address_bk}\nHĐ gốc: {inv_address}", bool(inv)),
                (10, f"Excel: {hd_no}\nHĐ gốc: {inv_no_str}", bool(inv)),
                (11, f"Excel: {hd_date}\nHĐ gốc: {inv_date_str}", date_ok),
            ]
            for c_idx, txt, is_ok in yellow_cells:
                it_y = QTableWidgetItem(txt)
                it_y.setBackground(bg_yellow if is_ok else bg_err)
                self.tbl_bk_audit.setItem(r_i, c_idx, it_y)

            # Cột 12..14: Phần Tô Xanh (Excel vs SC Gốc PDF)
            sc_no_bk = str(r.get('sc_no', '')).strip()
            vessel_bk = str(r.get('vessel_id', '')).strip().upper()
            owner_bk = str(r.get('owner', '')).strip()

            vk_clean = clean_vessel_key(vessel_bk)
            sck_clean = normalize_sc_key(sc_no_bk)
            sc_rec = sc_matched_map.get((sck_clean, vk_clean))
            sc_v_info = sc_vessel_lookup.get(vk_clean)

            if sc_v_info:
                sc_no_goc = sc_v_info.get('sc_number', sc_no_bk)
                vessel_goc = sc_v_info.get('vessel_id', vessel_bk)
                owner_goc = sc_v_info.get('owner', '')
                sc_kg_goc = sc_v_info.get('req_catch_kg', 0.0)
            elif sc_rec:
                sc_no_goc = sc_rec.get('sc_no', sc_no_bk)
                vessel_goc = sc_rec.get('vessel_id', vessel_bk)
                owner_goc = sc_rec.get('owner_sc', '')
                sc_kg_goc = sc_rec.get('sc_weight', 0.0)
            else:
                sc_no_goc = "Không tìm thấy"
                vessel_goc = "Không tìm thấy"
                owner_goc = "Không tìm thấy"
                sc_kg_goc = 0.0

            sc_found = (sc_no_goc != "Không tìm thấy")
            sc_no_match = (normalize_sc_key(sc_no_bk) == normalize_sc_key(sc_no_goc)) if sc_found else False
            vessel_match = (clean_vessel_key(vessel_bk) == clean_vessel_key(vessel_goc)) if sc_found else False
            owner_exact = (owner_bk.lower() == owner_goc.lower()) if sc_found else False

            if not sc_found:
                row_has_err = True
                row_notes.append(f"Tàu {vessel_bk} ngoài SC")
            else:
                if not sc_no_match:
                    row_has_err = True
                    row_notes.append("Lệch số SC")
                if not owner_exact:
                    row_has_warn = True
                    row_notes.append(f"Chủ tàu: {owner_bk} / {owner_goc}")

            green_cells = [
                (12, f"Excel: {sc_no_bk}\nSC gốc: {sc_no_goc}", sc_no_match),
                (13, f"Excel: {vessel_bk}\nSC gốc: {vessel_goc} ({sc_kg_goc:,.0f}kg)" if sc_found else f"Excel: {vessel_bk}\nSC gốc: Không tìm thấy", vessel_match),
                (14, f"Excel: {owner_bk}\nSC gốc: {owner_goc}", owner_exact),
            ]
            for c_idx, txt, is_ok in green_cells:
                it_g = QTableWidgetItem(txt)
                if not sc_found:
                    it_g.setBackground(bg_err)
                elif not is_ok:
                    it_g.setBackground(bg_warn if c_idx == 14 else bg_err)
                else:
                    it_g.setBackground(bg_green)
                self.tbl_bk_audit.setItem(r_i, c_idx, it_g)

            # Cột 15: Kết luận
            it_eval = QTableWidgetItem()
            if row_has_err:
                bk_issue_cnt += 1
                it_eval.setText("🔴 Sai lệch: " + "; ".join(row_notes))
                it_eval.setBackground(bg_err)
            elif row_has_warn:
                bk_issue_cnt += 1
                it_eval.setText("🟡 Lưu ý: " + "; ".join(row_notes))
                it_eval.setBackground(bg_warn)
            else:
                bk_perfect_cnt += 1
                it_eval.setText(f"🟢 Khớp 100% (Giá {ex_price:,.0f}đ; Tổng size {ex_size_sum:,.0f}/{inv_qty:,.0f}kg)")
                it_eval.setBackground(bg_ok)
            self.tbl_bk_audit.setItem(r_i, 15, it_eval)

        # ----------------------------------------------------
        # 2. TAB 2: BẢNG ĐỐI CHIẾU SAI KHÁC (XNNL ↔ SC GỐC CẢNG CÁ)
        # ----------------------------------------------------
        x_recons = xnnl_vs_sc.get('recons', [])
        self.tbl_xnnl.setRowCount(len(x_recons))
        xnnl_match_cnt = 0
        xnnl_issue_cnt = 0

        for r_i, xr in enumerate(x_recons):
            ex = xr.get('excel_data') or {}
            sc = xr.get('sc_data') or {}
            st = xr.get('status', 'MATCH')

            self.tbl_xnnl.setItem(r_i, 0, QTableWidgetItem(str(r_i + 1)))
            self.tbl_xnnl.setItem(r_i, 1, QTableWidgetItem(xr.get('vessel_id', '')))
            self.tbl_xnnl.setItem(r_i, 2, QTableWidgetItem(xr.get('sc_number', '')))

            item_xst = QTableWidgetItem()
            if st == 'MATCH':
                xnnl_match_cnt += 1
                item_xst.setText("🟢 Khớp 100%")
                item_xst.setBackground(bg_ok)
            elif st == 'WARNING':
                xnnl_issue_cnt += 1
                item_xst.setText("🟡 Cảnh báo")
                item_xst.setBackground(bg_warn)
            else:
                xnnl_issue_cnt += 1
                item_xst.setText("🔴 Sai lệch")
                item_xst.setBackground(bg_err)
            self.tbl_xnnl.setItem(r_i, 3, item_xst)

            merge_txt = f"Đã gộp {xr.get('merged_count', 2)} dòng" if xr.get('is_merged') else "1 dòng"
            self.tbl_xnnl.setItem(r_i, 4, QTableWidgetItem(merge_txt))

            self.tbl_xnnl.setItem(r_i, 5, QTableWidgetItem(f"Excel: {ex.get('owner', '')}\nSC gốc: {sc.get('owner', '-')}"))
            self.tbl_xnnl.setItem(r_i, 6, QTableWidgetItem(f"Excel: {ex.get('licence_no', '')}\nSC gốc: {sc.get('licence_no', '-')}"))
            self.tbl_xnnl.setItem(r_i, 7, QTableWidgetItem(f"Excel: {ex.get('licence_exp', '')}\nSC: {sc.get('licence_exp', '-')}"))
            self.tbl_xnnl.setItem(r_i, 8, QTableWidgetItem(f"Excel: {ex.get('catch_period', '')}\nSC: {sc.get('catch_period', '-')}"))
            self.tbl_xnnl.setItem(r_i, 9, QTableWidgetItem(f"Excel: {ex.get('landing_date', '')}\nSC: {sc.get('landing_date', '-')}"))

            ex_kg = float(ex.get('catch_kg', 0.0))
            sc_kg = float(sc.get('req_catch_kg') if sc.get('req_catch_kg') is not None else sc.get('total_catch_kg', 0.0))
            delta = ex_kg - sc_kg
            delta_str = f" ({delta:+.1f} kg)" if abs(delta) > 0.1 else " (Khớp)"
            it_kg = QTableWidgetItem(f"Excel: {ex_kg:,.1f} kg\nSC: {sc_kg:,.1f} kg{delta_str}")
            if abs(delta) > 0.1:
                it_kg.setBackground(bg_err)
            self.tbl_xnnl.setItem(r_i, 10, it_kg)

            act_list = xr.get('action_needed', [])
            act_txt = "; ".join(act_list) if act_list else "Dữ liệu hợp lệ, không cần chỉnh sửa."
            self.tbl_xnnl.setItem(r_i, 11, QTableWidgetItem(act_txt))

        # ----------------------------------------------------
        # 3. TAB 3: TOÀN BỘ TÀU TRÊN SC GỐC (CÓ DẤU TIẾNG VIỆT)
        # ----------------------------------------------------
        self.tbl_all_sc.setRowCount(len(all_sc_records))
        for r_i, sr in enumerate(all_sc_records):
            self.tbl_all_sc.setItem(r_i, 0, QTableWidgetItem(str(r_i + 1)))
            self.tbl_all_sc.setItem(r_i, 1, QTableWidgetItem(str(sr.get('sc_number', ''))))
            self.tbl_all_sc.setItem(r_i, 2, QTableWidgetItem(str(sr.get('vessel_id', ''))))
            self.tbl_all_sc.setItem(r_i, 3, QTableWidgetItem(str(sr.get('owner', ''))))
            self.tbl_all_sc.setItem(r_i, 4, QTableWidgetItem(str(sr.get('licence_no', ''))))
            self.tbl_all_sc.setItem(r_i, 5, QTableWidgetItem(str(sr.get('licence_exp', ''))))
            self.tbl_all_sc.setItem(r_i, 6, QTableWidgetItem(str(sr.get('catch_period', ''))))
            self.tbl_all_sc.setItem(r_i, 7, QTableWidgetItem(str(sr.get('landing_date', ''))))
            req_kg = float(sr.get('req_catch_kg') or sr.get('total_catch_kg') or 0.0)
            self.tbl_all_sc.setItem(r_i, 8, QTableWidgetItem(f"{req_kg:,.1f}"))

        # TAB: SC Excel <-> SC scan PDF
        self.populate_scx_table(master_res.get('sc_excel_vs_pdf', []))

        # Cập nhật KPI Strip
        inv_cnt = len(bk_vs_inv.get('recons', [])) or len(invoices_repo)
        sc_cnt = len(all_sc_records) or len(sc_vessel_lookup)
        self.lbl_kpi_bk.setText(str(len(bk_records)))
        self.lbl_kpi_inv.setText(str(inv_cnt))
        self.lbl_kpi_sc.setText(str(sc_cnt))
        self.lbl_kpi_match.setText(str(bk_perfect_cnt if bk_records else xnnl_match_cnt))
        self.lbl_kpi_diff.setText(str(bk_issue_cnt if bk_records else xnnl_issue_cnt))

        # Tự động chuyển sang Tab phù hợp nhất
        if bk_records:
            self.tabs.setCurrentIndex(0)
        elif x_recons:
            self.tabs.setCurrentIndex(1)

    def populate_scx_table(self, scx_results: list):
        from sc_core.sc_excel_vs_pdf import RULE_CHECKS, rule_display, _to_float, _sc_label
        rule_keys = {k for k, *_ in RULE_CHECKS}
        ok_list = [r for r in (scx_results or []) if 'rows' in r]
        errs = [f"❌ {r['error']}" for r in (scx_results or []) if 'error' in r]
        rows = []  # (nhãn SC, dòng kết quả)
        for res in ok_list:
            sc_lbl = _sc_label(res)
            rows.extend((sc_lbl, row) for row in res['rows'])
        st_col = {"MATCH": "#dcfce7", "WARN": "#fef9c3", "MISMATCH": "#fee2e2",
                  "ONLY_EXCEL": "#fed7aa", "ONLY_PDF": "#fed7aa"}
        st_txt = {"MATCH": "Khớp", "WARN": "Lưu ý (dấu)", "MISMATCH": "LỆCH",
                  "ONLY_EXCEL": "Chỉ có trong Excel", "ONLY_PDF": "Chỉ có trong PDF"}

        def disp(key, v):
            if v is None or v == "":
                return "-"
            if key in ("req_catch_kg", "total_catch_kg"):
                f = _to_float(v)
                return f"{f:,.1f}" if f is not None else str(v)
            return str(v).replace("\n", " ")

        self.tbl_scx.setRowCount(len(rows))
        for r_i, (sc_lbl, row) in enumerate(rows):
            ex, pf = row.get('excel'), row.get('pdf')
            self.tbl_scx.setItem(r_i, 0, QTableWidgetItem(str(r_i + 1)))
            self.tbl_scx.setItem(r_i, 1, QTableWidgetItem(str(row.get('vessel_id', ''))))
            self.tbl_scx.setItem(r_i, 2, QTableWidgetItem(str(sc_lbl)))
            it = QTableWidgetItem(st_txt.get(row['status'], row['status']))
            it.setBackground(QColor(st_col.get(row['status'], "#ffffff")))
            self.tbl_scx.setItem(r_i, 3, it)
            for c_i, (key, _, _) in enumerate(SCX_COLUMNS, 4):
                f = row.get('fields', {}).get(key)
                if key in rule_keys:
                    vx, vp = rule_display(key, ex), rule_display(key, pf)
                else:
                    vx, vp = disp(key, ex.get(key) if ex else None), disp(key, pf.get(key) if pf else None)
                cell = QTableWidgetItem(f"Excel: {vx}\nSC gốc: {vp}")
                st = f['status'] if f else (row['status'] if row['status'] in ("ONLY_EXCEL", "ONLY_PDF") else None)
                if st:
                    cell.setBackground(QColor(st_col.get(st, "#ffffff")))
                self.tbl_scx.setItem(r_i, c_i, cell)
            self.tbl_scx.setItem(r_i, len(SCX_COLUMNS) + 4, QTableWidgetItem(row.get('note', '')))

        if ok_list:
            parts = []
            n_all = len(scx_results)
            if n_all > 1:
                n_ok = sum(1 for r in ok_list if r['summary']['all_ok'])
                parts.append(f"📗 {n_all} file SC Excel: khớp hoàn toàn {n_ok}, có sai lệch {len(ok_list) - n_ok}, "
                             f"không đối chiếu được {len(errs)}")
            for res in ok_list:
                s = res['summary']
                pdf_name = res['pdf_info'].get('file_name') or os.path.basename(res.get('pdf_file', '') or '')
                parts.append(f"{'✅' if s['all_ok'] else '⚠️'} {os.path.basename(res.get('file', ''))} ↔ {pdf_name} "
                             f"[ghép theo: {res.get('match_method', '-')}] — SC {res['excel_info'].get('sc_number', '')}: "
                             f"{'KHỚP HOÀN TOÀN' if s['all_ok'] else 'CÓ SAI LỆCH'} — khớp {s['match']}/{s['total_excel']} tàu, "
                             f"lệch {s['mismatch']}, lưu ý {s['warn']}, chỉ Excel {s['only_excel']}, chỉ PDF {s['only_pdf']}")
                for h in res['header_checks']:
                    if h['status'] != 'MATCH':
                        parts.append(f"   ⚠ {h['label']}: Excel={h['excel']} | PDF={h['pdf']} ({h['note']})")
            self.lbl_scx_summary.setText("\n".join(parts + errs))
        elif errs:
            self.lbl_scx_summary.setText("\n".join(errs))
        else:
            self.lbl_scx_summary.setText("Chưa chọn file SC Excel nên không có đối chiếu SC Excel ↔ SC scan PDF.")

    def open_report_file(self):
        if self.last_report_path and os.path.exists(self.last_report_path):
            os.startfile(self.last_report_path)

    def open_fixed_file(self):
        if self.last_corrected_path and os.path.exists(self.last_corrected_path):
            os.startfile(self.last_corrected_path)

    def open_output_folder(self):
        d = self.last_out_dir or os.path.abspath("KetQua_DoiChieu")
        if os.path.exists(d):
            os.startfile(d)


# ========================================================
class UnifiedCopilotWidget(QWidget):
    def __init__(self, parent_app):
        super().__init__()
        self.parent_app = parent_app
        self.chat_worker: Optional[UnifiedCopilotWorker] = None
        self.chat_history: List[dict] = []

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(12)

        # Tiêu đề trang
        badge = QLabel("⚡ Gemini 3.8 Flash")
        badge.setObjectName("Badge")
        btn_clear = ui.button("🗑 Xóa lịch sử", "ghost")
        btn_clear.clicked.connect(self.clear_chat)
        layout.addLayout(ui.page_header(
            "Trợ lý AI Copilot",
            "Hỏi đáp nghiệp vụ khai báo C/O eCoSys và hồ sơ IUU / SC cảng cá.",
            [badge, btn_clear]))

        # Câu hỏi gợi ý nhanh theo 2 nhóm nghiệp vụ
        pills_box = ui.card()
        pills_l = QGridLayout(pills_box)
        pills_l.setContentsMargins(14, 12, 14, 12)
        pills_l.setHorizontalSpacing(8)
        pills_l.setVerticalSpacing(8)

        groups = [
            ("C/O eCoSys", [
                ("Tiêu chí WO, CTC, RVC 40%", "Hướng dẫn phân biệt và xác định tiêu chí xuất xứ WO, CTC (CTH/CTSH), RVC 40% và De Minimis khi khai báo C/O eCoSys?"),
                ("Vận chuyển trực tiếp & nước thứ 3", "Quy định vận chuyển trực tiếp và chuyển tải qua nước thứ 3 (Singapore, Hong Kong) để không làm mất xuất xứ C/O?"),
                ("Khắc phục lỗi Token eCoSys", "Cách sửa lỗi không nhận Chữ ký số USB Token MOITSignPlugin khi ký nộp hồ sơ C/O trên ecosys.gov.vn?"),
            ]),
            ("SC & IUU thủy sản", [
                ("Quy định Giấy SC & hồ sơ IUU", "Quy định kiểm tra tính hợp pháp của Giấy xác nhận SC gốc Cảng cá theo Thông tư 21/2018/TT-BNNPTNT để làm hồ sơ IUU xuất khẩu?"),
                ("Xử lý lệch Chủ tàu / GPKTTS", "Cách xử lý và giải trình khi tên Chủ tàu hoặc số GPKTTS trên Excel sản xuất không khớp với bản scan Giấy SC gốc của Cảng cá?"),
                ("Quy tắc gộp lượng tàu cá", "Quy tắc gộp lượng tàu cá khi cùng 1 tàu cập cảng/lên cá cùng ngày trong bảng kê Phụ lục 02a được quy định thế nào?"),
            ]),
        ]
        for r_i, (cap, items) in enumerate(groups):
            lbl = QLabel(cap.upper())
            lbl.setObjectName("Caption")
            lbl.setMinimumWidth(130)
            pills_l.addWidget(lbl, r_i, 0)
            for c_i, (txt, q) in enumerate(items, 1):
                b = ui.button(txt, "chip", tooltip=q)
                b.clicked.connect(lambda _=False, q=q: self.ask_quick(q))
                pills_l.addWidget(b, r_i, c_i)
            pills_l.setColumnStretch(len(items) + 1, 1)
        layout.addWidget(pills_box)

        # Khung hiển thị tin nhắn
        self.txt_chat = QTextBrowser()
        self.txt_chat.setOpenExternalLinks(True)
        self.txt_chat.setStyleSheet(f"QTextBrowser {{ border: 1px solid {ui.C['border']}; border-radius: 12px; "
                                    f"padding: 14px; font-size: 13px; }}")
        self.txt_chat.setHtml("""
            <div style="color: #475569; font-style: italic; padding: 10px;">
                👋 <b>Xin chào!</b> Tôi là Trợ lý AI Copilot chuyên gia về <b>Khai báo C/O eCoSys (Bộ Công Thương)</b> và <b>Hồ sơ IUU / Xác nhận nguyên liệu thủy sản (SC Cảng cá)</b>.<br/>
                Bạn có thể bấm các nút câu hỏi nhanh ở trên hoặc nhập câu hỏi nghiệp vụ vào ô bên dưới để tôi hỗ trợ ngay lập tức!
            </div>
        """)
        layout.addWidget(self.txt_chat, stretch=1)

        # Khung nhập câu hỏi
        input_bar = QHBoxLayout()
        input_bar.setSpacing(8)
        self.input_question = QLineEdit()
        self.input_question.setPlaceholderText("Nhập câu hỏi nghiệp vụ C/O hoặc đối chiếu SC — Enter để gửi...")
        self.input_question.setStyleSheet("QLineEdit { padding: 10px 14px; border-radius: 10px; font-size: 13px; }")
        self.input_question.returnPressed.connect(self.send_message)
        input_bar.addWidget(self.input_question, stretch=1)

        self.btn_send = ui.button("Gửi  ➤", "primary", "lg")
        self.btn_send.setMinimumWidth(120)
        self.btn_send.clicked.connect(self.send_message)
        input_bar.addWidget(self.btn_send)

        layout.addLayout(input_bar)

    def ask_quick(self, q: str):
        self.input_question.setText(q)
        self.send_message()

    def send_message(self):
        text = self.input_question.text().strip()
        if not text:
            return

        cfg = self.parent_app.shared_config
        api_key = cfg.get("api_key", "")
        api_source = cfg.get("api_source", "official")
        api_base_url = cfg.get("api_base_url", "https://api.apiz.vn/v1")

        if not api_key:
            QMessageBox.warning(self, "Chưa có API Key", "Vui lòng nhập API Key tại phân hệ 'Cài đặt API' trước khi đặt câu hỏi cho AI!")
            return

        self.append_user_message(text)
        self._pending_question = text
        self.input_question.clear()
        self.btn_send.setEnabled(False)
        self.btn_send.setText("⏳ Đang trả lời...")

        m_name = cfg.get("model_name", "gemini-3.8-flash" if api_source == "apiz" else "gemini-3.8-flash")
        self.chat_worker = UnifiedCopilotWorker(
            api_key=api_key,
            question=text,
            history=self.chat_history,
            api_source=api_source,
            api_base_url=api_base_url,
            model_name=m_name
        )
        self.chat_worker.reply_signal.connect(self.on_reply)
        self.chat_worker.start()

    def on_reply(self, answer: str, error: str):
        self.btn_send.setEnabled(True)
        self.btn_send.setText("Gửi  ➤")
        if answer:
            self.append_ai_message(answer)
            self.chat_history.append({"role": "user", "text": getattr(self, "_pending_question", "")})
            self.chat_history.append({"role": "assistant", "text": answer})
        else:
            self.append_ai_message(f"❌ <b>Có lỗi xảy ra:</b> {error}")

    def append_user_message(self, text: str):
        bubble = f"""
        <div style="margin: 8px 0; text-align: right;">
            <div style="display: inline-block; background: #e0f2fe; color: #0369a1; padding: 8px 14px; border-radius: 12px; font-weight: 500; max-width: 80%; text-align: left;">
                👤 <b>Bạn:</b> {text}
            </div>
        </div>
        """
        self.txt_chat.append(bubble)

    def append_ai_message(self, text: str):
        # Format markdown simple
        fmt_text = text.replace("\n", "<br/>")
        bubble = f"""
        <div style="margin: 8px 0; text-align: left;">
            <div style="display: inline-block; background: #f8fafc; border: 1px solid #cbd5e1; color: #0f172a; padding: 10px 16px; border-radius: 12px; max-width: 85%;">
                🤖 <b>Trợ lý AI Copilot:</b><br/>
                {fmt_text}
            </div>
        </div>
        """
        self.txt_chat.append(bubble)

    def clear_chat(self):
        self.chat_history.clear()
        self.txt_chat.clear()
        self.txt_chat.setHtml("""
            <div style="color: #475569; font-style: italic; padding: 10px;">
                Đã xóa lịch sử trò chuyện. Sẵn sàng nhận câu hỏi mới!
            </div>
        """)


# ========================================================
# 5. WIDGET CÀI ĐẶT API DÙNG CHUNG
# ========================================================
class UnifiedSettingsWidget(QWidget):
    def __init__(self, parent_app):
        super().__init__()
        self.parent_app = parent_app
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(14)

        layout.addLayout(ui.page_header(
            "Cài đặt API dùng chung",
            "Cấu hình API Key 1 lần — cả 2 phân hệ (Khai báo C/O eCoSys và Đối chiếu SC) đều dùng chung."))

        card = ui.card()
        card.setMaximumWidth(860)
        outer = QVBoxLayout(card)
        outer.setContentsMargins(22, 18, 22, 18)
        outer.setSpacing(14)
        sec = QLabel("Kết nối AI")
        sec.setObjectName("SectionTitle")
        outer.addWidget(sec)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(1, 1)

        def lbl(t):
            w = QLabel(t)
            w.setObjectName("Muted")
            w.setMinimumWidth(110)
            return w

        grid.addWidget(lbl("Nguồn API"), 0, 0)
        self.combo_source = QComboBox()
        self.combo_source.addItem("APIZ Vietnam Gateway (Khuyên dùng)", "apiz")
        self.combo_source.addItem("Google Gemini Official", "official")
        self.combo_source.currentIndexChanged.connect(self.on_source_changed)
        grid.addWidget(self.combo_source, 0, 1)

        grid.addWidget(lbl("API Key"), 1, 0)
        key_layout = QHBoxLayout()
        key_layout.setSpacing(6)
        self.entry_key = QLineEdit()
        self.entry_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.entry_key.setPlaceholderText("Dán API Key (sk-... cho APIZ hoặc AIzaSy... cho Google)")
        self.entry_key.textChanged.connect(self.on_key_typed)
        key_layout.addWidget(self.entry_key)
        btn_eye = ui.button("👁", "ghost", tooltip="Hiện / ẩn API Key")
        btn_eye.setFixedWidth(40)
        btn_eye.clicked.connect(self.toggle_eye)
        key_layout.addWidget(btn_eye)
        grid.addLayout(key_layout, 1, 1)

        self.lbl_base = lbl("Base URL")
        self.entry_base = QLineEdit("https://api.apiz.vn/v1")
        grid.addWidget(self.lbl_base, 2, 0)
        grid.addWidget(self.entry_base, 2, 1)

        grid.addWidget(lbl("Mô hình AI"), 3, 0)
        self.entry_model = QLineEdit("gemini-3.8-flash (Cố định chuẩn mới 2026)")
        self.entry_model.setEnabled(False)
        grid.addWidget(self.entry_model, 3, 1)
        outer.addLayout(grid)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_save = ui.button("💾  Lưu cấu hình", "primary", "lg")
        btn_save.clicked.connect(self.save_config)
        btn_row.addWidget(btn_save)
        outer.addLayout(btn_row)

        layout.addWidget(card)
        layout.addStretch()

        self.load_from_shared()

    def toggle_eye(self):
        if self.entry_key.echoMode() == QLineEdit.EchoMode.Password:
            self.entry_key.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.entry_key.setEchoMode(QLineEdit.EchoMode.Password)

    def on_source_changed(self):
        is_apiz = self.combo_source.currentData() == "apiz"
        self.lbl_base.setVisible(is_apiz)
        self.entry_base.setVisible(is_apiz)
        if is_apiz:
            if not self.entry_base.text().strip():
                self.entry_base.setText("https://api.apiz.vn/v1")
            self.entry_model.setText("gemini-3.8-flash (Cổng APIZ Vietnam)")
        else:
            self.entry_base.setText("")
            self.entry_model.setText("gemini-3.8-flash (Google Official Flagship)")

    def on_key_typed(self, text: str):
        t = text.strip()
        if t.startswith("AIzaSy"):
            idx = self.combo_source.findData("official")
            if idx >= 0:
                self.combo_source.setCurrentIndex(idx)
            self.entry_base.setText("")
            self.entry_model.setText("gemini-3.8-flash (Google Official Flagship)")
        elif t.startswith("sk-") and self.combo_source.currentData() != "apiz":
            idx = self.combo_source.findData("apiz")
            if idx >= 0:
                self.combo_source.setCurrentIndex(idx)
            if not self.entry_base.text().strip():
                self.entry_base.setText("https://api.apiz.vn/v1")
            self.entry_model.setText("gemini-3.8-flash (Cổng APIZ Vietnam)")

    def load_from_shared(self):
        cfg = self.parent_app.shared_config
        key = cfg.get("api_key", "")
        self.entry_key.setText(key)
        src = cfg.get("api_source", "official")
        idx = self.combo_source.findData(src)
        if idx >= 0:
            self.combo_source.setCurrentIndex(idx)
        b_url = cfg.get("api_base_url", "https://api.apiz.vn/v1")
        self.entry_base.setText(b_url)
        self.on_source_changed()

    def save_config(self):
        src = self.combo_source.currentData()
        m_name = "gemini-3.8-flash" if src == "apiz" else "gemini-3.8-flash"
        b_url = self.entry_base.text().strip() if src == "apiz" else ""
        cfg = {
            "api_key": self.entry_key.text().strip(),
            "api_source": src,
            "api_base_url": b_url,
            "model_name": m_name
        }
        self.parent_app.shared_config = cfg
        save_settings(cfg)

        # Sync to sc_core
        try:
            ai_c = load_ai_config()
            ai_c["provider"] = "apiz" if src == "apiz" else "gemini"
            if src == "apiz":
                ai_c["apiz_api_key"] = cfg["api_key"]
                ai_c["apiz_base_url"] = b_url or "https://api.apiz.vn/v1"
                ai_c["apiz_model"] = "gemini-3.8-flash"
            else:
                ai_c["gemini_api_key"] = cfg["api_key"]
                ai_c["gemini_model"] = "gemini-3.8-flash"
            save_ai_config(ai_c)
        except Exception as e:
            print(f"Sync to sc_core config failed: {e}")

        # Sync to C/O Window inputs
        if hasattr(self.parent_app, 'co_app_instance'):
            self.parent_app.co_app_instance.input_api_key.setText(cfg["api_key"])
            c_idx = self.parent_app.co_app_instance.combo_api_source.findData(cfg["api_source"])
            if c_idx >= 0:
                self.parent_app.co_app_instance.combo_api_source.setCurrentIndex(c_idx)
            self.parent_app.co_app_instance.input_base_url.setText(cfg["api_base_url"])

        QMessageBox.information(self, "Đã lưu", "Đã lưu cấu hình AI thành công cho toàn bộ hệ thống!")


# ========================================================
# 6. CỬA SỔ CHÍNH: UNIFIED SUITE v3.0 (COLLAPSIBLE SIDEBAR)
# ========================================================
class UnifiedSuiteApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hệ Thống Quản Trị Xuất Nhập Khẩu & Thủy Sản Toàn Diện (eCoSys C/O & Đối Chiếu SC)")
        self.resize(1420, 890)
        self.setMinimumSize(1080, 700)

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Trạng thái Sidebar
        self.is_sidebar_collapsed = False
        self.sidebar_expanded_width = 248
        self.sidebar_collapsed_width = 66

        # Cấu hình dùng chung
        self.shared_config = load_settings()

        self.init_ui()

    def init_ui(self):
        # Bộ giao diện chung (nếu nơi khởi chạy chưa áp dụng)
        app = QApplication.instance()
        if app is not None and not app.styleSheet():
            apply_app_theme(app)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ========================================================
        # THANH ĐIỀU HƯỚNG BÊN TRÁI (THU GỌN / MỞ RỘNG MƯỢT)
        # ========================================================
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(self.sidebar_expanded_width)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(12, 16, 12, 14)
        self.sidebar_layout.setSpacing(4)

        hdr_bar = QHBoxLayout()
        hdr_bar.setContentsMargins(2, 0, 0, 0)
        hdr_bar.setSpacing(10)
        self.lbl_logo_icon = QLabel("🚢")
        self.lbl_logo_icon.setObjectName("SideLogo")
        self.lbl_logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr_bar.addWidget(self.lbl_logo_icon)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        self.lbl_logo_title = QLabel("XNK & Thủy sản")
        self.lbl_logo_title.setObjectName("SideTitle")
        title_col.addWidget(self.lbl_logo_title)
        self.lbl_logo_sub = QLabel("Hệ thống hợp nhất")
        self.lbl_logo_sub.setObjectName("SideSub")
        title_col.addWidget(self.lbl_logo_sub)
        hdr_bar.addLayout(title_col, stretch=1)

        self.btn_toggle_sidebar = QPushButton("☰")
        self.btn_toggle_sidebar.setObjectName("SideToggle")
        self.btn_toggle_sidebar.setToolTip("Thu gọn / Mở rộng menu (Ctrl + B)")
        self.btn_toggle_sidebar.setFixedSize(34, 34)
        self.btn_toggle_sidebar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_sidebar.clicked.connect(self.toggle_sidebar)
        hdr_bar.addWidget(self.btn_toggle_sidebar)
        self.sidebar_layout.addLayout(hdr_bar)
        self.sidebar_layout.addSpacing(18)

        self.lbl_side_section = QLabel("PHÂN HỆ")
        self.lbl_side_section.setObjectName("SideSection")
        self.sidebar_layout.addWidget(self.lbl_side_section)
        self.sidebar_layout.addSpacing(4)

        # Nút điều hướng: checkable + nhóm loại trừ -> đổi trang không phải dựng lại style (mượt hơn)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.btn_nav_co = self.create_nav_button("📋   Khai báo C/O eCoSys", "📋", "Khai báo C/O eCoSys (Bộ Công Thương) [Ctrl+1]", active=True)
        self.btn_nav_sc = self.create_nav_button("⚓   Đối chiếu SC Cảng cá", "⚓", "Đối chiếu SC Cảng cá & XNNL PMSX [Ctrl+2]")
        self.btn_nav_copilot = self.create_nav_button("🤖   Trợ lý AI Copilot", "🤖", "Trợ lý AI Copilot nghiệp vụ C/O & IUU thủy sản [Ctrl+3]")
        self.btn_nav_settings = self.create_nav_button("⚙   Cài đặt API", "⚙", "Cài đặt API Key Gemini & APIZ dùng chung [Ctrl+4]")
        for i, b in enumerate((self.btn_nav_co, self.btn_nav_sc, self.btn_nav_copilot, self.btn_nav_settings)):
            b.setCheckable(True)
            self.nav_group.addButton(b, i)
            b.clicked.connect(lambda _=False, i=i: self.switch_page(i))
            self.sidebar_layout.addWidget(b)

        self.sidebar_layout.addStretch()

        divider = QFrame()
        divider.setObjectName("SideDivider")
        self.sidebar_layout.addWidget(divider)
        self.sidebar_layout.addSpacing(6)

        self.btn_nav_guide = self.create_nav_button("📖   Hướng dẫn sử dụng", "📖", "Cẩm nang hướng dẫn sử dụng (F1)")
        self.btn_nav_guide.clicked.connect(self.show_user_guide_dialog)
        self.sidebar_layout.addWidget(self.btn_nav_guide)

        self.btn_nav_update = self.create_nav_button("🔄   Cập nhật phiên bản", "🔄", "Kiểm tra và cập nhật phiên bản mới qua GitHub")
        self.btn_nav_update.clicked.connect(self.show_github_update_dialog)
        self.sidebar_layout.addWidget(self.btn_nav_update)
        self.sidebar_layout.addSpacing(8)

        app_ver = "3.2.0"
        try:
            for _vp in (os.path.join(app_exec_dir, "version.json"),
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.json")):
                if os.path.exists(_vp):
                    with open(_vp, "r", encoding="utf-8") as _vf:
                        app_ver = json.load(_vf).get("version", app_ver)
                    break
        except Exception:
            pass
        self.lbl_version = QLabel(f"v{app_ver} • Gemini 3.8 Flash\n© Ngô Quốc Tiến • 0905387808")
        self.lbl_version.setObjectName("SideVersion")
        self.sidebar_layout.addWidget(self.lbl_version)

        main_layout.addWidget(self.sidebar)

        # ========================================================
        # KHU VỰC NỘI DUNG CHÍNH (CHUYỂN TRANG CÓ HIỆU ỨNG MỜ DẦN)
        # ========================================================
        self.stack = ui.FadeStackedWidget()
        main_layout.addWidget(self.stack, stretch=1)

        # Trang 0: Khai báo C/O eCoSys (tái sử dụng COExtractorApp)
        self.co_app_instance = COExtractorApp()
        self.page_co = self.co_app_instance.centralWidget()
        self.page_co.layout().setContentsMargins(16, 14, 16, 14)
        self.stack.addWidget(self.page_co)
        self._polish_co_page()

        # Trang 1: Đối chiếu SC & XNNL
        self.page_sc = SCReconciliationWidget(self)
        self.stack.addWidget(self.page_sc)

        # Trang 2: Trợ lý AI Copilot
        self.page_copilot = UnifiedCopilotWidget(self)
        self.stack.addWidget(self.page_copilot)

        # Trang 3: Cài đặt API dùng chung
        self.page_settings = UnifiedSettingsWidget(self)
        self.stack.addWidget(self.page_settings)

        # Sửa lỗi mất ký tự '&' trên tab/khung/nút + cuộn bảng mượt theo pixel
        ui.fix_ampersands(self)
        ui.smooth_item_views(self)

        # Phím tắt toàn cục
        QShortcut(QKeySequence("Ctrl+B"), self, self.toggle_sidebar)
        QShortcut(QKeySequence("Ctrl+1"), self, lambda: self.switch_page(0))
        QShortcut(QKeySequence("Ctrl+2"), self, lambda: self.switch_page(1))
        QShortcut(QKeySequence("Ctrl+3"), self, lambda: self.switch_page(2))
        QShortcut(QKeySequence("Ctrl+4"), self, lambda: self.switch_page(3))
        QShortcut(QKeySequence(Qt.Key.Key_F1), self, self.show_user_guide_dialog)

    def _polish_co_page(self):
        """Tinh chỉnh nhẹ trang C/O cho đồng bộ giao diện chung (không đổi chức năng)."""
        co = self.co_app_instance
        btn = getattr(co, "btn_copy_json_top", None)
        if btn is not None:
            btn.setText("📋 Sao chép JSON")
            btn.setToolTip("Sao chép JSON hồ sơ để dán vào Extension eCoSys")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ext = getattr(co, "btn_extract", None)
        if ext is not None:
            ext.setCursor(Qt.CursorShape.PointingHandCursor)
        # Nới cột trái (chọn mẫu + chứng từ) để các nút không bị cắt chữ
        from PyQt6.QtWidgets import QGroupBox
        for gb in self.page_co.findChildren(QGroupBox):
            if gb.title().startswith("1. Mẫu C/O") and gb.parentWidget() is not None:
                gb.parentWidget().setMaximumWidth(430)
                gb.parentWidget().setMinimumWidth(360)
                break
        compact = ("Thêm...", "Xóa chọn", "Xóa hết", "Chỉ Đơn + Inv", "AI đọc hết")
        for b in self.page_co.findChildren(QPushButton):
            if b.cursor().shape() != Qt.CursorShape.PointingHandCursor:
                b.setCursor(Qt.CursorShape.PointingHandCursor)
            if any(k in b.text() for k in compact):
                ui.set_prop(b, "size", "sm")  # nút nhỏ ở cột trái để không bị cắt chữ
        for lb in self.page_co.findChildren(QLabel):
            t = lb.text()
            if t.startswith("DỮ LIỆU HỒ SƠ KHAI BÁO C/O"):
                lb.setText("Hồ sơ khai báo C/O")
                lb.setObjectName("PageTitle")
                lb.setStyleSheet("")
            elif "KILOGRAM" in t:
                lb.setText("🛡 Đơn vị: KILOGRAM (đã khóa)")
                lb.setObjectName("BadgeSuccess")
                lb.setStyleSheet("")

    def create_nav_button(self, full_text: str, icon_text: str, tooltip: str, active: bool = False) -> QPushButton:
        btn = QPushButton(full_text)
        btn.setObjectName("NavButton")
        btn.setProperty("full_text", full_text)
        btn.setProperty("icon_text", icon_text)
        btn.setProperty("collapsed", False)
        btn.setToolTip(tooltip)
        btn.setFixedHeight(42)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if active:
            btn.setCheckable(True)
            btn.setChecked(True)
        return btn

    def apply_nav_btn_style(self, btn: QPushButton, active: bool):
        """Giữ để tương thích ngược: trạng thái nút giờ dùng setChecked (style lấy từ ui_theme)."""
        if btn.isCheckable():
            btn.setChecked(active)

    def toggle_sidebar(self):
        """Thu gọn / mở rộng menu trái với hiệu ứng trượt mượt."""
        self.is_sidebar_collapsed = not self.is_sidebar_collapsed
        collapsed = self.is_sidebar_collapsed
        start = self.sidebar.width()
        end = self.sidebar_collapsed_width if collapsed else self.sidebar_expanded_width
        text_widgets = [self.lbl_logo_title, self.lbl_logo_sub, self.lbl_side_section, self.lbl_version, self.lbl_logo_icon]
        buttons = [self.btn_nav_co, self.btn_nav_sc, self.btn_nav_copilot, self.btn_nav_settings,
                   self.btn_nav_guide, self.btn_nav_update]

        def set_buttons(c):
            for b in buttons:
                b.setText(b.property("icon_text") if c else b.property("full_text"))
                ui.set_prop(b, "collapsed", c)

        if collapsed:
            for w in text_widgets:
                w.setVisible(False)
            set_buttons(True)
            ui.animate_width(self.sidebar, start, end)
        else:
            set_buttons(False)

            def done():
                for w in text_widgets:
                    w.setVisible(True)
            ui.animate_width(self.sidebar, start, end, on_done=done)

    def switch_page(self, idx: int):
        self.stack.setCurrentIndex(idx)
        b = self.nav_group.button(idx)
        if b is not None and not b.isChecked():
            b.setChecked(True)

    def show_user_guide_dialog(self):
        dlg = UserGuideDialog(self)
        dlg.exec()

    def show_github_update_dialog(self):
        try:
            from github_updater import GitHubUpdateDialog
            dlg = GitHubUpdateDialog(self)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi cập nhật", f"Không thể khởi động trình cập nhật: {e}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F1:
            self.show_user_guide_dialog()
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Dọn dẹp triệt để các luồng chạy ngầm theo chuẩn Graceful Shutdown - Chống đứng hình/treo máy"""
        # 1. Dừng an toàn luồng trích xuất C/O
        if hasattr(self, 'co_app_instance') and self.co_app_instance:
            for w in [getattr(self.co_app_instance, 'worker', None),
                      getattr(self.co_app_instance, 'chat_worker', None),
                      getattr(self.co_app_instance, 'token_worker', None)]:
                if w and w.isRunning():
                    try:
                        w.requestInterruption()
                        w.wait(400)
                    except Exception:
                        pass
            if hasattr(self.co_app_instance, 'inspector_doc') and self.co_app_instance.inspector_doc:
                try:
                    self.co_app_instance.inspector_doc.close()
                except Exception:
                    pass
                self.co_app_instance.inspector_doc = None

        # 2. Dừng an toàn luồng đối chiếu SC
        if hasattr(self, 'page_sc') and hasattr(self.page_sc, 'worker') and self.page_sc.worker:
            try:
                if self.page_sc.worker.isRunning():
                    self.page_sc.worker.requestInterruption()
                    self.page_sc.worker.wait(500)
            except Exception:
                pass

        # 3. Dừng an toàn luồng Copilot
        if hasattr(self, 'page_copilot') and hasattr(self.page_copilot, 'worker') and self.page_copilot.worker:
            try:
                if self.page_copilot.worker.isRunning():
                    self.page_copilot.worker.requestInterruption()
                    self.page_copilot.worker.wait(400)
            except Exception:
                pass

        # 4. Tắt máy chủ Stream server cục bộ
        try:
            from co_core import local_stream_server
            local_stream_server.stop_local_stream_server()
        except Exception:
            try:
                import local_stream_server
                local_stream_server.stop_local_stream_server()
            except Exception:
                pass

        # 5. Giải phóng Mutex Windows
        global mutex_handle
        if 'mutex_handle' in globals() and mutex_handle:
            try:
                import ctypes
                ctypes.windll.kernel32.CloseHandle(mutex_handle)
                mutex_handle = None
            except Exception:
                pass

        event.accept()
        QApplication.quit()


if __name__ == "__main__":
    import ctypes
    ui.setup_high_dpi()  # phải gọi trước khi tạo QApplication
    # Kiểm tra chống mở đè nhiều tiến trình (Single-Instance Protection)
    mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\XNK_eCoSys_SC_v3_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        app_dummy = QApplication(sys.argv)
        apply_app_theme(app_dummy)
        QMessageBox.warning(
            None,
            "Ứng dụng đang chạy",
            "Phần mềm XNK & Thủy Sản Toàn Diện đang được mở trên máy tính của bạn.\n\n"
            "👉 Vui lòng kiểm tra trên thanh Taskbar phía dưới màn hình."
        )
        sys.exit(0)

    app = QApplication(sys.argv)
    apply_app_theme(app)
    w = UnifiedSuiteApp()
    w.show()
    sys.exit(app.exec())
