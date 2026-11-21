"""
SỔ TÀU ĐÃ XÁC NHẬN (lớp kiểm tra 5)

Lưu thông tin tàu cá đã được xác nhận bởi >= 2 nguồn độc lập (SC scan khớp SC Excel / XNNL) hoặc do người duyệt.
Dùng làm "bằng chứng thứ 3" khi đọc SC mới: cùng số giấy phép mà hạn khác, chủ tàu khác, ngư cụ khác -> nghi ngờ.

Vị trí file: biến môi trường SO_TAU_PATH > ai_config.json "so_tau_path" (vd ổ mạng dùng chung W:\\...) >
%LOCALAPPDATA%\\DoiChieu_XNNL_SC\\so_tau.json
"""
import os
import re
import json
import threading
from datetime import datetime

_LOCK = threading.Lock()
TRUONG = ("owner", "licence_no", "licence_exp", "gear")


def _key(vessel_id):
    from sc_core.reconciler import clean_vessel_key
    return clean_vessel_key(vessel_id)


def _norm(field, v):
    from sc_core.reconciler import strip_vietnamese_accents
    s = str(v or "").replace("Ð", "Đ").strip()
    if field == "licence_exp":
        m = re.search(r"(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{4})", s)
        return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}" if m else ""
    if field in ("licence_no", "gear"):
        return re.sub(r"[^a-z0-9]", "", strip_vietnamese_accents(s))
    return re.sub(r"\s+", " ", s).lower()  # owner: giữ dấu (dấu khác = tên khác)


def duong_dan():
    p = os.environ.get("SO_TAU_PATH", "").strip()
    if not p:
        try:
            from sc_core.ai_extractor import load_ai_config
            p = str(load_ai_config().get("so_tau_path", "")).strip()
        except Exception:
            p = ""
    if not p:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        p = os.path.join(base, "DoiChieu_XNNL_SC", "so_tau.json")
    return p


def doc_so():
    p = duong_dan()
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"v": 1, "tau": {}}


def _ghi_so(so):
    p = duong_dan()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(so, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def ghi_nhan(vessel_id, field, value, nguon):
    """Ghi 1 giá trị đã xác nhận. nguon: vd 'SC 00297/2026 PDF=Excel' hoặc 'người duyệt'."""
    k = _key(vessel_id)
    if not k or field not in TRUONG or not str(value or "").strip():
        return
    with _LOCK:
        so = doc_so()
        t = so["tau"].setdefault(k, {"vessel_id": vessel_id})
        cur = t.get(field)
        if cur and _norm(field, cur["value"]) == _norm(field, value):
            cur["so_lan"] = cur.get("so_lan", 1) + 1
            if nguon not in cur["nguon"]:
                cur["nguon"] = (cur["nguon"] + [nguon])[-5:]
        else:
            # giá trị mới (vd gia hạn giấy phép) thay giá trị cũ; lưu lịch sử
            if cur:
                t.setdefault("lich_su", []).append({"field": field, **cur})
            t[field] = {"value": value, "so_lan": 1, "nguon": [nguon]}
        t["cap_nhat"] = datetime.now().isoformat(timespec="seconds")
        _ghi_so(so)


def hoc_tu_doi_chieu_sc(rows, sc_number=""):
    """Học từ kết quả reconcile_sc_excel_vs_pdf: trường nào SC PDF khớp SC Excel -> ghi vào sổ."""
    n = 0
    for r in rows or []:
        e, fields = r.get("excel"), r.get("fields") or {}
        if not e:
            continue
        for f in TRUONG:
            if (fields.get(f) or {}).get("status") == "MATCH" and e.get(f):
                ghi_nhan(e["vessel_id"], f, e.get(f), f"SC {sc_number} PDF=Excel")
                n += 1
    return n


def kiem_tra(records):
    """So các dòng SC vừa đọc với sổ tàu. Thêm r['nghi_ngo'] khi mâu thuẫn. Trả số dòng bị nghi."""
    so = doc_so().get("tau", {})
    if not so:
        return 0
    dem = 0
    for r in records:
        t = so.get(_key(r.get("vessel_id")))
        if not t:
            continue
        ghi, o = [], []
        # hạn GP: chỉ so khi cùng số giấy phép (gia hạn thì số GP đổi)
        if t.get("licence_no") and t.get("licence_exp") and _norm("licence_no", r.get("licence_no")) == _norm("licence_no", t["licence_no"]["value"]):
            if r.get("licence_exp") and _norm("licence_exp", r["licence_exp"]) != _norm("licence_exp", t["licence_exp"]["value"]):
                ghi.append(f"Hạn GP đọc được {r['licence_exp']} nhưng sổ tàu ghi {t['licence_exp']['value']} "
                           f"(cùng số GP, đã xác nhận {t['licence_exp'].get('so_lan', 1)} lần)")
                o.append("licence_exp")
        if t.get("owner") and r.get("owner") and _norm("owner", r["owner"]) != _norm("owner", t["owner"]["value"]):
            ghi.append(f"Chủ tàu đọc được '{r['owner']}' nhưng sổ tàu ghi '{t['owner']['value']}'")
            o.append("owner")
        if t.get("gear") and r.get("gear") and _norm("gear", r["gear"]) != _norm("gear", t["gear"]["value"]):
            ghi.append(f"Ngư cụ đọc được '{r['gear']}' nhưng sổ tàu ghi '{t['gear']['value']}'")
            o.append("gear")
        if ghi:
            r.setdefault("nghi_ngo", []).extend(ghi)
            r["o_nghi_ngo"] = sorted(set(r.get("o_nghi_ngo", [])) | set(o))
            r["goi_y_so_tau"] = {f: t[f]["value"] for f in o}
            dem += 1
    return dem
