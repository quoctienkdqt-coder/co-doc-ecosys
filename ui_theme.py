"""
BỘ GIAO DIỆN DÙNG CHUNG (DESIGN SYSTEM) CHO TOÀN BỘ ỨNG DỤNG
-----------------------------------------------------------
- 1 bảng màu, 1 stylesheet áp cho cả QApplication (mọi trang, mọi hộp thoại đều đồng bộ).
- Nút theo biến thể:  btn.setProperty("variant", "primary" | "success" | "secondary" | "ghost" | "danger")
- Thẻ (card):          frame.setObjectName("Card")
- Hiệu ứng mượt:       FadeStackedWidget (chuyển trang mờ dần), animate_width (thu/mở sidebar),
                       smooth_item_views (cuộn bảng theo pixel).
"""
try:  # ghi lỗi bị bỏ qua vào loi_bo_qua.log (thay cho except: pass im lặng)
    from nhat_ky_loi import ghi as _ghi_loi_bo_qua
except Exception:  # pragma: no cover
    def _ghi_loi_bo_qua(*_a, **_k):
        return None
from PyQt6.QtCore import Qt, QEasingCurve, QPropertyAnimation, QVariantAnimation, QAbstractAnimation
from PyQt6.QtGui import QFont, QColor, QPalette
from PyQt6.QtWidgets import (
    QApplication, QStackedWidget, QGraphicsOpacityEffect, QAbstractItemView, QWidget,
    QTabWidget, QGroupBox, QAbstractButton, QFrame, QLabel, QHBoxLayout, QVBoxLayout,
    QGraphicsDropShadowEffect,
)

# ------------------------------------------------------------------ BẢNG MÀU
# Hệ thiết kế "Hải trình" (v3.4): navy + cobalt, 3 màu trạng thái khác nhau cả độ sáng lẫn ký hiệu (✓ ? ×)
C = {
    "bg": "#F3F5F8", "surface": "#FFFFFF", "surface_2": "#F7F9FC",
    "border": "#E4E9F0", "border_strong": "#D3DAE4",
    "text": "#0B1A2E", "text_2": "#475569", "muted": "#7A8799",
    "primary": "#1F5FD6", "primary_hover": "#174AA8", "primary_press": "#123C8A", "primary_soft": "#EAF1FE",
    "success": "#15803D", "success_hover": "#166534", "success_soft": "#E8F6EE",
    "warning": "#B45309", "warning_soft": "#FEF4E2",
    "danger": "#C2261F", "danger_soft": "#FDECEC",
    "side_bg": "#0A1628", "side_bg_2": "#0D2140", "side_hover": "#13284A", "side_text": "#B6C3D6",
    "side_active": "#1F5FD6",
}

FONT_FAMILY = "Segoe UI"          # đổi thành "Be Vietnam Pro" khi nạp được font đi kèm (assets/fonts)
FONT_FALLBACK = "Segoe UI"


def _nap_font():
    """Nạp Be Vietnam Pro (font thiết kế cho tiếng Việt, giấy phép OFL) từ assets/fonts. Trả tên họ font."""
    import os
    from PyQt6.QtGui import QFontDatabase
    goc = os.path.dirname(os.path.abspath(__file__))
    for thu_muc in (os.path.join(goc, "assets", "fonts"), os.path.join(goc, "_internal", "assets", "fonts")):
        if not os.path.isdir(thu_muc):
            continue
        ho = None
        for f in sorted(os.listdir(thu_muc)):
            if f.lower().endswith((".ttf", ".otf")):
                fid = QFontDatabase.addApplicationFont(os.path.join(thu_muc, f))
                if fid >= 0 and QFontDatabase.applicationFontFamilies(fid):
                    ho = ho or QFontDatabase.applicationFontFamilies(fid)[0]
        if ho:
            return ho
    return None
_ICONS = {}


