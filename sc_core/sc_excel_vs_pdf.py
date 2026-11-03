"""
Đối chiếu Giấy xác nhận nguyên liệu (SC) dạng file Excel với bản SC scan PDF.

- load_sc_excel(): đọc bảng "Thông tin tàu cá" trong file SC Excel -> (sc_info, records)
  (records dùng cùng schema với bản bóc tách PDF của sc_extractor / ai_extractor).
- reconcile_sc_excel_vs_pdf(): so khớp từng tàu + từng trường + tổng số liệu.
- add_sc_excel_vs_pdf_sheet(): ghi kết quả thành sheet Excel (dùng trong báo cáo tổng).
"""
import os
import re
from datetime import datetime, date

import openpyxl

from sc_core.reconciler import strip_vietnamese_accents, clean_vessel_key

TOL_KG = 0.5

FIELD_LABELS = [
    ("owner", "Chủ tàu / Thuyền trưởng"),
    ("gear", "Ngư cụ"),
    ("licence_no", "Số GPKTTS"),
    ("licence_exp", "Hạn GPKTTS"),
    ("catch_area", "Vùng khai thác"),
    ("catch_period", "Thời gian khai thác"),
    ("species", "Loài thủy sản"),
    ("landing_date", "Ngày bốc dỡ"),
    ("req_catch_kg", "KL nguyên liệu mua (kg)"),
    ("total_catch_kg", "KL khai thác (kg)"),
]

_DATE_RE = re.compile(r"(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{4})")


# ------------------------------------------------------------------ helpers
def _s(v):
    return "" if v is None else str(v).replace("\xa0", " ").strip()


def _norm_text(v):
    """Bỏ dấu, hạ chữ thường, chỉ giữ chữ-số."""
    return re.sub(r"[^a-z0-9]", "", strip_vietnamese_accents(_s(v)))


def _dates_in(v):
    out = []
    if isinstance(v, (datetime, date)):
        return [v.strftime("%d/%m/%Y")]
    for d, m, y in _DATE_RE.findall(_s(v)):
        out.append(f"{int(d):02d}/{int(m):02d}/{y}")
    return out


def _to_float(v):
    if v is None or _s(v) in ("", "-", "–"):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = _s(v).replace(" ", "")
    if re.search(r"\d,\d{3}(?!\d)", t) and "." not in t:
        t = t.replace(",", "")
    elif "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    else:
        t = t.replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    return float(m.group(0)) if m else None


def _fao_codes(v):
    t = strip_vietnamese_accents(_s(v)).upper()
    return sorted(set(re.sub(r"\s+", "", c) for c in re.findall(r"FAO\s*\d+\s*-\s*[A-Z0-9]+", t)))


def _species_key(v):
    """Ưu tiên tên khoa học trong ngoặc, nếu không có thì dùng cả chuỗi."""
    t = _s(v)
    m = re.search(r"\(([^)]+)\)", t)
    if m:
        return _norm_text(m.group(1))
    return _norm_text(t)


def normalize_sc_number(s):
    """00080/2026/SC-ĐL-ĐT -> '00080/2026/SC-DL-DT' (bỏ dấu, bỏ khoảng trắng, in hoa)."""
    t = strip_vietnamese_accents(_s(s)).upper()
    t = re.sub(r"\s+", "", t)
    m = re.search(r"\d{3,6}/\d{4}/SC-[A-Z]{1,4}-[A-Z]{1,4}", t)
    if m:
        return m.group(0)
    m = re.search(r"(\d{3,6})[/_\-.\s]?(\d{4})", t)
    return f"{int(m.group(1)):05d}/{m.group(2)}" if m else t


# ------------------------------------------------------------------ Excel loader
def _find_header(ws):
    """Tìm dòng tiêu đề bảng tàu cá và ánh xạ cột."""
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 60)):
        cells = {c.column: strip_vietnamese_accents(_s(c.value)) for c in row if c.value is not None}
        txt = " | ".join(cells.values())
        if "so dang" in txt.replace("\n", " ") and "chu tau" in txt.replace("\n", " "):
            cm = {}
            for col, t in cells.items():
                t = re.sub(r"\s+", " ", t)
                if "so dang" in t: cm["vessel_id"] = col
                elif "chu tau" in t: cm["owner"] = col
                elif "ngu cu" in t: cm["gear"] = col
                elif "giay phep" in t or "gpkt" in t: cm["licence"] = col
                elif "vung" in t and "thoi gian" in t: cm["area_period"] = col
                elif "ten loai" in t: cm["species"] = col
                elif "ngay boc" in t: cm["landing_date"] = col
                elif "mua tu tau" in t: cm["req_catch_kg"] = col
                elif "khai thac cua tau" in t: cm["total_catch_kg"] = col
            return row[0].row, cm
    return None, {}


