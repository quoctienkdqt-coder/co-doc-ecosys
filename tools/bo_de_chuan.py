"""
BỘ ĐỀ CHUẨN (golden set) cho phần đọc SC scan.

Không cần bộ mẫu đã kiểm tra sẵn: với mỗi cặp (SC scan PDF + SC Excel cùng số SC)
  - Đọc A: đúng cách phần mềm đang làm (gửi cả file, ảnh 150 dpi)
  - Đọc B: độc lập - từng trang một, ảnh 220 dpi, prompt từng trang
  - So từng ô (tàu x trường) giữa SC Excel, Đọc A, Đọc B:
      3 nguồn khớp  -> đáp án tự động (bo_de_chuan/dap_an.json)
      còn lại        -> file Excel cho người chọn giá trị đúng (bo_de_chuan/can_xem.xlsx)
  - Đo luôn: tỷ lệ khớp của Đọc A (cách hiện tại) với Excel, lỗi tổng TOTAL, lỗi luật ngày.

Chạy:  python tools\\bo_de_chuan.py <thư mục chứa cặp PDF + Excel> [thư mục khác...]
Sau khi người điền cột "Giá trị đúng" trong can_xem.xlsx:  python tools\\bo_de_chuan.py --nap-duyet
"""
import os
import sys
import re
import json
import base64
import shutil
import concurrent.futures
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "sc_core"), os.path.join(ROOT, "co_core")]

import fitz  # noqa: E402
import openpyxl  # noqa: E402
from openpyxl.styles import PatternFill, Font, Alignment  # noqa: E402

from sc_core import ai_extractor as ai  # noqa: E402
from sc_core.sc_excel_vs_pdf import (load_sc_excel, normalize_sc_number, _cmp_field, _pair_records,  # noqa: E402
                                     FIELD_LABELS, check_licence_validity, check_landing_after_catch, _to_float)
from sc_core.reconciler import clean_vessel_key  # noqa: E402

OUT = os.path.join(ROOT, "bo_de_chuan")
FIELDS = [k for k, _ in FIELD_LABELS]
LABEL = dict(FIELD_LABELS)