def _make_icons():
    """Vẽ icon dấu tick (checkbox) & mũi tên (combobox) ra PNG tạm — không cần file ảnh/plugin SVG đi kèm."""
    import os
    import tempfile
    from PyQt6.QtGui import QPixmap, QPainter, QPen
    from PyQt6.QtCore import QPointF
    d = os.path.join(tempfile.gettempdir(), "xnk_ui_icons_v1")
    os.makedirs(d, exist_ok=True)

    def draw(name, color, pts, w=28, h=28, width=3.2):
        p = os.path.join(d, name)
        if not os.path.exists(p):
            pm = QPixmap(w, h)
            pm.fill(Qt.GlobalColor.transparent)
            qp = QPainter(pm)
            qp.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor(color), width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            qp.setPen(pen)
            qp.drawPolyline(*[QPointF(x, y) for x, y in pts])
            qp.end()
            pm.save(p, "PNG")
        return p.replace("\\", "/")

    _ICONS["check"] = draw("check.png", "#FFFFFF", [(7, 14.5), (12, 19.5), (21, 9)])
    _ICONS["chevron"] = draw("chevron.png", "#64748B", [(8, 11), (14, 17), (20, 11)], width=2.6)
    return _ICONS


def _qss():
    c = C
    ic = _ICONS or {"check": "", "chevron": ""}
    return f"""
/* ================= NỀN & CHỮ ================= */
QMainWindow, QDialog {{ background: {c['bg']}; }}
QToolTip {{
    background: #0F172A; color: #F8FAFC; border: none; padding: 6px 9px; border-radius: 6px; font-size: 12px;
}}
QLabel {{ color: {c['text']}; background: transparent; }}
QLabel#PageTitle {{ font-size: 19px; font-weight: 700; color: {c['text']}; }}
QLabel#PageSubtitle {{ font-size: 12.5px; color: {c['text_2']}; }}
QLabel#SectionTitle {{ font-size: 13px; font-weight: 700; color: {c['text']}; }}
QLabel#Caption {{ font-size: 11.5px; font-weight: 600; color: {c['muted']}; }}
QLabel#Muted {{ color: {c['text_2']}; font-size: 12px; }}
QLabel#StatusText {{ color: {c['text_2']}; font-size: 12px; }}
QLabel#BadgeSuccess {{
    background: {c['success_soft']}; color: #166534; border: 1px solid #BBF7D0; border-radius: 10px;
    padding: 3px 10px; font-size: 11.5px; font-weight: 600;
}}
QLabel#Badge {{
    background: {c['primary_soft']}; color: {c['primary_press']}; border-radius: 10px;
    padding: 3px 10px; font-size: 11.5px; font-weight: 600;
}}

/* ================= THẺ (CARD) ================= */
QFrame#Card {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 14px; }}
QFrame#Inset {{ background: {c['surface_2']}; border: 1px solid {c['border']}; border-radius: 10px; }}
QFrame#KpiCard {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 14px; }}
QFrame#KpiCard[tone="ok"] {{ background: #FFFFFF; border: 1px solid #CBE9D6; }}
QFrame#KpiCard[tone="xem"] {{ background: #FFFBF3; border: 1px solid #F6DDB4; }}
QFrame#KpiCard[tone="lech"] {{ background: #FFF7F6; border: 1px solid #F5C9C6; }}
QFrame#HeroCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #EAF1FE, stop:0.7 #FFFFFF);
    border: none; border-bottom: 1px solid {c['border']}; border-top-left-radius: 16px; border-top-right-radius: 16px;
}}
QFrame#OpenLot {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 16px; }}
QFrame#DocTile {{ background: transparent; border: none; border-right: 1px solid #EEF2F6; }}
QLabel#Eyebrow {{ font-size: 11.5px; font-weight: 700; color: {c['primary']}; letter-spacing: 1px; }}
QLabel#BigNumber {{ font-size: 24px; font-weight: 800; color: {c['text']}; }}
QLabel#HeroTitle {{ font-size: 20px; font-weight: 700; color: {c['text']}; }}
QFrame#KpiAccent {{ border-radius: 2px; }}

QGroupBox {{
    background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px;
    margin-top: 4px; padding: 34px 10px 10px 10px; font-weight: 700; color: {c['text']};
}}
QGroupBox::title {{
    subcontrol-origin: padding; subcontrol-position: top left; left: 14px; top: 11px; padding: 0;
    color: {c['text']}; background: transparent;
}}

/* ================= Ô NHẬP LIỆU ================= */
QLineEdit, QComboBox, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit {{
    background: {c['surface']}; border: 1px solid {c['border_strong']}; border-radius: 8px;
    padding: 5px 10px; min-height: 22px; color: {c['text']}; selection-background-color: {c['primary']};
    selection-color: #FFFFFF;
}}
QLineEdit:hover, QComboBox:hover, QTextEdit:hover, QPlainTextEdit:hover {{ border-color: {c['muted']}; }}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDateEdit:focus {{
    border: 1px solid {c['primary']}; background: #FFFFFF;
}}
QLineEdit:disabled, QComboBox:disabled {{ background: {c['surface_2']}; color: {c['muted']}; }}
QLineEdit#SearchLike {{ background: {c['surface_2']}; padding: 8px 12px; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ image: url("{ic['chevron']}"); width: 14px; height: 14px; margin-right: 8px; }}
QComboBox QAbstractItemView {{
    background: #FFFFFF; border: 1px solid {c['border']}; border-radius: 8px; padding: 4px;
    selection-background-color: {c['primary_soft']}; selection-color: {c['primary_press']}; outline: 0;
}}

/* ================= NÚT ================= */
QPushButton {{
    background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border_strong']};
    border-radius: 10px; padding: 7px 15px; min-height: 22px; font-weight: 600;
}}
QPushButton:hover {{ background: {c['surface_2']}; border-color: {c['muted']}; }}
QPushButton:pressed {{ background: {c['border']}; }}
QPushButton:disabled {{ color: {c['muted']}; background: {c['surface_2']}; border-color: {c['border']}; }}
QPushButton:focus {{ outline: none; }}

QPushButton[variant="primary"], QPushButton#btn_extract {{
    background: {c['primary']}; color: #FFFFFF; border: 1px solid {c['primary']};
}}
QPushButton[variant="primary"]:hover, QPushButton#btn_extract:hover {{
    background: {c['primary_hover']}; border-color: {c['primary_hover']};
}}
QPushButton[variant="primary"]:pressed, QPushButton#btn_extract:pressed {{ background: {c['primary_press']}; }}
QPushButton[variant="primary"]:disabled, QPushButton#btn_extract:disabled {{
    background: #93B4F5; border-color: #93B4F5; color: #F8FAFC;
}}
QPushButton#btn_extract {{ padding: 11px 16px; font-size: 13.5px; }}

QPushButton[variant="success"], QPushButton#btn_copy_json {{
    background: {c['success']}; color: #FFFFFF; border: 1px solid {c['success']};
}}
QPushButton[variant="success"]:hover, QPushButton#btn_copy_json:hover {{
    background: {c['success_hover']}; border-color: {c['success_hover']};
}}
QPushButton[variant="success"]:disabled {{ background: #A7D7B5; border-color: #A7D7B5; color: #F8FAFC; }}

QPushButton[variant="soft"] {{
    background: {c['primary_soft']}; color: {c['primary_press']}; border: 1px solid #DBE7FE;
}}
QPushButton[variant="soft"]:hover {{ background: #DBEAFE; }}
QPushButton[variant="soft"]:disabled {{ background: {c['surface_2']}; color: {c['muted']}; border-color: {c['border']}; }}

QPushButton[variant="ghost"] {{ background: transparent; border: 1px solid transparent; color: {c['text_2']}; }}
QPushButton[variant="ghost"]:hover {{ background: {c['border']}; color: {c['text']}; }}
QPushButton[variant="ghost"]:checked {{ background: {c['primary_soft']}; color: {c['primary_press']}; }}

QPushButton[variant="danger"] {{ background: {c['surface']}; color: {c['danger']}; border: 1px solid #FECACA; }}
QPushButton[variant="danger"]:hover {{ background: {c['danger_soft']}; }}

QPushButton[size="lg"] {{ padding: 10px 20px; font-size: 13.5px; border-radius: 10px; }}
QPushButton[size="sm"] {{ padding: 4px 10px; min-height: 20px; font-size: 12px; }}
QTextEdit, QPlainTextEdit {{ min-height: 0; }}

/* Chip gợi ý / chip trạng thái file */
QPushButton[variant="chip"] {{
    background: {c['surface']}; color: {c['text_2']}; border: 1px solid {c['border']};
    border-radius: 16px; padding: 6px 12px; font-weight: 500; text-align: left;
}}
QPushButton[variant="chip"]:hover {{ border-color: {c['primary']}; color: {c['primary_press']}; background: {c['primary_soft']}; }}
QPushButton[variant="chip"][state="on"] {{
    background: {c['success_soft']}; color: #166534; border: 1px solid #BBF7D0; font-weight: 600;
}}
QPushButton[variant="chip"][state="on"]:hover {{ border-color: {c['success']}; }}
QPushButton[variant="chip"][state="off"] {{ border-style: dashed; border-color: {c['border_strong']}; }}
QPushButton[variant="chip"]:checked {{
    background: {c['text']}; color: #FFFFFF; border: 1px solid {c['text']}; font-weight: 600;
}}
QPushButton[variant="chip"]:checked:hover {{ background: #1B2B44; color: #FFFFFF; }}
QPushButton[size="xl"] {{ padding: 11px 22px; font-size: 14px; border-radius: 12px; font-weight: 700; }}

/* ================= CHECKBOX ================= */
QCheckBox {{ spacing: 7px; color: {c['text']}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 5px; border: 1px solid {c['border_strong']}; background: #FFFFFF;
}}
QCheckBox::indicator:hover {{ border-color: {c['primary']}; }}
QCheckBox::indicator:checked {{ background: {c['primary']}; border-color: {c['primary']}; image: url("{ic['check']}"); }}
QListWidget::indicator, QTableWidget::indicator {{
    width: 15px; height: 15px; border-radius: 4px; border: 1px solid {c['border_strong']}; background: #FFFFFF;
}}
QListWidget::indicator:checked, QTableWidget::indicator:checked {{
    background: {c['primary']}; border-color: {c['primary']}; image: url("{ic['check']}");
}}
QListWidget::item {{ padding: 4px 6px; border-radius: 6px; }}
QListWidget::item:hover {{ background: {c['surface_2']}; }}
QListWidget::item:selected {{ background: #DBEAFE; color: {c['text']}; }}

/* ================= TAB (KIỂU GẠCH CHÂN) ================= */
QTabWidget::pane {{
    background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px; top: -1px;
}}
QTabBar {{ qproperty-drawBase: 0; background: transparent; }}
QTabBar::tab {{
    background: transparent; color: {c['text_2']}; padding: 9px 16px; margin-right: 2px;
    border: none; border-bottom: 2px solid transparent; font-weight: 600;
}}
QTabBar::tab:hover {{ color: {c['text']}; border-bottom: 2px solid {c['border_strong']}; }}
QTabBar::tab:selected {{ color: {c['primary']}; border-bottom: 2px solid {c['primary']}; font-weight: 700; }}
QTabBar::scroller {{ width: 26px; }}
QTabBar QToolButton {{ background: {c['bg']}; border: none; border-radius: 6px; }}

/* ================= BẢNG ================= */
QTableWidget, QTableView, QTreeView, QListWidget, QListView {{
    background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px;
    gridline-color: {c['border']}; selection-background-color: #DBEAFE; selection-color: {c['text']};
    alternate-background-color: {c['surface_2']}; outline: 0;
}}
QHeaderView {{ background: transparent; border: none; }}
QHeaderView::section {{
    background: {c['surface_2']}; color: {c['text_2']}; font-weight: 700; font-size: 11.5px;
    border: none; border-bottom: 1px solid {c['border']}; border-right: 1px solid #EEF2F6;
    padding: 8px 6px;
}}
QTableCornerButton::section {{ background: {c['surface_2']}; border: none; }}

/* ================= THANH CUỘN MẢNH ================= */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {c['border_strong']}; border-radius: 3px; min-height: 28px; min-width: 28px;
}}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{ background: {c['muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ================= TIẾN TRÌNH ================= */
QProgressBar {{ background: {c['border']}; border: none; border-radius: 2px; }}
QProgressBar::chunk {{ background: {c['primary']}; border-radius: 2px; }}

QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: 8px; }}
QSplitter::handle:hover {{ background: {c['border']}; }}

QMenu {{ background: #FFFFFF; border: 1px solid {c['border']}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c['primary_soft']}; color: {c['primary_press']}; }}

/* Nhật ký dạng terminal */
QTextEdit#LogView {{
    background: #0B1220; color: #9CC9FF; border: 1px solid #0B1220; border-radius: 10px;
    font-family: Consolas, 'Cascadia Mono', monospace; font-size: 12px; padding: 8px;
}}

/* ================= SIDEBAR ================= */
QFrame#Sidebar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['side_bg']}, stop:1 {c['side_bg_2']}); border: none;
}}
QFrame#Sidebar QLabel {{ color: #E2E8F0; }}
QLabel#SideLogo {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3B7BF0, stop:1 {c['primary']});
    color: #FFFFFF; border-radius: 12px; font-size: 18px;
    min-width: 40px; max-width: 40px; min-height: 40px; max-height: 40px;
}}
QLabel#SideTitle {{ font-size: 14.5px; font-weight: 700; color: #FFFFFF; }}
QLabel#SideSub {{ font-size: 11.5px; color: #7F93B3; }}
QLabel#SideSection {{ font-size: 10.5px; font-weight: 700; color: #6F84A6; padding-left: 12px; letter-spacing: 1px; }}
QLabel#SideVersion {{ font-size: 10.5px; color: #5E7395; padding-left: 8px; }}
QLabel#SideStatus {{ font-size: 11.5px; color: #8EA3C2; padding-left: 8px; }}
QFrame#SideDivider {{ background: #1C3152; max-height: 1px; min-height: 1px; border: none; }}
QPushButton#NavButton {{
    background: transparent; color: {c['side_text']}; border: none; border-radius: 10px;
    text-align: left; padding: 0 12px; font-size: 13.5px; font-weight: 500;
    min-height: 42px; max-height: 42px;
}}
QPushButton#NavButton:hover {{ background: {c['side_hover']}; color: #FFFFFF; }}
QPushButton#NavButton:checked {{ background: {c['side_active']}; color: #FFFFFF; font-weight: 600; }}
QPushButton#NavButton[collapsed="true"] {{ text-align: center; padding: 0; font-size: 16px; }}
QPushButton#SideToggle {{
    background: transparent; color: {c['side_text']}; border: 1px solid #1C3152; border-radius: 9px;
    padding: 0; font-size: 15px; min-height: 34px; max-height: 34px; min-width: 34px; max-width: 34px;
}}
QPushButton#SideToggle:hover {{ background: {c['side_hover']}; color: #FFFFFF; }}
"""


