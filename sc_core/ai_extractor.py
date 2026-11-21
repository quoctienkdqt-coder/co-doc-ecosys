try:  # ghi lỗi bị bỏ qua vào loi_bo_qua.log (thay cho except: pass im lặng)
    from nhat_ky_loi import ghi as _ghi_loi_bo_qua
except Exception:  # pragma: no cover
    def _ghi_loi_bo_qua(*_a, **_k):
        return None
import os
import sys
import json
import re
import hashlib
import fitz

CONFIG_FILE_NAME = "ai_config.json"
SC_CACHE_VER = "v4"  # đổi mỗi khi sửa prompt/luật đọc SC để không dùng lại kết quả đọc theo cách cũ
TOL_KG = 0.5


def _ngay(v):
    from datetime import datetime as _dt
    m = re.search(r"(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{4})", str(v or ""))
    try:
        return _dt(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None
    except ValueError:
        return None


def _nghi(r, field_list, msg):
    r.setdefault("nghi_ngo", []).append(msg)
    r["o_nghi_ngo"] = sorted(set(r.get("o_nghi_ngo", [])) | set(field_list))


def danh_dau_nghi_ngo(records):
    """Lớp 4 + 5: luật logic từng dòng và sổ tàu. Gắn r['nghi_ngo'] (mô tả) và r['o_nghi_ngo'] (tên trường)."""
    for r in records:
        r.pop("nghi_ngo", None)
        r.pop("o_nghi_ngo", None)
        # 1. KL mua không bao giờ > KL khai thác -> AI đọc đảo cột: đổi lại, vẫn đánh dấu để đọc lại xác nhận
        mua, kt = r.get("req_catch_kg") or 0.0, r.get("total_catch_kg") or 0.0
        if kt > 0 and mua > kt + TOL_KG:
            r["req_catch_kg"], r["total_catch_kg"] = kt, mua
            _nghi(r, ["req_catch_kg", "total_catch_kg"], f"AI đọc đảo cột KL (mua {mua:g} > khai thác {kt:g}) - đã tự đổi lại")
        # 2. Hạn GP trước ngày bốc dỡ: thường do lấy nhầm năm trong số GP -> nghi ngờ, chưa kết luận hết hạn
        han, boc = _ngay(r.get("licence_exp")), _ngay(r.get("landing_date"))
        if han and boc and han < boc:
            nam_so_gp = re.findall(r"/(\d{4})/", str(r.get("licence_no") or ""))
            goi_y = " (trùng năm trong số GP - rất có thể đọc nhầm)" if str(han.year) in nam_so_gp else ""
            _nghi(r, ["licence_exp"], f"Hạn GP {han:%d/%m/%Y} trước ngày bốc dỡ {boc:%d/%m/%Y}{goi_y} - cần xem ảnh SC")
    # 3. Sổ tàu đã xác nhận
    try:
        from sc_core import so_tau
        so_tau.kiem_tra(records)
    except Exception as e:
        print(f"Bỏ qua kiểm tra sổ tàu: {e}")


def kiem_tra_tong(records, printed_total, to_float):
    out = []
    if isinstance(printed_total, dict):
        for k, ten in (("req_catch_kg", "KL nguyên liệu mua"), ("total_catch_kg", "KL khai thác")):
            raw = printed_total.get(k)
            if raw in (None, "", "null"):
                continue
            in_giay = to_float(raw)
            tong = sum(r.get(k) or 0.0 for r in records)
            if in_giay and abs(tong - in_giay) > TOL_KG:
                out.append(f"Tổng {ten} các dòng đọc được = {tong:,.0f} kg nhưng dòng TOTAL in trên SC = {in_giay:,.0f} kg "
                           f"(lệch {tong - in_giay:+,.0f}) - cần xem lại SC")
    return out


def kiem_tra_sc_sau_khi_doc(records, printed_total=None, to_float=None, doc_lai=None):
    """
    Chạy NGAY SAU khi AI đọc SC:
      - Lớp 4 (luật logic) + lớp 5 (sổ tàu): đánh dấu ô nghi ngờ (không tốn API)
      - Lớp 6: nếu có ô nghi ngờ và có hàm doc_lai -> đọc lại RIÊNG các ô đó (ảnh nét hơn), rồi kiểm tra lại
      - Tổng các dòng phải = dòng TOTAL in trên giấy
    Sửa trực tiếp records; trả về danh sách cảnh báo cho người dùng.
    """
    to_float = to_float or (lambda v: float(v or 0))
    danh_dau_nghi_ngo(records)
    if doc_lai and any(r.get("o_nghi_ngo") for r in records):
        try:
            doc_lai([r for r in records if r.get("o_nghi_ngo")])
        except Exception as e:
            print(f"Đọc lại ô khó thất bại: {e}")
        danh_dau_nghi_ngo(records)
    canh_bao = kiem_tra_tong(records, printed_total, to_float)
    for r in records:
        for n in r.get("da_doc_lai", []):
            canh_bao.append(f"{r.get('vessel_id')}: đã đọc lại - {n}")
        for n in r.get("nghi_ngo", []):
            canh_bao.append(f"{r.get('vessel_id')}: CẦN XEM - {n}")
    return canh_bao


DOC_LAI_PROMPT = """Ảnh là 1 trang Giấy xác nhận nguyên liệu thủy sản khai thác (Mẫu số 01).
Hãy ĐỌC LẠI THẬT CẨN THẬN chỉ các ô sau (đúng dòng của số đăng ký tàu ghi kèm):
{yeu_cau}
Quy tắc:
- licence_exp: ngày hết hạn ở DÒNG CUỐI của ô "Số giấy phép khai thác - thời hạn đến" (thường có dấu nháy ' đứng trước). KHÔNG lấy năm trong số giấy phép.
- req_catch_kg: số ở cột (11) "Tổng khối lượng nguyên liệu mua từ tàu cá (kg)"; total_catch_kg: số ở cột (12) "Tổng khối lượng khai thác của tàu cá (kg)". Dấu chấm là phân cách hàng nghìn (1.320 = 1320).
- owner: họ tên ở cột (2), giữ nguyên dấu tiếng Việt.
- Với licence_exp: CHÉP NGUYÊN VĂN toàn bộ chữ trong ô cột (7) vào "licence_cell_text" (giữ xuống dòng bằng \\n, giữ dấu nháy), từng ký tự một.
- Ô nào không đọc rõ: ghi null, KHÔNG đoán.
Chỉ trả JSON: {{"vessels": [{{"vessel_id": "...", "licence_cell_text": "...", "<trường>": "<giá trị>"}}]}}"""


def _hoi_anh(img_bytes, prompt, provider, key, model, base_url):
    """Gửi 1 ảnh + prompt, trả dict JSON (hoặc {})."""
    import base64
    if provider == "gemini":
        from app_config_manager import tao_google_client
        from google.genai import types
        client = tao_google_client(key)
        resp = client.models.generate_content(
            model=model, contents=[types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"), prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0))
        txt = resp.text or ""
    else:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=base_url)
        msgs = [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(img_bytes).decode(),
                                                "detail": "high"}}]}]
        resp = client.chat.completions.create(model=model, messages=msgs, temperature=0.0)
        txt = resp.choices[0].message.content or ""
    m = re.search(r"\{[\s\S]*\}", txt)
    try:
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}


