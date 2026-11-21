"""
LÀM GỌN TRANG KHAI BÁO C/O eCoSys theo thiết kế "Hải trình" — CHỈ đổi giao diện, không đụng logic.
Gọi 1 lần sau khi dựng trang:  lam_gon_trang_co(page_co, co_app)

- Tab: tên ngắn + icon nét (hết tràn/cắt chữ), tên đầy đủ ở tooltip.
- Khung nhập liệu (QGroupBox + QFormLayout): nhãn nằm TRÊN ô nhập, xếp 2 khung / hàng.
- Nút: bỏ emoji, chữ thường, icon nét theo chức năng; 1 nút chính (Trích xuất / Sao chép JSON) màu cobalt.
- Dòng gợi ý 💡 -> chữ nhạt có icon; bỏ chữ đỏ / màu lẻ.
"""
import re

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QWidget, QTabWidget, QGroupBox, QFormLayout, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QCheckBox, QScrollArea, QSizePolicy
)

import ui_theme as ui
from ui_icons import icon

# (tên ngắn, icon) theo thứ tự tab của COExtractorApp
TAB_MOI = [("Doanh nghiệp", "building"), ("Vận tải && Hóa đơn", "ship"), ("Hàng hóa", "box"),
           ("Đính kèm", "paperclip"), ("Xuất JSON", "code"), ("Trợ lý AI", "sparkle"), ("Xem chứng từ", "eye")]

# từ khóa trong chữ nút -> (chữ mới hoặc None = giữ, icon)
NUT = [
    ("BẮT ĐẦU TRÍCH XUẤT", "Trích xuất bằng AI", "sparkle"),
    ("SAO CHÉP JSON", "Sao chép JSON", "copy"),
    ("Nạp dữ liệu mẫu", None, "flask"),
    ("Thêm", None, "plus"), ("Phóng to", None, "plus"),
    ("Xóa chọn", None, "minus"), ("Xóa dòng", None, "minus"), ("Bỏ tệp", None, "minus"), ("Thu nhỏ", None, "minus"),
    ("Xóa hết", None, "trash"),
    ("Chỉ Đơn", "Chỉ Đơn + Invoice", "target"),
    ("AI đọc hết", None, "list_check"),
    ("Lưu file", None, "save"),
    ("Tính lại", None, "refresh"), ("Đồng bộ", None, "refresh"), ("Quét lại", None, "refresh"), ("Cập nhật", None, "refresh"),
    ("nhận diện", None, "search"),
    ("Gom", None, "folder"),
    ("Ký số", None, "pen"),
    ("Hướng dẫn", None, "book"),
    ("Gửi", None, "send"),
    ("Trang trước", "Trang trước", "chevron_l"), ("Trang tiếp", "Trang tiếp", "chevron_r"),
]

# Chữ nút quá dài (bị cắt khi dồn 1 hàng) -> chữ ngắn; tên đầy đủ chuyển vào tooltip
RUT_GON = [
    ("Thêm tệp chứng từ", "Thêm tệp"), ("Bỏ tệp khỏi danh sách", "Bỏ tệp"),
    ("Tự động nhận diện loại chứng từ", "Nhận diện loại"), ("Gom & Chuẩn hóa thư mục", "Chuẩn hóa thư mục"),
    ("Ký số hàng loạt", "Ký số hàng loạt"), ("Hướng dẫn đặt tên chứng từ", "Cách đặt tên"),
    ("Quét lại USB Token", "Quét lại Token"), ("Đồng bộ dữ liệu vào JSON", "Đồng bộ JSON"),
    ("Tính lại tổng FOB", "Tính lại FOB"),
]

_EMOJI_DAU = re.compile(r"^[^\w(\"'“]+", re.UNICODE)


def _bo_emoji(t: str) -> str:
    t = _EMOJI_DAU.sub("", t or "").strip()
    return re.sub(r"\s*[◀▶]\s*", " ", t).strip()


