"""
HÀNG ĐỢI DUYỆT: gom mọi kết quả đối chiếu thành 1 danh sách mục cần người xử lý.

Mỗi mục (dict):
  loai      : "SAI_LECH" (đọc chắc chắn nhưng hồ sơ khác nhau) | "CAN_XEM" (máy đọc chưa chắc / cần người nhìn)
  nhom      : "XNNL ↔ SC" | "Bảng kê ↔ SC" | "Bảng kê ↔ Hóa đơn" | "Đọc SC" | "SC Excel ↔ PDF"
  tieu_de   : vd "BĐ-96680-TS · Tên chủ tàu"
  mo_ta     : 1 dòng ngắn
  nguon     : [(tên nguồn, giá trị, trạng thái "ok"|"lech"|"nghi")]
  ly_do     : [chuỗi giải thích]
  de_xuat   : chuỗi hành động đề xuất (có thể rỗng)
  vessel_id, field, sc_number, sc_file, page : để cắt ảnh SC đúng dòng / ghi sổ tàu
  gia_tri_sc: giá trị trên SC (để "Chấp nhận theo SC" ghi sổ tàu)
Thống kê: dem_kiem (số tàu/hóa đơn đã kiểm), dem_tu_duyet, dem_can_xem, dem_sai_lech.
"""
import os

from sc_core.reconciler import clean_vessel_key

FIELD_SC = {  # nhãn trường trong diff -> khóa record SC
    "Tên Chủ tàu / Thuyền trưởng": "owner", "Tên Chủ tàu": "owner",
    "Số Giấy phép KTTS": "licence_no", "Hạn Giấy phép KTTS": "licence_exp",
    "Ngày lên cá / bốc dỡ": "landing_date", "Khối lượng nguyên liệu mua (kg)": "req_catch_kg",
    "Khối lượng tàu (kg)": "req_catch_kg", "Thời gian khai thác": "catch_period",
}
TEN_TRUONG = {"owner": "Tên chủ tàu", "licence_no": "Số GPKTTS", "licence_exp": "Hạn GPKTTS",
              "landing_date": "Ngày bốc dỡ", "req_catch_kg": "KL nguyên liệu mua", "total_catch_kg": "KL khai thác",
              "gear": "Ngư cụ", "catch_period": "Thời gian khai thác", "catch_area": "Vùng khai thác",
              "species": "Loài thủy sản", "validity": "Khai thác & bốc dỡ trong hạn GP",
              "landing_order": "Bốc dỡ sau ngày khai thác"}


def _sc_index(master_res):
    """(sc_number_ngắn, vessel_key) -> (record, file_path); vessel_key -> [(record, file_path)]."""
    by_sc_v, by_v = {}, {}
    seen = set()
    for _k, pack in (master_res.get("sc_repo") or {}).items():
        if not isinstance(pack, dict):
            continue
        fp = pack.get("file_path")
        for r in pack.get("records") or []:
            if id(r) in seen:
                continue
            seen.add(id(r))
            vk = clean_vessel_key(r.get("vessel_id"))
            sc = str(r.get("sc_number") or "")[:10]
            by_sc_v[(sc, vk)] = (r, fp)
            by_v.setdefault(vk, []).append((r, fp))
    return by_sc_v, by_v


def _tim_sc(idx, vessel_id, sc_number=""):
    by_sc_v, by_v = idx
    vk = clean_vessel_key(vessel_id)
    hit = by_sc_v.get((str(sc_number or "")[:10], vk))
    if hit:
        return hit
    lst = by_v.get(vk) or []
    return lst[0] if lst else (None, None)


def _loai(t):
    return "SAI_LECH" if t == "CRITICAL" else "CAN_XEM"


COT_MA_TRAN = [("owner", "Chủ tàu"), ("licence_no", "Số GPKTTS"), ("licence_exp", "Hạn GP"),
               ("catch_period", "TG khai thác"), ("landing_date", "Ngày bốc dỡ"), ("kg", "KL mua"),
               ("in_sc", "Có trên SC"), ("hd", "Hóa đơn VAT")]