_OCR = None
_OCR_LOCK = __import__("threading").Lock()


def _ocr_engine():
    """RapidOCR nạp mô hình mất vài giây -> chỉ tạo 1 lần cho cả phiên."""
    global _OCR
    with _OCR_LOCK:
        if _OCR is None:
            from rapidocr_onnxruntime import RapidOCR
            _OCR = RapidOCR()
    return _OCR


def _vi_tri_cac_dong(page):
    """OCR cục bộ (RapidOCR, không tốn API) -> {vessel_key: (y_giữa, chiều_cao_dòng)} theo tọa độ PDF."""
    from sc_core.reconciler import clean_vessel_key
    import statistics
    out = {}
    try:
        dpi = 150
        # Chỉ OCR dải trái (cột số đăng ký tàu nằm sát lề trái Mẫu 01) -> nhanh hơn nhiều so với cả trang.
        # Thử dải 25% trước; không thấy số tàu nào thì OCR cả trang.
        res = None
        for frac in (0.25, 1.0):
            clip = fitz.Rect(0, 0, page.rect.width * frac, page.rect.height)
            res, _ = _ocr_engine()(page.get_pixmap(dpi=dpi, clip=clip).tobytes("png"))
            if res and any(re.search(r"[A-Za-zĐđÐ]{2,3}\s*-\s*\d{4,5}", b[1]) for b in res):
                break
        vb = []
        for b in res or []:
            if re.search(r"[A-Za-zĐđÐ]{2,3}\s*-\s*\d{4,5}", b[1]):
                ys = [p[1] for p in b[0]]
                vb.append((clean_vessel_key(b[1]), (min(ys) + max(ys)) / 2 * 72 / dpi))
        yc = sorted(y for _, y in vb)
        gap = statistics.median([b - a for a, b in zip(yc, yc[1:])]) if len(yc) > 1 else 55.0
        out = {k: (y, gap) for k, y in vb}
    except Exception as e:
        print(f"OCR định vị dòng lỗi: {e}")
    return out


_CAT_LOCK = __import__("threading").RLock()


def cat_dai_dong(file_path, page_no, vessel_id, dpi=250, x_frac=1.0, x_start=0.0):
    """Ảnh JPEG của đúng 1 dòng tàu trên trang (None nếu không định vị được). An toàn khi gọi từ nhiều luồng.
    x_start..x_frac: phần bề ngang cần lấy (0..1) — vd 0..0.62 cho cột tên/GP, 0.35..1 cho cột ngày/kg."""
    with _CAT_LOCK:  # PyMuPDF + RapidOCR không an toàn đa luồng
        return _cat_dai_dong(file_path, page_no, vessel_id, dpi, x_frac, x_start)


_VI_TRI_CACHE = {}


def _vi_tri_dong_cache(file_path, page_no, page):
    ck = (file_path, page_no)
    if ck not in _VI_TRI_CACHE:
        _VI_TRI_CACHE[ck] = _vi_tri_cac_dong(page)
    return _VI_TRI_CACHE[ck]


def _cat_dai_dong(file_path, page_no, vessel_id, dpi=250, x_frac=1.0, x_start=0.0):
    from sc_core.reconciler import clean_vessel_key
    doc = fitz.open(file_path)
    try:
        if not page_no or page_no > len(doc):
            return None
        page = doc[page_no - 1]
        pos = _vi_tri_dong_cache(file_path, page_no, page).get(clean_vessel_key(vessel_id))
        if not pos:
            return None
        y, gap = pos
        clip = fitz.Rect(page.rect.width * x_start, max(0, y - gap * 0.55), page.rect.width * x_frac,
                         min(page.rect.height, y + gap * 0.55))
        return page.get_pixmap(dpi=dpi, clip=clip).tobytes("jpeg")
    finally:
        doc.close()


def cat_o_ten(file_path, page_no, vessel_id, dpi=600):
    """
    Ảnh JPEG CHỈ ô họ tên chủ tàu của đúng dòng tàu (không phụ thuộc bố cục cột từng cảng):
    OCR dải dòng -> ô chữ đầu tiên bên phải ô số tàu = ô tên -> cắt sát ô đó ở độ phân giải cao.
    (Qua cổng AI công ty, ảnh càng sát ô tên thì dấu tiếng Việt càng đọc đúng.)
    """
    from sc_core.reconciler import clean_vessel_key
    with _CAT_LOCK:
        doc = fitz.open(file_path)
        try:
            if not page_no or page_no > len(doc):
                return None
            page = doc[page_no - 1]
            pos = _vi_tri_dong_cache(file_path, page_no, page).get(clean_vessel_key(vessel_id))
            if not pos:
                return None
            y, gap = pos
            W = page.rect.width
            y0, y1 = max(0, y - gap * 0.5), min(page.rect.height, y + gap * 0.5)
            # OCR nửa trái CẢ TRANG 1 lần (dải mỏng RapidOCR hay trả rỗng), lọc các ô chữ nằm trên dòng này
            ck = ("hop", file_path, page_no)
            if ck not in _VI_TRI_CACHE:
                sdpi = 170
                res, _ = _ocr_engine()(page.get_pixmap(dpi=sdpi, clip=fitz.Rect(0, 0, W * 0.5, page.rect.height)).tobytes("png"))
                s = 72 / sdpi
                _VI_TRI_CACHE[ck] = [(min(p[0] for p in b[0]) * s, max(p[0] for p in b[0]) * s,
                                      (min(p[1] for p in b[0]) + max(p[1] for p in b[0])) / 2 * s, b[1]) for b in res or []]
            hop = sorted(((x0, x1, t) for x0, x1, yc, t in _VI_TRI_CACHE[ck] if y0 <= yc <= y1), key=lambda t: t[0])
            k = 1.0  # tọa độ đã ở đơn vị PDF
            vx = None
            for x0, x1, t in hop:
                if clean_vessel_key(t) == clean_vessel_key(vessel_id) or re.search(r"[A-Za-zĐđÐ]{2,3}\s*-\s*\d{4,5}", t):
                    vx = x1
                    break
            if vx is None:
                return None
            ten = [(x0, x1) for x0, x1, t in hop if x0 > vx + 1 and re.search(r"[^\W\d_]{2,}", t)]
            if not ten:
                return None
            # gộp các mảnh chữ liền nhau của cùng ô tên (tên có thể bị OCR tách nhiều mảnh / 2 dòng)
            a, b = ten[0]
            for x0, x1 in ten[1:]:
                if x0 - b < 14:
                    b = max(b, x1)
                else:
                    break
            pad = 7
            clip = fitz.Rect(max(0, (a - pad) * k), y0, min(W, (b + pad) * k), y1)
            return page.get_pixmap(dpi=dpi, clip=clip).tobytes("jpeg")
        finally:
            doc.close()