def _nut(b: QPushButton):
    goc = b.text()
    if not goc or b.objectName() in ("NavButton", "SideToggle"):
        return
    chu = _bo_emoji(goc)
    ten_icon = None
    for kw, moi, ic in NUT:
        if kw.lower() in goc.lower():
            chu = moi or chu
            ten_icon = ic
            break
    if chu.isupper() and len(chu) > 6:  # CHỮ IN HOA -> chữ thường đầu câu
        chu = chu[:1] + chu[1:].lower()
    for dai, ngan in RUT_GON:
        if dai.lower() in chu.lower():
            if not b.toolTip():
                b.setToolTip(chu)
            chu = ngan
            break
    # bỏ màu tự đặt của từng nút (xanh lá, xanh nhạt...) -> dùng màu chung của thiết kế
    if "background" in (b.styleSheet() or ""):
        b.setStyleSheet("")
    b.setText(chu)
    variant = b.property("variant")
    mau = "#FFFFFF" if variant in ("primary", "success") or b.objectName() in ("btn_extract", "btn_copy_json") \
        else ui.C["text"]
    if ten_icon:
        b.setIcon(icon(ten_icon, mau))
        b.setIconSize(QSize(16, 16))


def _form_nhan_tren(form: QFormLayout):
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
    form.setVerticalSpacing(6)
    form.setContentsMargins(4, 2, 4, 6)
    for i in range(form.rowCount()):
        it = form.itemAt(i, QFormLayout.ItemRole.LabelRole)
        lb = it.widget() if it else None
        if isinstance(lb, QLabel):
            lb.setText(lb.text().rstrip().rstrip(":"))
            lb.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {ui.C['text_2']}; padding-top: 6px;")


def _xep_2_cot(vlay: QVBoxLayout):
    """Hai QGroupBox-form liền nhau -> 1 hàng 2 cột. Bảng nhiều dòng / khung khác giữ nguyên toàn chiều rộng."""
    muc = []
    while vlay.count():
        it = vlay.takeAt(0)
        if it.widget() is not None:
            muc.append(("w", it.widget()))
        elif it.layout() is not None:
            muc.append(("l", it.layout()))
        elif it.spacerItem() is not None:
            muc.append(("s", None))
    i = 0
    while i < len(muc):
        k, w = muc[i]
        la_form = k == "w" and isinstance(w, QGroupBox) and isinstance(w.layout(), QFormLayout)
        tiep = muc[i + 1] if i + 1 < len(muc) else None
        la_form2 = tiep and tiep[0] == "w" and isinstance(tiep[1], QGroupBox) and isinstance(tiep[1].layout(), QFormLayout)
        if la_form and la_form2:
            h = QHBoxLayout()
            h.setSpacing(12)
            for x in (w, tiep[1]):
                x.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
                h.addWidget(x, 1, Qt.AlignmentFlag.AlignTop)
            vlay.addLayout(h)
            i += 2
            continue
        if k == "w":
            vlay.addWidget(w)
        elif k == "l":
            vlay.addLayout(w)
        else:
            vlay.addStretch(1)
        i += 1


def _lay_ra(layout):
    """Gỡ hết phần tử khỏi layout (không xóa widget). Trả [('w'|'l'|'s', obj)]."""
    out = []
    while layout.count():
        it = layout.takeAt(0)
        if it.widget() is not None:
            out.append(("w", it.widget()))
        elif it.layout() is not None:
            out.append(("l", it.layout()))
        else:
            out.append(("s", None))
    return out


