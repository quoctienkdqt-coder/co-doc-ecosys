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
import os

# Cho phép nạp các file mã nguồn .py cập nhật trực tiếp từ thư mục làm việc (Hỗ trợ Live-Update qua GitHub)
app_exec_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
if app_exec_dir and app_exec_dir not in sys.path:
    sys.path.insert(0, app_exec_dir)

import json
import subprocess
from datetime import datetime
from typing import List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QCheckBox, QProgressBar,
    QStackedWidget, QFrame, QTextEdit, QTextBrowser, QFileDialog, QMessageBox,
    QSplitter, QHeaderView, QTableWidget, QTableWidgetItem
)
from PyQt6.QtGui import QFont, QIcon, QColor, QKeySequence, QShortcut

# Import C/O Module & Gemini Advisor
from app_co_extractor import COExtractorApp, UserGuideDialog, load_settings, save_settings, CONFIG_FILE
from gemini_extractor import ask_co_advisor

# Import SC Core Engine (Self-contained in sc_core)
from sc_core.sc_extractor import extract_multiple_sc_documents
from sc_core.excel_processor import load_excel_xnnl, aggregate_and_validate_excel
from sc_core.reconciler import reconcile_excel_vs_sc
from sc_core.report_generator import create_reconciliation_excel_report, generate_corrected_excel_xnnl
from sc_core.ai_extractor import load_ai_config, save_ai_config


