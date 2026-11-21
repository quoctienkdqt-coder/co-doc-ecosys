"""
DANH SÁCH LÔ HÀNG GẦN ĐÂY (trang chủ "Lô hàng").
Lưu mỗi máy riêng: %APPDATA%\\XNK_eCoSys_SC\\lo_gan_day.json (tối đa 50 lô, mới nhất trước).
"""
try:  # ghi lỗi bị bỏ qua vào loi_bo_qua.log (thay cho except: pass im lặng)
    from nhat_ky_loi import ghi as _ghi_loi_bo_qua
except Exception:  # pragma: no cover
    def _ghi_loi_bo_qua(*_a, **_k):
        return None
import os
import json
from datetime import datetime

TOI_DA = 50


def _duong_dan():
    base = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "XNK_eCoSys_SC")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "lo_gan_day.json")


def doc_ds():
    try:
        with open(_duong_dan(), encoding="utf-8") as f:
            ds = json.load(f)
        return [x for x in ds if isinstance(x, dict) and x.get("path")]
    except Exception:
        return []


def ghi_lo(path, **info):
    """Ghi/cập nhật 1 lô (khóa = đường dẫn thư mục). info: so_sc, chung_tu, tu_duyet, can_xem, sai_lech, bao_cao..."""
    if not path:
        return
    path = os.path.normpath(path)
    ds = [x for x in doc_ds() if os.path.normpath(x["path"]).lower() != path.lower()]
    muc = {"path": path, "ten": os.path.basename(path) or path,
           "cap_nhat": datetime.now().strftime("%d/%m/%Y %H:%M"), **info}
    ds.insert(0, muc)
    try:
        tmp = _duong_dan() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(ds[:TOI_DA], f, ensure_ascii=False, indent=1)
        os.replace(tmp, _duong_dan())
    except Exception as e:
        print(f"Không lưu được danh sách lô gần đây: {e}")


def xoa_lo(path):
    path = os.path.normpath(path).lower()
    ds = [x for x in doc_ds() if os.path.normpath(x["path"]).lower() != path]
    try:
        with open(_duong_dan(), "w", encoding="utf-8") as f:
            json.dump(ds, f, ensure_ascii=False, indent=1)
    except Exception:
        _ghi_loi_bo_qua()