XAC_MINH_TEN_PROMPT ="""Ảnh là 1 DÒNG (dải cắt) của Giấy xác nhận nguyên liệu thủy sản khai thác.
Đọc họ tên ở cột "Họ và tên chủ tàu/thuyền trưởng" của tàu {vessel_id}.
Đang phân vân giữa các cách viết sau (chỉ khác nhau ở dấu):
{ung_vien}
{chu_khac}
Nhìn THẬT KỸ từng dấu thanh (sắc ´, huyền `, hỏi ˀ, ngã ~, nặng .) và dấu mũ/râu/trăng (â ê ô ơ ư ă) trên ảnh.
Phân biệt: "a" KHÔNG có gì phía trên chữ (chỉ có dấu thanh) ; "ă" có nét cong hình trăng (˘) ; "â" có mũ (^).
Chép lại tên ĐÚNG NHƯ TRÊN ẢNH (có thể khác các cách viết trên nếu ảnh ghi khác).
Chỉ trả JSON: {{"ten": "<họ tên đúng như ảnh>", "chac_chan": true hoặc false}}"""


def xac_minh_ten(file_path, page_no, vessel_id, ung_vien, provider, key, model, base_url):
    """Lớp 6 cho tên: cắt đúng dòng, hỏi AI chọn cách viết. Trả tên (str) nếu AI chắc chắn, ngược lại None."""
    ds = "\n".join(f"{i + 1}) {t}" for i, t in enumerate(ung_vien))
    # Chỉ rõ TỪ nào đang khác nhau để AI tập trung nhìn đúng chỗ
    tu = [t.split() for t in ung_vien]
    khac = []
    for j in range(max(len(x) for x in tu)):
        bien = sorted({x[j] for x in tu if j < len(x)})
        if len(bien) > 1:
            khac.append(f"từ thứ {j + 1}: " + " hay ".join(f'"{b}"' for b in bien))
    chu_khac = ("Các cách viết chỉ khác nhau ở " + "; ".join(khac) + ".") if khac else ""
    # 1) chỉ ô tên (600 dpi, định vị bằng OCR) -> 2) cột số tàu + tên (~1/3 bề ngang) -> 3) cả dòng
    def anh():
        try:
            yield cat_o_ten(file_path, page_no, vessel_id)
        except Exception as e:
            print(f"Cắt ô tên lỗi: {e}")
        yield cat_dai_dong(file_path, page_no, vessel_id, dpi=400, x_frac=0.32)
        yield cat_dai_dong(file_path, page_no, vessel_id, dpi=300, x_frac=1.0)
    for img in anh():
        if img is None:
            continue
        data = _hoi_anh(img, XAC_MINH_TEN_PROMPT.format(vessel_id=vessel_id, ung_vien=ds, chu_khac=chu_khac),
                        provider, key, model, base_url)
        ten = str(data.get("ten") or "").strip()
        if ten and data.get("chac_chan") in (True, "true", "True"):
            return ten
    return None