# ========================================================
# 1. WORKER CHẠY NGẦM ĐỐI CHIẾU SC (QTHREAD)
# ========================================================
class SCReconcileWorker(QThread):
    progress_signal = pyqtSignal(int, str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, dict, str)

    def __init__(self, sc_sources: List[str], excel_file: str, out_dir: str,
                 use_ai: bool, api_key: str, api_source: str, api_base_url: str,
                 do_merge: bool, do_correct: bool):
        super().__init__()
        self.sc_sources = sc_sources
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
            self.log_signal.emit("Bắt đầu quá trình đối chiếu tự động...")
            if len(self.sc_sources) == 1 and os.path.isdir(self.sc_sources[0]):
                self.log_signal.emit(f"Thư mục nguồn SC gốc: {self.sc_sources[0]}")
            else:
                self.log_signal.emit(f"Nguồn SC gốc: {len(self.sc_sources)} tệp tin.")
            self.log_signal.emit(f"File Excel XNNL: {os.path.basename(self.excel_file)}")

            # Step 1: Scan & OCR SC
            def sc_cb(pct, msg):
                self.progress_signal.emit(int(pct * 40), msg)

            prov = "apiz" if (self.api_source == "apiz" or self.api_key.startswith("sk-")) else "gemini"
            if self.use_ai and self.api_key:
                self.log_signal.emit(f"🤖 Kích hoạt Trí Tuệ Nhân Tạo (Gemini 3.8 Flash) để bóc tách SC gốc...")
            else:
                self.log_signal.emit("💻 Sử dụng bộ nhận dạng OCR Cục bộ (Offline RapidOCR)...")

            sc_repo, all_sc_records = extract_multiple_sc_documents(
                self.sc_sources,
                cache_dir="cache",
                progress_cb=sc_cb,
                use_ai=(self.use_ai and bool(self.api_key)),
                api_key=self.api_key,
                provider=prov
            )

            sc_numbers = [v['sc_info']['sc_number'] for k, v in sc_repo.items() if '/' in k]
            self.log_signal.emit(f"✅ Đã quét xong {len(sc_numbers)} Giấy SC gốc ({len(all_sc_records)} tàu cá).")
            for sc_n in sc_numbers:
                self.log_signal.emit(f"   • Giấy SC: {sc_n}")

            # Step 2: Load Excel XNNL
            self.progress_signal.emit(50, "Đang đọc file Excel XNNL...")
            ex_meta, raw_records, chu_tau_map = load_excel_xnnl(self.excel_file)
            self.log_signal.emit(f"✅ Đã đọc dữ liệu Excel ({ex_meta.get('format_type','Chung')}): Tìm thấy {len(raw_records)} dòng dữ liệu tàu.")

            # Step 3: Aggregate
            self.progress_signal.emit(65, "Đang kiểm tra dữ liệu và gộp lượng...")
            if self.do_merge:
                agg_records, merge_logs = aggregate_and_validate_excel(raw_records)
                if merge_logs:
                    self.log_signal.emit(f"🔄 Đã tự động gộp lượng cho {len(merge_logs)} lượt tàu trùng ngày lên cá:")
                    for m in merge_logs:
                        self.log_signal.emit(f"   • Tàu {m['vessel_id']} ({m['landing_date']}): Gộp {m['merged_count']} dòng -> Tổng: {m['sum_weight']:,.1f} kg")
                else:
                    self.log_signal.emit("ℹ️ Không phát hiện tàu nào trùng ngày cần gộp lượng.")
            else:
                agg_records = raw_records
                merge_logs = []

            # Step 4: Reconcile
            self.progress_signal.emit(80, "Đang đối chiếu so khớp với SC gốc...")
            recon_results, summary_stats = reconcile_excel_vs_sc(agg_records, sc_repo)

            # Log differences
            self.log_signal.emit("\n--- KẾT QUẢ ĐỐI CHIẾU SO KHỚP ---")
            for r in recon_results:
                v_id = r['vessel_id']
                sc_tag = f" [{r.get('sc_number','')}]" if r.get('sc_number') else ""
                if r['status'] == 'MATCH':
                    self.log_signal.emit(f"🟢 [KHỚP 100%] Tàu {v_id}{sc_tag}")
                elif r['status'] == 'WARNING':
                    self.log_signal.emit(f"🟡 [CẢNH BÁO] Tàu {v_id}{sc_tag}")
                elif r['status'] == 'CONFLICT':
                    self.log_signal.emit(f"🔴 [SAI LỆCH] Tàu {v_id}{sc_tag}:")
                    for d in r.get('diffs', []):
                        if d.get('type') == 'CRITICAL':
                            self.log_signal.emit(f"   * {d.get('message')}")

            # Step 5: Export Reports
            self.progress_signal.emit(90, "Đang xuất file báo cáo Excel...")
            os.makedirs(self.out_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_name = f"BaoCao_DoiChieu_SC_XNNL_{timestamp}.xlsx"
            report_path = os.path.join(self.out_dir, report_name)

            first_sc = next(iter(sc_repo.values())) if sc_repo else None
            first_sc_info = first_sc.get('sc_info') if first_sc else None

            create_reconciliation_excel_report(
                report_path,
                recon_results,
                summary_stats,
                merge_logs,
                all_sc_records,
                first_sc_info
            )
            self.log_signal.emit(f"📊 Đã tạo Báo cáo đối chiếu: {report_path}")

            corrected_path = None
            if self.do_correct:
                corrected_name = f"XNNL_DaChuanHoa_{timestamp}.xlsx"
                corrected_path = os.path.join(self.out_dir, corrected_name)
                generate_corrected_excel_xnnl(self.excel_file, corrected_path, recon_results)
                self.log_signal.emit(f"📑 Đã tạo File XNNL chuẩn hóa: {corrected_path}")

            self.progress_signal.emit(100, "Hoàn tất đối chiếu thành công!")
            self.log_signal.emit("✨ Quá trình đối chiếu hoàn tất thành công 100%!")

            result_data = {
                "summary": summary_stats,
                "report_path": report_path,
                "corrected_path": corrected_path,
                "output_dir": self.out_dir
            }
            self.finished_signal.emit(True, result_data, "")

        except Exception as e:
            self.log_signal.emit(f"❌ LỖI TRONG QUÁ TRÌNH XỬ LÝ: {e}")
            self.finished_signal.emit(False, {}, str(e))


# ========================================================
# 2. WORKER CHATBOT COPILOT ĐA NGHIỆP VỤ (QTHREAD)
# ========================================================
class UnifiedCopilotWorker(QThread):
    reply_signal = pyqtSignal(str, str)

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
            m_target = self.model_name or ("gemini-3.8-flash" if self.api_source == "apiz" else "gemini-3.8-flash")
            ans = ask_co_advisor(
                api_key=self.api_key,
                question=self.question,
                history=self.history,
                api_source=self.api_source,
                api_base_url=self.api_base_url,
                model_name=m_target
            )
            self.reply_signal.emit(ans, "")
        except Exception as e:
            self.reply_signal.emit("", str(e))


# ========================================================
# 3. WIDGET PHÂN HỆ 2: ĐỐI CHIẾU SC & XNNL CẢNG CÁ
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
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Header bar
        hdr = QHBoxLayout()
        title = QLabel("⚓ ĐỐI CHIẾU XÁC NHẬN NGUYÊN LIỆU (XNNL & SC GỐC CẢNG CÁ)")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e3a8a;")
        hdr.addWidget(title)

        badge = QLabel("🐟 Thẩm định Hồ sơ IUU & Chuẩn hóa PMSX")
        badge.setStyleSheet("background: #e0f2fe; color: #0369a1; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11.5px;")
        hdr.addWidget(badge)
        hdr.addStretch()

        layout.addLayout(hdr)

        # 1. Box Chọn Tệp Đầu Vào
        box_input = QFrame()
        box_input.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px;")
        grid_in = QGridLayout(box_input)
        grid_in.setSpacing(8)

        # Hàng 1: SC Gốc
        grid_in.addWidget(QLabel("<b>Bản Scan SC Gốc (PDF / Folder):</b>"), 0, 0)
        self.entry_sc = QLineEdit()
        self.entry_sc.setPlaceholderText("Chọn 1 hoặc nhiều file PDF Scan SC (hoặc thư mục chứa SC)...")
        grid_in.addWidget(self.entry_sc, 0, 1)

        btn_box_sc = QHBoxLayout()
        btn_sc_file = QPushButton("Chọn File(s)...")
        btn_sc_file.clicked.connect(self.browse_sc_files)
        btn_sc_dir = QPushButton("Thư Mục SC...")
        btn_sc_dir.setStyleSheet("background: #0284c7; color: white; font-weight: bold;")
        btn_sc_dir.clicked.connect(self.browse_sc_dir)
        btn_box_sc.addWidget(btn_sc_file)
        btn_box_sc.addWidget(btn_sc_dir)
        grid_in.addLayout(btn_box_sc, 0, 2)

        # Hàng 2: Excel PMSX
        grid_in.addWidget(QLabel("<b>File Excel XNNL (PMSX):</b>"), 1, 0)
        self.entry_excel = QLineEdit()
        self.entry_excel.setPlaceholderText("Chọn file Excel XNNL xuất từ phần mềm sản xuất...")
        grid_in.addWidget(self.entry_excel, 1, 1)

        btn_ex = QPushButton("Chọn File Excel...")
        btn_ex.clicked.connect(self.browse_excel_file)
        grid_in.addWidget(btn_ex, 1, 2)

        # Hàng 3: Thư mục kết quả
        grid_in.addWidget(QLabel("<b>Thư mục xuất kết quả:</b>"), 2, 0)
        self.entry_output = QLineEdit()
        default_out = os.path.abspath("KetQua_DoiChieu")
        self.entry_output.setText(default_out)
        grid_in.addWidget(self.entry_output, 2, 1)

        btn_out = QPushButton("Chọn Thư Mục...")
        btn_out.clicked.connect(self.browse_output_dir)
        grid_in.addWidget(btn_out, 2, 2)

        layout.addWidget(box_input)

        # 2. Box Tùy Chọn & Nút Thực Thi
        box_opt = QFrame()
        box_opt.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px 12px;")
        opt_layout = QHBoxLayout(box_opt)

        self.chk_ai = QCheckBox("🤖 Bóc tách bằng AI Vision (Gemini 3.8 Flash)")
        self.chk_ai.setChecked(True)
        opt_layout.addWidget(self.chk_ai)

        self.chk_merge = QCheckBox("🔄 Tự động gộp lượng (Cùng tàu + Cùng ngày)")
        self.chk_merge.setChecked(True)
        opt_layout.addWidget(self.chk_merge)

        self.chk_correct = QCheckBox("✏️ Tự động sửa Chủ tàu & GPKTTS theo SC gốc")
        self.chk_correct.setChecked(True)
        opt_layout.addWidget(self.chk_correct)

        opt_layout.addStretch()

        self.btn_run = QPushButton("🚀 BẮT ĐẦU ĐỐI CHIẾU & XỬ LÝ TỰ ĐỘNG")
        self.btn_run.setStyleSheet("""
            QPushButton {
                background-color: #1e40af;
                color: #ffffff;
                font-weight: bold;
                padding: 10px 22px;
                border-radius: 6px;
                font-size: 13.5px;
            }
            QPushButton:hover {
                background-color: #1e3a8a;
            }
            QPushButton:disabled {
                background-color: #94a3b8;
            }
        """)
        self.btn_run.clicked.connect(self.start_reconciliation)
        opt_layout.addWidget(self.btn_run)

        layout.addWidget(box_opt)

        # Tiến trình
        self.prog_bar = QProgressBar()
        self.prog_bar.setFixedHeight(6)
        self.prog_bar.setValue(0)
        self.prog_bar.setTextVisible(False)
        layout.addWidget(self.prog_bar)

        self.lbl_status = QLabel("Sẵn sàng thực hiện đối chiếu hồ sơ.")
        self.lbl_status.setStyleSheet("color: #64748b; font-style: italic; font-size: 11.5px;")
        layout.addWidget(self.lbl_status)

        # 3. Dãy 5 Thẻ KPI Thống Kê
        kpi_box = QHBoxLayout()
        kpi_box.setSpacing(10)

        self.lbl_kpi_sc = self.create_kpi_card(kpi_box, "TÀU SC GỐC", "0", "#1e3a8a")
        self.lbl_kpi_excel = self.create_kpi_card(kpi_box, "TÀU EXCEL", "0", "#334155")
        self.lbl_kpi_match = self.create_kpi_card(kpi_box, "KHỚP 100%", "0", "#15803d")
        self.lbl_kpi_diff = self.create_kpi_card(kpi_box, "SAI LỆCH CẦN SỬA", "0", "#b91c1c")
        self.lbl_kpi_merged = self.create_kpi_card(kpi_box, "ĐÃ GỘP LƯỢNG", "0", "#b45309")

        layout.addLayout(kpi_box)

        # 4. Thanh Nút Mở Kết Quả
        exp_box = QFrame()
        exp_box.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px 12px;")
        exp_l = QHBoxLayout(exp_box)
        exp_l.addWidget(QLabel("<b>📁 KẾT QUẢ ĐÃ XUẤT:</b>"))

        self.btn_open_report = QPushButton("📊 Mở Báo Cáo Đối Chiếu (.xlsx)")
        self.btn_open_report.setStyleSheet("background: #15803d; color: white; font-weight: bold; padding: 7px 14px;")
        self.btn_open_report.clicked.connect(self.open_report_file)
        self.btn_open_report.setEnabled(False)
        exp_l.addWidget(self.btn_open_report)

        self.btn_open_fixed = QPushButton("📑 Mở File XNNL Chuẩn Hóa (.xlsx)")
        self.btn_open_fixed.setStyleSheet("background: #0284c7; color: white; font-weight: bold; padding: 7px 14px;")
        self.btn_open_fixed.clicked.connect(self.open_fixed_file)
        self.btn_open_fixed.setEnabled(False)
        exp_l.addWidget(self.btn_open_fixed)

        self.btn_open_folder = QPushButton("📂 Mở Thư Mục Kết Quả")
        self.btn_open_folder.setStyleSheet("background: #475569; color: white; font-weight: bold; padding: 7px 14px;")
        self.btn_open_folder.clicked.connect(self.open_output_folder)
        exp_l.addWidget(self.btn_open_folder)

        layout.addWidget(exp_box)

        # 5. Khung Nhật Ký Xử Lý (Log Console)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("background: #0f172a; color: #38bdf8; font-family: Consolas, monospace; font-size: 11.5px; border-radius: 6px; padding: 8px;")
        self.txt_log.setPlaceholderText("Nhật ký xử lý chi tiết sẽ hiển thị tại đây...")
        layout.addWidget(self.txt_log, stretch=1)

    def create_kpi_card(self, parent_layout, title: str, val: str, color: str) -> QLabel:
        card = QFrame()
        card.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px;")
        l = QVBoxLayout(card)
        l.setContentsMargins(6, 6, 6, 6)
        l.setSpacing(2)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748b;")
        lbl_t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(lbl_t)

        lbl_v = QLabel(val)
        lbl_v.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {color};")
        lbl_v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(lbl_v)

        parent_layout.addWidget(card)
        return lbl_v

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.txt_log.append(f"[{ts}] {msg}")

    def browse_sc_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn các file Scan SC gốc", "",
            "Tài liệu PDF / Ảnh (*.pdf *.png *.jpg *.jpeg);;Tất cả tệp (*.*)"
        )
        if files:
            self.entry_sc.setText("; ".join(files))

    def browse_sc_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa các file Scan SC gốc")
        if d:
            self.entry_sc.setText(d)

    def browse_excel_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Chọn file Excel XNNL từ phần mềm khai thác", "",
            "Tệp Excel (*.xlsx *.xls);;Tất cả tệp (*.*)"
        )
        if f:
            self.entry_excel.setText(f)

    def browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục xuất báo cáo đối chiếu")
        if d:
            self.entry_output.setText(d)

    def load_sample_sc_paths(self):
        """Nạp nhanh đường dẫn mẫu của Dự án Chị Nguyên"""
        p_sc = os.path.abspath(r"c:\Users\Admin\Desktop\chị Nguyên\00180 2026 SC  GL TQ HL.pdf")
        p_ex = os.path.abspath(r"c:\Users\Admin\Desktop\chị Nguyên\XKNL_26260EUR_1.xlsx")
        if os.path.exists(p_sc):
            self.entry_sc.setText(p_sc)
        if os.path.exists(p_ex):
            self.entry_excel.setText(p_ex)
        self.log("Đã nạp đường dẫn tệp mẫu thành công!")

    def start_reconciliation(self):
        raw_sc = self.entry_sc.text().strip()
        excel_path = self.entry_excel.text().strip()
        out_dir = self.entry_output.text().strip() or os.path.abspath("KetQua_DoiChieu")

        if not raw_sc:
            QMessageBox.warning(self, "Thiếu dữ liệu", "Vui lòng chọn ít nhất 1 file Scan SC gốc hoặc thư mục chứa SC!")
            return
        if not excel_path or not os.path.exists(excel_path):
            QMessageBox.warning(self, "Thiếu dữ liệu", "Vui lòng chọn đúng file Excel XNNL từ phần mềm sản xuất!")
            return

        if ";" in raw_sc:
            sc_sources = [s.strip() for s in raw_sc.split(";") if s.strip()]
        else:
            sc_sources = [raw_sc]

        # Get API key from shared settings
        cfg = self.parent_app.shared_config
        api_key = cfg.get("api_key", "")
        api_source = cfg.get("api_source", "official")
        api_base_url = cfg.get("api_base_url", "https://api.apiz.vn/v1")

        self.btn_run.setEnabled(False)
        self.btn_run.setText("⏳ Đang xử lý đối chiếu...")
        self.prog_bar.setValue(0)
        self.txt_log.clear()

        self.worker = SCReconcileWorker(
            sc_sources=sc_sources,
            excel_file=excel_path,
            out_dir=out_dir,
            use_ai=self.chk_ai.isChecked(),
            api_key=api_key,
            api_source=api_source,
            api_base_url=api_base_url,
            do_merge=self.chk_merge.isChecked(),
            do_correct=self.chk_correct.isChecked()
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
        self.btn_run.setText("🚀 BẮT ĐẦU ĐỐI CHIẾU & XỬ LÝ TỰ ĐỘNG")

        if success:
            summary = res.get("summary", {})
            self.lbl_kpi_sc.setText(str(summary.get("total_sc", 0)))
            self.lbl_kpi_excel.setText(str(summary.get("total_excel", 0)))
            self.lbl_kpi_match.setText(str(summary.get("exact_match", 0)))
            self.lbl_kpi_diff.setText(str(summary.get("critical_conflict", 0)))
            self.lbl_kpi_merged.setText(str(summary.get("merged_rows", 0)))

            self.last_report_path = res.get("report_path")
            self.last_corrected_path = res.get("corrected_path")
            self.last_out_dir = res.get("output_dir")

            self.btn_open_report.setEnabled(bool(self.last_report_path))
            self.btn_open_fixed.setEnabled(bool(self.last_corrected_path))

            QMessageBox.information(
                self, "Hoàn tất đối chiếu",
                f"Đã hoàn thành đối chiếu thành công!\n\n"
                f"• Tổng số tàu SC gốc: {summary.get('total_sc', 0)}\n"
                f"• Khớp 100%: {summary.get('exact_match', 0)}\n"
                f"• Sai lệch cần xử lý: {summary.get('critical_conflict', 0)}\n\n"
                f"Bạn có thể mở ngay file Báo cáo hoặc File XNNL đã sửa ở thanh kết quả bên dưới."
            )
        else:
            QMessageBox.critical(self, "Lỗi đối chiếu", f"Quá trình đối chiếu phát sinh lỗi:\n{err}")

    def open_report_file(self):
        if self.last_report_path and os.path.exists(self.last_report_path):
            os.startfile(self.last_report_path)

    def open_fixed_file(self):
        if self.last_corrected_path and os.path.exists(self.last_corrected_path):
            os.startfile(self.last_corrected_path)

    def open_output_folder(self):
        d = self.last_out_dir or self.entry_output.text().strip()
        if os.path.exists(d):
            os.startfile(d)


# ========================================================
# 4. WIDGET TRỢ LÝ AI COPILOT ĐA NGHIỆP VỤ (C/O + IUU/SC)
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
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("🤖 TRỢ LÝ AI COPILOT CHUYÊN GIA NGOẠI THƯƠNG & THỦY SẢN")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0078d4;")
        hdr.addWidget(title)

        badge = QLabel("⚡ Gemini 3.8 Flash • Sẵn sàng 24/7")
        badge.setStyleSheet("background: #f3e8ff; color: #7e22ce; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11.5px;")
        hdr.addWidget(badge)
        hdr.addStretch()

        btn_clear = QPushButton("🗑️ Xóa Lịch Sử Chat")
        btn_clear.clicked.connect(self.clear_chat)
        hdr.addWidget(btn_clear)
        layout.addLayout(hdr)

        # Dãy câu hỏi gợi ý nhanh theo 2 nhóm nghiệp vụ
        pills_box = QFrame()
        pills_box.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px;")
        pills_l = QVBoxLayout(pills_box)
        pills_l.setSpacing(6)

        # Nhóm C/O eCoSys (Xanh dương)
        row_co = QHBoxLayout()
        lbl_co = QLabel("<b>📋 Nghiệp vụ C/O eCoSys:</b>")
        lbl_co.setStyleSheet("color: #0284c7; font-size: 11.5px;")
        row_co.addWidget(lbl_co)

        btn_co1 = QPushButton("📜 Tiêu chí WO, CTC, RVC 40%")
        btn_co1.clicked.connect(lambda: self.ask_quick("Hướng dẫn phân biệt và xác định tiêu chí xuất xứ WO, CTC (CTH/CTSH), RVC 40% và De Minimis khi khai báo C/O eCoSys?"))
        btn_co2 = QPushButton("🚢 Vận chuyển trực tiếp & Nước thứ 3")
        btn_co2.clicked.connect(lambda: self.ask_quick("Quy định vận chuyển trực tiếp và chuyển tải qua nước thứ 3 (Singapore, Hong Kong) để không làm mất xuất xứ C/O?"))
        btn_co3 = QPushButton("🔑 Khắc phục lỗi Token eCoSys")
        btn_co3.clicked.connect(lambda: self.ask_quick("Cách sửa lỗi không nhận Chữ ký số USB Token MOITSignPlugin khi ký nộp hồ sơ C/O trên ecosys.gov.vn?"))

        row_co.addWidget(btn_co1)
        row_co.addWidget(btn_co2)
        row_co.addWidget(btn_co3)
        row_co.addStretch()
        pills_l.addLayout(row_co)

        # Nhóm IUU & SC Cảng cá (Xanh lá / Navy)
        row_sc = QHBoxLayout()
        lbl_sc = QLabel("<b>⚓ Nghiệp vụ SC & IUU Thủy sản:</b>")
        lbl_sc.setStyleSheet("color: #15803d; font-size: 11.5px;")
        row_sc.addWidget(lbl_sc)

        btn_sc1 = QPushButton("🐟 Quy định Giấy SC & Hồ sơ IUU")
        btn_sc1.clicked.connect(lambda: self.ask_quick("Quy định kiểm tra tính hợp pháp của Giấy xác nhận SC gốc Cảng cá theo Thông tư 21/2018/TT-BNNPTNT để làm hồ sơ IUU xuất khẩu?"))
        btn_sc2 = QPushButton("⚓ Xử lý lệch Chủ tàu / GPKTTS")
        btn_sc2.clicked.connect(lambda: self.ask_quick("Cách xử lý và giải trình khi tên Chủ tàu hoặc số GPKTTS trên Excel sản xuất không khớp với bản scan Giấy SC gốc của Cảng cá?"))
        btn_sc3 = QPushButton("🔄 Quy tắc gộp lượng tàu cá")
        btn_sc3.clicked.connect(lambda: self.ask_quick("Quy tắc gộp lượng tàu cá khi cùng 1 tàu cập cảng/lên cá cùng ngày trong bảng kê Phụ lục 02a được quy định thế nào?"))

        row_sc.addWidget(btn_sc1)
        row_sc.addWidget(btn_sc2)
        row_sc.addWidget(btn_sc3)
        row_sc.addStretch()
        pills_l.addLayout(row_sc)

        layout.addWidget(pills_box)

        # Khung hiển thị tin nhắn Chat
        self.txt_chat = QTextBrowser()
        self.txt_chat.setOpenExternalLinks(True)
        self.txt_chat.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; font-size: 13px;")
        self.txt_chat.setHtml("""
            <div style="color: #475569; font-style: italic; padding: 10px;">
                👋 <b>Xin chào!</b> Tôi là Trợ lý AI Copilot chuyên gia về <b>Khai báo C/O eCoSys (Bộ Công Thương)</b> và <b>Hồ sơ IUU / Xác nhận nguyên liệu thủy sản (SC Cảng cá)</b>.<br/>
                Bạn có thể bấm các nút câu hỏi nhanh ở trên hoặc nhập câu hỏi nghiệp vụ vào ô bên dưới để tôi hỗ trợ ngay lập tức!
            </div>
        """)
        layout.addWidget(self.txt_chat, stretch=1)

        # Khung nhập câu hỏi
        input_bar = QHBoxLayout()
        self.input_question = QLineEdit()
        self.input_question.setPlaceholderText("Nhập câu hỏi nghiệp vụ C/O hoặc đối chiếu SC (bấm Enter để gửi)...")
        self.input_question.returnPressed.connect(self.send_message)
        input_bar.addWidget(self.input_question, stretch=1)

        self.btn_send = QPushButton("🚀 Gửi Câu Hỏi")
        self.btn_send.setStyleSheet("background: #0078d4; color: white; font-weight: bold; padding: 8px 20px;")
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
        self.input_question.clear()
        self.btn_send.setEnabled(False)
        self.btn_send.setText("⏳ Đang suy nghĩ...")

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
        self.btn_send.setText("🚀 Gửi Câu Hỏi")
        if answer:
            self.append_ai_message(answer)
            self.chat_history.append({"role": "user", "text": self.input_question.text()})
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
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("⚙️ CÀI ĐẶT HỆ THỐNG & API KEY DÙNG CHUNG")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #0f172a;")
        layout.addWidget(title)

        sub = QLabel("Chỉ cần cấu hình API Key 1 lần duy nhất, cả 2 phân hệ (Khai báo C/O eCoSys và Đối chiếu SC) đều được kích hoạt tự động với mô hình Gemini 3.8 Flash!")
        sub.setStyleSheet("font-size: 13px; color: #475569;")
        layout.addWidget(sub)

        card = QFrame()
        card.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 20px;")
        grid = QGridLayout(card)
        grid.setSpacing(14)

        grid.addWidget(QLabel("<b>Nguồn API:</b>"), 0, 0)
        self.combo_source = QComboBox()
        self.combo_source.addItem("APIZ Vietnam Gateway (Khuyên dùng)", "apiz")
        self.combo_source.addItem("Google Gemini Official", "official")
        self.combo_source.currentIndexChanged.connect(self.on_source_changed)
        grid.addWidget(self.combo_source, 0, 1)

        grid.addWidget(QLabel("<b>API Key:</b>"), 1, 0)
        key_layout = QHBoxLayout()
        self.entry_key = QLineEdit()
        self.entry_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.entry_key.setPlaceholderText("Dán API Key (bắt đầu bằng sk-... cho APIZ hoặc AIzaSy... cho Google)...")
        self.entry_key.textChanged.connect(self.on_key_typed)
        key_layout.addWidget(self.entry_key)

        btn_eye = QPushButton("👁️")
        btn_eye.setFixedWidth(36)
        btn_eye.clicked.connect(self.toggle_eye)
        key_layout.addWidget(btn_eye)
        grid.addLayout(key_layout, 1, 1)

        self.lbl_base = QLabel("<b>Base URL:</b>")
        self.entry_base = QLineEdit("https://api.apiz.vn/v1")
        grid.addWidget(self.lbl_base, 2, 0)
        grid.addWidget(self.entry_base, 2, 1)

        grid.addWidget(QLabel("<b>Mô hình AI:</b>"), 3, 0)
        self.entry_model = QLineEdit("gemini-3.8-flash (Cố định chuẩn mới 2026)")
        self.entry_model.setEnabled(False)
        grid.addWidget(self.entry_model, 3, 1)

        btn_save = QPushButton("💾 LƯU CẤU HÌNH CHO TOÀN BỘ ỨNG DỤNG")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                font-weight: bold;
                padding: 10px 24px;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0067b8;
            }
        """)
        btn_save.clicked.connect(self.save_config)
        grid.addWidget(btn_save, 4, 1, Qt.AlignmentFlag.AlignRight)

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
        self.sidebar_expanded_width = 240
        self.sidebar_collapsed_width = 64

        # Cấu hình dùng chung
        self.shared_config = load_settings()

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
        # THANH ĐIỀU HƯỚNG BÊN TRÁI (COLLAPSIBLE SIDEBAR)
        # ========================================================
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(self.sidebar_expanded_width)
        self.sidebar.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border-right: 1px solid #1e293b;
            }
            QLabel {
                color: #f8fafc;
            }
        """)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(10, 14, 10, 14)
        self.sidebar_layout.setSpacing(8)

        # Header Sidebar + Nút Hamburger Thu gọn / Mở rộng
        hdr_bar = QHBoxLayout()
        hdr_bar.setContentsMargins(4, 0, 4, 0)

        self.lbl_logo_icon = QLabel("🚢")
        self.lbl_logo_icon.setStyleSheet("font-size: 20px;")
        hdr_bar.addWidget(self.lbl_logo_icon)

        self.lbl_logo_title = QLabel("XNK & THỦY SẢN")
        self.lbl_logo_title.setStyleSheet("font-size: 14.5px; font-weight: bold; color: #38bdf8;")
        hdr_bar.addWidget(self.lbl_logo_title, stretch=1)

        self.btn_toggle_sidebar = QPushButton("☰")
        self.btn_toggle_sidebar.setToolTip("Thu gọn / Mở rộng menu (Ctrl + B)")
        self.btn_toggle_sidebar.setFixedSize(34, 34)
        self.btn_toggle_sidebar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_sidebar.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #334155;
                font-size: 16px;
                font-weight: bold;
                border-radius: 6px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
        """)
        self.btn_toggle_sidebar.clicked.connect(self.toggle_sidebar)
        hdr_bar.addWidget(self.btn_toggle_sidebar)

        self.sidebar_layout.addLayout(hdr_bar)

        self.lbl_logo_sub = QLabel("Hệ Thống Hợp Nhất 2 Trong 1")
        self.lbl_logo_sub.setStyleSheet("font-size: 11px; color: #94a3b8; margin-left: 4px; margin-bottom: 10px;")
        self.sidebar_layout.addWidget(self.lbl_logo_sub)

        # Danh sách các nút điều hướng
        self.btn_nav_co = self.create_nav_button("📋  Khai báo C/O eCoSys", "📋", "Khai báo C/O eCoSys (Bộ Công Thương) [Ctrl+1]", active=True)
        self.btn_nav_co.clicked.connect(lambda: self.switch_page(0))
        self.sidebar_layout.addWidget(self.btn_nav_co)

        self.btn_nav_sc = self.create_nav_button("⚓  Đối chiếu SC Cảng Cá", "⚓", "Đối chiếu SC Cảng Cá & XNNL PMSX (Chị Nguyên) [Ctrl+2]", active=False)
        self.btn_nav_sc.clicked.connect(lambda: self.switch_page(1))
        self.sidebar_layout.addWidget(self.btn_nav_sc)

        self.btn_nav_copilot = self.create_nav_button("🤖  Trợ lý AI Copilot", "🤖", "Trợ lý AI Copilot nghiệp vụ C/O & IUU Thủy sản [Ctrl+3]", active=False)
        self.btn_nav_copilot.clicked.connect(lambda: self.switch_page(2))
        self.sidebar_layout.addWidget(self.btn_nav_copilot)

        self.btn_nav_settings = self.create_nav_button("⚙️  Cài đặt API Chung", "⚙️", "Cài đặt API Key Gemini & APIZ dùng chung [Ctrl+4]", active=False)
        self.btn_nav_settings.clicked.connect(lambda: self.switch_page(3))
        self.sidebar_layout.addWidget(self.btn_nav_settings)

        self.sidebar_layout.addStretch()

        self.btn_nav_guide = self.create_nav_button("📖  Hướng dẫn sử dụng", "📖", "Cẩm nang hướng dẫn sử dụng toàn diện (F1)", active=False)
        self.btn_nav_guide.clicked.connect(self.show_user_guide_dialog)
        self.sidebar_layout.addWidget(self.btn_nav_guide)

        self.btn_nav_update = self.create_nav_button("🔄  Cập nhật GitHub", "🔄", "Kiểm tra và cập nhật phiên bản mới qua GitHub", active=False)
        self.btn_nav_update.clicked.connect(self.show_github_update_dialog)
        self.sidebar_layout.addWidget(self.btn_nav_update)

        self.lbl_version = QLabel("v3.1.0 • Gemini 3.8 Flash\n© Ngô Quốc Tiến • 0905387808")
        self.lbl_version.setStyleSheet("font-size: 10px; color: #64748b; margin-left: 6px; line-height: 1.3;")
        self.sidebar_layout.addWidget(self.lbl_version)

        main_layout.addWidget(self.sidebar)

        # ========================================================
        # KHU VỰC NỘI DUNG CHÍNH (STACKED WIDGET)
        # ========================================================
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, stretch=1)

        # Trang 0: Khai báo C/O eCoSys (Tái sử dụng nguyên vẹn COExtractorApp)
        self.co_app_instance = COExtractorApp()
        self.page_co = self.co_app_instance.centralWidget()
        self.stack.addWidget(self.page_co)

        # Trang 1: Đối chiếu SC & XNNL (Dự án Chị Nguyên)
        self.page_sc = SCReconciliationWidget(self)
        self.stack.addWidget(self.page_sc)

        # Trang 2: Trợ lý AI Copilot Đa Nghiệp Vụ
        self.page_copilot = UnifiedCopilotWidget(self)
        self.stack.addWidget(self.page_copilot)

        # Trang 3: Cài đặt API dùng chung
        self.page_settings = UnifiedSettingsWidget(self)
        self.stack.addWidget(self.page_settings)

        # Phím tắt toàn cục
        QShortcut(QKeySequence("Ctrl+B"), self, self.toggle_sidebar)
        QShortcut(QKeySequence("Ctrl+1"), self, lambda: self.switch_page(0))
        QShortcut(QKeySequence("Ctrl+2"), self, lambda: self.switch_page(1))
        QShortcut(QKeySequence("Ctrl+3"), self, lambda: self.switch_page(2))
        QShortcut(QKeySequence("Ctrl+4"), self, lambda: self.switch_page(3))
        QShortcut(QKeySequence(Qt.Key.Key_F1), self, self.show_user_guide_dialog)

    def create_nav_button(self, full_text: str, icon_text: str, tooltip: str, active: bool = False) -> QPushButton:
        btn = QPushButton(full_text)
        btn.setProperty("full_text", full_text)
        btn.setProperty("icon_text", icon_text)
        btn.setToolTip(tooltip)
        btn.setFixedHeight(44)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_nav_btn_style(btn, active)
        return btn

    def apply_nav_btn_style(self, btn: QPushButton, active: bool):
        if active:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: #ffffff;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: bold;
                    border: none;
                    text-align: left;
                    padding-left: 12px;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #cbd5e1;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: 500;
                    border: none;
                    text-align: left;
                    padding-left: 12px;
                }
                QPushButton:hover {
                    background-color: #1e293b;
                    color: #ffffff;
                }
            """)

    def toggle_sidebar(self):
        """Thu gọn hoặc mở rộng thanh điều hướng để mở rộng không gian làm việc"""
        self.is_sidebar_collapsed = not self.is_sidebar_collapsed
        w = self.sidebar_collapsed_width if self.is_sidebar_collapsed else self.sidebar_expanded_width
        self.sidebar.setFixedWidth(w)

        # Ẩn / Hiện các nhãn chữ lớn
        self.lbl_logo_title.setVisible(not self.is_sidebar_collapsed)
        self.lbl_logo_sub.setVisible(not self.is_sidebar_collapsed)
        self.lbl_version.setVisible(not self.is_sidebar_collapsed)

        buttons = [self.btn_nav_co, self.btn_nav_sc, self.btn_nav_copilot, self.btn_nav_settings, self.btn_nav_guide, self.btn_nav_update]
        for btn in buttons:
            if self.is_sidebar_collapsed:
                btn.setText(btn.property("icon_text"))
                btn.setStyleSheet(btn.styleSheet() + " text-align: center; padding-left: 0px; font-size: 16px;")
            else:
                btn.setText(btn.property("full_text"))
                btn.setStyleSheet(btn.styleSheet().replace("text-align: center; padding-left: 0px; font-size: 16px;", "text-align: left; padding-left: 12px; font-size: 13px;"))

    def switch_page(self, idx: int):
        self.stack.setCurrentIndex(idx)
        self.apply_nav_btn_style(self.btn_nav_co, active=(idx == 0))
        self.apply_nav_btn_style(self.btn_nav_sc, active=(idx == 1))
        self.apply_nav_btn_style(self.btn_nav_copilot, active=(idx == 2))
        self.apply_nav_btn_style(self.btn_nav_settings, active=(idx == 3))

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
        """Dọn dẹp triệt để các luồng chạy ngầm để chống hiện tượng treo/lag và tiến trình zombie"""
        # 1. Dừng luồng trích xuất C/O
        if hasattr(self, 'co_app_instance'):
            if hasattr(self.co_app_instance, 'worker') and self.co_app_instance.worker:
                try:
                    if self.co_app_instance.worker.isRunning():
                        self.co_app_instance.worker.terminate()
                except Exception:
                    pass
            if hasattr(self.co_app_instance, 'chat_worker') and self.co_app_instance.chat_worker:
                try:
                    if self.co_app_instance.chat_worker.isRunning():
                        self.co_app_instance.chat_worker.terminate()
                except Exception:
                    pass

        # 2. Dừng luồng đối chiếu SC
        if hasattr(self, 'page_sc') and hasattr(self.page_sc, 'worker') and self.page_sc.worker:
            try:
                if self.page_sc.worker.isRunning():
                    self.page_sc.worker.terminate()
            except Exception:
                pass

        # 3. Dừng luồng Copilot
        if hasattr(self, 'page_copilot') and hasattr(self.page_copilot, 'worker') and self.page_copilot.worker:
            try:
                if self.page_copilot.worker.isRunning():
                    self.page_copilot.worker.terminate()
            except Exception:
                pass

        event.accept()
        os._exit(0)


if __name__ == "__main__":
    import ctypes
    # Kiểm tra chống mở đè nhiều tiến trình (Single-Instance Protection)
    mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\XNK_eCoSys_SC_v3_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        app_dummy = QApplication(sys.argv)
        QMessageBox.warning(
            None,
            "Ứng dụng đang chạy",
            "Phần mềm XNK & Thủy Sản Toàn Diện đang được mở trên máy tính của bạn.\n\n"
            "👉 Vui lòng kiểm tra trên thanh Taskbar phía dưới màn hình."
        )
        sys.exit(0)

    app = QApplication(sys.argv)
    w = UnifiedSuiteApp()
    w.show()
    sys.exit(app.exec())
