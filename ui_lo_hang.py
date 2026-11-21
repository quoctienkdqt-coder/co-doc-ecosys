"""
TRANG CHỦ "LÔ HÀNG" (thiết kế Hải trình v3.4)
- Thả / chọn / dán thư mục lô -> thẻ "Lô đang mở" hiện 5 loại chứng từ đã nhận diện + nút "Đọc & đối chiếu ngay".
- Danh sách lô gần đây: icon theo trạng thái, thanh kết quả 3 màu (Tự duyệt / Cần xem / Sai lệch), Mở · Chạy lại ngay trên dòng.
"""
import os

from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QSize
from PyQt6.QtGui import QColor, QPainter, QFont, QPen
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QLineEdit, QAbstractItemView, QStyledItemDelegate, QStyle, QSizePolicy
)

import ui_theme as ui
from ui_icons import pixmap, icon
from sc_core import lo_gan_day

MAU_TT = {"lech": ("#C2261F", "#FDECEC"), "xem": ("#B45309", "#FEF4E2"), "ok": ("#15803D", "#E8F6EE"),
          "chua": ("#475569", "#EEF2F6")}


def _trang_thai(x):
    if x.get("sai_lech"):
        return "lech", f"{x['sai_lech']} sai lệch thật" + (f" · {x['can_xem']} cần xem" if x.get("can_xem") else "")
    if x.get("can_xem"):
        return "xem", f"{x['can_xem']} mục cần xem"
    if x.get("tu_duyet") is not None:
        return "ok", f"Tự duyệt toàn bộ · {x.get('tu_duyet', 0)}"
    return "chua", "Chưa đối chiếu"