def tao_ham_doc_lai(file_path, provider, key, model, base_url):
    """Lớp 6: trả hàm doc_lai(records) - mỗi trang có ô nghi ngờ gửi 1 ảnh 250 dpi kèm danh sách ô cần đọc."""
    if not str(file_path).lower().endswith(".pdf"):
        return None

    def hoi(img_bytes, prompt):
        import base64
        if provider == "gemini":
            from app_config_manager import tao_google_client
            from google.genai import types
            client = tao_google_client(key)
            resp = client.models.generate_content(
                model=model, contents=[types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"), prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0))
            txt = resp.text or ""
        else:
            from openai import OpenAI
            client = OpenAI(api_key=key, base_url=base_url)
            msgs = [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(img_bytes).decode(),
                                                    "detail": "high"}}]}]
            resp = client.chat.completions.create(model=model, messages=msgs, temperature=0.0)
            txt = resp.choices[0].message.content or ""
        m = re.search(r"\{[\s\S]*\}", txt)
        return json.loads(m.group(0)) if m else {}

    def vi_tri_dong(page, cache, pno):
        """OCR cục bộ (không tốn API) -> {vessel_key: (y_giữa, chiều_cao_dòng)} theo tọa độ PDF."""
        if pno in cache:
            return cache[pno]
        from sc_core.reconciler import clean_vessel_key
        import statistics
        out = {}
        try:
            from rapidocr_onnxruntime import RapidOCR
            dpi = 150
            res, _ = RapidOCR()(page.get_pixmap(dpi=dpi).tobytes("png"))
            vb = []
            for b in res or []:
                if re.search(r"[A-Za-zĐđÐ]{2,3}\s*-\s*\d{4,5}", b[1]):
                    ys = [p[1] for p in b[0]]
                    vb.append((clean_vessel_key(b[1]), (min(ys) + max(ys)) / 2 * 72 / dpi))
            yc = sorted(y for _, y in vb)
            gap = statistics.median([b - a for a, b in zip(yc, yc[1:])]) if len(yc) > 1 else 55.0
            out = {k: (y, gap) for k, y in vb}
        except Exception as e:
            print(f"OCR định vị dòng lỗi: {e}")
        cache[pno] = out
        return out

    def doc_lai(records):
        from sc_core.reconciler import clean_vessel_key
        import concurrent.futures
        doc = fitz.open(file_path)
        ocr_cache, viec = {}, []
        try:
            for r in records:
                pno = r.get("page") or 0
                if not pno or pno > len(doc):
                    continue
                page = doc[pno - 1]
                pos = vi_tri_dong(page, ocr_cache, pno).get(clean_vessel_key(r.get("vessel_id")))
                if pos:  # cắt đúng 1 dải ngang của dòng tàu -> AI không lẫn dòng, không bị số GP "lôi kéo"
                    y, gap = pos
                    clip = fitz.Rect(0, max(0, y - gap * 0.55), page.rect.width, min(page.rect.height, y + gap * 0.55))
                    img = page.get_pixmap(dpi=250, clip=clip).tobytes("jpeg")
                    p = DOC_LAI_PROMPT.replace("Ảnh là 1 trang Giấy", "Ảnh là 1 DÒNG (dải cắt) của Giấy")
                else:
                    img = page.get_pixmap(dpi=250).tobytes("jpeg")
                    p = DOC_LAI_PROMPT
                viec.append((r, img, p.format(yeu_cau=f"- Tàu {r.get('vessel_id')}: {', '.join(r['o_nghi_ngo'])}")))
        finally:
            doc.close()

        def mot(job):
            r, img, prompt = job
            try:
                return r, hoi(img, prompt)
            except Exception as e:
                print(f"Đọc lại {r.get('vessel_id')} lỗi: {e}")
                return r, {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            ket_qua = list(ex.map(mot, viec))
        if True:
            for r, data in ket_qua:
                theo_tau = {clean_vessel_key(v.get("vessel_id")): v for v in (data.get("vessels") or [])}
                if True:
                    v = theo_tau.get(clean_vessel_key(r.get("vessel_id")))
                    if not v:
                        continue
                    for f in r["o_nghi_ngo"]:
                        moi = v.get(f)
                        if f == "licence_exp" and v.get("licence_cell_text"):
                            # Hạn GP = ngày CUỐI CÙNG trong ô (số GP có năm nhưng không có dạng dd/mm/yyyy)
                            ds = re.findall(r"(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{4})", str(v["licence_cell_text"]))
                            if ds:
                                d_, m_, y_ = ds[-1]
                                moi = f"{int(d_):02d}/{int(m_):02d}/{y_}"
                        if moi in (None, "", "null"):
                            continue
                        if f.endswith("_kg"):
                            moi = float(re.sub(r"[^\d]", "", str(moi)) or 0) if not isinstance(moi, (int, float)) else float(moi)
                        cu = r.get(f)
                        if str(cu) != str(moi):
                            r.setdefault("da_doc_lai", []).append(f"{f}: {cu} -> {moi}")
                            r[f] = moi
                        else:
                            r.setdefault("da_doc_lai", []).append(f"{f}: xác nhận {moi}")

    return doc_lai

def get_config_dir():
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        cfg_dir = os.path.join(local_app_data, "DoiChieu_XNNL_SC")
    else:
        cfg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(cfg_dir, exist_ok=True)
    return cfg_dir

def get_config_path():
    return os.path.join(get_config_dir(), CONFIG_FILE_NAME)

def load_ai_config():
    """Loads configuration for AI API (APIZ.vn / Gemini / OpenAI)."""
    cfg_path = get_config_path()
    default_cfg = {
        "use_ai": True,
        "provider": "apiz",
        "apiz_base_url": "https://api.apiz.vn/v1",
        "apiz_api_key": os.environ.get("APIZ_API_KEY") or "",
        "apiz_model": "gemini-3.8-flash",
        "gemini_api_key": os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "",
        "gemini_model": "gemini-3.8-flash",
        "openai_api_key": os.environ.get("OPENAI_API_KEY") or "",
        "openai_model": "gpt-4o-mini",
        "openai_base_url": "https://api.openai.com/v1"
    }
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_cfg.update(data)
        except Exception:
            _ghi_loi_bo_qua()
            
    return default_cfg

def save_ai_config(cfg_dict):
    """Saves AI configuration."""
    cfg_path = get_config_path()
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg_dict, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def test_ai_connection(provider, api_key, model_name=None, base_url=None):
    """
    Tests if the provided API key works.
    Returns: (success: bool, message: str, working_model: str)
    """
    if not api_key or not api_key.strip():
        return False, "API Key đang để trống!", None

    api_key = api_key.strip()
    
    if provider.lower() == "apiz":
        b_url = base_url or "https://api.apiz.vn/v1"
        m_name = model_name or "gemini-3.8-flash"
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=b_url)
            res = client.chat.completions.create(
                model=m_name,
                messages=[{"role": "user", "content": "Ping. Trả lời đúng từ: PONG"}],
                max_tokens=10
            )
            txt = res.choices[0].message.content or ""
            return True, f"Kết nối APIZ.vn thành công! (Model: {m_name}, Phản hồi: {txt.strip()})\n\nBạn có thể vào Bảng điều khiển → Nhật ký API trên apiz.vn để xem chi phí và request đã được ghi nhận.", m_name
        except Exception as e:
            err_str = str(e)
            if "401" in err_str or "API key" in err_str:
                return False, f"Mã khóa API không hợp lệ trên APIZ.vn!\nChi tiết: {err_str}\n\n👉 Hướng dẫn: Đăng nhập https://apiz.vn → vào 'Bảng điều khiển' → 'Khóa API' → bấm nút 'Sao chép' (Copy) lại khóa sk-... (nhóm Tự động).", None
            return False, f"Lỗi kết nối APIZ.vn: {e}", None

    elif provider.lower() == "gemini":
        # Cổng AI công ty chỉ cho phép gemini-3.8-flash (kiểm 20/11/2026) -> 3.8 đứng đầu, bản cũ chỉ dự phòng
        m_req = model_name or "gemini-3.8-flash"
        candidate_models = list(dict.fromkeys([m_req, "gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash"]))

        last_err = ""
        try:
            from google import genai
            from app_config_manager import tao_google_client
            client = tao_google_client(api_key)
            for m in candidate_models:
                try:
                    response = client.models.generate_content(
                        model=m,
                        contents="Ping. Trả lời đúng từ: PONG"
                    )
                    txt = response.text or ""
                    if "PONG" in txt.upper() or len(txt) > 0:
                        return True, f"Kết nối Google Gemini thành công! (Model: {m})", m
                except Exception as inner_e:
                    last_err = str(inner_e)
                    continue
        except Exception as e:
            last_err = str(e)

        # (Đã bỏ fallback google.generativeai: thư viện cũ gọi thẳng Google, vượt qua cổng AI công ty)
        return False, f"Lỗi kết nối Cổng AI công ty (key Google): {last_err}", None

    elif provider.lower() == "openai":
        b_url = base_url or "https://api.openai.com/v1"
        model = model_name or "gpt-4o-mini"
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=b_url)
            res = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Ping"}],
                max_tokens=5
            )
            return True, f"Kết nối OpenAI thành công! (Model: {model})", model
        except Exception as e:
            return False, f"Lỗi kết nối OpenAI: {e}", None

    return False, f"Nhà cung cấp không hỗ trợ: {provider}", None