_FIELD_COT = {
    "Tên Chủ tàu / Thuyền trưởng": "owner", "Tên Chủ tàu": "owner",
    "Số Giấy phép KTTS": "licence_no", "Hạn Giấy phép KTTS": "licence_exp",
    "Thời gian khai thác": "catch_period", "Ngày lên cá / bốc dỡ": "landing_date",
    "Khối lượng nguyên liệu mua (kg)": "kg", "Khối lượng tàu (kg)": "kg",
    "Tồn tại trong SC": "in_sc", "Tờ Giấy SC Cảng cá": "in_sc", "Giấy xác nhận SC": "in_sc", "Tàu trong Giấy SC": "in_sc",
}
_UU_TIEN = {"na": 0, "ok": 1, "xem": 2, "lech": 3}


def tao_ma_tran(master_res):
    """
    Ma trận tàu × tiêu chí. Trả {"cot": [(khóa, nhãn)], "dong": [{"vessel_id", "sc", "o": {khóa: (trạng thái, chú thích)}}]}
    trạng thái: ok (khớp mọi nguồn) | xem (cần người xem) | lech (sai lệch thật) | na (không áp dụng / không có dữ liệu)
    """
    dong, theo_v = [], {}

    def lay(vid, sc=""):
        vk = clean_vessel_key(vid)
        if not vk:
            return None
        if vk not in theo_v:
            theo_v[vk] = {"vessel_id": vid, "sc": sc or "", "o": {k: ("na", "") for k, _ in COT_MA_TRAN}}
            dong.append(theo_v[vk])
        if sc and not theo_v[vk]["sc"]:
            theo_v[vk]["sc"] = sc
        return theo_v[vk]

    def dat(d, cot, tt, ghi=""):
        cu, ghi_cu = d["o"].get(cot, ("na", ""))
        if _UU_TIEN[tt] > _UU_TIEN[cu]:
            d["o"][cot] = (tt, ghi)
        elif _UU_TIEN[tt] == _UU_TIEN[cu] and ghi and ghi not in ghi_cu:
            d["o"][cot] = (cu, (ghi_cu + "\n" + ghi).strip())

    luong = [("XNNL", (master_res.get("xnnl_vs_sc") or {}).get("recons") or [], "sc_number"),
             ("Bảng kê", (master_res.get("bk_vs_sc") or {}).get("recons") or [], "sc_no")]
    for ten, recons, k_sc in luong:
        for r in recons:
            d = lay(r.get("vessel_id"), r.get(k_sc))
            if d is None:
                continue
            bi = set()
            for df in r.get("diffs") or []:
                cot = _FIELD_COT.get(df.get("field"))
                if not cot:
                    continue
                t = df.get("type")
                tt = "lech" if t == "CRITICAL" else ("xem" if t == "WARNING" else "ok")
                dat(d, cot, tt, f"{ten}: {df.get('message') or df.get('field')}")
                bi.add(cot)
            # trường không bị báo trong luồng này -> khớp
            cot_luong = ["owner", "kg", "in_sc"] + (["licence_no", "licence_exp", "catch_period", "landing_date"] if ten == "XNNL" else [])
            for cot in cot_luong:
                if cot not in bi:
                    dat(d, cot, "ok", "")
    # Hóa đơn: gắn trạng thái hóa đơn cho các tàu có dòng bảng kê thuộc hóa đơn đó
    for r in (master_res.get("bk_vs_invoices") or {}).get("recons") or []:
        st = r.get("status")
        tt = "lech" if st in ("MISSING", "OVER_ALLOCATED") else ("xem" if st == "WARNING" else "ok")
        ghi = f"HĐ {r.get('hd_no')}: " + ("khớp" if tt == "ok" else "; ".join(
            d.get("message") or d.get("field", "") for d in r.get("diffs") or []) or st)
        for it in r.get("items") or []:
            d = lay(it.get("vessel_id"), it.get("sc_no"))
            if d:
                dat(d, "hd", tt, ghi)
    # Đọc SC còn nghi ngờ
    seen = set()
    for _k, pack in (master_res.get("sc_repo") or {}).items():
        for rec in (pack or {}).get("records") or [] if isinstance(pack, dict) else []:
            if id(rec) in seen or not rec.get("nghi_ngo"):
                continue
            seen.add(id(rec))
            d = theo_v.get(clean_vessel_key(rec.get("vessel_id")))
            if d:
                for f in rec.get("o_nghi_ngo") or []:
                    dat(d, "kg" if f.endswith("_kg") else f, "xem", "; ".join(rec["nghi_ngo"]))
    dong.sort(key=lambda d: (-max(_UU_TIEN[v[0]] for v in d["o"].values()), d["sc"], d["vessel_id"]))
    return {"cot": COT_MA_TRAN, "dong": dong}