def apply_app_theme(app: QApplication):
    """Gọi 1 lần ngay sau khi tạo QApplication."""
    global FONT_FAMILY
    app.setStyle("Fusion")
    try:
        ho = _nap_font()
        if ho:
            FONT_FAMILY = ho
    except Exception:
        _ghi_loi_bo_qua()
    f = QFont(FONT_FAMILY, 10)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(f)
    pal = app.palette()
    pal.setColor(QPalette.ColorRole.Window, QColor(C["bg"]))
    pal.setColor(QPalette.ColorRole.Base, QColor(C["surface"]))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(C["surface_2"]))
    pal.setColor(QPalette.ColorRole.Text, QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(C["primary"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(C["muted"]))
    app.setPalette(pal)
    try:
        _make_icons()
    except Exception:
        _ghi_loi_bo_qua()
    app.setStyleSheet(_qss())


def setup_high_dpi():
    """Gọi TRƯỚC khi tạo QApplication: hiển thị sắc nét ở mức scale 125%/150%."""
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        _ghi_loi_bo_qua()


# ------------------------------------------------------------------ HELPERS
def set_prop(w: QWidget, name: str, value):
    """Đổi thuộc tính style động và vẽ lại ngay (dùng cho chip trạng thái, nút thu gọn...)."""
    if w.property(name) == value:
        return
    w.setProperty(name, value)
    st = w.style()
    st.unpolish(w)
    st.polish(w)
    w.update()


def button(text: str, variant: str = None, size: str = None, tooltip: str = None, cursor=True):
    from PyQt6.QtWidgets import QPushButton
    b = QPushButton(text)
    if variant:
        b.setProperty("variant", variant)
    if size:
        b.setProperty("size", size)
    if tooltip:
        b.setToolTip(tooltip)
    if cursor:
        b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def card(object_name="Card", shadow=False):
    f = QFrame()
    f.setObjectName(object_name)
    if shadow:
        add_shadow(f)
    return f


def add_shadow(w: QWidget, blur=18, y=2, alpha=18):
    eff = QGraphicsDropShadowEffect(w)
    eff.setBlurRadius(blur)
    eff.setOffset(0, y)
    eff.setColor(QColor(15, 23, 42, alpha))
    w.setGraphicsEffect(eff)


def page_header(title: str, subtitle: str = "", right_widgets=()):
    """Thanh tiêu đề trang: Tiêu đề lớn + mô tả nhỏ bên trái, các nút bên phải."""
    box = QHBoxLayout()
    box.setSpacing(10)
    col = QVBoxLayout()
    col.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("PageTitle")
    col.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("PageSubtitle")
        s.setWordWrap(True)
        col.addWidget(s)
    box.addLayout(col, stretch=1)
    for w in right_widgets:
        box.addWidget(w, alignment=Qt.AlignmentFlag.AlignVCenter)
    return box


def smooth_item_views(root: QWidget):
    """Bảng / danh sách cuộn mượt theo pixel thay vì nhảy từng dòng."""
    for v in root.findChildren(QAbstractItemView):
        v.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        v.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        try:
            v.verticalScrollBar().setSingleStep(18)
            v.horizontalScrollBar().setSingleStep(24)
        except Exception:
            _ghi_loi_bo_qua()


def _fix_amp(text: str) -> str:
    # '&' đơn lẻ bị Qt hiểu là phím tắt (mnemonic) và bị ẩn -> đổi thành '&&' để hiện đúng chữ '&'
    out, i = [], 0
    while i < len(text):
        if text[i] == "&":
            if i + 1 < len(text) and text[i + 1] == "&":
                out.append("&&")
                i += 2
                continue
            if i + 1 < len(text) and text[i + 1] != " ":
                out.append("&")  # có thể là phím tắt cố ý (vd '&File')
            else:
                out.append("&&")
            i += 1
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def fix_ampersands(root: QWidget):
    """Sửa lỗi mất ký tự '&' trên tab, tiêu đề khung, nút (vd 'Doanh nghiệp & Địa điểm')."""
    for tw in root.findChildren(QTabWidget):
        for i in range(tw.count()):
            tw.setTabText(i, _fix_amp(tw.tabText(i)))
    for gb in root.findChildren(QGroupBox):
        gb.setTitle(_fix_amp(gb.title()))
    for b in root.findChildren(QAbstractButton):
        b.setText(_fix_amp(b.text()))


# ------------------------------------------------------------------ HIỆU ỨNG
class FadeStackedWidget(QStackedWidget):
    """QStackedWidget chuyển trang có hiệu ứng mờ dần (fade-in) nhẹ nhàng."""
    DURATION = 170

    def setCurrentIndex(self, idx: int):
        if idx == self.currentIndex():
            return
        super().setCurrentIndex(idx)
        w = self.currentWidget()
        if w is None:
            return
        eff = QGraphicsOpacityEffect(w)
        eff.setOpacity(0.0)
        w.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", w)
        anim.setDuration(self.DURATION)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        # Gỡ hiệu ứng sau khi xong để trang không bị vẽ qua lớp offscreen (giữ hiệu năng)
        anim.finished.connect(lambda: w.setGraphicsEffect(None))
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


def animate_width(widget: QWidget, start: int, end: int, duration=180, on_done=None):
    """Thu / mở chiều rộng widget mượt (dùng cho sidebar)."""
    old = getattr(widget, "_width_anim", None)
    if old is not None:
        old.stop()
    anim = QVariantAnimation(widget)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setDuration(duration)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.valueChanged.connect(lambda v: widget.setFixedWidth(int(v)))
    if on_done:
        anim.finished.connect(on_done)
    widget._width_anim = anim
    anim.start()
    return anim