PAGE_EXTRACTION_PROMPT = """Bạn là chuyên gia bóc tách hồ sơ thủy sản IUU Việt Nam (Giấy xác nhận nguyên liệu khai thác - Giấy SC cảng cá theo Phụ lục II/02a Thông tư 21/2018/TT-BNNPTNT).

Nhiệm vụ: Trích xuất toàn bộ dữ liệu từ hình ảnh trang tài liệu SC đính kèm.
Xuất ra DUY NHẤT một khối JSON theo cấu trúc:
{
  "sc_number": "Số giấy SC nếu có trên trang (ví dụ: 00213/2026/SC-GL-TQ, 00064/2026/SC-DL-DT... đầy đủ số và hậu tố cảng), nếu không có để null",
  "port_name": "Tên cảng cá nếu có trên trang, nếu không có để null",
  "issue_date": "Ngày cấp giấy (dd/mm/yyyy) nếu có trên trang, nếu không có để null",
  "vessels": [
    {
      "stt": 1,
      "vessel_id": "Số đăng ký tàu (ví dụ: BĐ-96698-TS, PY-90016-TS... Phải có gạch nối và -TS, chuẩn hóa chữ Đ có gạch ngang)",
      "owner": "Họ và tên chủ tàu / thuyền trưởng ghi tại cột này (giữ nguyên đầy đủ họ tên tiếng Việt)",
      "gear": "Nghề khai thác (LHP, LĐ, RÊ...)",
      "licence_no": "Số giấy phép KTTS (ví dụ: 1735/2025/GL-GPKTTS, 32733/2025/DL-GPKTTS...)",
      "licence_exp": "Thời hạn giấy phép đến ngày (dd/mm/yyyy)",
      "catch_area": "Vùng biển khai thác (ví dụ: FAO71-TB2...)",
      "catch_period": "Thời gian chuyến biển (dd/mm/yyyy - dd/mm/yyyy)",
      "species": "Tên loài thủy sản (ví dụ: Cá ngừ vây vàng...)",
      "landing_date": "Ngày bốc dỡ / lên cá (dd/mm/yyyy)",
      "req_catch_kg": 489.0,
      "total_catch_kg": 620.0
    }
  ],
  "printed_total": {"req_catch_kg": "Số ở dòng TỔNG/TOTAL in trên giấy, cột KL nguyên liệu mua (null nếu trang không có dòng tổng)", "total_catch_kg": "Số ở dòng TỔNG/TOTAL, cột KL khai thác (null nếu không có)"}
}

QUY TẮC BẮT BUỘC ĐẢM BẢO CHÍNH XÁC 100%:
1. Đọc đúng từng cột của từng dòng tàu trong bảng.
2. Cột 'Thời hạn giấy phép đến' là ngày hết hạn của Giấy phép KTTS (thường là một ngày trong tương lai 2026-2030). KHÔNG ĐƯỢC lấy ngày bốc dỡ hay ngày chuyến biển đưa vào cột hạn phép!
3. HẠN GIẤY PHÉP (cột 7 "Số giấy phép khai thác - thời hạn đến"): ô ghi số GP dạng "154-1/2026/QNg-GPKTTS" rồi xuống dòng ngày hạn, thường có dấu nháy đứng trước ('11/04/2029).
   licence_exp = NGÀY SAU DẤU NHÁY / ngày ở dòng cuối của ô. TUYỆT ĐỐI KHÔNG lấy năm nằm trong số giấy phép (2026 trong "154-1/2026/...") làm năm hết hạn.
   PHÂN BIỆT RÕ 2 CỘT KHỐI LƯỢNG TRONG GIẤY SC - XÁC ĐỊNH THEO TIÊU ĐỀ CỘT, KHÔNG THEO THỨ TỰ LIỆT KÊ TRONG JSON:
   - Trên Mẫu số 01 hiện hành: cột (11) "Tổng khối lượng nguyên liệu mua từ tàu cá (kg)" đứng TRƯỚC, cột (12) "Tổng khối lượng khai thác của tàu cá (kg)" đứng SAU.
     => số ở cột (11) là req_catch_kg, số ở cột (12) là total_catch_kg. Mẫu khác có thể đổi vị trí: luôn đọc chữ ở tiêu đề cột.
   - Kiểm tra lại: KL nguyên liệu mua KHÔNG BAO GIỜ lớn hơn KL khai thác của cùng dòng. Nếu thấy mua > khai thác thì bạn đang đọc đảo cột - đọc lại.
   - "total_catch_kg": Cột "Tổng khối lượng khai thác của tàu cá (kg)" (tổng sản lượng tàu đánh bắt).
   - "req_catch_kg": Cột "Tổng khối lượng nguyên liệu mua từ tàu cá (kg)" (số lượng nguyên liệu mua thực tế đưa vào hồ sơ XNNL).
   - QUY TẮC BẮT BUỘC VỀ DẤU GẠCH NGANG '-' HOẶC ĐỂ TRỐNG:
     Trong cột "Tổng khối lượng nguyên liệu mua từ tàu cá (kg)", nếu dòng nào có dấu gạch ngang '-' hoặc để trống (ví dụ các loài phụ: Cá dũa, Mực xà, Cá kiếm, Cá thu... mà doanh nghiệp không mua), thì req_catch_kg BẮT BUỘC ghi là 0.0!
     TUYỆT ĐỐI KHÔNG ĐƯỢC lấy số ở cột khai thác điền vào req_catch_kg nếu ô đó là dấu '-' hoặc trống!
4. Nếu trang không có dòng tàu nào (chỉ có chữ ký/con dấu), trả về vessels: [].
5. Chỉ xuất JSON, không có bất kỳ văn bản giải thích nào ngoài JSON.
"""