def tao_hang_doi(master_res):
    idx = _sc_index(master_res)
    muc = []

    def them(loai, nhom, vessel_id, field_lbl, nguon, ly_do, de_xuat="", sc_number="", field_key=None):
        rec, fp = _tim_sc(idx, vessel_id, sc_number) if vessel_id else (None, None)
        fk = field_key or FIELD_SC.get(field_lbl)
        nhan = TEN_TRUONG.get(fk, field_lbl) if fk else field_lbl
        muc.append({
            "loai": loai, "nhom": nhom, "truong": nhan,
            "tieu_de": f"{vessel_id} · {nhan}" if vessel_id else nhan,
            "mo_ta": " | ".join(f"{n}: {v}" for n, v, _ in nguon[:2]),
            "nguon": nguon, "ly_do": [x for x in ly_do if x], "de_xuat": de_xuat,
            "vessel_id": vessel_id, "field": fk,
            "sc_number": (rec or {}).get("sc_number") or sc_number, "sc_file": fp,
            "page": (rec or {}).get("page"),
            "gia_tri_sc": (rec or {}).get(fk) if (rec and fk) else None,
        })

    # Bảng kê theo tàu: thêm làm nguồn thứ 3 cho mục XNNL ↔ SC
    bk_v = {}
    for b in master_res.get("bang_ke_records") or []:
        e = bk_v.setdefault(clean_vessel_key(b.get("vessel_id")), {"owner": b.get("owner"), "qty": 0.0})
        e["qty"] += float(b.get("qty") or 0)

    # 1. XNNL ↔ SC
    x = (master_res.get("xnnl_vs_sc") or {}).get("recons") or []
    for r in x:
        for d in r.get("diffs") or []:
            if d.get("type") == "INFO":
                continue
            nguon = [("Hồ sơ · XNNL (PMSX)", d.get("excel_val"), "lech"), ("SC gốc (bản scan)", d.get("sc_val"), "ok")]
            bk = bk_v.get(clean_vessel_key(r.get("vessel_id")))
            fk = FIELD_SC.get(d.get("field", ""))
            if bk and fk == "owner":
                nguon.append(("Bảng kê (tham khảo)", bk["owner"], "tham_khao"))
            elif bk and fk == "req_catch_kg":
                nguon.append(("Bảng kê (tổng)", f"{bk['qty']:,.1f}", "tham_khao"))
            them(_loai(d.get("type")), "XNNL ↔ SC", r.get("vessel_id"), d.get("field", ""),
                 nguon, [d.get("message")], "; ".join(r.get("action_needed") or []), r.get("sc_number"))
    # 2. Bảng kê ↔ SC
    for r in (master_res.get("bk_vs_sc") or {}).get("recons") or []:
        for d in r.get("diffs") or []:
            if d.get("type") == "INFO":
                continue
            them(_loai(d.get("type")), "Bảng kê ↔ SC", r.get("vessel_id"), d.get("field", ""),
                 [("Hồ sơ · Bảng kê", d.get("bk_val"), "lech"), ("SC gốc (bản scan)", d.get("sc_val"), "ok")],
                 [d.get("message")], "; ".join(r.get("action_needed") or []), r.get("sc_no"))
    # 3. Bảng kê ↔ Hóa đơn
    for r in (master_res.get("bk_vs_invoices") or {}).get("recons") or []:
        for d in r.get("diffs") or []:
            if d.get("type") == "INFO":
                continue
            them(_loai(d.get("type")), "Bảng kê ↔ Hóa đơn", None, f"HĐ {r.get('hd_no')} · {d.get('field', '')}",
                 [("Hồ sơ · Bảng kê", d.get("bk_val"), "lech"), ("Hóa đơn VAT", d.get("pdf_val"), "ok")],
                 [d.get("message")], "; ".join(r.get("action_needed") or []))
    # 4. Đọc SC chưa chắc (luật logic / sổ tàu / đọc lại vẫn nghi)
    seen = set()
    for _k, pack in (master_res.get("sc_repo") or {}).items():
        if not isinstance(pack, dict):
            continue
        for rec in pack.get("records") or []:
            if id(rec) in seen or not rec.get("nghi_ngo"):
                continue
            seen.add(id(rec))
            fk = (rec.get("o_nghi_ngo") or [None])[0]
            them("CAN_XEM", "Đọc SC", rec.get("vessel_id"), TEN_TRUONG.get(fk, "Dữ liệu SC"),
                 [("SC gốc (máy đọc)", rec.get(fk) if fk else "", "nghi")]
                 + [("Sổ tàu đã xác nhận", v, "ok") for f, v in (rec.get("goi_y_so_tau") or {}).items() if f == fk],
                 list(rec.get("nghi_ngo")), "Nhìn ảnh cắt dòng bên cạnh và chọn giá trị đúng",
                 rec.get("sc_number"), field_key=fk)
        for cb in (pack.get("sc_info") or {}).get("canh_bao") or []:
            if ("TOTAL" in cb or "OCR" in cb) and cb not in seen:
                seen.add(cb)
                them("CAN_XEM", "Đọc SC", None, f"SC {(pack.get('sc_info') or {}).get('sc_number', '')} · Tổng TOTAL",
                     [("Cảnh báo", cb, "nghi")], [cb], "Mở SC gốc kiểm tra các dòng bị đọc sót/sai")
    # 5. SC Excel ↔ PDF
    for res in master_res.get("sc_excel_vs_pdf") or []:
        if "rows" not in res:
            continue
        for row in res["rows"]:
            if row.get("status") in ("MATCH",):
                continue
            if row.get("status") in ("ONLY_EXCEL", "ONLY_PDF"):
                them("SAI_LECH", "SC Excel ↔ PDF", row.get("vessel_id"), "Có ở một bên",
                     [("Ghi chú", row.get("note"), "lech")], [row.get("note")])
                continue
            fields = row.get("fields") or {}
            co_lech_so_lieu = any(k not in ("validity", "landing_order") and v.get("status") != "MATCH"
                                  for k, v in fields.items())
            for fk, f in fields.items():
                if f.get("status") == "MATCH":
                    continue
                # Luật ngày (hạn GP / bốc dỡ sau khai thác) chỉ là HỆ QUẢ khi đã có ô số liệu lệch -> không tạo mục trùng
                if fk in ("validity", "landing_order") and co_lech_so_lieu:
                    continue
                them("SAI_LECH" if f.get("status") == "MISMATCH" else "CAN_XEM", "SC Excel ↔ PDF",
                     row.get("vessel_id"), TEN_TRUONG.get(fk, fk),
                     [("Hồ sơ · SC Excel", f.get("excel"), "lech"), ("SC gốc (bản scan)", f.get("pdf"), "ok")],
                     [f.get("note")], field_key=fk if fk in TEN_TRUONG else None)

    muc.sort(key=lambda m: (m["loai"] != "SAI_LECH", m["nhom"], str(m["vessel_id"] or "")))
    dem_kiem = (len((master_res.get("xnnl_vs_sc") or {}).get("recons") or [])
                + len((master_res.get("bk_vs_sc") or {}).get("recons") or [])
                + len((master_res.get("bk_vs_invoices") or {}).get("recons") or []))
    co_van_de = set()
    for m in muc:
        co_van_de.add((m["nhom"], m["vessel_id"] or m["tieu_de"]))
    return {
        "muc": muc,
        "dem_kiem": dem_kiem,
        "dem_can_xem": sum(1 for m in muc if m["loai"] == "CAN_XEM"),
        "dem_sai_lech": sum(1 for m in muc if m["loai"] == "SAI_LECH"),
        "dem_tu_duyet": max(0, dem_kiem - len({k for k in co_van_de if k[0] != "Đọc SC"})),
    }
