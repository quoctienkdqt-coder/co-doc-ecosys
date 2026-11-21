"""
TAB "CẦN XỬ LÝ" (Hàng đợi duyệt) cho trang Đối chiếu SC.

Trái: danh sách mục (Sai lệch thật / Cần xem). Phải: chi tiết mục đang chọn
  - giá trị theo từng nguồn
  - ẢNH CẮT ĐÚNG DÒNG tàu trên SC gốc (OCR cục bộ định vị dòng, không tốn API)
  - lý do máy kết luận + đề xuất
  - nút Chấp nhận (Enter) / Đã xem / Mở SC gốc
Chấp nhận giá trị SC -> ghi vào Sổ tàu đã xác nhận (nguồn "người duyệt") + nhật ký duyệt JSON.
"""
try:  # ghi lỗi bị bỏ qua vào loi_bo_qua.log (thay cho except: pass im lặng)
    from nhat_ky_loi import ghi as _ghi_loi_bo_qua
except Exception:  # pragma: no cover
    def _ghi_loi_bo_qua(*_a, **_k):
        return None
import os
import json
from datetime import datetime

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QRectF
from PyQt6.QtGui import QPixmap, QColor, QKeySequence, QShortcut, QPainter, QPen, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QFrame, QSizePolicy,
    QStyledItemDelegate, QStyle
)

import ui_theme as ui

MAU = {
    "SAI_LECH": ("#B91C1C", "#FEF2F2", "Sai lệch thật"),
    "CAN_XEM": ("#B45309", "#FFFBEB", "Cần người xem"),
    "DA_XU_LY": ("#15803D", "#F0FDF4", "Đã xử lý"),
}
MAU_NGUON = {"ok": ("#166534", "#F0FDF4", "chuẩn để so"), "lech": ("#991B1B", "#FEF2F2", "khác SC gốc"),
             "nghi": ("#92400E", "#FFFBEB", "chưa chắc"), "tham_khao": ("#334155", "#F8FAFC", "tham khảo")}


# Phần bề ngang dòng SC cần cắt theo trường (Mẫu 01: cột trái = tàu/chủ tàu/GP, cột phải = ngày/kg)
VUNG_CAT = {"owner": (0.0, 0.5), "gear": (0.0, 0.62), "licence_no": (0.0, 0.62), "licence_exp": (0.0, 0.62),
            "catch_period": (0.3, 0.85), "catch_area": (0.3, 0.85), "species": (0.4, 0.95),
            "landing_date": (0.45, 1.0), "req_catch_kg": (0.5, 1.0), "total_catch_kg": (0.5, 1.0)}


class _AnhWorker(QThread):
    xong = pyqtSignal(int, bytes)

    def __init__(self, sinh, file_path, page, vessel_id, field=None):
        super().__init__()
        self.sinh, self.fp, self.page, self.vid, self.field = sinh, file_path, page, vessel_id, field

    def run(self):
        try:
            from sc_core.ai_extractor import cat_dai_dong
            x0, x1 = VUNG_CAT.get(self.field or "", (0.0, 1.0))
            img = cat_dai_dong(self.fp, self.page, self.vid, dpi=200 if x1 - x0 < 0.8 else 170,
                               x_frac=x1, x_start=x0) or b""
        except Exception:
            img = b""
        self.xong.emit(self.sinh, img)