DOCUMENT_EXTRACTION_PROMPT = """Bạn là chuyên gia bóc tách hồ sơ thủy sản IUU Việt Nam (Giấy xác nhận nguyên liệu khai thác - Giấy SC cảng cá theo Phụ lục II/02a Thông tư 21/2018/TT-BNNPTNT).

Nhiệm vụ: Phân tích toàn bộ tài liệu đính kèm (có thể gồm nhiều trang PDF hoặc ảnh scan).
Hãy bóc tách đầy đủ tất cả các dòng dữ liệu tàu cá trong bảng biểu từ trang đầu đến trang cuối cùng.

Xuất ra DUY NHẤT một khối JSON theo cấu trúc sau:
{
  "sc_number": "Số giấy SC (ví dụ: 00257/2026/SC-GL-TQ, 00064/2026/SC-ĐL-ĐT... đầy đủ số, năm và hậu tố cảng nếu có)",
  "port_name": "Tên cảng cá cấp giấy",
  "issue_date": "Ngày cấp giấy (dd/mm/yyyy)",
  "vessels": [
    {
      "stt": 1,
      "page": 1,
      "vessel_id": "Số đăng ký tàu (ví dụ: BĐ-96698-TS, PY-90016-TS... bắt buộc có -TS, chuẩn hóa chữ Đ có gạch)",
      "owner": "Họ và tên chủ tàu / thuyền trưởng",
      "gear": "Nghề khai thác (LHP, LĐ, RÊ...)",
      "licence_no": "Số giấy phép KTTS (ví dụ: 1735/2025/GL-GPKTTS, 32733/2025/DL-GPKTTS...)",
      "licence_exp": "Thời hạn giấy phép đến ngày (dd/mm/yyyy)",
      "catch_area": "Vùng biển khai thác (ví dụ: FAO71-TB2...)",
      "catch_period": "Thời gian chuyến biển (dd/mm/yyyy - dd/mm/yyyy)",
      "species": "Tên loài thủy sản (ví dụ: Cá ngừ vây vàng...)",
      "landing_date": "Ngày bốc dỡ / lên cá (dd/mm/yyyy)",
      "req_catch_kg": 489.0,
      "total_catch_kg": 620.0
    }
  ],
  "printed_total": {"req_catch_kg": "Số ở dòng TỔNG/TOTAL in trên giấy, cột KL nguyên liệu mua (null nếu trang không có dòng tổng)", "total_catch_kg": "Số ở dòng TỔNG/TOTAL, cột KL khai thác (null nếu không có)"}
}

QUY TẮC BẮT BUỘC ĐẢM BẢO CHÍNH XÁC 100%:
1. ĐỌC ĐẦY ĐỦ TẤT CẢ CÁC TRANG: Duyệt toàn bộ tài liệu từ trang 1 đến trang cuối cùng, không bỏ sót bất kỳ dòng tàu nào.
2. HƯỚNG QUÉT & GÓC NGHIÊNG: Tài liệu scan có thể bị xoay ngang (90°, 270°), xoay ngược (180°), hoặc bị scan nghiêng góc. Hãy tự động nhận diện chiều chữ, xoay đúng chiều để đọc chính xác tuyệt đối chữ và số.
3. CỘT 'THỜI HẠN GIẤY PHÉP ĐẾN': Là ngày hết hạn của Giấy phép KTTS (thường là một ngày trong tương lai 2026-2030). KHÔNG ĐƯỢC nhầm với ngày bốc dỡ hay ngày chuyến biển.
4. HẠN GIẤY PHÉP (cột 7 "Số giấy phép khai thác - thời hạn đến"): ô ghi số GP dạng "154-1/2026/QNg-GPKTTS" rồi xuống dòng ngày hạn, thường có dấu nháy đứng trước ('11/04/2029).
   licence_exp = NGÀY SAU DẤU NHÁY / ngày ở dòng cuối của ô. TUYỆT ĐỐI KHÔNG lấy năm nằm trong số giấy phép (2026 trong "154-1/2026/...") làm năm hết hạn.
   PHÂN BIỆT RÕ 2 CỘT KHỐI LƯỢNG TRONG GIẤY SC - XÁC ĐỊNH THEO TIÊU ĐỀ CỘT, KHÔNG THEO THỨ TỰ LIỆT KÊ TRONG JSON:
   - Trên Mẫu số 01 hiện hành: cột (11) "Tổng khối lượng nguyên liệu mua từ tàu cá (kg)" đứng TRƯỚC, cột (12) "Tổng khối lượng khai thác của tàu cá (kg)" đứng SAU.
     => số ở cột (11) là req_catch_kg, số ở cột (12) là total_catch_kg. Mẫu khác có thể đổi vị trí: luôn đọc chữ ở tiêu đề cột.
   - Kiểm tra lại: KL nguyên liệu mua KHÔNG BAO GIỜ lớn hơn KL khai thác của cùng dòng. Nếu thấy mua > khai thác thì bạn đang đọc đảo cột - đọc lại.
   - "total_catch_kg": Cột "Tổng khối lượng khai thác của tàu cá (kg)" (tổng sản lượng đánh bắt).
   - "req_catch_kg": Cột "Tổng khối lượng nguyên liệu mua từ tàu cá (kg)" (số lượng nguyên liệu mua đưa vào hồ sơ XNNL).
   - QUY TẮC BẮT BUỘC VỀ DẤU GẠCH NGANG '-' HOẶC ĐỂ TRỐNG:
     Trong cột "Tổng khối lượng nguyên liệu mua từ tàu cá (kg)", nếu dòng nào có dấu gạch ngang '-' hoặc để trống (ví dụ các loài phụ: Cá dũa, Mực xà, Cá kiếm, Cá thu... mà doanh nghiệp không mua), thì req_catch_kg BẮT BUỘC ghi là 0.0!
     TUYỆT ĐỐI KHÔNG ĐƯỢC lấy số ở cột khai thác điền vào req_catch_kg nếu ô đó là dấu '-' hoặc trống!
5. CHỈ XUẤT JSON THUẦN TÚY, không có bất kỳ văn bản giải thích nào ngoài khối JSON.
"""

def extract_sc_with_gemini(file_path, api_key, model="gemini-3.8-flash", progress_cb=None):
    """
    Extracts SC tabular data using Google Gemini Vision API.
    Uses Direct Document Upload (native PDF processing) for maximum speed and auto-orientation.
    Falls back to page-by-page rendering if direct document upload encounters an error.
    """
    if progress_cb: progress_cb(0.1, f"Đang gửi tài liệu tới Gemini AI ({model})...")

    from google import genai
    from google.genai import types

    from app_config_manager import tao_google_client
    client = tao_google_client(api_key)

    m_cur = model or "gemini-3.8-flash"
    candidate_models = [m_cur, "gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
    seen = set()
    models_to_try = [m for m in candidate_models if m and not (m in seen or seen.add(m))]

    # 1. Direct Document Upload
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        mime_type = "application/pdf"
    elif ext == ".png":
        mime_type = "image/png"
    elif ext in [".jpg", ".jpeg"]:
        mime_type = "image/jpeg"
    else:
        mime_type = "application/pdf"

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    doc_part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.0
    )

    resp = None
    last_err = None

    if progress_cb: progress_cb(0.3, "Gemini AI đang phân tích tài liệu và tự động chỉnh góc nghiêng...")
    for m in models_to_try:
        try:
            resp = client.models.generate_content(
                model=m,
                contents=[doc_part, DOCUMENT_EXTRACTION_PROMPT],
                config=config
            )
            if resp and resp.text:
                break
        except Exception as e:
            last_err = e
            continue

    if resp is None:
        print(f"Direct upload failed: {last_err}. Chuyển sang quét ảnh từng trang...")
        return _extract_sc_gemini_page_by_page(file_path, client, models_to_try, progress_cb)

    raw_text = resp.text.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    raw_text = raw_text.strip()

    try:
        data = json.loads(raw_text)
    except Exception:
        m_json = re.search(r'(\{[\s\S]*\})', raw_text)
        if m_json:
            try:
                data = json.loads(m_json.group(1))
            except Exception:
                data = {}
        else:
            data = {}

    sc_number = data.get("sc_number")
    port_name = data.get("port_name")
    issue_date = data.get("issue_date")
    all_vessels = data.get("vessels", [])

    # Fallback to filename if SC number missing
    if not sc_number or sc_number.startswith("/") or len(sc_number) < 5:
        m_fn = re.search(r'(\d{4,6})\D+(\d{4})\D+SC\s*([A-ZĐ\s\-]+)?', os.path.basename(file_path), re.IGNORECASE)
        if m_fn:
            num_pref = m_fn.group(1)
            yr = m_fn.group(2)
            suf = m_fn.group(3).strip().replace(" ", "-") if m_fn.group(3) else "GL-TQ"
            sc_number = f"{num_pref}/{yr}/SC-{suf}"

    if progress_cb: progress_cb(0.95, f"AI trích xuất thành công {len(all_vessels)} tàu cá từ tài liệu!")

    return {
        "sc_number": sc_number or os.path.basename(file_path),
        "port_name": port_name or "",
        "issue_date": issue_date or "",
        "records": all_vessels,
        "printed_total": data.get("printed_total")
    }