class _OBuoc(QWidget):
    """Ô bước trên thanh: vòng tròn (số / ✓ nảy), nhãn nhỏ, giá trị, mũi tên xoay. Vẽ tay để có chuyển động."""
    from PyQt6.QtCore import pyqtSignal as _sig
    bam = _sig()

    def __init__(self, so, nhan, mo_duoc=True):
        super().__init__()
        from PyQt6.QtCore import QVariantAnimation, QEasingCurve
        self.so, self.nhan, self.gia_tri, self.mo_duoc = so, nhan, "", mo_duoc
        self.xong, self.dang_mo, self._hover = False, False, False
        self._xoay, self._ty_le = 0.0, 1.0
        self.setCursor(Qt.CursorShape.PointingHandCursor if mo_duoc else Qt.CursorShape.ArrowCursor)
        self.setMinimumHeight(62)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self._a_xoay = QVariantAnimation(self)
        self._a_xoay.setDuration(280)
        self._a_xoay.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._a_xoay.valueChanged.connect(lambda v: (setattr(self, "_xoay", float(v)), self.update()))
        self._a_nay = QVariantAnimation(self)
        self._a_nay.setDuration(450)
        self._a_nay.setStartValue(0.4)
        self._a_nay.setKeyValueAt(0.6, 1.18)
        self._a_nay.setEndValue(1.0)
        self._a_nay.valueChanged.connect(lambda v: (setattr(self, "_ty_le", float(v)), self.update()))

    def sizeHint(self):
        return QSize(260, 62)

    def dat(self, gia_tri=None, xong=None, dang_mo=None):
        if gia_tri is not None:
            self.gia_tri = gia_tri
        if xong is not None and xong != self.xong:
            self.xong = xong
            if xong:
                self._a_nay.stop()
                self._a_nay.start()
        if dang_mo is not None and dang_mo != self.dang_mo:
            self.dang_mo = dang_mo
            self._a_xoay.stop()
            self._a_xoay.setStartValue(self._xoay)
            self._a_xoay.setEndValue(180.0 if dang_mo else 0.0)
            self._a_xoay.start()
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if self.mo_duoc and e.button() == Qt.MouseButton.LeftButton:
            self.bam.emit()

    def paintEvent(self, e):
        from PyQt6.QtGui import QPainter, QColor, QFont, QPen
        from PyQt6.QtCore import QRectF, QPointF
        from ui_icons import ve_ky_hieu
        C = ui.C
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        if self.dang_mo:
            p.fillRect(r, QColor("#F5F8FF"))
        elif self._hover and self.mo_duoc:
            p.fillRect(r, QColor("#FAFBFD"))
        p.setPen(QPen(QColor("#EEF2F6"), 1))
        p.drawLine(r.topRight(), r.bottomRight())
        # vòng tròn
        d = 30 * (self._ty_le if self.xong else 1.0)
        cx, cy = 16 + 15, r.center().y()
        vong = QRectF(cx - d / 2, cy - d / 2, d, d)
        if self.xong:
            bg, fg = "#E8F6EE", "#15803D"
        elif self.dang_mo:
            bg, fg = C["primary"], "#FFFFFF"
        else:
            bg, fg = "#EEF2F6", C["text_2"]
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(bg))
        p.drawEllipse(vong)
        if self.xong:
            ve_ky_hieu(p, QRectF(cx - 15, cy - 15, 30, 30), "ok", fg)
        else:
            f = QFont(self.font())
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(fg))
            p.drawText(QRectF(cx - 15, cy - 15, 30, 30), Qt.AlignmentFlag.AlignCenter, str(self.so))
        # chữ
        x0 = 16 + 30 + 12
        rong = r.width() - x0 - 34
        f1 = QFont(self.font())
        f1.setBold(True)
        f1.setPointSizeF(max(7.0, self.font().pointSizeF() - 2.2))
        f1.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
        p.setFont(f1)
        p.setPen(QColor(C["text_2"]))
        p.drawText(QRectF(x0, cy - 19, rong, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.nhan)
        f2 = QFont(self.font())
        f2.setBold(True)
        f2.setPointSizeF(self.font().pointSizeF() + 0.6)
        p.setFont(f2)
        p.setPen(QColor(C["text"]))
        p.drawText(QRectF(x0, cy - 1, rong, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(self.gia_tri, Qt.TextElideMode.ElideRight, int(rong)))
        # mũi tên xoay
        if self.mo_duoc:
            p.save()
            p.translate(r.right() - 20, cy)
            p.rotate(self._xoay)
            pen = QPen(QColor(C["muted"]), 1.8)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawPolyline([QPointF(-4, -2), QPointF(0, 2), QPointF(4, -2)])
            p.restore()
        p.end()


class _VetSang(QWidget):
    """Vệt sáng chạy ngang trên nút khi đang trích xuất."""

    def __init__(self, nut):
        super().__init__(nut)
        from PyQt6.QtCore import QVariantAnimation
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._x = -1.0
        self._a = QVariantAnimation(self)
        self._a.setStartValue(-0.5)
        self._a.setEndValue(1.5)
        self._a.setDuration(1100)
        self._a.setLoopCount(-1)
        self._a.valueChanged.connect(lambda v: (setattr(self, "_x", float(v)), self.update()))
        self.hide()

    def chay(self, bat):
        self.setGeometry(self.parent().rect())
        self.setVisible(bat)
        (self._a.start() if bat else self._a.stop())

    def paintEvent(self, e):
        from PyQt6.QtGui import QPainter, QLinearGradient, QColor, QPainterPath
        from PyQt6.QtCore import QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        x = self._x * w
        g = QLinearGradient(x - w * 0.25, 0, x + w * 0.25, 0)
        g.setColorAt(0, QColor(255, 255, 255, 0))
        g.setColorAt(0.5, QColor(255, 255, 255, 110))
        g.setColorAt(1, QColor(255, 255, 255, 0))
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 12, 12)
        p.setClipPath(path)
        p.fillRect(self.rect(), g)
        p.end()


def _mo_dong(khung, mo, ms=300, moi_khung=None):
    """Trượt mở/đóng khung (chiều cao) + mờ dần. moi_khung(): gọi mỗi khung hình (để vùng chứa co giãn theo)."""
    from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
    from PyQt6.QtWidgets import QGraphicsOpacityEffect
    cao = khung.sizeHint().height() if mo else 0
    if mo:
        khung.setVisible(True)
    eff = khung.graphicsEffect()
    if not isinstance(eff, QGraphicsOpacityEffect):
        eff = QGraphicsOpacityEffect(khung)
        khung.setGraphicsEffect(eff)
    nhom = QParallelAnimationGroup(khung)
    a1 = QPropertyAnimation(khung, b"maximumHeight")
    a1.setDuration(ms)
    a1.setEasingCurve(QEasingCurve.Type.OutCubic)
    a1.setStartValue(khung.height() if khung.isVisible() else 0)
    a1.setEndValue(cao)
    a2 = QPropertyAnimation(eff, b"opacity")
    a2.setDuration(int(ms * 0.75))
    a2.setStartValue(eff.opacity())
    a2.setEndValue(1.0 if mo else 0.0)
    nhom.addAnimation(a1)
    nhom.addAnimation(a2)
    if moi_khung is not None:
        a1.valueChanged.connect(lambda *_: moi_khung())

    def xong():
        if not mo:
            khung.setVisible(False)
        else:
            khung.setMaximumHeight(cao)
            khung.setGraphicsEffect(None)  # bỏ lớp mờ khi đã mở hẳn (giữ hiệu năng)
        if moi_khung is not None:
            moi_khung()
    nhom.finished.connect(xong)
    old = getattr(khung, "_anim", None)
    if old is not None:
        old.stop()
    khung._anim = nhom
    nhom.start()


def xep_tren_duoi(page: QWidget, co_app):
    """
    Mẫu C (người dùng chọn 21/11): thanh 3 bước ở trên [1 Mẫu C/O ▾][2 Chứng từ ▾][3 Trích xuất] + nút Trích xuất;
    bấm bước 1/2 -> khung chi tiết trượt mở ngay dưới (hàng nút nằm CẠNH DƯỚI khung chứng từ).
    Chuyển động: khung trượt + mờ, gạch chân trượt theo bước, mũi tên xoay, ✓ nảy, vệt sáng khi đang trích xuất.
    Phần 2 (form/tab) toàn bề ngang ở dưới. Chỉ đổi giao diện, không đụng logic C/O.
    """
    from PyQt6.QtWidgets import QSplitter, QFrame, QListWidget, QListView
    from PyQt6.QtCore import QTimer, QPropertyAnimation, QEasingCurve, QRect
    from datetime import datetime
    sp = next((s for s in page.findChildren(QSplitter) if s.count() == 2), None)
    if sp is None or co_app is None:
        return
    trai = sp.widget(0)
    lay_trai = trai.layout()
    combo = getattr(co_app, "combo_form", None)
    ds_file = getattr(co_app, "list_files", None)
    btn_ex = getattr(co_app, "btn_extract", None)
    prog = getattr(co_app, "progress_bar", None)
    lbl_st = getattr(co_app, "lbl_status", None)
    if lay_trai is None or combo is None or ds_file is None or btn_ex is None:  # QListWidget rỗng có bool() = False
        return
    docs_group = next((g for g in trai.findChildren(QGroupBox) if "Chứng từ" in g.title()), None)
    nut_tep = list(docs_group.findChildren(QPushButton)) if docs_group else []
    for k, w in _lay_ra(lay_trai):
        if k == "w" and isinstance(w, QGroupBox):
            w.setVisible(False)
    if prog is not None:
        prog.setParent(None)
        prog.hide()
    if lbl_st is not None:
        lbl_st.hide()
    C = ui.C

    the = QFrame()
    the.setObjectName("OpenLot")
    tl = QVBoxLayout(the)
    tl.setContentsMargins(0, 0, 0, 0)
    tl.setSpacing(0)

    # ---------- thanh bước
    thanh = QWidget()
    thanh.setFixedHeight(62)
    hl = QHBoxLayout(thanh)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(0)
    b1 = _OBuoc(1, "BƯỚC 1 · MẪU C/O")
    b2 = _OBuoc(2, "BƯỚC 2 · CHỨNG TỪ")
    b3 = _OBuoc(3, "BƯỚC 3 · TRÍCH XUẤT", mo_duoc=False)
    for b in (b1, b2, b3):
        hl.addWidget(b, 1)
    o_nut = QHBoxLayout()
    o_nut.setContentsMargins(14, 0, 14, 0)
    btn_ex.setParent(None)
    btn_ex.setMinimumWidth(210)
    btn_ex.setMinimumHeight(44)
    btn_ex.setMaximumHeight(44)
    o_nut.addWidget(btn_ex)
    hl.addLayout(o_nut)
    vet = _VetSang(btn_ex)
    gach = QFrame(thanh)
    gach.setStyleSheet(f"background: {C['primary']}; border: none;")
    gach.setGeometry(0, 60, 10, 2)
    gach.hide()
    tl.addWidget(thanh)

    # ---------- khung bước 1: mẫu C/O
    k1 = QFrame()
    k1.setStyleSheet(f"QFrame#K1 {{ border-top: 1px solid {C['border']}; }}")
    k1.setObjectName("K1")
    l1 = QHBoxLayout(k1)
    l1.setContentsMargins(18, 12, 18, 12)
    l1.setSpacing(12)
    combo.setParent(None)
    combo.setStyleSheet("")
    combo.setMinimumWidth(300)
    combo.setMinimumHeight(38)
    l1.addWidget(combo)
    g1 = QLabel("Hiệp định / mẫu C/O quyết định các ô bắt buộc trên eCoSys.")
    g1.setStyleSheet(f"color: {C['text_2']}; font-size: 12px;")
    l1.addWidget(g1, 1)

    # ---------- khung bước 2: chứng từ (lưới 3 cột) + hàng nút ở CẠNH DƯỚI
    k2 = QFrame()
    k2.setObjectName("K2")
    k2.setStyleSheet(f"QFrame#K2 {{ border-top: 1px solid {C['border']}; }}")
    l2 = QVBoxLayout(k2)
    l2.setContentsMargins(18, 12, 18, 6)
    l2.setSpacing(4)
    ds_file.setParent(None)
    ds_file.setFlow(QListView.Flow.LeftToRight)
    ds_file.setWrapping(True)
    ds_file.setResizeMode(QListView.ResizeMode.Adjust)
    ds_file.setUniformItemSizes(True)
    ds_file.setSpacing(0)
    ds_file.setMinimumHeight(70)
    ds_file.setMaximumHeight(110)
    ds_file.setStyleSheet(f"QListWidget {{ border: 1px dashed #C4D6F3; border-radius: 10px; background: #FAFCFF; padding: 4px 8px; }}"
                          " QListWidget::item { padding: 3px 4px; }")

    def luoi_3_cot():
        # trừ lề trong (padding 8px x2) + khoảng an toàn để luôn đủ 3 cột, tên file không bị cắt
        w = max(300, ds_file.viewport().width() - 28)
        o = QSize(w // 3, 30)
        ds_file.setGridSize(o)
        for i in range(ds_file.count()):
            ds_file.item(i).setSizeHint(QSize(o.width() - 6, 28))
    l2.addWidget(ds_file)
    trong = QLabel("Thả file PDF / ảnh chứng từ vào đây  ·  hoặc bấm Thêm", ds_file.viewport())
    trong.setStyleSheet(f"color: {C['muted']}; font-size: 13px; background: transparent;")
    trong.setAlignment(Qt.AlignmentFlag.AlignCenter)
    trong.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    _goc_resize = ds_file.resizeEvent

    def _resize(e):
        _goc_resize(e)
        trong.resize(ds_file.viewport().size())
        luoi_3_cot()
    ds_file.resizeEvent = _resize
    cc = QHBoxLayout()
    cc.setSpacing(2)
    cc.setContentsMargins(0, 2, 0, 2)
    for i, b in enumerate(nut_tep):
        b.setParent(None)
        b.setProperty("variant", "ghost")
        b.setProperty("size", "sm")
        b.setStyleSheet("")
        cc.addWidget(b)
        if i == 2 and len(nut_tep) > 3:
            v = QFrame()
            v.setFixedSize(1, 18)
            v.setStyleSheet(f"background: {C['border']}; border: none;")
            cc.addSpacing(6)
            cc.addWidget(v)
            cc.addSpacing(6)
    cc.addStretch(1)
    g2 = QLabel("Kéo thả thêm file vào khung · tích ô = cho AI đọc")
    g2.setStyleSheet(f"color: {C['muted']}; font-size: 12px;")
    cc.addWidget(g2)
    l2.addLayout(cc)

    tl.addWidget(k1)
    tl.addWidget(k2)
    k1.setVisible(False)
    k1.setMaximumHeight(0)

    lay_trai.addWidget(the)
    trai.setMinimumWidth(0)
    trai.setMaximumWidth(16777215)
    trai.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    sp.setOrientation(Qt.Orientation.Vertical)
    sp.setChildrenCollapsible(False)
    sp.setHandleWidth(8)
    sp.setStretchFactor(0, 0)
    sp.setStretchFactor(1, 1)

    st = {"mo": 2, "tt": "cho", "luc": ""}

    def ve_gach():
        o = {1: b1, 2: b2}.get(st["mo"])
        if o is None:
            gach.hide()
            return
        dich = QRect(o.x(), thanh.height() - 2, o.width(), 2)
        if not gach.isVisible():
            gach.setGeometry(dich)
            gach.show()
            gach.raise_()
            return
        a = QPropertyAnimation(gach, b"geometry", gach)
        a.setDuration(320)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.setStartValue(gach.geometry())
        a.setEndValue(dich)
        a.start()
        gach._a = a

    def cap_nhat():
        n = ds_file.count()
        k = sum(1 for i in range(n) if ds_file.item(i).checkState() == Qt.CheckState.Checked)
        trong.setVisible(n == 0)
        trong.resize(ds_file.viewport().size())
        b1.dat(combo.currentText(), True, st["mo"] == 1)
        b2.dat(f"{n} file · {k} cho AI đọc" if n else "Chưa có file — thả vào đây", n > 0, st["mo"] == 2)
        txt = {"cho": "Chưa trích xuất", "chay": f"Đang đọc {k} file…", "xong": f"Xong lúc {st['luc']}",
               "loi": "Lỗi — xem thông báo"}[st["tt"]]
        b3.dat(txt, st["tt"] == "xong", False)

    def vua_khung():
        """Vùng trên (thanh bước + khung đang mở) co giãn đúng chiều cao thật -> không còn khoảng trắng thừa."""
        cao = thanh.height() + sum(k.height() for k in (k1, k2) if k.isVisible()) + 2
        tong = sum(sp.sizes())
        if tong > 0:
            sp.setSizes([cao, max(200, tong - cao)])

    def mo_buoc(i):
        cu = st["mo"]
        st["mo"] = 0 if cu == i else i
        if cu == 1 and st["mo"] != 1:
            _mo_dong(k1, False, moi_khung=vua_khung)
        if cu == 2 and st["mo"] != 2:
            _mo_dong(k2, False, moi_khung=vua_khung)
        if st["mo"] == 1:
            _mo_dong(k1, True, moi_khung=vua_khung)
        if st["mo"] == 2:
            _mo_dong(k2, True, moi_khung=vua_khung)
        cap_nhat()
        QTimer.singleShot(0, ve_gach)

    b1.bam.connect(lambda: mo_buoc(1))
    b2.bam.connect(lambda: mo_buoc(2))
    for sig in (ds_file.model().rowsInserted, ds_file.model().rowsRemoved, ds_file.model().modelReset):
        sig.connect(lambda *_: cap_nhat())
    ds_file.itemChanged.connect(lambda *_: cap_nhat())
    combo.currentTextChanged.connect(lambda *_: cap_nhat())

    # theo dõi trạng thái trích xuất (nút bị khóa = đang chạy) -> vệt sáng + bước 3
    def theo_doi():
        dang = not btn_ex.isEnabled()
        if dang and st["tt"] != "chay":
            st["tt"] = "chay"
            vet.chay(True)
            cap_nhat()
        elif not dang and st["tt"] == "chay":
            vet.chay(False)
            t = lbl_st.text() if lbl_st is not None else ""
            st["tt"] = "loi" if ("Lỗi" in t or "❌" in t) else st["tt"]
            if st["tt"] == "chay":
                st["tt"] = "cho"
            cap_nhat()
    tm = QTimer(the)
    tm.timeout.connect(theo_doi)
    tm.start(250)

    goc = co_app.on_extraction_finished

    def xong(co_data, error):
        goc(co_data, error)
        vet.chay(False)
        if error:
            st["tt"] = "loi"
        else:
            st["tt"] = "xong"
            st["luc"] = datetime.now().strftime("%H:%M")
            btn_ex.setText("Trích xuất lại")
            btn_ex.setIcon(icon("refresh", "#FFFFFF"))
            if st["mo"]:
                mo_buoc(st["mo"])  # đóng khung đang mở -> form rộng
        cap_nhat()
    co_app.on_extraction_finished = xong
    co_app._thu_gon_phan_chung_tu = lambda gon: (mo_buoc(st["mo"]) if gon and st["mo"] else (mo_buoc(2) if not gon else None))

    cap_nhat()
    QTimer.singleShot(50, lambda: (luoi_3_cot(), ve_gach(), vua_khung()))
    ds_file.model().rowsInserted.connect(lambda *_: QTimer.singleShot(0, luoi_3_cot))
    _goc_thanh_resize = thanh.resizeEvent

    def _thanh_resize(e):
        _goc_thanh_resize(e)
        o = {1: b1, 2: b2}.get(st["mo"])
        if o is not None:
            gach.setGeometry(o.x(), thanh.height() - 2, o.width(), 2)
    thanh.resizeEvent = _thanh_resize


def lam_gon_trang_co(page: QWidget, co_app=None):
    # 1. Tab chính: tên ngắn + icon
    tabs = [t for t in page.findChildren(QTabWidget)]
    if tabs:
        tw = max(tabs, key=lambda t: t.count())
        tw.setUsesScrollButtons(False)
        tw.setElideMode(Qt.TextElideMode.ElideNone)
        for i in range(min(tw.count(), len(TAB_MOI))):
            full = _bo_emoji(tw.tabText(i)).replace("&&", "&")
            ten, ic = TAB_MOI[i]
            tw.setTabToolTip(i, full)
            tw.setTabText(i, ten)
            tw.setTabIcon(i, icon(ic, ui.C["text_2"]))
        tw.setIconSize(QSize(16, 16))
        # 2. Trong từng tab: form nhãn trên + 2 cột
        for i in range(tw.count()):
            tab = tw.widget(i)
            for sa in tab.findChildren(QScrollArea):
                inner = sa.widget()
                if inner is not None and isinstance(inner.layout(), QVBoxLayout):
                    _xep_2_cot(inner.layout())
    for f in page.findChildren(QFormLayout):
        _form_nhan_tren(f)

    # 3. Nút
    for b in page.findChildren(QPushButton):
        _nut(b)
    ext = getattr(co_app, "btn_extract", None)
    if ext is not None:
        ext.setProperty("variant", "primary")
        ext.setProperty("size", "xl")
        ext.setStyleSheet("")
        ext.setMinimumHeight(48)
    for b in page.findChildren(QPushButton):
        if "Sao chép JSON" in b.text():
            b.setObjectName("")  # QSS cũ tô xanh lá theo objectName btn_copy_json
            b.setProperty("variant", "primary")
            b.setStyleSheet("")
            b.setIcon(icon("copy", "#FFFFFF"))
        elif "Ký số hàng loạt" in b.text():
            b.setProperty("variant", "soft")
            b.setIcon(icon("pen", ui.C["primary_press"]))
    for gb in page.findChildren(QGroupBox):
        gb.setTitle(_bo_emoji(gb.title()))
    for cb in page.findChildren(QCheckBox):
        if "Issued Retrospectively" in cb.text():
            cb.setToolTip(cb.text())
            cb.setText("Issued Retrospectively")
    for b in page.findChildren(QPushButton):
        if "Nạp dữ liệu mẫu" in b.text():
            b.setProperty("variant", "ghost")
            b.setStyleSheet("")

    # 4. Nhãn gợi ý 💡 / chữ màu lẻ
    for lb in page.findChildren(QLabel):
        t = lb.text()
        if t.startswith(("💡", "🛡")):
            lb.setText(_bo_emoji(t))
        if t.startswith("💡"):
            lb.setStyleSheet(f"color: {ui.C['text_2']}; font-size: 12px; background: transparent; border: none;")
    for cb in page.findChildren(QCheckBox):
        if "color" in cb.styleSheet():
            cb.setStyleSheet("")

    # 5. Bảng: cột tự giãn đủ chữ tiêu đề (không cắt chữ "Mã HS XK (8 số)"...), bảng rộng thì cuộn ngang
    from PyQt6.QtWidgets import QTableWidget, QHeaderView
    for tb in page.findChildren(QTableWidget):
        h = tb.horizontalHeader()
        if tb.columnCount() <= 0:
            continue
        h.setStretchLastSection(True)
        fm = h.fontMetrics()
        for c in range(tb.columnCount()):
            it = tb.horizontalHeaderItem(c)
            if it is None:
                continue
            can = fm.horizontalAdvance(it.text()) + 30
            if h.sectionResizeMode(c) != QHeaderView.ResizeMode.Stretch and tb.columnWidth(c) < can:
                tb.setColumnWidth(c, can)

    # 6. Phần chọn chứng từ lên trên thành dải ngang, form toàn bề ngang ở dưới
    try:
        xep_tren_duoi(page, co_app)
    except Exception as e:
        print(f"Không xếp lại được bố cục C/O: {e}")

    # 7. Áp lại style cho các nút vừa đổi variant
    for b in page.findChildren(QPushButton):
        st = b.style()
        st.unpolish(b)
        st.polish(b)