class _MucDelegate(QStyledItemDelegate):
    """Vẽ mỗi mục trong hàng đợi thành 1 thẻ: ô ký hiệu (× ? ✓) + tiêu đề đậm + dòng phụ nhạt."""

    def sizeHint(self, opt, idx):
        return QSize(opt.rect.width(), 66)

    def paint(self, p: QPainter, opt, idx):
        m = idx.data(Qt.ItemDataRole.UserRole)
        if not m:
            return super().paint(p, opt, idx)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(opt.rect).adjusted(2, 3, -4, -3)
        chon = bool(opt.state & QStyle.StateFlag.State_Selected)
        xong = m.get("trang_thai") in ("da_chap_nhan", "giu_nguyen")
        if chon:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(31, 95, 214, 30))
            p.drawRoundedRect(r.adjusted(-2, -2, 2, 2), 14, 14)
        p.setPen(QPen(QColor(ui.C["primary"] if chon else ui.C["border"]), 1.4 if chon else 1))
        p.setBrush(QColor("#FFFFFF" if chon else "#FBFCFD"))
        p.drawRoundedRect(r, 12, 12)
        loai = m["loai"]
        if xong:
            ky, fg, bg = "✓", "#15803D", "#E8F6EE"
        elif loai == "SAI_LECH":
            ky, fg, bg = "×", "#FFFFFF", "#C2261F"
        else:
            ky, fg, bg = "?", "#9A4A06", "#FEF4E2"
        o = QRectF(r.left() + 12, r.center().y() - 14, 28, 28)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(bg))
        p.drawRoundedRect(o, 8, 8)
        from ui_icons import ve_ky_hieu
        ve_ky_hieu(p, o, {"✓": "ok", "×": "lech", "?": "xem"}[ky], fg)
        tx = r.adjusted(52, 10, -10, -r.height() / 2)
        f1 = QFont(opt.font)
        f1.setBold(True)
        p.setFont(f1)
        p.setPen(QColor(ui.C["muted"] if xong else ui.C["text"]))
        p.drawText(tx, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                   p.fontMetrics().elidedText(m["tieu_de"], Qt.TextElideMode.ElideRight, int(tx.width())))
        f2 = QFont(opt.font)
        f2.setPointSizeF(opt.font.pointSizeF() - 0.8)
        p.setFont(f2)
        p.setPen(QColor(ui.C["text_2"]))
        gt = [str(v) for _, v, _ in m["nguon"][:2] if v not in (None, "")]
        phu = m["nhom"] + (" · " + " ≠ ".join(gt) if len(gt) == 2 else "")
        if xong:
            phu = ("Đã sửa theo SC gốc" if m["trang_thai"] == "da_chap_nhan" else "Giữ nguyên hồ sơ") + " · " + m["nhom"]
        tx2 = r.adjusted(52, r.height() / 2 + 3, -10, -8)
        p.drawText(tx2, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                   p.fontMetrics().elidedText(phu, Qt.TextElideMode.ElideRight, int(tx2.width())))
        p.restore()


KY_HIEU = {"ok": ("✓", "#166534", "#DCFCE7", "Khớp mọi nguồn"), "xem": ("?", "#92400E", "#FEF3C7", "Cần người xem"),
           "lech": ("×", "#FFFFFF", "#B91C1C", "Sai lệch thật"), "na": ("–", "#64748B", "#F1F5F9", "Không áp dụng")}


class _ODelegate(QStyledItemDelegate):
    """Ô ma trận: viên bo góc 36×28 có ký hiệu, nền trắng (giống bản thiết kế)."""

    def paint(self, p: QPainter, opt, idx):
        tt = idx.data(Qt.ItemDataRole.UserRole)
        if not tt:
            return super().paint(p, opt, idx)
        g, fg, bg, _ = KY_HIEU[tt]
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if opt.state & QStyle.StateFlag.State_Selected:
            p.fillRect(opt.rect, QColor("#F2F6FE"))
        o = QRectF(opt.rect.center().x() - 18, opt.rect.center().y() - 14, 36, 28)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(bg))
        p.drawRoundedRect(o, 9, 9)
        from ui_icons import ve_ky_hieu
        ve_ky_hieu(p, QRectF(o.center().x() - 14, o.top(), 28, 28), tt, fg)
        p.restore()