# ---------------------------------------------------------------- Đọc B: từng trang, ảnh nét hơn
def _doc_tung_trang(file_path, api_key, model="gemini-3.8-flash", base_url="https://api.apiz.vn/v1", progress_cb=None):
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)
    doc = fitz.open(file_path)
    imgs = []
    for pno in range(len(doc)):
        pix = doc[pno].get_pixmap(dpi=220)
        imgs.append(base64.b64encode(pix.tobytes("jpeg")).decode())
    doc.close()

    def one(pno):
        for _ in range(3):  # thử lại khi lỗi mạng / JSON hỏng
            try:
                kq = _one(pno)
                if kq[1]:
                    return kq
            except Exception:
                pass
        return pno, {}

    def _one(pno):
        msgs = [{"role": "user", "content": [
            {"type": "text", "text": ai.PAGE_EXTRACTION_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imgs[pno]}", "detail": "high"}}]}]
        try:
            r = client.chat.completions.create(model=model, messages=msgs, temperature=0.0,
                                               response_format={"type": "json_object"})
        except Exception:
            r = client.chat.completions.create(model=model, messages=msgs, temperature=0.0)
        t = (r.choices[0].message.content or "").strip()
        m = re.search(r"\{[\s\S]*\}", t)
        try:
            d = json.loads(m.group(0)) if m else {}
        except Exception:
            d = {}
        return pno, d

    out = {"sc_number": None, "port_name": "", "issue_date": "", "records": []}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        res = sorted(ex.map(one, range(len(imgs))))
    for pno, d in res:
        if d.get("sc_number") and not out["sc_number"]:
            out["sc_number"] = d["sc_number"]
        pt = d.get("printed_total")
        if isinstance(pt, dict) and any(pt.get(k) not in (None, "") for k in ("req_catch_kg", "total_catch_kg")):
            out["printed_total"] = pt
        for v in d.get("vessels", []) or []:
            v["page"] = pno + 1
            out["records"].append(v)
    out["vessels"] = out["records"]
    return out


def doc_A(pdf, key, base_url):
    return ai.extract_sc_with_ai(pdf, provider="apiz", api_key=key, base_url=base_url,
                                 cache_dir=os.path.join(OUT, "cache_A"))


def doc_B(pdf, key, base_url):
    # Dùng lại đúng phần chuẩn hóa của extract_sc_with_ai, chỉ thay hàm gọi AI
    goc = ai.extract_sc_with_openai_compatible
    ai.extract_sc_with_openai_compatible = _doc_tung_trang
    try:
        return ai.extract_sc_with_ai(pdf, provider="apiz", api_key=key, base_url=base_url,
                                     cache_dir=os.path.join(OUT, "cache_B"))
    finally:
        ai.extract_sc_with_openai_compatible = goc


# ---------------------------------------------------------------- ghép cặp file
def tim_cap(folders):
    pdfs, xls = [], []
    for f in folders:
        for r, _, fs in os.walk(f):
            for n in fs:
                p = os.path.join(r, n)
                if n.lower().endswith(".pdf"):
                    pdfs.append(p)
                elif n.lower().endswith((".xlsx", ".xlsm")) and not n.startswith("~$"):
                    xls.append(p)
    cap = []
    for x in xls:
        try:
            info, recs = load_sc_excel(x)
        except Exception:
            continue
        k = normalize_sc_number(info.get("sc_number") or os.path.basename(x))
        so = re.match(r"(\d{3,6})", k)
        for p in pdfs:
            m = re.match(r"\D*(\d{3,6})", os.path.basename(p))
            if so and m and int(m.group(1)) == int(so.group(1)):
                cap.append((p, x, info, recs))
                break
    return cap


# ---------------------------------------------------------------- so 3 nguồn
def _gia_tri(rec, k):
    if rec is None:
        return None
    v = rec.get(k)
    if k in ("req_catch_kg", "total_catch_kg"):
        f = _to_float(v)
        return 0.0 if f is None else f
    return "" if v is None else str(v).strip()


def _khop(k, a, b):
    if a is None or b is None:
        return False
    return _cmp_field(k, a, b)[0] == "MATCH"


def ghep(ex_recs, pdf_recs):
    """Trả về list (excel_rec, pdf_rec|None) và các dòng PDF thừa."""
    by_v = {}
    for p in pdf_recs:
        by_v.setdefault(clean_vessel_key(p.get("vessel_id", "")), []).append(p)
    pairs, used = [], set()
    groups = {}
    for e in ex_recs:
        groups.setdefault(clean_vessel_key(e["vessel_id"]), []).append(e)
    for vk, es in groups.items():
        ps = by_v.get(vk, [])
        used.add(vk)
        pr, _ = _pair_records(es, ps)
        pairs += pr
    thua = [p for vk, ps in by_v.items() if vk not in used for p in ps]
    return pairs, thua


def chay(folders):
    cfg = ai.load_ai_config()
    key = cfg.get("apiz_api_key")
    base = cfg.get("apiz_base_url") or "https://api.apiz.vn/v1"
    if not key:
        sys.exit("Chưa có APIZ key trong ai_config.json")
    os.makedirs(OUT, exist_ok=True)
    caps = tim_cap(folders)
    print(f"Tìm thấy {len(caps)} cặp SC PDF + Excel")

    jobs = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for pdf, *_ in caps:
            jobs[(pdf, "A")] = ex.submit(doc_A, pdf, key, base)
            jobs[(pdf, "B")] = ex.submit(doc_B, pdf, key, base)
        kq = {}
        for k, fut in jobs.items():
            try:
                kq[k] = fut.result()
            except Exception as e:
                print("LỖI đọc", k, e)
                kq[k] = ({}, [])

    anh_dir = os.path.join(OUT, "anh_trang")
    os.makedirs(anh_dir, exist_ok=True)
    dap_an, can_xem, tong = [], [], []
    for pdf, xlsx, info, ex_recs in caps:
        sc = normalize_sc_number(info.get("sc_number")) or os.path.basename(xlsx)
        (iA, rA), (iB, rB) = kq[(pdf, "A")], kq[(pdf, "B")]
        pA, thuaA = ghep(ex_recs, rA)
        pB, thuaB = ghep(ex_recs, rB)
        mapA = {id(e): p for e, p in pA}
        mapB = {id(e): p for e, p in pB}
        # ảnh trang để người đối chiếu
        doc = fitz.open(pdf)
        trang_png = []
        for i in range(len(doc)):
            fp = os.path.join(anh_dir, f"{sc.replace('/', '_')}_trang{i + 1}.png")
            if not os.path.exists(fp):
                doc[i].get_pixmap(dpi=170).save(fp)
            trang_png.append(fp)
        doc.close()

        st = {"sc": sc, "pdf": os.path.basename(pdf), "tau_excel": len(ex_recs), "tau_A": len(rA), "tau_B": len(rB),
              "o": 0, "khop3": 0, "A_dung_excel": 0, "B_dung_excel": 0, "A_thieu_dong": 0, "A_thua_dong": len(thuaA),
              "A_gear_bia": 0}
        for e in ex_recs:
            a, b = mapA.get(id(e)), mapB.get(id(e))
            if a is None:
                st["A_thieu_dong"] += 1
            for k in FIELDS:
                # Quy ước: cột "khai thác" trong SC Excel = KL mua trên PDF
                kp = "req_catch_kg" if k == "total_catch_kg" else k
                ve, va, vb = _gia_tri(e, k), _gia_tri(a, kp), _gia_tri(b, kp)
                st["o"] += 1
                ae, be, ab = _khop(k, ve, va), _khop(k, ve, vb), _khop(k, va, vb)
                st["A_dung_excel"] += ae
                st["B_dung_excel"] += be
                if k == "gear" and a is not None and not ae and va == "LHP":
                    st["A_gear_bia"] += 1
                o = {"sc": sc, "vessel_id": e["vessel_id"], "excel_row": e.get("excel_row"), "field": k,
                     "page": (a or b or {}).get("page")}
                if ae and be:
                    st["khop3"] += 1
                    dap_an.append({**o, "value": ve, "nguon": "tu_dong_3_nguon"})
                else:
                    so_lech = 3 - (2 if (ae or be or ab) else 0) - (1 if (ae and be) else 0)
                    pg = o["page"]
                    can_xem.append({**o, "excel": ve, "A": va, "B": vb,
                                    "muc": "1 nguồn lệch" if (ae or be or ab) else "3 nguồn khác nhau",
                                    "goi_y": ve if (ae or be) else (va if ab else ""),
                                    "anh": trang_png[pg - 1] if pg and 0 < pg <= len(trang_png) else ""})
        # tổng TOTAL in trên SC Excel vs tổng các dòng đọc được
        tot = info.get("sheet_total_req_kg")
        st["total_excel"] = tot
        st["sum_A"] = round(sum(r.get("req_catch_kg") or 0 for r in rA), 1)
        st["sum_B"] = round(sum(r.get("req_catch_kg") or 0 for r in rB), 1)
        st["luat_ngay_A_vi_pham"] = sum(1 for r in rA if check_licence_validity(r)[0] == "MISMATCH"
                                        or check_landing_after_catch(r)[0] == "MISMATCH")
        st["luat_ngay_excel_vi_pham"] = sum(1 for r in ex_recs if check_licence_validity(r)[0] == "MISMATCH"
                                            or check_landing_after_catch(r)[0] == "MISMATCH")
        st["canh_bao_A"] = (iA or {}).get("canh_bao") or []
        st["canh_bao_B"] = (iB or {}).get("canh_bao") or []
        tong.append(st)
        for p in thuaA:
            can_xem.append({"sc": sc, "vessel_id": p.get("vessel_id"), "excel_row": None, "field": "(cả dòng)",
                            "page": p.get("page"), "excel": "(không có trong Excel)", "A": "có dòng này", "B": "",
                            "muc": "Dòng thừa ở Đọc A", "goi_y": "", "anh": ""})

    with open(os.path.join(OUT, "dap_an.json"), "w", encoding="utf-8") as f:
        json.dump({"tao_luc": datetime.now().isoformat(timespec="seconds"), "o": dap_an}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "tong_ket.json"), "w", encoding="utf-8") as f:
        json.dump(tong, f, ensure_ascii=False, indent=1)
    xuat_excel(tong, can_xem)
    in_tong_ket(tong, len(can_xem))


def xuat_excel(tong, can_xem):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cần xem"
    hdr = ["SC", "Trang", "Số tàu", "Dòng Excel", "Trường", "SC Excel", "Đọc A (cách hiện tại)",
           "Đọc B (từng trang)", "Mức", "Gợi ý", "GIÁ TRỊ ĐÚNG (bạn điền)", "Ảnh trang"]
    ws.append(hdr)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="0B5CAD")
        c.alignment = Alignment(wrap_text=True, vertical="center")
    vang = PatternFill("solid", fgColor="FFF2CC")
    can_xem.sort(key=lambda x: (x["muc"] != "3 nguồn khác nhau", x["sc"], x.get("excel_row") or 0))
    for x in can_xem:
        ws.append([x["sc"], x.get("page"), x["vessel_id"], x.get("excel_row"), LABEL.get(x["field"], x["field"]),
                   x.get("excel"), x.get("A"), x.get("B"), x["muc"], x.get("goi_y"), None,
                   "Mở ảnh" if x.get("anh") else ""])
        r = ws.max_row
        ws.cell(r, 11).fill = vang
        if x.get("anh"):
            ws.cell(r, 12).hyperlink = x["anh"]
            ws.cell(r, 12).font = Font(color="0B5CAD", underline="single")
        ws.cell(r, 13).value = x["field"]  # cột ẩn: mã trường
    ws.column_dimensions["M"].hidden = True
    for col, w in zip("ABCDEFGHIJKL", [22, 7, 15, 8, 22, 28, 28, 28, 18, 24, 26, 10]):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"

    t = wb.create_sheet("Tổng kết")
    t.append(["SC", "File PDF", "Tàu (Excel/A/B)", "Ô kiểm", "3 nguồn khớp", "Đọc A khớp Excel", "Đọc B khớp Excel",
              "A thiếu dòng", "A thừa dòng", "A tự điền LHP", "TOTAL Excel", "Tổng A", "Tổng B",
              "A vi phạm luật ngày", "Excel vi phạm luật ngày"])
    for s in tong:
        o = s["o"] or 1
        t.append([s["sc"], s["pdf"], f'{s["tau_excel"]}/{s["tau_A"]}/{s["tau_B"]}', s["o"],
                  f'{s["khop3"] / o:.1%}', f'{s["A_dung_excel"] / o:.1%}', f'{s["B_dung_excel"] / o:.1%}',
                  s["A_thieu_dong"], s["A_thua_dong"], s["A_gear_bia"], s["total_excel"], s["sum_A"], s["sum_B"],
                  s["luat_ngay_A_vi_pham"], s["luat_ngay_excel_vi_pham"]])
    for c in t[1]:
        c.font = Font(bold=True)
    wb.save(os.path.join(OUT, "can_xem.xlsx"))


def in_tong_ket(tong, n_xem):
    O = sum(s["o"] for s in tong) or 1
    print("\n=== TỔNG KẾT ===")
    for s in tong:
        o = s["o"] or 1
        print(f'{s["sc"]:<22} tàu {s["tau_excel"]}/{s["tau_A"]}/{s["tau_B"]}  ô {s["o"]:>4}  '
              f'3 khớp {s["khop3"] / o:6.1%}  A=Excel {s["A_dung_excel"] / o:6.1%}  B=Excel {s["B_dung_excel"] / o:6.1%}  '
              f'TOTAL {s["total_excel"]} | A {s["sum_A"]} | B {s["sum_B"]}  LHP bịa {s["A_gear_bia"]}')
        for tag in ("A", "B"):
            for c in s.get("canh_bao_" + tag, []):
                print(f"     ⚠ {tag}: {c}")
    print(f'TẤT CẢ: {O} ô | 3 nguồn khớp {sum(s["khop3"] for s in tong) / O:.1%} | '
          f'Đọc A khớp Excel {sum(s["A_dung_excel"] for s in tong) / O:.1%} | '
          f'Đọc B khớp Excel {sum(s["B_dung_excel"] for s in tong) / O:.1%} | cần người xem: {n_xem} ô')
    print("File:", os.path.join(OUT, "can_xem.xlsx"))


def nap_duyet():
    """Đọc cột GIÁ TRỊ ĐÚNG người đã điền -> bổ sung vào dap_an.json."""
    fp = os.path.join(OUT, "dap_an.json")
    data = json.load(open(fp, encoding="utf-8"))
    ws = openpyxl.load_workbook(os.path.join(OUT, "can_xem.xlsx"))["Cần xem"]
    them = 0
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r[10] not in (None, ""):
            data["o"].append({"sc": r[0], "page": r[1], "vessel_id": r[2], "excel_row": r[3], "field": r[12],
                              "value": r[10], "nguon": "nguoi_duyet"})
            them += 1
    json.dump(data, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Đã nạp {them} ô người duyệt. Bộ đề: {len(data['o'])} ô.")


if __name__ == "__main__":
    if "--nap-duyet" in sys.argv:
        nap_duyet()
    else:
        chay(sys.argv[1:] or [os.path.join(ROOT, "tai_lieu_mau", "ld.han")])
