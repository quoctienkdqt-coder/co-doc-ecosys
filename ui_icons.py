"""
BỘ ICON NÉT "HẢI TRÌNH" — vẽ từ đường SVG (cùng bộ với bản thiết kế), không cần file ảnh đi kèm.
Dùng:  from ui_icons import icon, pixmap
       btn.setIcon(icon("home", "#B6C3D6"))      # màu nét tùy chọn
       label.setPixmap(pixmap("anchor", "#FFFFFF", 22))
"""
from PyQt6.QtCore import Qt, QByteArray, QRectF
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer

# Đường SVG 24x24, nét (stroke) — giống hệt bảng vẽ thiết kế
PATHS = {
    "home": "M3 10.5L12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z",
    "doc": "M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6",
    "anchor": "M12 3v15M8 7h8M5 13c0 4 3 7 7 7s7-3 7-7",
    "sparkle": "M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8zM19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z",
    "settings": "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-2.7-1.1l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 3.6 15H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.1-2.7l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.6 1.6 0 0 0 9.7 4.6V4a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0 1.1 2.7H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z",
    "book": "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zM4 19V5M8 7h7",
    "refresh": "M21 12a9 9 0 1 1-2.6-6.4M21 3v6h-6",
    "folder": "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
    "folder_check": "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM9 13l2 2 4-4",
    "play": "M7 5l12 7-12 7z",
    "check": "M5 12.5l4.5 4.5L19 7.5",
    "x": "M6 6l12 12M18 6L6 18",
    "alert": "M12 8v5M12 16.5v.01M10.3 3.9L2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
    "menu": "M4 7h16M4 12h16M4 17h16",
    "file_x": "M7 3h7l5 5v13H7zM14 3v5h5M10 12l4 4M14 12l-4 4",
    "grid": "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
    "list": "M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01",
    "external": "M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5",
    "plus": "M12 5v14M5 12h14",
    "minus": "M5 12h14",
    "trash": "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3",
    "target": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 12h.01",
    "list_check": "M4 7l2 2 3-3M4 15l2 2 3-3M12 8h8M12 16h8",
    "copy": "M9 9h11v11H9zM5 15H4V4h11v1",
    "flask": "M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.7 3h10.6a2 2 0 0 0 1.7-3l-5-9V3M7.5 14h9",
    "save": "M5 3h11l3 3v15H5zM8 3v5h7V3M8 21v-7h8v7",
    "search": "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4",
    "pen": "M4 20l4-1L19 8l-3-3L5 16zM14 6l3 3",
    "building": "M4 21V5l8-2v18M12 8h8v13M8 8h.01M8 12h.01M8 16h.01M16 12h.01M16 16h.01M3 21h18",
    "ship": "M3 17l2 4h14l2-4-9-3zM12 3v11M7 12V7h10v5",
    "box": "M21 8l-9-5-9 5v8l9 5 9-5zM3 8l9 5 9-5M12 13v8",
    "paperclip": "M20 11l-8.5 8.5a5 5 0 0 1-7-7L13 4a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L14 7",
    "code": "M9 8l-5 4 5 4M15 8l5 4-5 4",
    "eye": "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    "key": "M15 7a4 4 0 1 1-3.9 5H3v3h3v3h3v-3h2.1A4 4 0 0 1 15 7z",
    "send": "M22 2L11 13M22 2l-7 20-4-9-9-4z",
    "chevron_l": "M15 6l-6 6 6 6",
    "chevron_r": "M9 6l6 6-6 6",
    "info": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v5M12 8h.01",
}


def _svg(name, color, width=1.9):
    d = PATHS.get(name, PATHS["doc"])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"><path d="{d}"/></svg>')


def pixmap(name, color="#0B1A2E", size=18, width=1.9, dpr=2.0):
    """Ảnh icon sắc nét ở màn hình 125–200% (vẽ ở mật độ điểm ảnh gấp đôi)."""
    px = int(size * dpr)
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    r = QSvgRenderer(QByteArray(_svg(name, color, width).encode("utf-8")))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r.render(p, QRectF(0, 0, px, px))
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def ve_ky_hieu(p, rect, loai, color):
    """Vẽ ký hiệu trạng thái bằng NÉT (không phụ thuộc font): 'ok' ✓ · 'lech' × · 'xem' ? · 'na' –."""
    from PyQt6.QtGui import QPen, QColor, QFont
    from PyQt6.QtCore import QPointF
    s = min(rect.width(), rect.height())
    cx, cy = rect.center().x(), rect.center().y()
    k = s * 0.2
    pen = QPen(QColor(color), max(1.8, s * 0.11))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    if loai == "lech":
        p.drawLine(QPointF(cx - k, cy - k), QPointF(cx + k, cy + k))
        p.drawLine(QPointF(cx + k, cy - k), QPointF(cx - k, cy + k))
    elif loai == "ok":
        p.drawPolyline([QPointF(cx - k * 1.2, cy + k * 0.05), QPointF(cx - k * 0.3, cy + k * 0.9),
                        QPointF(cx + k * 1.25, cy - k * 0.85)])
    elif loai == "na":
        p.drawLine(QPointF(cx - k, cy), QPointF(cx + k, cy))
    else:
        f = QFont(p.font())
        f.setBold(True)
        f.setPixelSize(int(s * 0.62))
        p.setFont(f)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "?")


def icon(name, color="#0B1A2E", color_active=None, size=18):
    """QIcon có thể đổi màu khi nút được chọn (checked) / hover."""
    ic = QIcon()
    ic.addPixmap(pixmap(name, color, size), QIcon.Mode.Normal, QIcon.State.Off)
    if color_active:
        act = pixmap(name, color_active, size)
        ic.addPixmap(act, QIcon.Mode.Normal, QIcon.State.On)
        ic.addPixmap(act, QIcon.Mode.Active, QIcon.State.Off)
        ic.addPixmap(act, QIcon.Mode.Active, QIcon.State.On)
    return ic