class MaTranWidget(QWidget):
    """Ma trận tàu × tiêu chí: mỗi ô = kết luận của mọi nguồn. Bấm đúp ô -> mở mục trong Cần xử lý."""
    mo_tau = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt6.QtWidgets import QCheckBox
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        hang = QHBoxLayout()
        hang.setSpacing(14)
        self.chk = QCheckBox("Chỉ tàu có vấn đề")
        self.chk.toggled.connect(self._ve)
        hang.addWidget(self.chk)
        from ui_icons import ve_ky_hieu
        for k in ("ok", "xem", "lech", "na"):
            g, fg, bg, nhan = KY_HIEU[k]
            pm = QPixmap(60, 44)
            pm.fill(Qt.GlobalColor.transparent)
            qp = QPainter(pm)
            qp.setRenderHint(QPainter.RenderHint.Antialiasing)
            qp.setPen(Qt.PenStyle.NoPen)
            qp.setBrush(QColor(bg))
            qp.drawRoundedRect(QRectF(0, 0, 60, 44), 16, 16)
            ve_ky_hieu(qp, QRectF(8, 0, 44, 44), k, fg)
            qp.end()
            pm.setDevicePixelRatio(2.0)
            o = QHBoxLayout()
            o.setSpacing(6)
            ic = QLabel()
            ic.setPixmap(pm)
            o.addWidget(ic)
            o.addWidget(QLabel(nhan))
            hang.addLayout(o)
        hang.addStretch(1)
        self.lbl = QLabel("Rê chuột vào ô để xem chi tiết · bấm đúp để xử lý")
        self.lbl.setObjectName("Muted")
        hang.addWidget(self.lbl)
        lay.addLayout(hang)
        self.bang = QTableWidget(0, 0)
        self.bang.verticalHeader().setVisible(False)
        self.bang.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.bang.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.bang.verticalHeader().setDefaultSectionSize(40)
        self.bang.setShowGrid(False)
        self.bang.setStyleSheet("QTableWidget::item { border-bottom: 1px solid #F1F4F8; }")
        self._o_dg = _ODelegate(self.bang)
        self.bang.cellDoubleClicked.connect(self._bam_dup)
        lay.addWidget(self.bang, stretch=1)
        self.mt = {"cot": [], "dong": []}

    def dat_du_lieu(self, ma_tran):
        self.mt = ma_tran or {"cot": [], "dong": []}
        self._ve()

    def _ve(self):
        cot = self.mt["cot"]
        dong = [d for d in self.mt["dong"]
                if not self.chk.isChecked() or any(v[0] in ("xem", "lech") for v in d["o"].values())]
        self._dong = dong
        self.bang.setColumnCount(2 + len(cot))
        self.bang.setHorizontalHeaderLabels(["Số đăng ký tàu", "Số SC"] + [n for _, n in cot])
        self.bang.setRowCount(len(dong))
        for r, d in enumerate(dong):
            self.bang.setItem(r, 0, QTableWidgetItem(d["vessel_id"]))
            self.bang.setItem(r, 1, QTableWidgetItem(d["sc"]))
            for c, (k, nhan) in enumerate(cot):
                tt, ghi = d["o"].get(k, ("na", ""))
                g, fg, bg, ten = KY_HIEU[tt]
                it = QTableWidgetItem(g)
                it.setData(Qt.ItemDataRole.UserRole, tt)  # _ODelegate vẽ viên bo góc
                it.setToolTip(f"{nhan}: {ten}" + (f"\n{ghi}" if ghi else ""))
                self.bang.setItem(r, 2 + c, it)
                self.bang.setItemDelegateForColumn(2 + c, self._o_dg)
        h = self.bang.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for c in range(2, 2 + len(cot)):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.Stretch)
        n_vd = sum(1 for d in self.mt["dong"] if any(v[0] in ("xem", "lech") for v in d["o"].values()))
        self.lbl.setText(f"{len(self.mt['dong'])} tàu · {n_vd} tàu có vấn đề · bấm đúp ô để xử lý")

    def _bam_dup(self, r, c):
        if 0 <= r < len(getattr(self, "_dong", [])):
            self.mo_tau.emit(self._dong[r]["vessel_id"])