def _extract_sc_gemini_page_by_page(file_path, client, models_to_try, progress_cb=None):
    from google.genai import types
    doc = fitz.open(file_path)
    total_pages = len(doc)
    all_vessels = []
    sc_number = None
    port_name = None
    issue_date = None
    printed_total = None

    for pno in range(total_pages):
        pct = 0.2 + (pno / total_pages) * 0.7
        if progress_cb: progress_cb(pct, f"Gemini AI quét trang {pno + 1}/{total_pages}...")

        page = doc[pno]
        pix = page.get_pixmap(dpi=180)
        img_bytes = pix.tobytes("jpeg")
        img_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0
        )

        page_resp = None
        for m in models_to_try:
            try:
                page_resp = client.models.generate_content(
                    model=m,
                    contents=[img_part, PAGE_EXTRACTION_PROMPT],
                    config=config
                )
                if page_resp and page_resp.text:
                    break
            except Exception:
                continue

        if not page_resp: continue

        raw_text = page_resp.text.strip()
        if raw_text.startswith("```json"): raw_text = raw_text[7:]
        if raw_text.startswith("```"): raw_text = raw_text[3:]
        if raw_text.endswith("```"): raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        try:
            data = json.loads(raw_text)
        except Exception:
            m_json = re.search(r'(\{[\s\S]*\})', raw_text)
            data = json.loads(m_json.group(1)) if m_json else {}

        if not sc_number and data.get("sc_number"): sc_number = data.get("sc_number")
        if not port_name and data.get("port_name"): port_name = data.get("port_name")
        if not issue_date and data.get("issue_date"): issue_date = data.get("issue_date")
        pt = data.get("printed_total")
        if isinstance(pt, dict) and any(pt.get(k) not in (None, "") for k in ("req_catch_kg", "total_catch_kg")):
            printed_total = pt

        for v in data.get("vessels", []):
            v["page"] = pno + 1
            all_vessels.append(v)

    return {
        "printed_total": printed_total,
        "sc_number": sc_number or os.path.basename(file_path),
        "port_name": port_name or "",
        "issue_date": issue_date or "",
        "records": all_vessels
    }

def extract_sc_with_openai_compatible(file_path, api_key, model="gemini-3.8-flash", base_url="https://api.apiz.vn/v1", progress_cb=None):
    """
    Extracts SC data using OpenAI-compatible Vision API (converts PDF pages to images).
    Fully compatible with APIZ.vn reverse proxy and native OpenAI.
    """
    import base64
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)

    doc = fitz.open(file_path)
    total_pages = len(doc)
    
    image_contents = []
    for pno in range(total_pages):
        if progress_cb:
            pct = 0.1 + (pno / total_pages) * 0.4
            progress_cb(pct, f"Đang kết xuất trang {pno + 1}/{total_pages} gửi AI Vision ({model})...")
        page = doc[pno]
        pix = page.get_pixmap(dpi=150)
        img_b64 = base64.b64encode(pix.tobytes("jpeg")).decode("utf-8")
        image_contents.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "high"}
        })

    doc.close()
    if progress_cb: progress_cb(0.5, f"AI Vision ({model}) đang phân tích bảng biểu SC...")
    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": DOCUMENT_EXTRACTION_PROMPT},
            *image_contents
        ]}
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1
        )
    except Exception:
        # Fallback if specific model on proxy doesn't support json_object mode
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1
        )

    raw_text = (response.choices[0].message.content or "").strip()
    if "```json" in raw_text:
        raw_text = raw_text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in raw_text:
        raw_text = raw_text.split("```", 1)[1].split("```", 1)[0].strip()

    data = {}
    try:
        data = json.loads(raw_text)
    except Exception:
        m_json = re.search(r'(\{[\s\S]*\})', raw_text)
        if m_json:
            try:
                data = json.loads(m_json.group(1))
            except Exception:
                _ghi_loi_bo_qua()
        if not data:
            for fix in [']}', '}', '"]}', '0]}']:
                try:
                    data = json.loads(raw_text + fix)
                    if data: break
                except Exception:
                    _ghi_loi_bo_qua()

    if isinstance(data, list):
        data = {"vessels": data}

    vessels = data.get("vessels") or data.get("records") or []
    sc_number = data.get("sc_number")
    port_name = data.get("port_name")
    issue_date = data.get("issue_date")

    # Fallback to filename if SC number missing
    if not sc_number or sc_number.startswith("/") or len(sc_number) < 5:
        m_fn = re.search(r'(\d{4,6})\D+(\d{4})\D+SC\s*([A-ZĐ\s\-]+)?', os.path.basename(file_path), re.IGNORECASE)
        if m_fn:
            num_pref = m_fn.group(1)
            yr = m_fn.group(2)
            suf = m_fn.group(3).strip().replace(" ", "-") if m_fn.group(3) else "GL-TQ"
            sc_number = f"{num_pref}/{yr}/SC-{suf}"

    return {
        "sc_number": sc_number or os.path.basename(file_path),
        "port_name": port_name or "",
        "issue_date": issue_date or "",
        "records": vessels,
        "vessels": vessels,
        "printed_total": data.get("printed_total")
    }

def extract_sc_with_openai(file_path, api_key, model="gpt-4o-mini", progress_cb=None):
    return extract_sc_with_openai_compatible(file_path, api_key, model=model, base_url="https://api.openai.com/v1", progress_cb=progress_cb)