class _LoDelegate(QStyledItemDelegate):
    """Cột 0: ô icon màu theo trạng thái + tên lô (đậm) + chứng từ (nhạt). Cột 2: thanh kết quả 3 màu + chữ."""

    def paint(self, p: QPainter, opt, idx):
        x = idx.data(Qt.ItemDataRole.UserRole)
        if not x:
            return super().paint(p, opt, idx)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if opt.state & QStyle.StateFlag.State_Selected:
            p.fillRect(opt.rect, QColor("#F2F6FE"))
        p.setPen(QPen(QColor("#EEF2F6"), 1))
        p.drawLine(opt.rect.bottomLeft(), opt.rect.bottomRight())
        r = opt.rect.adjusted(14, 0, -10, 0)
        tt, nhan = _trang_thai(x)
        fg, bg = MAU_TT[tt]
        if idx.column() == 0:
            o = QRectF(r.left(), r.center().y() - 19, 38, 38)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(bg))
            p.drawRoundedRect(o, 10, 10)
            p.drawPixmap(int(o.left() + 9), int(o.top() + 9), pixmap("folder", fg, 20))
            f = QFont(opt.font)
            f.setBold(True)
            f.setPointSizeF(opt.font.pointSizeF() + 1)
            p.setFont(f)
            p.setPen(QColor(ui.C["text"]))
            tx = r.adjusted(52, 8, 0, -r.height() // 2)
            p.drawText(tx, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, x.get("ten", ""))
            f2 = QFont(opt.font)
            f2.setPointSizeF(opt.font.pointSizeF() - 0.5)
            p.setFont(f2)
            p.setPen(QColor(ui.C["text_2"] if os.path.isdir(x["path"]) else ui.C["muted"]))
            phu = x.get("chung_tu") or x["path"]
            if not os.path.isdir(x["path"]):
                phu = "Không truy cập được thư mục (ổ mạng?) · " + phu
            tx2 = r.adjusted(52, r.height() // 2 + 2, 0, -6)
            p.drawText(tx2, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                       p.fontMetrics().elidedText(phu, Qt.TextElideMode.ElideRight, tx2.width()))
        elif idx.column() == 2:
            ok, xem, lech = x.get("tu_duyet") or 0, x.get("can_xem") or 0, x.get("sai_lech") or 0
            tong = ok + xem + lech
            bar = QRectF(r.left(), r.center().y() - 11, r.width() - 6, 8)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#EEF2F6"))
            p.drawRoundedRect(bar, 4, 4)
            if tong:
                xx = bar.left()
                for v, c in ((ok, "#15803D"), (xem, "#D97706"), (lech, "#C2261F")):
                    if v:
                        w = bar.width() * v / tong
                        p.setBrush(QColor(c))
                        p.drawRoundedRect(QRectF(xx, bar.top(), w, bar.height()), 4, 4)
                        xx += w
            f = QFont(opt.font)
            f.setBold(True)
            f.setPointSizeF(opt.font.pointSizeF() - 0.5)
            p.setFont(f)
            p.setPen(QColor(fg))
            p.drawText(QRectF(r.left(), bar.bottom() + 4, r.width(), 20), Qt.AlignmentFlag.AlignLeft, nhan)
        p.restore()


class LoHangWidget(QWidget):
    mo_lo = pyqtSignal(str, bool)   # (thư mục, chạy đối chiếu ngay?)
    xem_lo = pyqtSignal(str)        # thư mục vừa thả/chọn -> app nhận diện chứng từ rồi gọi hien_lo_dang_mo()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._lo = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 26, 30, 20)
        lay.setSpacing(18)

        # ---------------- tiêu đề
        dau = QHBoxLayout()
        cot = QVBoxLayout()
        cot.setSpacing(2)
        t = QLabel("Lô hàng")
        t.setStyleSheet("font-size: 27px; font-weight: 800;")
        s = QLabel("Thả thư mục hồ sơ vào — phần mềm tự nhận chứng từ, đọc và đối chiếu.")
        s.setObjectName("PageSubtitle")
        cot.addWidget(t)
        cot.addWidget(s)
        dau.addLayout(cot, stretch=1)
        b = ui.button("  Chọn thư mục", None)
        b.setIcon(icon("folder", ui.C["text"]))
        b.clicked.connect(self._chon)
        dau.addWidget(b, alignment=Qt.AlignmentFlag.AlignVCenter)
        lay.addLayout(dau)

        # ---------------- vùng thả (khi chưa mở lô)
        self.vung = QFrame()
        self.vung.setObjectName("VungTha")
        self._kieu_vung(False)
        vl = QHBoxLayout(self.vung)
        vl.setContentsMargins(26, 24, 26, 24)
        vl.setSpacing(20)
        ic = QLabel()
        ic.setPixmap(pixmap("folder", ui.C["primary"], 40, width=1.6))
        ic.setFixedSize(64, 64)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet(f"background: {ui.C['primary_soft']}; border-radius: 16px;")
        vl.addWidget(ic)
        c2 = QVBoxLayout()
        c2.setSpacing(6)
        t1 = QLabel("Kéo thả thư mục lô hàng vào đây")
        t1.setStyleSheet("font-size: 18px; font-weight: 700;")
        t2 = QLabel("Hoặc dán đường dẫn (kể cả ổ mạng W:\\…) rồi Enter. Không cần chọn lẻ từng file — chỉ sửa khi phần mềm nhận sai.")
        t2.setObjectName("Muted")
        t2.setWordWrap(True)
        hang = QHBoxLayout()
        self.o_duong_dan = QLineEdit()
        self.o_duong_dan.setPlaceholderText("Dán đường dẫn thư mục lô hàng…")
        self.o_duong_dan.setMinimumHeight(38)
        self.o_duong_dan.returnPressed.connect(self._mo_tu_o)
        hang.addWidget(self.o_duong_dan, stretch=1)
        bm = ui.button("Mở lô", "soft")
        bm.clicked.connect(self._mo_tu_o)
        hang.addWidget(bm)
        c2.addWidget(t1)
        c2.addWidget(t2)
        c2.addLayout(hang)
        vl.addLayout(c2, stretch=1)
        lay.addWidget(self.vung)

        # ---------------- thẻ "Lô đang mở"
        self.the_lo = QFrame()
        self.the_lo.setObjectName("OpenLot")
        ui.add_shadow(self.the_lo, blur=24, y=4, alpha=16)
        tl = QVBoxLayout(self.the_lo)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)
        hero = QFrame()
        hero.setObjectName("HeroCard")
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(24, 20, 24, 20)
        hl.setSpacing(18)
        hic = QLabel()
        hic.setPixmap(pixmap("folder_check", "#FFFFFF", 26))
        hic.setFixedSize(52, 52)
        hic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hic.setStyleSheet(f"background: {ui.C['primary']}; border-radius: 14px;")
        hl.addWidget(hic)
        hc = QVBoxLayout()
        hc.setSpacing(2)
        e = QLabel("LÔ ĐANG MỞ")
        e.setObjectName("Eyebrow")
        self.lbl_ten_lo = QLabel()
        self.lbl_ten_lo.setObjectName("HeroTitle")
        self.lbl_duong_dan = QLabel()
        self.lbl_duong_dan.setObjectName("Muted")
        for w in (e, self.lbl_ten_lo, self.lbl_duong_dan):
            hc.addWidget(w)
        hl.addLayout(hc, stretch=1)
        self.b_doi = ui.button("Đổi lô", "ghost")
        self.b_doi.clicked.connect(self.dong_lo)
        self.b_xem = ui.button("Xem từng file", None, "lg")
        self.b_xem.clicked.connect(lambda: self._lo and self.mo_lo.emit(self._lo, False))
        self.b_chay = ui.button("  Đọc && đối chiếu ngay", "primary", "xl")
        self.b_chay.setIcon(icon("play", "#FFFFFF"))
        self.b_chay.clicked.connect(lambda: self._lo and self.mo_lo.emit(self._lo, True))
        for w in (self.b_doi, self.b_xem, self.b_chay):
            hl.addWidget(w, alignment=Qt.AlignmentFlag.AlignVCenter)
        tl.addWidget(hero)
        self.o_ct = QHBoxLayout()
        self.o_ct.setSpacing(0)
        self.o_ct.setContentsMargins(0, 0, 0, 0)
        tl.addLayout(self.o_ct)
        self.lbl_canh_bao = QLabel()
        self.lbl_canh_bao.setWordWrap(True)
        self.lbl_canh_bao.setStyleSheet(f"color: {ui.C['warning']}; font-weight: 600; padding: 0 24px 16px 24px;")
        tl.addWidget(self.lbl_canh_bao)
        lay.addWidget(self.the_lo)
        self.the_lo.setVisible(False)

        # ---------------- gần đây
        the = ui.card()
        gl = QVBoxLayout(the)
        gl.setContentsMargins(0, 10, 0, 6)
        gl.setSpacing(6)
        hd = QHBoxLayout()
        hd.setContentsMargins(20, 0, 20, 4)
        lb = QLabel("Gần đây")
        lb.setStyleSheet("font-size: 17px; font-weight: 700;")
        hd.addWidget(lb)
        hd.addSpacing(10)
        self.btn_loc = {}
        for k, t in (("ALL", "Tất cả"), ("lech", "Có sai lệch"), ("xem", "Cần xem"), ("ok", "Tự duyệt hết")):
            bb = ui.button(t, "chip")
            bb.setCheckable(True)
            bb.clicked.connect(lambda _=False, kk=k: self._dat_loc(kk))
            self.btn_loc[k] = bb
            hd.addWidget(bb)
        hd.addStretch(1)
        self.lbl_dem = QLabel()
        self.lbl_dem.setObjectName("Muted")
        hd.addWidget(self.lbl_dem)
        gl.addLayout(hd)

        self.bang = QTableWidget(0, 5)
        self.bang.setHorizontalHeaderLabels(["Lô hàng", "Giấy SC", "Kết quả", "Cập nhật", ""])
        self.bang.verticalHeader().setVisible(False)
        self.bang.setShowGrid(False)
        self.bang.setFrameShape(QFrame.Shape.NoFrame)
        self.bang.setStyleSheet("QTableWidget { border: none; } QTableWidget::item { border-bottom: 1px solid #EEF2F6; }")
        self.bang.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.bang.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.bang.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.bang.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bang.verticalHeader().setDefaultSectionSize(64)
        self._dg = _LoDelegate(self.bang)
        self.bang.setItemDelegateForColumn(0, self._dg)
        self.bang.setItemDelegateForColumn(2, self._dg)
        h = self.bang.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.bang.setColumnWidth(1, 230)
        self.bang.setColumnWidth(2, 250)
        self.bang.setColumnWidth(4, 132)
        h.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.bang.cellDoubleClicked.connect(lambda r, c: self._mo_dong(r, False))
        gl.addWidget(self.bang, stretch=1)
        self.lbl_trong = QLabel("Chưa có lô nào. Thả thư mục lô hàng vào khung phía trên để bắt đầu.")
        self.lbl_trong.setObjectName("Muted")
        self.lbl_trong.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_trong.setMinimumHeight(80)
        gl.addWidget(self.lbl_trong)
        lay.addWidget(the, stretch=1)
        self._loc = "ALL"
        self.lam_moi()

    # ------------------------------------------------------------ vùng thả
    def _kieu_vung(self, keo):
        mau = ui.C["primary"] if keo else "#9DB9EC"
        nen = ui.C["primary_soft"] if keo else ui.C["surface"]
        self.vung.setStyleSheet(f"QFrame#VungTha {{ border: 2px dashed {mau}; border-radius: 16px; background: {nen}; }}")

    @staticmethod
    def _thu_muc(e):
        for u in e.mimeData().urls():
            p = u.toLocalFile()
            if p and os.path.isdir(p):
                return p
            if p and os.path.isfile(p):
                return os.path.dirname(p)
        return None

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and self._thu_muc(e):
            e.acceptProposedAction()
            self._kieu_vung(True)

    def dragLeaveEvent(self, e):
        self._kieu_vung(False)

    def dropEvent(self, e):
        self._kieu_vung(False)
        p = self._thu_muc(e)
        if p:
            self.xem_lo.emit(p)

    def _chon(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục hồ sơ lô hàng")
        if d:
            self.xem_lo.emit(d)

    def _mo_tu_o(self):
        p = self.o_duong_dan.text().strip().strip('"')
        if p and os.path.isdir(p):
            self.xem_lo.emit(p)
        elif p:
            self.o_duong_dan.clear()
            self.o_duong_dan.setPlaceholderText("Không tìm thấy thư mục này — kiểm tra lại đường dẫn / ổ mạng")

    # ------------------------------------------------------------ thẻ lô đang mở
    def hien_lo_dang_mo(self, path, chung_tu):
        """chung_tu: [{ten, so, ghi, co}] (từ trang SC: tom_tat_chung_tu())."""
        self._lo = path
        self.lbl_ten_lo.setText(os.path.basename(path) or path)
        self.lbl_duong_dan.setText(path)
        while self.o_ct.count():
            it = self.o_ct.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for i, c in enumerate(chung_tu):
            o = QFrame()
            o.setObjectName("DocTile")
            if i == len(chung_tu) - 1:
                o.setStyleSheet("QFrame#DocTile { border-right: none; }")
            ol = QVBoxLayout(o)
            ol.setContentsMargins(20, 16, 18, 16)
            ol.setSpacing(4)
            d = QHBoxLayout()
            d.setSpacing(8)
            dau = QLabel("✓" if c["co"] else "–")
            dau.setFixedSize(22, 22)
            dau.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fg, bg = (("#15803D", "#E8F6EE") if c["co"] else ("#7A8799", "#EEF2F6"))
            dau.setStyleSheet(f"background: {bg}; color: {fg}; border-radius: 11px; font-weight: 800; font-size: 12px;")
            ten = QLabel(c["ten"])
            ten.setStyleSheet(f"font-size: 12.5px; font-weight: 600; color: {ui.C['text_2']};")
            d.addWidget(dau)
            d.addWidget(ten, stretch=1)
            ol.addLayout(d)
            so = QLabel(c["so"])
            so.setStyleSheet(f"font-size: 21px; font-weight: 800; color: {ui.C['text'] if c['co'] else ui.C['muted']};")
            ol.addWidget(so)
            ghi = QLabel(c["ghi"])
            ghi.setObjectName("Muted")
            ol.addWidget(ghi)
            self.o_ct.addWidget(o, stretch=1)
        thieu_sc = not chung_tu or not chung_tu[0]["co"]
        thieu_ex = not any(c["co"] for c in chung_tu[1:4:2]) and not (len(chung_tu) > 4 and chung_tu[4]["co"])
        canh = []
        if thieu_sc:
            canh.append("Chưa thấy file SC scan (PDF có chữ 'SC' trong tên).")
        if thieu_ex:
            canh.append("Cần ít nhất Bảng kê, XNNL hoặc SC Excel để đối chiếu.")
        self.lbl_canh_bao.setText("⚠  " + " ".join(canh) if canh else "")
        self.lbl_canh_bao.setVisible(bool(canh))
        self.b_chay.setEnabled(not canh)
        self.vung.setVisible(False)
        self.the_lo.setVisible(True)

    def dong_lo(self):
        self._lo = None
        self.the_lo.setVisible(False)
        self.vung.setVisible(True)

    # ------------------------------------------------------------ gần đây
    def _dat_loc(self, k):
        self._loc = k
        self.lam_moi()

    def lam_moi(self):
        ds = lo_gan_day.doc_ds()
        for k, b in self.btn_loc.items():
            n = len(ds) if k == "ALL" else sum(1 for x in ds if _trang_thai(x)[0] == k)
            b.setText({"ALL": "Tất cả", "lech": "Có sai lệch", "xem": "Cần xem", "ok": "Tự duyệt hết"}[k] + f"  {n}")
            b.setChecked(k == self._loc)
        self._ds = [x for x in ds if self._loc == "ALL" or _trang_thai(x)[0] == self._loc]
        self.lbl_dem.setText(f"{len(ds)} lô · lưu riêng trên máy này" if ds else "")
        self.bang.setRowCount(len(self._ds))
        for r, x in enumerate(self._ds):
            it0 = QTableWidgetItem()
            it0.setData(Qt.ItemDataRole.UserRole, x)
            it0.setToolTip(x["path"])
            self.bang.setItem(r, 0, it0)
            so_sc = " · ".join(s.split("/")[0] for s in (x.get("so_sc") or []))
            it1 = QTableWidgetItem(so_sc or "—")
            it1.setToolTip(", ".join(x.get("so_sc") or []))
            it1.setForeground(QColor("#334155"))
            self.bang.setItem(r, 1, it1)
            it2 = QTableWidgetItem()
            it2.setData(Qt.ItemDataRole.UserRole, x)
            self.bang.setItem(r, 2, it2)
            it3 = QTableWidgetItem(x.get("cap_nhat", ""))
            it3.setForeground(QColor(ui.C["text_2"]))
            self.bang.setItem(r, 3, it3)
            nut = QWidget()
            nl = QHBoxLayout(nut)
            nl.setContentsMargins(4, 12, 12, 12)
            nl.setSpacing(6)
            bm = ui.button("Mở", "soft", "sm")
            bm.clicked.connect(lambda _=False, p=x["path"]: self._mo_path(p, False))
            bc = ui.button("", None, "sm", tooltip="Chạy lại đối chiếu lô này")
            bc.setIcon(icon("refresh", ui.C["text_2"]))
            bc.setFixedWidth(36)
            bc.clicked.connect(lambda _=False, p=x["path"]: self._mo_path(p, True))
            ok = os.path.isdir(x["path"])
            bm.setEnabled(ok)
            bc.setEnabled(ok)
            nl.addWidget(bm)
            nl.addWidget(bc)
            self.bang.setCellWidget(r, 4, nut)
        self.lbl_trong.setVisible(not self._ds)
        self.bang.setVisible(bool(self._ds))

    def _mo_path(self, p, chay):
        if os.path.isdir(p):
            self.mo_lo.emit(p, chay)

    def _mo_dong(self, r, chay):
        if 0 <= r < len(self._ds):
            self._mo_path(self._ds[r]["path"], chay)
