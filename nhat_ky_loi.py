"""
NHẬT KÝ LỖI BỊ BỎ QUA
Trước đây ~50 chỗ `except: pass` nuốt lỗi im lặng (vd luật ngày XNNL không chạy suốt thời gian dài mà không ai biết).
Nay các chỗ đó gọi ghi() -> lỗi được ghi (kèm vị trí + traceback) vào:
    %APPDATA%\\XNK_eCoSys_SC\\loi_bo_qua.log
Mỗi vị trí chỉ ghi tối đa SO_LAN_TOI_DA lần / phiên để file không phình. so_loi() cho biết số lỗi đã gặp.
"""
import os
import sys
import threading
import traceback
from datetime import datetime

SO_LAN_TOI_DA = 3
_DEM = {}
_KHOA = threading.Lock()


def thu_muc():
    d = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "XNK_eCoSys_SC")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def duong_dan():
    return os.path.join(thu_muc(), "loi_bo_qua.log")


def ghi(vi_tri: str = ""):
    """Gọi bên trong khối except. Không bao giờ tự ném lỗi."""
    try:
        if not vi_tri:
            f = sys._getframe(1)
            vi_tri = f"{os.path.basename(f.f_code.co_filename)}:{f.f_lineno} ({f.f_code.co_name})"
        with _KHOA:
            n = _DEM.get(vi_tri, 0) + 1
            _DEM[vi_tri] = n
            if n > SO_LAN_TOI_DA:
                return
            p = duong_dan()
            if os.path.exists(p) and os.path.getsize(p) > 2_000_000:  # quá 2MB -> giữ 1 bản cũ
                try:
                    os.replace(p, p + ".1")
                except Exception:
                    pass
            with open(p, "a", encoding="utf-8") as fh:
                fh.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {vi_tri}"
                         + (" (lần cuối được ghi cho vị trí này)" if n == SO_LAN_TOI_DA else "") + "\n")
                fh.write(traceback.format_exc(limit=4).rstrip() + "\n\n")
    except Exception:
        pass


def so_loi() -> int:
    with _KHOA:
        return sum(_DEM.values())


def chuyen_print_vao_file():
    """Bản .exe không có cửa sổ console: print() / lỗi chưa bắt sẽ mất. Chuyển vào nhat_ky.log."""
    try:
        if sys.stdout is None or sys.stderr is None or getattr(sys, "frozen", False):
            fh = open(os.path.join(thu_muc(), "nhat_ky.log"), "a", encoding="utf-8", buffering=1)
            fh.write(f"\n===== Khởi động {datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
            sys.stdout = fh
            sys.stderr = fh
    except Exception:
        pass