def extract_sc_with_ai(file_path, provider=None, api_key=None, model=None, base_url=None, cache_dir="cache", progress_cb=None):
    """
    Unified AI extraction interface with caching.
    Supports APIZ.vn (Gemini / OpenAI proxy), Google Gemini (direct), and OpenAI (direct).
    Returns: (sc_info, records_list)
    """
    cfg = load_ai_config()
    provider = provider or cfg.get("provider", "apiz")
    
    if provider.lower() == "apiz":
        key = api_key or cfg.get("apiz_api_key", "")
        model_name = model or cfg.get("apiz_model", "gemini-3.8-flash")
        b_url = base_url or cfg.get("apiz_base_url", "https://api.apiz.vn/v1")
    elif provider.lower() == "gemini":
        key = api_key or cfg.get("gemini_api_key", "")
        # KHÔNG ép xuống 2.5: cổng AI công ty chỉ whitelist gemini-3.8-flash
        model_name = model or cfg.get("gemini_model") or "gemini-3.8-flash"
        b_url = None
    else:
        key = api_key or cfg.get("openai_api_key", "")
        model_name = model or cfg.get("openai_model", "gpt-4o-mini")
        b_url = base_url or cfg.get("openai_base_url", "https://api.openai.com/v1")

    if not key:
        raise ValueError(f"Chưa cấu hình API Key cho {provider.upper()}! Vui lòng nhập API Key trong phần Cấu hình AI.")

    # 1. Check cache
    # Băm TOÀN BỘ file (không chỉ 64KB đầu): PDF ký số / sửa thêm thường chỉ đổi phần cuối file
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        for khoi in iter(lambda: f.read(1 << 20), b""):
            hasher.update(khoi)
    fhash = hasher.hexdigest()
    
    os.makedirs(cache_dir, exist_ok=True)
    # v2 (11/2026): sửa lỗi đảo cột KL mua/khai thác -> KHÔNG dùng lại cache cũ (sc_ai_<hash>.json) đã đọc sai
    cache_meta = os.path.join(cache_dir, f"sc_ai_{SC_CACHE_VER}_{fhash}.json")

    if os.path.exists(cache_meta):
        try:
            with open(cache_meta, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                cached_records = cached_data.get("records", [])
                if cached_records and len(cached_records) > 0:
                    if progress_cb: progress_cb(0.9, "Đang tải dữ liệu AI từ bộ nhớ đệm...")
                    return cached_data["sc_info"], cached_records
        except Exception:
            _ghi_loi_bo_qua()

    # 2. Call AI
    if provider.lower() == "apiz":
        extracted = extract_sc_with_openai_compatible(file_path, key, model=model_name, base_url=b_url, progress_cb=progress_cb)
    elif provider.lower() == "gemini":
        extracted = extract_sc_with_gemini(file_path, key, model=model_name, progress_cb=progress_cb)
    elif provider.lower() == "openai":
        extracted = extract_sc_with_openai_compatible(file_path, key, model=model_name, base_url=b_url, progress_cb=progress_cb)
    else:
        raise ValueError(f"Provider không hợp lệ: {provider}")

    # 3. Format and clean
    sc_number = extracted.get("sc_number", "")
    m_fn = re.search(r'(\d{4,6})\D+(\d{4})\D+SC\s*([A-ZĐ\s\-]+)?', os.path.basename(file_path), re.IGNORECASE)
    if not sc_number or sc_number.startswith("/") or len(sc_number) < 5:
        if m_fn:
            num_pref = m_fn.group(1)
            yr = m_fn.group(2)
            suf = m_fn.group(3).strip().replace(" ", "-") if m_fn.group(3) else "GL-TQ"
            sc_number = f"{num_pref}/{yr}/SC-{suf}"
    elif m_fn and "/" in sc_number:
        # Nếu tên file ghi rõ số SC (VD: 00047) mà AI đọc nhầm chữ số mờ (VD: 00042), chuẩn hóa theo số trên tên file
        fn_num = m_fn.group(1).zfill(5)
        sc_prefix = sc_number.split("/")[0].strip().zfill(5)
        if fn_num != sc_prefix:
            sc_number = f"{m_fn.group(1)}{sc_number[sc_number.find('/'):]}"

    raw_records = extracted.get("records") or extracted.get("vessels") or []
    records = []

    def _parse_safe_float(v):
        if v is None: return 0.0
        if isinstance(v, (int, float)): return float(v)
        s = str(v).replace("'", "").replace("ud", "").strip()
        if "," in s and "." in s:
            s = s.replace(",", "")
        elif "," in s:
            parts = s.split(",")
            if len(parts) == 2 and len(parts[1]) == 3:
                s = parts[0] + parts[1]
            else:
                s = s.replace(",", ".")
        elif "." in s:
            parts = s.split(".")
            if len(parts) == 2 and len(parts[1]) == 3:
                s = parts[0] + parts[1]
        m = re.search(r'(\d+(?:\.\d+)?)', s)
        return float(m.group(1)) if m else 0.0

    for r in raw_records:
        v_id = str(r.get("vessel_id") or r.get("so_tau") or "").strip().upper().replace("Ð", "Đ").replace("BD-", "BĐ-")
        if not v_id.endswith("-TS") and "-TS" in v_id:
            v_id = v_id.split("-TS")[0] + "-TS"
        elif not v_id.endswith("-TS") and v_id:
            v_id = v_id + "-TS"

        tot_kg = _parse_safe_float(r.get("total_catch_kg") or r.get("total_catch") or r.get("san_luong"))
        req_raw = r.get("req_catch_kg")
        if req_raw is None:
            req_raw = r.get("req_catch") or r.get("san_luong_mua")

        if req_raw is not None and str(req_raw).strip() in ['-', '--', '', 'None', 'null']:
            req_kg = 0.0
        elif req_raw is not None:
            req_kg = _parse_safe_float(req_raw)
        else:
            req_kg = tot_kg

        records.append({
            "sc_number": sc_number,
            "page": r.get("page", 1),
            "vessel_id": v_id,
            "owner": str(r.get("owner", "")).strip(),
            "gear": str(r.get("gear") or "").strip(),  # không tự điền "LHP" khi không đọc được
            "licence_no": str(r.get("licence_no", "")).strip(),
            "licence_exp": str(r.get("licence_exp", "")).strip(),
            "catch_area": str(r.get("catch_area", "")).strip(),
            "catch_period": str(r.get("catch_period", "")).strip(),
            "species": str(r.get("species", "")).strip(),
            "landing_date": str(r.get("landing_date", "")).strip(),
            "total_catch_kg": tot_kg,
            "req_catch_kg": req_kg
        })

    if progress_cb: progress_cb(0.92, "Đang tự kiểm tra kết quả đọc (luật logic, sổ tàu, đọc lại ô nghi ngờ)...")
    canh_bao = kiem_tra_sc_sau_khi_doc(
        records, extracted.get("printed_total"), _parse_safe_float,
        doc_lai=tao_ham_doc_lai(file_path, provider.lower(), key, model_name, b_url))

    sc_info = {
        "canh_bao": canh_bao,
        "printed_total": extracted.get("printed_total"),
        "sc_number": sc_number,
        "file_name": os.path.basename(file_path),
        "total_vessels": len(records),
        "total_catch_kg": sum(r["total_catch_kg"] for r in records),
        "total_req_catch_kg": sum(r["req_catch_kg"] for r in records),
        "port_name": extracted.get("port_name", ""),
        "extractor": f"AI ({provider.upper()} - {model_name})"
    }

    # Only save to cache if we actually found records
    if records:
        with open(cache_meta, "w", encoding="utf-8") as f:
            json.dump({"sc_info": sc_info, "records": records}, f, ensure_ascii=False, indent=2)

    if progress_cb: progress_cb(1.0, f"AI trích xuất thành công {len(records)} tàu cá!")
    return sc_info, records