class _ChuanBiAnhWorker(QThread):
    """Chạy nền: nạp sẵn mô hình OCR (viec rỗng) hoặc định vị dòng tàu cho mọi mục -> lúc bấm vào mục ảnh hiện ngay."""

    def __init__(self, viec):
        super().__init__()
        self.viec = viec

    def run(self):
        try:
            from sc_core.ai_extractor import cat_dai_dong, _ocr_engine
            _ocr_engine()
            for fp, page, vid in self.viec:
                if self.isInterruptionRequested():
                    return
                try:
                    cat_dai_dong(fp, page, vid, dpi=72)
                except Exception:
                    _ghi_loi_bo_qua()
        except Exception:
            _ghi_loi_bo_qua()


class HangDoiWidget(QWidget):
    da_thay_doi = pyqtSignal(int, int)  # (còn sai lệch, còn cần xem)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.muc, self.out_dir, self._sinh, self._workers, self._loc = [], None, 0, [], "ALL"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        # Bộ lọc
        loc = QHBoxLayout()
        loc.setSpacing(6)
        self.btn_loc = {}
        for k, t in (("ALL", "Tất cả"), ("SAI_LECH", "Sai lệch thật"), ("CAN_XEM", "Cần xem"), ("DA_XU_LY", "Đã xử lý")):
            b = ui.button(t, "chip")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, kk=k: self._dat_loc(kk))
            self.btn_loc[k] = b
            loc.addWidget(b)
        loc.addStretch(1)
        self.lbl_goi_y = QLabel("↑↓ chọn mục · Enter chấp nhận")
        self.lbl_goi_y.setObjectName("Muted")
        loc.addWidget(self.lbl_goi_y)
        lay.addLayout(loc)

        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.setChildrenCollapsible(False)
        self.ds = QListWidget()
        self.ds.setMinimumWidth(330)
        self.ds.setSpacing(1)
        self.ds.setItemDelegate(_MucDelegate(self.ds))
        self.ds.setStyleSheet("QListWidget { background: transparent; border: none; }"
                              " QListWidget::item, QListWidget::item:selected, QListWidget::item:hover"
                              " { background: transparent; border: none; }")
        self.ds.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.ds.currentRowChanged.connect(self._chon)
        sp.addWidget(self.ds)

        # Chi tiết
        cuon = QScrollArea()
        cuon.setWidgetResizable(True)
        cuon.setFrameShape(QFrame.Shape.NoFrame)
        ct = QWidget()
        self.ct = QVBoxLayout(ct)
        self.ct.setContentsMargins(16, 6, 12, 6)
        self.ct.setSpacing(10)
        self.lbl_loai = QLabel()
        self.lbl_tieu_de = QLabel()
        self.lbl_tieu_de.setWordWrap(True)
        self.lbl_tieu_de.setStyleSheet("font-size: 18px; font-weight: 700;")
        self.lbl_vi_tri = QLabel()
        self.lbl_vi_tri.setObjectName("Muted")
        for w in (self.lbl_loai, self.lbl_tieu_de, self.lbl_vi_tri):
            self.ct.addWidget(w)

        cap = QLabel("Số liệu: hồ sơ của bạn và SC gốc")
        cap.setStyleSheet("font-weight: 600;")
        self.ct.addWidget(cap)
        self.bang = QTableWidget(0, 3)
        self.bang.setHorizontalHeaderLabels(["Nguồn", "Số liệu", "Đánh giá"])
        self.bang.verticalHeader().setVisible(False)
        self.bang.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.bang.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.bang.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.bang.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.bang.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.bang.verticalHeader().setDefaultSectionSize(34)
        self.ct.addWidget(self.bang)

        cap2 = QLabel("Ảnh cắt đúng dòng trên SC gốc")
        cap2.setStyleSheet("font-weight: 600;")
        self.ct.addWidget(cap2)
        self.anh = QLabel("—")
        self.anh.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.anh.setMinimumHeight(90)
        self.anh.setStyleSheet(f"background: {ui.C['surface_2']}; border: 1px solid {ui.C['border']}; border-radius: 8px;")
        self.anh.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.ct.addWidget(self.anh)

        self.lbl_ly_do = QLabel()
        self.lbl_ly_do.setWordWrap(True)
        self.lbl_ly_do.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_ly_do.setStyleSheet(f"background: {ui.C['surface_2']}; border: 1px solid {ui.C['border']};"
                                     " border-radius: 8px; padding: 10px;")
        self.ct.addWidget(self.lbl_ly_do)

        cap3 = QLabel("Bấm nút sẽ làm gì")
        cap3.setStyleSheet("font-weight: 600;")
        self.ct.addWidget(cap3)
        self.lbl_ket_qua = QLabel()
        self.lbl_ket_qua.setWordWrap(True)
        self.lbl_ket_qua.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_ket_qua.setStyleSheet(f"background: {ui.C['primary_soft']}; border: 1px solid #D5E3FB;"
                                       " border-radius: 10px; padding: 12px 14px; line-height: 150%;")
        self.ct.addWidget(self.lbl_ket_qua)

        nut = QHBoxLayout()
        nut.setSpacing(8)
        self.btn_ok = ui.button("✓   Sửa theo SC gốc   ⏎", "primary", "xl")
        self.btn_ok.setToolTip("Enter — lấy giá trị trên SC gốc: ghi vào file XNNL đã sửa và Sổ tàu")
        self.btn_ok.clicked.connect(self.chap_nhan)
        self.btn_xem = ui.button("Giữ nguyên hồ sơ", None, "lg")
        self.btn_xem.setToolTip("Hồ sơ đúng, SC gốc là ngoại lệ — KHÔNG sửa ô này trong file XNNL đã sửa")
        self.btn_xem.clicked.connect(lambda: self._danh_dau("giu_nguyen"))
        self.btn_mo = ui.button("  Mở SC gốc", "ghost", "lg")
        from ui_icons import icon as _icon
        self.btn_mo.setIcon(_icon("external", ui.C["text_2"]))
        self.btn_mo.clicked.connect(self._mo_sc)
        for b in (self.btn_ok, self.btn_xem, self.btn_mo):
            nut.addWidget(b)
        nut.addStretch(1)
        self.ct.addLayout(nut)
        self.ct.addStretch(1)
        cuon.setWidget(ct)
        sp.addWidget(cuon)
        sp.setStretchFactor(0, 2)
        sp.setStretchFactor(1, 5)
        lay.addWidget(sp, stretch=1)

        self.lbl_trong = QLabel("✓  Chưa có kết quả. Chọn thư mục lô hàng rồi bấm Bắt đầu đối chiếu.")
        self.lbl_trong.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_trong.setStyleSheet("font-size: 15px; padding: 30px;")
        lay.addWidget(self.lbl_trong)
        self._sp = sp
        QShortcut(QKeySequence(Qt.Key.Key_Return), self.ds, activated=self.chap_nhan)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self.ds, activated=self.chap_nhan)
        self._hien_trong(True)
        self.btn_loc["ALL"].setChecked(True)
        # Nạp sẵn mô hình OCR (~vài giây) trong lúc người dùng còn chọn hồ sơ / chờ đối chiếu
        self._nap_ocr = _ChuanBiAnhWorker([])
        self._nap_ocr.start()

    # ------------------------------------------------------------ dữ liệu
    def dat_du_lieu(self, hang_doi: dict, out_dir: str = None):
        self.muc = list(hang_doi.get("muc") or [])
        for m in self.muc:
            m.setdefault("trang_thai", "")
        self.out_dir = out_dir
        viec, seen = [], set()
        for m in self.muc:
            k = (m.get("sc_file"), m.get("page"))
            if m.get("sc_file") and m.get("page") and m.get("vessel_id") and k not in seen:
                seen.add(k)
                viec.append((m["sc_file"], m["page"], m["vessel_id"]))
        if viec:
            self._chuan_bi = _ChuanBiAnhWorker(viec)
            self._chuan_bi.start()
        if not self.muc:
            self.lbl_trong.setText("✓  Không có mục nào cần xử lý — mọi dữ liệu đã tự duyệt (khớp giữa các nguồn).")
            self.lbl_trong.setStyleSheet(f"font-size: 15px; padding: 30px; color: {ui.C['success']}; font-weight: 600;")
        self._hien_trong(not self.muc)
        self._dat_loc("ALL")

    def _hien_trong(self, trong):
        self._sp.setVisible(not trong)
        self.lbl_trong.setVisible(trong)

    def _loai_hien(self, m):
        return "DA_XU_LY" if m.get("trang_thai") in ("da_chap_nhan", "giu_nguyen") else m["loai"]

    def giu_nguyen_set(self):
        """(số tàu, trường) người dùng chọn 'Giữ nguyên hồ sơ' ở mục XNNL ↔ SC -> không sửa trong file XNNL đã sửa."""
        return {(m["vessel_id"], m["field"]) for m in self.muc
                if m.get("trang_thai") == "giu_nguyen" and m.get("nhom") == "XNNL ↔ SC" and m.get("vessel_id") and m.get("field")}

    def _dat_loc(self, k):
        self._loc = k
        for kk, b in self.btn_loc.items():
            b.setChecked(kk == k)
        self._ve_ds()

    def _ve_ds(self):
        self.ds.blockSignals(True)
        self.ds.clear()
        self._hien = [m for m in self.muc if self._loc == "ALL" or self._loai_hien(m) == self._loc]
        for m in self._hien:
            it = QListWidgetItem(m["tieu_de"])  # chữ để trợ năng/tìm kiếm; delegate vẽ thành thẻ
            it.setData(Qt.ItemDataRole.UserRole, m)
            it.setSizeHint(QSize(300, 66))
            self.ds.addItem(it)
        self.ds.blockSignals(False)
        for k, b in self.btn_loc.items():
            n = len(self.muc) if k == "ALL" else sum(1 for m in self.muc if self._loai_hien(m) == k)
            b.setText({"ALL": "Tất cả", "SAI_LECH": "Sai lệch thật", "CAN_XEM": "Cần xem", "DA_XU_LY": "Đã xử lý"}[k] + f" ({n})")
        if self._hien:
            self.ds.setCurrentRow(0)
            self._chon(0)
        self.da_thay_doi.emit(sum(1 for m in self.muc if self._loai_hien(m) == "SAI_LECH"),
                              sum(1 for m in self.muc if self._loai_hien(m) == "CAN_XEM"))

    def _chon(self, i):
        if i < 0 or i >= len(getattr(self, "_hien", [])):
            return
        m = self._hien[i]
        mau, nen, nhan = MAU[self._loai_hien(m)]
        self.lbl_loai.setText(nhan.upper())
        self.lbl_loai.setStyleSheet(f"color: {mau}; background: {nen}; font-weight: 800; font-size: 11.5px;"
                                    " padding: 4px 10px; border-radius: 10px;")
        self.lbl_loai.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.lbl_tieu_de.setText(m["tieu_de"])
        vt = [m["nhom"]]
        if m.get("sc_number"):
            vt.append(f"SC {m['sc_number']}")
        if m.get("page"):
            vt.append(f"trang {m['page']}")
        self.lbl_vi_tri.setText(" · ".join(vt))
        self.bang.setRowCount(len(m["nguon"]))
        for r, (ten, gt, tt) in enumerate(m["nguon"]):
            fg, bg, nhan_tt = MAU_NGUON.get(tt, MAU_NGUON["tham_khao"])
            for c, v in enumerate((ten, "" if gt is None else str(gt), nhan_tt)):
                it = QTableWidgetItem(v)
                it.setBackground(QColor(bg))
                if c == 2:
                    it.setForeground(QColor(fg))
                self.bang.setItem(r, c, it)
        self.bang.setFixedHeight(self.bang.horizontalHeader().sizeHint().height() + 34 * len(m["nguon"]) + 6)
        ly = "".join(f"• {x}<br>" for x in m["ly_do"])
        if m.get("de_xuat"):
            ly += f"<br><b>Đề xuất:</b> {m['de_xuat']}"
        self.lbl_ly_do.setText(ly or "—")
        co_sc = bool(m.get("sc_file") and m.get("page"))
        self.btn_mo.setEnabled(co_sc)
        self.btn_ok.setEnabled(True)
        self._ve_ket_qua(m)
        self.anh.setPixmap(QPixmap())
        if co_sc and m.get("vessel_id"):
            self.anh.setText("Đang cắt ảnh dòng tàu trên SC gốc…")
            self._sinh += 1
            w = _AnhWorker(self._sinh, m["sc_file"], m["page"], m["vessel_id"], m.get("field"))
            w.xong.connect(self._nhan_anh)
            self._workers = [x for x in self._workers if x.isRunning()] + [w]
            w.start()
        else:
            self.anh.setText("Mục này không gắn với dòng tàu trên SC scan.")

    def _ve_ket_qua(self, m):
        """Nói rõ: số liệu hồ sơ là gì, SC gốc là gì, mỗi nút sẽ ghi gì vào file nào."""
        import html as _h
        ho_so = next((str(v) for _, v, t in m["nguon"] if t == "lech" and v not in (None, "")), "")
        ten_hs = next((n for n, _, t in m["nguon"] if t == "lech"), "Hồ sơ").replace("Hồ sơ · ", "")
        sc = next((str(v) for _, v, t in m["nguon"] if t == "ok" and v not in (None, "")), "") \
            or str(m.get("gia_tri_sc") or "")
        n_hs, n_sc = _h.escape(ho_so)[:80], _h.escape(sc)[:80]
        xong = {"da_chap_nhan": "✓ Đã chọn: theo SC gốc", "giu_nguyen": "✓ Đã chọn: giữ hồ sơ"}.get(m.get("trang_thai"), "")
        if m["nhom"] == "XNNL ↔ SC":
            self.btn_ok.setText("✓   Sửa XNNL theo SC gốc   ⏎")
            self.btn_xem.setText("Giữ nguyên XNNL")
            txt = (f"<b>Sửa XNNL theo SC gốc</b> → file <b>XNNL đã sửa</b> ghi <b>{n_sc or '(giá trị SC)'}</b>"
                   + (f" thay cho <s>{n_hs}</s>" if n_hs else "") + "; ghi thêm vào Sổ tàu.<br>"
                   f"<b>Giữ nguyên XNNL</b> → file XNNL đã sửa giữ <b>{n_hs or '(giá trị hồ sơ)'}</b> như hồ sơ gốc.<br>"
                   "<span style='color:#475569'>File XNNL gốc của bạn không bị đụng tới; file đã sửa nằm ở nút “XNNL đã sửa”.</span>")
        else:
            file_goc = ten_hs or "hồ sơ"
            self.btn_ok.setText("✓   SC gốc đúng   ⏎")
            self.btn_xem.setText("Hồ sơ đúng")
            txt = (f"Phần mềm <b>không tự sửa file {_h.escape(file_goc)}</b> — 2 nút chỉ ghi nhận kết luận và đưa mục vào “Đã xử lý”.<br>"
                   f"<b>SC gốc đúng</b> → bạn cần sửa tay {_h.escape(file_goc)} thành <b>{n_sc or '(giá trị SC)'}</b>"
                   + (f" (đang ghi <s>{n_hs}</s>)" if n_hs else "") + "; số liệu SC được ghi vào Sổ tàu.<br>"
                   "<b>Hồ sơ đúng</b> → chấp nhận khác biệt (vd SC cảng ghi sai); không làm gì thêm.")
        if xong:
            txt = f"<b style='color:#15803D'>{xong}</b><br>" + txt
        self.lbl_ket_qua.setText(txt)

    def _nhan_anh(self, sinh, img):
        if sinh != self._sinh:
            return
        if not img:
            self.anh.setText("Không định vị được dòng tàu trên SC — bấm 'Mở SC gốc' để xem cả trang.")
            return
        pm = QPixmap()
        pm.loadFromData(img)
        w = max(400, self.anh.width() - 16)
        pm = pm.scaledToWidth(w, Qt.TransformationMode.SmoothTransformation)
        if pm.height() > 230:  # dải hẹp mà cao quá thì giới hạn chiều cao, giữ tỉ lệ
            pm = pm.scaledToHeight(230, Qt.TransformationMode.SmoothTransformation)
        self.anh.setPixmap(pm)

    # ------------------------------------------------------------ hành động
    def _hien_tai(self):
        i = self.ds.currentRow()
        return self._hien[i] if 0 <= i < len(getattr(self, "_hien", [])) else None

    def chap_nhan(self):
        m = self._hien_tai()
        if not m or not self.btn_ok.isEnabled():
            return
        try:
            from sc_core import so_tau
            if m.get("field") in so_tau.TRUONG and m.get("gia_tri_sc") not in (None, ""):
                so_tau.ghi_nhan(m["vessel_id"], m["field"], m["gia_tri_sc"], "người duyệt")
        except Exception as e:
            print(f"Không ghi được sổ tàu: {e}")
        self._danh_dau("da_chap_nhan")

    def _danh_dau(self, tt):
        m = self._hien_tai()
        if not m:
            return
        i = self.ds.currentRow()
        m["trang_thai"] = tt
        self._ghi_nhat_ky(m, tt)
        self._ve_ds()
        if self._hien:
            j = min(i, len(self._hien) - 1)
            self.ds.setCurrentRow(j)
            self._chon(j)

    def _ghi_nhat_ky(self, m, tt):
        if not self.out_dir:
            return
        try:
            os.makedirs(self.out_dir, exist_ok=True)
            fp = os.path.join(self.out_dir, "NhatKy_Duyet.jsonl")
            with open(fp, "a", encoding="utf-8") as f:
                f.write(json.dumps({"luc": datetime.now().isoformat(timespec="seconds"), "hanh_dong": tt,
                                    "tieu_de": m["tieu_de"], "nhom": m["nhom"], "vessel_id": m.get("vessel_id"),
                                    "field": m.get("field"), "gia_tri_sc": m.get("gia_tri_sc"),
                                    "nguon": [[a, str(b), c] for a, b, c in m["nguon"]]}, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Không ghi được nhật ký duyệt: {e}")

    def chon_tau(self, vessel_id):
        """Chọn mục đầu tiên của tàu (dùng khi bấm đúp ở ma trận)."""
        from sc_core.reconciler import clean_vessel_key
        vk = clean_vessel_key(vessel_id)
        self._dat_loc("ALL")
        for i, m in enumerate(self._hien):
            if clean_vessel_key(m.get("vessel_id")) == vk:
                self.ds.setCurrentRow(i)
                self._chon(i)
                self.ds.setFocus()
                return True
        return False

    def _mo_sc(self):
        m = self._hien_tai()
        if m and m.get("sc_file") and os.path.exists(m["sc_file"]):
            try:
                os.startfile(m["sc_file"])
            except Exception:
                _ghi_loi_bo_qua()