def load_sc_excel(file_path):
    """Đọc SC dạng Excel. Trả về (sc_info, records)."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}")
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = None
    hdr_row, cm = None, {}
    for cand in wb.worksheets:
        hdr_row, cm = _find_header(cand)
        if hdr_row and "vessel_id" in cm:
            ws = cand
            break
    if ws is None:
        raise ValueError("Không tìm thấy bảng 'Thông tin tàu cá' trong file SC Excel.")

    # ---- Header thông tin chung
    sc_number, company = "", ""
    for row in ws.iter_rows(min_row=1, max_row=hdr_row):
        for c in row:
            t = _s(c.value)
            if not sc_number and re.search(r"\d{3,6}\s*/\s*\d{4}\s*/\s*SC", t, re.I):
                sc_number = t
            if "Tổ chức, cá nhân đề nghị xác nhận" in t:
                nxt = ws.cell(row=c.row, column=c.column + 1).value
                company = _s(nxt)

    def get(r, key):
        col = cm.get(key)
        return ws.cell(row=r, column=col).value if col else None

    records, sheet_total = [], {}
    for r in range(hdr_row + 1, ws.max_row + 1):
        # dòng TOTAL
        row_vals = [_s(ws.cell(row=r, column=c).value).upper() for c in range(1, ws.max_column + 1)]
        if "TOTAL" in row_vals:
            vals = {k: _to_float(get(r, k)) for k in ("req_catch_kg", "total_catch_kg")}
            sheet_total = vals
            break
        vid = _s(get(r, "vessel_id"))
        if not vid or not re.search(r"\d{3,}", vid):
            continue
        lic_raw = _s(get(r, "licence"))
        lic_dates = _dates_in(lic_raw)
        lic_no = re.split(r"[\n\r]", lic_raw)[0].strip()
        ap_raw = _s(get(r, "area_period"))
        period_dates = _dates_in(ap_raw)
        area = ", ".join(_fao_codes(ap_raw))
        rq = _to_float(get(r, "req_catch_kg"))
        tc = _to_float(get(r, "total_catch_kg"))
        ld = _dates_in(get(r, "landing_date"))
        records.append({
            "sc_number": sc_number,
            "excel_row": r,
            "vessel_id": vid,
            "owner": _s(get(r, "owner")),
            "gear": _s(get(r, "gear")),
            "licence_no": lic_no,
            "licence_exp": lic_dates[-1] if lic_dates else "",
            "catch_area": area,
            "catch_period": " - ".join(period_dates[:2]),
            "species": _s(get(r, "species")).replace("\n", " "),
            "landing_date": ld[0] if ld else "",
            "total_catch_kg": tc if tc is not None else 0.0,
            "req_catch_kg": rq if rq is not None else 0.0,
        })

    info = {
        "sc_number": sc_number,
        "company": company,
        "file_name": os.path.basename(file_path),
        "total_vessels": len(records),
        "total_catch_kg": sum(x["total_catch_kg"] for x in records),
        "total_req_catch_kg": sum(x["req_catch_kg"] for x in records),
        "sheet_total_req_kg": sheet_total.get("req_catch_kg"),
        "sheet_total_catch_kg": sheet_total.get("total_catch_kg"),
    }
    return info, records


# ------------------------------------------------------------------ comparison
def _cmp_field(key, a, b):
    """Trả về (status, ghi_chú). status: MATCH / WARN / MISMATCH."""
    if key in ("req_catch_kg", "total_catch_kg"):
        fa, fb = _to_float(a) or 0.0, _to_float(b) or 0.0
        if abs(fa - fb) <= TOL_KG:
            return "MATCH", ""
        return "MISMATCH", f"Lệch {fa - fb:+,.1f} kg"
    if key in ("licence_exp", "landing_date"):
        da, db = _dates_in(a), _dates_in(b)
        if not da and not db:
            return "MATCH", ""
        return ("MATCH", "") if da == db else ("MISMATCH", "Khác ngày")
    if key == "catch_period":
        da, db = _dates_in(a), _dates_in(b)
        if not da and not db:
            return "MATCH", ""
        return ("MATCH", "") if da == db else ("MISMATCH", "Khác thời gian")
    if key == "catch_area":
        fa, fb = set(_fao_codes(a)), set(_fao_codes(b))
        if fa == fb:
            return "MATCH", ""
        return "MISMATCH", f"Chỉ Excel: {', '.join(sorted(fa - fb)) or '-'} | Chỉ PDF: {', '.join(sorted(fb - fa)) or '-'}"
    if key == "species":
        ka, kb = _species_key(a), _species_key(b)
        if ka == kb or (ka and kb and (ka in kb or kb in ka)):
            return "MATCH", ""
        return "MISMATCH", "Khác loài"
    if key == "licence_no":
        ka, kb = _norm_text(a), _norm_text(b)
        if ka == kb:
            return "MATCH", ""
        # cùng phần số, khác phần chữ (vd GPKKTS vs GPKTTS)
        na, nb = re.findall(r"\d+", _s(a)), re.findall(r"\d+", _s(b))
        return "MISMATCH", ("Cùng số, khác ký hiệu" if na == nb else "Khác số GPKTTS")
    if key == "gear":
        return ("MATCH", "") if _norm_text(a) == _norm_text(b) else ("MISMATCH", "Khác ngư cụ")
    # owner & text khác
    ta, tb = _s(a).replace("Ð", "Đ").lower(), _s(b).replace("Ð", "Đ").lower()
    if re.sub(r"\s+", " ", ta) == re.sub(r"\s+", " ", tb):
        return "MATCH", ""
    if _norm_text(a) == _norm_text(b):
        return "WARN", "Chỉ khác dấu tiếng Việt"
    return "MISMATCH", "Khác nội dung"


def _d(s):
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except Exception:
        return None


def check_licence_validity(rec):
    """
    Kiểm tra: thời gian khai thác và ngày bốc dỡ phải nằm trong thời hạn giấy phép (<= hạn GPKTTS).
    Trả về (status, ghi_chú). status: MATCH / MISMATCH / WARN (thiếu dữ liệu).
    """
    exp = _d("".join(_dates_in(rec.get("licence_exp"))[:1]))
    period = _dates_in(rec.get("catch_period"))
    start = _d(period[0]) if period else None
    end = _d(period[-1]) if period else None
    land = _d("".join(_dates_in(rec.get("landing_date"))[:1]))
    if not exp:
        return "WARN", "Không có hạn giấy phép để kiểm tra"
    errs = []
    if start and start > exp:
        errs.append(f"Ngày bắt đầu khai thác {start:%d/%m/%Y} sau hạn GP {exp:%d/%m/%Y}")
    if end and end > exp:
        errs.append(f"Ngày kết thúc khai thác {end:%d/%m/%Y} sau hạn GP {exp:%d/%m/%Y}")
    if start and end and start > end:
        errs.append("Ngày bắt đầu khai thác sau ngày kết thúc")
    if land and land > exp:
        errs.append(f"Ngày bốc dỡ {land:%d/%m/%Y} sau hạn GP {exp:%d/%m/%Y}")
    if not period or not land:
        return ("MISMATCH", "; ".join(errs)) if errs else ("WARN", "Thiếu thời gian khai thác hoặc ngày bốc dỡ")
    return ("MISMATCH", "; ".join(errs)) if errs else ("MATCH", "")


def check_landing_after_catch(rec):
    """
    Kiểm tra: ngày bốc dỡ phải SAU (hoặc cùng ngày) ngày kết thúc khai thác.
    Trả về (status, ghi_chú). status: MATCH / MISMATCH / WARN (thiếu dữ liệu).
    """
    period = _dates_in(rec.get("catch_period"))
    start = _d(period[0]) if period else None
    end = _d(period[-1]) if period else None
    land = _d("".join(_dates_in(rec.get("landing_date"))[:1]))
    if not land or not end:
        return "WARN", "Thiếu ngày bốc dỡ hoặc thời gian khai thác"
    if start and land < start:
        return "MISMATCH", f"Bốc dỡ {land:%d/%m/%Y} trước cả ngày bắt đầu khai thác {start:%d/%m/%Y}"
    if land < end:
        return "MISMATCH", f"Bốc dỡ {land:%d/%m/%Y} trước ngày kết thúc khai thác {end:%d/%m/%Y}"
    return "MATCH", ""


# Các cột kiểm tra quy tắc (áp dụng riêng cho cả bản Excel và bản SC gốc):
# (khóa, tiêu đề cột, hàm kiểm tra, tên ngắn, chữ hiển thị khi đạt)
RULE_CHECKS = [
    ("validity", "Khai thác & bốc dỡ trong hạn GP", check_licence_validity, "Hiệu lực GP", "Hợp lệ"),
    ("landing_order", "Ngày bốc dỡ sau ngày khai thác", check_landing_after_catch, "Bốc dỡ sau khai thác", "Đúng"),
]


def rule_display(key, rec):
    """Chữ hiển thị kết quả kiểm tra quy tắc của 1 bản ghi (dùng cho báo cáo và giao diện)."""
    if rec is None:
        return "-"
    for k, _, fn, _, ok_txt in RULE_CHECKS:
        if k == key:
            return fn(rec)[1] or ok_txt
    return "-"


def _pair_records(ex_list, pdf_list):
    """Ghép các dòng cùng 1 tàu (nhiều dòng/loài) theo loài -> ngày bốc dỡ -> thứ tự."""
    pairs, left_pdf = [], list(pdf_list)
    for e in ex_list:
        best, best_score = None, -1
        for p in left_pdf:
            score = 0
            if _species_key(e["species"]) == _species_key(p.get("species")): score += 2
            if e["landing_date"] == "".join(_dates_in(p.get("landing_date"))[:1]): score += 2
            if abs((e["req_catch_kg"] or 0) - (_to_float(p.get("req_catch_kg")) or 0)) <= TOL_KG: score += 1
            if score > best_score:
                best, best_score = p, score
        if best is not None:
            left_pdf.remove(best)
        pairs.append((e, best))
    return pairs, left_pdf


def reconcile_sc_excel_vs_pdf(excel_info, excel_records, pdf_info, pdf_records):
    """
    So khớp SC Excel với SC PDF scan.
    Trả về dict: header_checks, rows, summary.
    """
    pdf_info = pdf_info or {}
    header_checks = []

    def hc(label, ex_v, pdf_v, status, note=""):
        header_checks.append({"label": label, "excel": ex_v, "pdf": pdf_v, "status": status, "note": note})

    # --- Số SC
    ex_sc, pdf_sc = normalize_sc_number(excel_info.get("sc_number")), normalize_sc_number(pdf_info.get("sc_number"))
    hc("Số Giấy xác nhận SC", excel_info.get("sc_number", ""), pdf_info.get("sc_number", ""),
       "MATCH" if ex_sc == pdf_sc else "MISMATCH", "" if ex_sc == pdf_sc else "Khác số SC")
    # --- Số tàu
    n_ex, n_pdf = len(excel_records), len(pdf_records)
    hc("Tổng số tàu", n_ex, n_pdf, "MATCH" if n_ex == n_pdf else "MISMATCH",
       "" if n_ex == n_pdf else f"Lệch {n_ex - n_pdf:+d} tàu")
    # --- Tổng khối lượng (cộng từ các dòng)
    sum_ex_rq = sum(r["req_catch_kg"] for r in excel_records)
    sum_pdf_rq = sum(_to_float(r.get("req_catch_kg")) or 0 for r in pdf_records)
    sum_ex_tc = sum(r["total_catch_kg"] for r in excel_records)
    sum_pdf_tc = sum(_to_float(r.get("total_catch_kg")) or 0 for r in pdf_records)
    for lbl, a, b in (("Tổng KL nguyên liệu mua (kg)", sum_ex_rq, sum_pdf_rq),
                      ("Tổng KL khai thác (kg)", sum_ex_tc, sum_pdf_tc)):
        ok = abs(a - b) <= TOL_KG
        hc(lbl, a, b, "MATCH" if ok else "MISMATCH", "" if ok else f"Lệch {a - b:+,.1f} kg")
    # --- Tổng in trên tờ giấy so với cộng dòng (kiểm tra nội bộ từng bên)
    if excel_info.get("sheet_total_req_kg") is not None:
        a, b = excel_info["sheet_total_req_kg"], sum_ex_rq
        ok = abs(a - b) <= TOL_KG
        hc("Excel: ô TOTAL so với cộng các dòng", a, b, "MATCH" if ok else "MISMATCH",
           "" if ok else "Ô TOTAL trong Excel không bằng tổng các dòng")
    if pdf_info.get("total_req_catch_kg") is not None:
        a, b = _to_float(pdf_info.get("total_req_catch_kg")) or 0, sum_pdf_rq
        ok = abs(a - b) <= TOL_KG
        hc("PDF: dòng TOTAL so với cộng các dòng", a, b, "MATCH" if ok else "MISMATCH",
           "" if ok else "Tổng in trên PDF không bằng tổng các dòng (có thể AI đọc sót/sai)")

    # --- Từng tàu
    ex_map, pdf_map = {}, {}
    for r in excel_records:
        ex_map.setdefault(clean_vessel_key(r["vessel_id"]), []).append(r)
    for r in pdf_records:
        pdf_map.setdefault(clean_vessel_key(r.get("vessel_id")), []).append(r)

    rows = []
    for vk, e_list in ex_map.items():
        p_list = pdf_map.get(vk, [])
        if not p_list:
            for e in e_list:
                rows.append({"vessel_id": e["vessel_id"], "status": "ONLY_EXCEL", "excel": e, "pdf": None,
                             "fields": {}, "diff_fields": [], "note": "Có trong Excel nhưng không thấy trong PDF"})
            continue
        pairs, left = _pair_records(e_list, p_list)
        for e, p in pairs:
            if p is None:
                rows.append({"vessel_id": e["vessel_id"], "status": "ONLY_EXCEL", "excel": e, "pdf": None,
                             "fields": {}, "diff_fields": [], "note": "Dòng dư trong Excel"})
                continue
            fields, diffs, warns = {}, [], []
            for key, label in FIELD_LABELS:
                st, note = _cmp_field(key, e.get(key), p.get(key))
                fields[key] = {"status": st, "note": note, "excel": e.get(key), "pdf": p.get(key)}
                if st == "MISMATCH": diffs.append(label)
                elif st == "WARN": warns.append(label)
            _lbl = dict(FIELD_LABELS)
            for rkey, _rtitle, rfn, rshort, ok_txt in RULE_CHECKS:
                vsrc = {}
                for src_name, rec in (("Excel", e), ("PDF", p)):
                    st_v, nt_v = rfn(rec)
                    vsrc[src_name] = {"status": st_v, "note": nt_v}
                    if st_v == "MISMATCH": diffs.append(f"{rshort} ({src_name})")
                    elif st_v == "WARN": warns.append(f"{rshort} ({src_name})")
                fields[rkey] = {"status": "MISMATCH" if any(v["status"] == "MISMATCH" for v in vsrc.values())
                                else ("WARN" if any(v["status"] == "WARN" for v in vsrc.values()) else "MATCH"),
                                "note": "; ".join(f"{k}: {v['note']}" for k, v in vsrc.items() if v["note"]),
                                "excel": vsrc["Excel"]["note"] or ok_txt, "pdf": vsrc["PDF"]["note"] or ok_txt}
                _lbl[rkey] = rshort
            status = "MISMATCH" if diffs else ("WARN" if warns else "MATCH")
            notes = [f"{_lbl[k]}: {fields[k]['note']}"
                     for k in fields if fields[k]["status"] != "MATCH" and fields[k]["note"]]
            rows.append({"vessel_id": e["vessel_id"], "status": status, "excel": e, "pdf": p,
                         "fields": fields, "diff_fields": diffs + warns, "note": "; ".join(notes)})
        for p in left:
            rows.append({"vessel_id": p.get("vessel_id", ""), "status": "ONLY_PDF", "excel": None, "pdf": p,
                         "fields": {}, "diff_fields": [], "note": "Dòng dư trong PDF"})
    for vk, p_list in pdf_map.items():
        if vk not in ex_map:
            for p in p_list:
                rows.append({"vessel_id": p.get("vessel_id", ""), "status": "ONLY_PDF", "excel": None, "pdf": p,
                             "fields": {}, "diff_fields": [], "note": "Có trong PDF nhưng không thấy trong Excel"})

    cnt = lambda s: sum(1 for r in rows if r["status"] == s)
    hdr_bad = sum(1 for h in header_checks if h["status"] != "MATCH")
    summary = {
        "total_excel": n_ex, "total_pdf": n_pdf,
        "match": cnt("MATCH"), "warn": cnt("WARN"), "mismatch": cnt("MISMATCH"),
        "only_excel": cnt("ONLY_EXCEL"), "only_pdf": cnt("ONLY_PDF"),
        "header_issues": hdr_bad,
        "all_ok": hdr_bad == 0 and cnt("MATCH") == len(rows),
    }
    return {"excel_info": excel_info, "pdf_info": pdf_info, "header_checks": header_checks,
            "rows": rows, "summary": summary}


def run_sc_excel_vs_pdf(excel_path, pdf_path, **extract_kwargs):
    """Tiện ích: đọc Excel + bóc tách PDF + đối chiếu."""
    from sc_core.sc_extractor import extract_sc_document
    ex_info, ex_recs = load_sc_excel(excel_path)
    pdf_info, pdf_recs = extract_sc_document(pdf_path, **extract_kwargs)
    return reconcile_sc_excel_vs_pdf(ex_info, ex_recs, pdf_info, pdf_recs)


# ------------------------------------------------------------------ report
def _sc_label(res):
    """Số SC hiển thị cho 1 kết quả: ưu tiên số trên Excel, không có thì lấy số trên PDF / tên file."""
    raw = ((res.get("excel_info") or {}).get("sc_number") or (res.get("pdf_info") or {}).get("sc_number") or "")
    return _clean_sc(raw) or os.path.basename(res.get("file", ""))


def _clean_sc(raw):
    """'Số: 00080/2026/SC-ĐL-ĐT' -> '00080/2026/SC-ĐL-ĐT' (giữ dấu tiếng Việt)."""
    m = re.search(r"\d{3,6}\s*/\s*\d{4}\s*/\s*SC[^\s,;]*", _s(raw), re.I)
    return re.sub(r"\s+", "", m.group(0)) if m else _s(raw)


def _lbl_short(label):
    return {"Số Giấy xác nhận SC": "Số SC", "Excel: ô TOTAL so với cộng các dòng": "Ô TOTAL Excel",
            "PDF: dòng TOTAL so với cộng các dòng": "Dòng TOTAL SC gốc"}.get(label, label)


def add_sc_excel_vs_pdf_sheet(wb, result, sheet_title="Đối Chiếu SC Excel vs PDF", insert_index=None, sc_repo=None):
    """
    Ghi kết quả đối chiếu SC Excel vs PDF vào 1 sheet duy nhất.
    result: 1 dict kết quả hoặc list nhiều kết quả (nhiều file SC Excel) -> tất cả chung 1 bảng,
    phân biệt bằng cột 'Số Giấy SC'.
    """
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    results = list(result) if isinstance(result, (list, tuple)) else [result]
    ok_list = [x for x in results if "rows" in x]
    err_list = [x for x in results if "error" in x]
    ws = wb.create_sheet(sheet_title, insert_index) if insert_index is not None else wb.create_sheet(sheet_title)
    fills = {"MATCH": "C6EFCE", "WARN": "FFEB9C", "MISMATCH": "FFC7CE", "ONLY_EXCEL": "F8CBAD", "ONLY_PDF": "F8CBAD",
             "ERROR": "F8CBAD"}
    fill = lambda k: PatternFill("solid", fgColor=fills[k])
    head_fill = PatternFill("solid", fgColor="1F4E78")
    thin = Side(style="thin", color="BBBBBB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    status_txt = {"MATCH": "Khớp", "WARN": "Lưu ý (dấu)", "MISMATCH": "LỆCH",
                  "ONLY_EXCEL": "Chỉ có trong Excel", "ONLY_PDF": "Chỉ có trong PDF", "ERROR": "Không đối chiếu được"}
    tot = {k: sum(x["summary"][k] for x in ok_list) for k in
           ("total_excel", "total_pdf", "match", "warn", "mismatch", "only_excel", "only_pdf")}
    all_ok = bool(ok_list) and not err_list and all(x["summary"]["all_ok"] for x in ok_list)

    ws["A1"] = "ĐỐI CHIẾU GIẤY XÁC NHẬN SC: FILE EXCEL vs BẢN SCAN PDF"
    ws["A1"].font = Font(bold=True, size=14)
    if len(results) == 1 and ok_list:
        ws["A2"] = f"Excel: {ok_list[0]['excel_info'].get('file_name', '')}   |   PDF: {ok_list[0]['pdf_info'].get('file_name', '')}"
    else:
        ws["A2"] = (f"Số file SC Excel: {len(results)} | Đối chiếu được: {len(ok_list)} | "
                    f"Khớp hoàn toàn: {sum(1 for x in ok_list if x['summary']['all_ok'])} | Không đối chiếu được: {len(err_list)}")
    ws["A3"] = (f"Tàu Excel: {tot['total_excel']} | Tàu PDF: {tot['total_pdf']} | Khớp: {tot['match']} | Lưu ý: {tot['warn']} | "
                f"Lệch: {tot['mismatch']} | Chỉ Excel: {tot['only_excel']} | Chỉ PDF: {tot['only_pdf']} | "
                f"Kết luận: {'KHỚP HOÀN TOÀN' if all_ok else 'CÓ SAI LỆCH CẦN RÀ SOÁT'}")
    ws["A3"].font = Font(bold=True, color="006100" if all_ok else "C00000")

    # ---- Bảng chi tiết (chung cho mọi SC): mỗi ô hiển thị "Excel: ..." / "SC gốc: ..."
    from openpyxl.utils import get_column_letter as L
    fields_all = list(FIELD_LABELS) + [(k, t) for k, t, *_ in RULE_CHECKS]
    rule_keys = {k for k, *_ in RULE_CHECKS}
    heads = ["STT", "Số ĐK Tàu", "Số Giấy SC", "Kết quả"] + [lb for _, lb in fields_all] + ["Chi tiết sai lệch"]
    F0 = 5  # cột bắt đầu của các trường so sánh
    r = r_h = 5
    for j, h in enumerate(heads, 1):
        c = ws.cell(row=r_h, column=j, value=h)
        c.font, c.fill, c.border = Font(bold=True, color="FFFFFF"), head_fill, border
        c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
    ws.row_dimensions[r_h].height = 32

    def disp(key, v):
        if v is None or v == "":
            return "-"
        if key in ("req_catch_kg", "total_catch_kg"):
            f = _to_float(v)
            return f"{f:,.0f}" if f is not None and float(f).is_integer() else (f"{f:,.1f}" if f is not None else str(v))
        return str(v).replace("\n", " ")

    all_rows = [(_sc_label(res), row) for res in ok_list for row in res["rows"]]
    for i, (sc_lbl, row) in enumerate(all_rows, 1):
        r += 1
        ws.cell(row=r, column=1, value=i).border = border
        c = ws.cell(row=r, column=2, value=row["vessel_id"])
        c.border, c.font = border, Font(bold=True)
        c = ws.cell(row=r, column=3, value=sc_lbl)
        c.border, c.font = border, Font(italic=True)
        c = ws.cell(row=r, column=4, value=status_txt[row["status"]])
        c.fill, c.border = fill(row["status"]), border
        for j in (1, 2, 3, 4):
            ws.cell(row=r, column=j).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ex, pf = row["excel"], row["pdf"]
        for j, (key, _) in enumerate(fields_all, F0):
            f = row["fields"].get(key)
            if key in rule_keys:
                vx, vp = rule_display(key, ex), rule_display(key, pf)
                st = f["status"] if f else None
            else:
                vx, vp = disp(key, ex.get(key) if ex else None), disp(key, pf.get(key) if pf else None)
                st = f["status"] if f else None
            c = ws.cell(row=r, column=j, value=f"Excel: {vx}\nSC gốc: {vp}")
            c.border = border
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if st:
                c.fill = fill(st)
            elif row["status"] in ("ONLY_EXCEL", "ONLY_PDF"):
                c.fill = fill(row["status"])
        c = ws.cell(row=r, column=len(heads), value=row["note"])
        c.border, c.alignment = border, Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 48 if any(
            len(str((ex or pf or {}).get(k, ""))) > 30 for k in ("species", "catch_area", "catch_period")) else 32

    # ---- Thông tin chung từng SC: MỖI SC 1 DÒNG, mỗi mục so sánh là 1 cột (ô: "Excel: ... / SC gốc: ...")
    r += 2
    ws.cell(row=r, column=1, value="KIỂM TRA THÔNG TIN CHUNG TỪNG SC").font = Font(bold=True, size=12)
    r += 1
    CHECKS = [  # (nhãn header_check trong reconcile_sc_excel_vs_pdf, tiêu đề cột, nhãn dòng 1, nhãn dòng 2)
        ("Số Giấy xác nhận SC", "Số SC", "Excel", "SC gốc"),
        ("Tổng số tàu", "Tổng số tàu", "Excel", "SC gốc"),
        ("Tổng KL nguyên liệu mua (kg)", "Tổng KL nguyên liệu mua (kg)", "Excel", "SC gốc"),
        ("Excel: ô TOTAL so với cộng các dòng", "Excel: ô TOTAL = cộng các dòng?", "Ô TOTAL", "Cộng dòng"),
        ("PDF: dòng TOTAL so với cộng các dòng", "SC gốc: dòng TOTAL = cộng các dòng?", "Dòng TOTAL", "Cộng dòng"),
    ]
    info_heads = ["STT", "Số Giấy SC", "Kết luận"] + [c[1] for c in CHECKS] + ["Ghi chú"]
    for j, h in enumerate(info_heads, 1):
        c = ws.cell(row=r, column=j, value=h)
        c.font, c.fill, c.border = Font(bold=True, color="FFFFFF"), head_fill, border
        c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
    ws.row_dimensions[r].height = 32

    def num(v):
        if isinstance(v, (int, float)):
            return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.1f}"
        return _s(v) or "-"

    def put_row(vals, concl_status, check_cells):
        nonlocal r
        r += 1
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=j, value=v)
            c.border, c.alignment = border, Alignment(wrap_text=True, vertical="top")
        ws.cell(row=r, column=2).font = Font(italic=True, bold=True)
        cc = ws.cell(row=r, column=3)
        cc.fill, cc.font = fill(concl_status), Font(bold=True)
        for j, st in check_cells:
            if st:
                ws.cell(row=r, column=j).fill = fill(st)
        ws.row_dimensions[r].height = 46

    n_info = 0
    C0 = 4  # cột bắt đầu của các mục so sánh
    for res in ok_list:
        n_info += 1
        hmap = {h["label"]: h for h in res["header_checks"]}
        cells, sts, notes = [], [], []
        for j, (lbl, _, l1, l2) in enumerate(CHECKS, C0):
            h = hmap.get(lbl)
            if not h:
                cells.append("-")
                sts.append((j, None))
                continue
            a, b = (h["excel"], h["pdf"]) if lbl != "Số Giấy xác nhận SC" else (_clean_sc(h["excel"]) or "-", _clean_sc(h["pdf"]) or "-")
            cells.append(f"{l1}: {num(a)}\n{l2}: {num(b)}")
            sts.append((j, h["status"]))
            if h["status"] != "MATCH" and h["note"]:
                notes.append(f"{_lbl_short(lbl)}: {h['note']}")
        s = res["summary"]
        if s["mismatch"] or s["only_excel"] or s["only_pdf"]:
            notes.append(f"Chi tiết tàu: lệch {s['mismatch']}, chỉ Excel {s['only_excel']}, chỉ PDF {s['only_pdf']}")
        if res.get("match_method") and res["match_method"] != "Số SC":
            notes.append(f"Ghép với SC gốc theo: {res['match_method']}")
        concl = "MATCH" if s["all_ok"] else "MISMATCH"
        put_row([n_info, _sc_label(res), "KHỚP HOÀN TOÀN" if s["all_ok"] else "CÓ SAI LỆCH"]
                + cells + ["; ".join(notes)], concl, sts)
    for res in err_list:
        n_info += 1
        put_row([n_info, _sc_label(res) or "-", "KHÔNG CÓ BẢN PDF"]
                + ["-"] * len(CHECKS) + [res["error"]], "ERROR", [])
    # Bản SC PDF không được file Excel nào dùng (sc_repo có thể lưu 1 bản dưới nhiều khóa -> xét theo từng bản thật)
    if sc_repo and ok_list:
        used_files = {os.path.normcase(x.get("pdf_file") or "") for x in ok_list if x.get("pdf_file")}
        used_nums = {_num_year((x.get("pdf_info") or {}).get("sc_number")) for x in ok_list} - {None}
        seen = set()
        for key, v in sc_repo.items():
            fpath = v.get("file_path") or ""
            ident = os.path.normcase(fpath) or id(v)
            if ident in seen:
                continue
            seen.add(ident)
            info = v.get("sc_info", {})
            if (fpath and os.path.normcase(fpath) in used_files) or _num_year(info.get("sc_number") or key) in used_nums:
                continue
            n_info += 1
            pdf_name = info.get("file_name") or os.path.basename(fpath)
            put_row([n_info, _sc_label({"pdf_info": info}) or key, "THIẾU FILE EXCEL",
                     "-", f"Excel: -\nSC gốc: {len(v.get('records', []))} tàu"]
                    + ["-"] * (len(CHECKS) - 2) + [f"Có bản SC gốc ({pdf_name}) nhưng chưa chọn file SC Excel tương ứng"],
                    "ERROR", [])

    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 24
    ws.column_dimensions["C"].width = 26
    ws.column_dimensions["D"].width = 30
    widths = {"owner": 30, "gear": 20, "licence_no": 30, "licence_exp": 20, "catch_area": 28, "catch_period": 34,
              "species": 40, "landing_date": 20, "req_catch_kg": 22, "total_catch_kg": 22, "validity": 34,
              "landing_order": 34}
    for j, (key, _) in enumerate(fields_all, F0):
        ws.column_dimensions[L(j)].width = widths.get(key, 24)
    ws.column_dimensions[L(len(heads))].width = 45
    # nới rộng các cột dùng chung với bảng thông tin chung
    for j, w in ((C0, 28), (C0 + len(CHECKS), 45)):
        ws.column_dimensions[L(j)].width = max(ws.column_dimensions[L(j)].width or 0, w)
    ws.freeze_panes = ws.cell(row=r_h + 1, column=F0)
    return ws


def add_sc_excel_vs_pdf_sheets(wb, results, sc_repo=None, insert_index=None):
    """Ghi kết quả của 1 hoặc nhiều file SC Excel vào DUY NHẤT 1 sheet (có cột 'Số Giấy SC')."""
    results = list(results or [])
    if not results:
        return []
    return [add_sc_excel_vs_pdf_sheet(wb, results, insert_index=insert_index, sc_repo=sc_repo)]


def export_sc_excel_vs_pdf_report(output_path, result_or_results, sc_repo=None):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    results = result_or_results if isinstance(result_or_results, list) else [result_or_results]
    add_sc_excel_vs_pdf_sheets(wb, results, sc_repo)
    wb.save(output_path)
    return output_path


def _num_year(sc_text):
    """'00080/2026/SC-...' -> (80, '2026'); không đọc được -> None."""
    m = re.match(r"(\d+)/(\d{4})", normalize_sc_number(sc_text))
    return (int(m.group(1)), m.group(2)) if m else None


def _num_year_from_filename(path):
    """'80 2026 SC DL DT.xlsx' / '00080_2026_SC.pdf' -> (80, '2026')."""
    bn = os.path.splitext(os.path.basename(path or ""))[0]
    m = re.search(r"(?<!\d)(\d{1,6})\D{0,3}(20\d{2})(?!\d)", bn)
    return (int(m.group(1)), m.group(2)) if m else None


def _vessel_overlap(ex_recs, pdf_recs):
    """Tỷ lệ số tàu của Excel có mặt trong PDF (0..1)."""
    ek = {clean_vessel_key(r.get("vessel_id")) for r in ex_recs if r.get("vessel_id")}
    pk = {clean_vessel_key(r.get("vessel_id")) for r in pdf_recs or [] if r.get("vessel_id")}
    return (len(ek & pk) / len(ek)) if ek else 0.0


def _find_pdf_pack(fp, ex_info, ex_recs, repo, n_excel):
    """
    Tìm bản SC PDF tương ứng cho 1 file SC Excel. Thứ tự ưu tiên:
      1. Trùng số SC đầy đủ
      2. Trùng số/năm SC
      3. Trùng số/năm đọc từ tên file (Excel hoặc PDF)
      4. Trùng danh sách tàu >= 60%
      5. Chỉ có 1 Excel và 1 PDF
    Trả về (key, pack, cách_ghép) hoặc (None, None, "").
    """
    items = list(repo.items())
    ex_key = normalize_sc_number(ex_info.get("sc_number"))
    ex_ny = _num_year(ex_info.get("sc_number")) or _num_year_from_filename(fp)

    def pdf_sc(k, v):
        return v.get("sc_info", {}).get("sc_number") or k

    if ex_info.get("sc_number"):
        for k, v in items:
            if normalize_sc_number(pdf_sc(k, v)) == ex_key:
                return k, v, "Số SC"
    if ex_ny:
        for k, v in items:
            if _num_year(pdf_sc(k, v)) == ex_ny:
                return k, v, "Số/năm SC"
        for k, v in items:
            if _num_year_from_filename(v.get("file_path") or v.get("sc_info", {}).get("file_name")) == ex_ny:
                return k, v, "Tên file"
    best, best_ov = None, 0.0
    for k, v in items:
        ov = _vessel_overlap(ex_recs, v.get("records", []))
        if ov > best_ov:
            best, best_ov = (k, v), ov
    if best and best_ov >= 0.6:
        return best[0], best[1], f"Trùng {best_ov:.0%} số tàu"
    if len(items) == 1 and n_excel == 1:
        return items[0][0], items[0][1], "Chỉ có 1 cặp file"
    return None, None, ""


def reconcile_sc_excel_files_vs_repo(excel_files, sc_repo, log_cb=None):
    """
    Đối chiếu NHIỀU file SC Excel với các bản SC scan PDF trong sc_repo.
    Mỗi file Excel được ghép tự động với bản PDF tương ứng (xem _find_pdf_pack).
    Trả về list kết quả (mỗi phần tử là dict của reconcile_sc_excel_vs_pdf + 'file', 'pdf_key',
    'match_method'; hoặc dict có khóa 'error' nếu không thể đối chiếu).
    """
    results = []
    repo = sc_repo or {}
    files = []
    for fp in excel_files or []:
        if fp and fp not in files:
            files.append(fp)
    used = {}  # pdf_key -> tên file Excel đã dùng bản PDF này
    for fp in files:
        try:
            ex_info, ex_recs = load_sc_excel(fp)
        except Exception as e:
            results.append({"error": f"Không đọc được SC Excel '{os.path.basename(fp)}': {e}", "file": fp})
            continue
        key, pack, method = _find_pdf_pack(fp, ex_info, ex_recs, repo, len(files))
        if pack is None:
            results.append({"error": f"Không tìm thấy bản scan PDF cho SC Excel '{os.path.basename(fp)}' "
                                     f"(số SC: {ex_info.get('sc_number') or 'không đọc được'})",
                            "file": fp, "excel_info": ex_info})
            continue
        res = reconcile_sc_excel_vs_pdf(ex_info, ex_recs, pack.get("sc_info", {}), pack.get("records", []))
        res["file"] = fp
        res["pdf_key"] = key
        res["pdf_file"] = pack.get("file_path") or pack.get("sc_info", {}).get("file_name", "")
        res["match_method"] = method
        if not res["pdf_info"].get("file_name") and res["pdf_file"]:
            res["pdf_info"] = dict(res["pdf_info"], file_name=os.path.basename(res["pdf_file"]))
        ident = os.path.normcase(res["pdf_file"] or "") or id(pack)
        if ident in used and log_cb:
            log_cb(f"⚠️ Bản PDF SC '{key}' được dùng cho cả '{used[ident]}' và '{os.path.basename(fp)}'")
        used.setdefault(ident, os.path.basename(fp))
        results.append(res)
        if log_cb:
            s = res["summary"]
            log_cb(f"🔎 SC Excel ↔ PDF [{ex_info.get('sc_number') or os.path.basename(fp)}] (ghép theo: {method}): "
                   f"khớp {s['match']}/{s['total_excel']} tàu, lệch {s['mismatch']}, lưu ý {s['warn']}, "
                   f"chỉ Excel {s['only_excel']}, chỉ PDF {s['only_pdf']}")
    if log_cb and len(files) > 1:
        ok = [r for r in results if "rows" in r]
        log_cb(f"📗 Tổng: {len(files)} file SC Excel — đối chiếu được {len(ok)}, "
               f"khớp hoàn toàn {sum(1 for r in ok if r['summary']['all_ok'])}, lỗi/không ghép được {len(files) - len(ok)}")
    return results

