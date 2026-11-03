"""
ĐỌC HÓA ĐƠN VAT BẢN SCAN BẰNG AI (Gemini / APIZ / OpenAI Vision)
---------------------------------------------------------------
Dùng khi không có hóa đơn điện tử PDF gốc, chỉ có file scan (thường gộp nhiều loại giấy tờ trong 1 file:
hóa đơn + giấy cam kết + bảng kê mua hàng...).

1. classify_pages(): lọc trang KHÔNG tốn API
   - Màu giấy hồng (hóa đơn GTGT in trên giấy hồng)  -> hóa đơn
   - Lớp chữ OCR có từ khóa hóa đơn ("VAT invoice", "giá trị gia tăng", "ký hiệu"...) -> hóa đơn
   - Có từ khóa giấy tờ khác ("Cộng hòa xã hội...", "Kính gửi", "Bảng kê"...) -> bỏ qua
   - Không rõ: nếu file đã có trang chắc chắn là hóa đơn -> bỏ qua; nếu không -> nhờ AI xác định.
2. read_invoice_pages_with_ai(): chỉ gửi AI các trang hóa đơn (song song, có cache theo nội dung ảnh trang
   -> chạy lại không tốn API).
"""
import os
import re
import json
import hashlib
import unicodedata
import concurrent.futures

import fitz

INVOICE_PROMPT = """Ảnh là 1 trang tài liệu scan trong hồ sơ thu mua cá ngừ ở Việt Nam.

Nếu trang này là HÓA ĐƠN GIÁ TRỊ GIA TĂNG (VAT INVOICE), trả về JSON:
{
  "is_invoice": true,
  "so_hd": "95",                       // Số hóa đơn (No.) – chỉ chữ số, bỏ số 0 ở đầu
  "ky_hieu": "1C26TTK",                // Ký hiệu (Serial)
  "ngay_hd": "26/06/2026",             // Ngày lập, dạng dd/mm/yyyy
  "seller_name": "CÔNG TY TNHH ...",   // Đơn vị bán hàng
  "seller_mst": "4400335223",
  "seller_address": "...",
  "buyer_name": "...",                 // Đơn vị mua hàng
  "buyer_mst": "...",
  "items": [                           // MỌI dòng hàng hóa trong bảng
    {"item_name": "Cá ngừ GG 30kg up", "unit": "kg", "qty": 2034, "price": 110100, "amount": 223943400}
  ],
  "total_before_vat": 238729900,       // Cộng tiền hàng
  "vat_amount": 0,
  "total_amount": 238729900            // Tổng tiền thanh toán
}

Nếu KHÔNG phải hóa đơn GTGT (giấy cam kết, bảng kê mua hàng, tờ khai, phiếu cân...), trả về:
{"is_invoice": false, "doc_type": "mô tả ngắn loại giấy tờ"}

Quy tắc số: hóa đơn Việt Nam dùng dấu chấm phân cách hàng nghìn: "2.034" = 2034, "87.100" = 87100,
"223.943.400" = 223943400; dấu phẩy là thập phân: "1.553,5" = 1553.5. Trả số dạng number, không có dấu phân cách.
Đọc chính xác từng chữ số; nếu chữ ký tay/đóng dấu che mờ thì đọc theo số liệu trong bảng.
Chỉ trả về JSON, không giải thích."""

_INV_STRONG = [r"vat\s*i?nvoice", r"\(?\bv\s*a\s*t\b", r"nvoice", r"orce\b", r"gia tri gia t", r"hoa don gia",
               r"ky hieu", r"serial", r"ma cua co quan thue", r"don vi ban hang", r"\bseller\b", r"tax code",
               r"tien thanh toan", r"total payment", r"thue suat", r"tien hang"]
_OTHER = [r"cong h[od]a", r"doc l[a-z]p", r"hanh phuc|h[a-z]nh ph", r"kinh g", r"cam ket", r"bang ke",
          r"tieu chi ap dung", r"chu ghe", r"so cccd", r"tran trong", r"to khai"]


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t or "")
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9()]+", " ", t.lower().replace("đ", "d"))


def _page_signature(page):
    """(tỷ lệ điểm ảnh màu hồng, mã băm nội dung trang dùng làm khóa cache)."""
    pix = page.get_pixmap(dpi=30)
    s = pix.samples
    n = pix.width * pix.height or 1
    step = pix.n
    pink = 0
    for i in range(0, len(s) - 2, step):
        r, g, b = s[i], s[i + 1], s[i + 2]
        if r > 180 and b > 150 and r - g > 35:
            pink += 1
    return pink / n, hashlib.md5(bytes(s)).hexdigest()


def classify_pages(pdf_path):
    """Phân loại từng trang. Trả về list dict: page (1-based), label ('invoice'|'other'|'unsure'), lý do, hash."""
    out = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, 1):
            t = _norm(page.get_text())
            inv = [k for k in _INV_STRONG if re.search(k, t)]
            oth = [k for k in _OTHER if re.search(k, t)]
            pink, h = _page_signature(page)
            if pink >= 0.45:
                label, why = "invoice", f"giấy hồng ({pink:.0%})"
            elif len(inv) >= 2 and len(inv) > len(oth):
                label, why = "invoice", f"từ khóa hóa đơn: {', '.join(inv[:3])}"
            elif oth:
                label, why = "other", f"giấy tờ khác: {', '.join(oth[:2])}"
            else:
                label, why = "unsure", "không rõ"
            out.append({"page": i, "label": label, "reason": why, "pink": pink, "hash": h})
    # Đã có trang chắc chắn là hóa đơn -> trang không rõ coi như không phải (bảng kê xoay ngang, phụ lục...)
    if any(p["label"] == "invoice" for p in out):
        for p in out:
            if p["label"] == "unsure":
                p["label"], p["reason"] = "other", "không có dấu hiệu hóa đơn"
    return out


# ------------------------------------------------------------------ gọi AI
def _resolve_ai(provider=None, api_key=None, model=None, base_url=None):
    from sc_core.ai_extractor import load_ai_config
    cfg = load_ai_config()
    provider = (provider or cfg.get("provider", "apiz")).lower()
    if provider == "apiz":
        key = api_key or cfg.get("apiz_api_key", "")
        model = model or cfg.get("apiz_model", "gemini-3.8-flash")
        base_url = base_url or cfg.get("apiz_base_url", "https://api.apiz.vn/v1")
    elif provider == "gemini":
        key = api_key or cfg.get("gemini_api_key", "")
        model = model or cfg.get("gemini_model", "gemini-2.5-flash")
        if "3.8" in str(model):
            model = "gemini-2.5-flash"
        base_url = None
    else:
        key = api_key or cfg.get("openai_api_key", "")
        model = model or cfg.get("openai_model", "gpt-4o-mini")
        base_url = base_url or cfg.get("openai_base_url", "https://api.openai.com/v1")
    if not key:
        raise ValueError("Chưa cấu hình API Key — vào 'Cài đặt API' để nhập trước khi đọc hóa đơn scan bằng AI.")
    return provider, key, model, base_url


def _parse_json(raw: str) -> dict:
    raw = (raw or "").strip()
    if "```" in raw:
        raw = raw.split("```json", 1)[-1] if "```json" in raw else raw.split("```", 1)[-1]
        raw = raw.split("```", 1)[0]
    raw = raw.strip()
    try:
        data = json.loads(raw)
    except Exception:
        m = re.search(r"(\{[\s\S]*\})", raw)
        try:
            data = json.loads(m.group(1)) if m else {}
        except Exception:
            data = {}
    return data if isinstance(data, dict) else {}


def _ask_vision(img_bytes, provider, key, model, base_url):
    if provider == "gemini":
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)
        part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
        cfg = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
        last = None
        for m in [model, "gemini-2.5-flash", "gemini-2.0-flash"]:
            try:
                resp = client.models.generate_content(model=m, contents=[part, INVOICE_PROMPT], config=cfg)
                if resp and resp.text:
                    return _parse_json(resp.text)
            except Exception as e:
                last = e
        raise RuntimeError(f"Gemini lỗi: {last}")
    import base64
    from openai import OpenAI
    client = OpenAI(api_key=key, base_url=base_url)
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    messages = [{"role": "user", "content": [
        {"type": "text", "text": INVOICE_PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}},
    ]}]
    try:
        resp = client.chat.completions.create(model=model, messages=messages,
                                              response_format={"type": "json_object"}, temperature=0.0)
    except Exception:
        resp = client.chat.completions.create(model=model, messages=messages, temperature=0.0)
    return _parse_json(resp.choices[0].message.content or "")


def _num(v):
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", s):          # 223.943.400 / 1.553,5
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", s):        # 223,943,400
        s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    m = re.search(r"-?\d+(\.\d+)?", s)
    return float(m.group(0)) if m else 0.0


def _to_invoice(data, pdf_path, page_no, model_label):
    so = re.sub(r"\D", "", str(data.get("so_hd") or "")).lstrip("0") or ""
    items = []
    for it in data.get("items") or []:
        qty, price, amount = _num(it.get("qty")), _num(it.get("price")), _num(it.get("amount"))
        if qty <= 0 and amount <= 0:
            continue
        items.append({"item_name": str(it.get("item_name") or "").strip(), "unit": str(it.get("unit") or "kg"),
                      "qty": qty, "price": price, "amount": amount or round(qty * price)})
    ngay = str(data.get("ngay_hd") or "").strip()
    m = re.search(r"(\d{1,2})\D(\d{1,2})\D(\d{2,4})", ngay)
    if m:
        y = m.group(3) if len(m.group(3)) == 4 else "20" + m.group(3)
        ngay = f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{y}"
    total_amount = _num(data.get("total_amount")) or _num(data.get("total_before_vat")) or sum(i["amount"] for i in items)
    return {
        "file_name": f"{os.path.basename(pdf_path)} (trang {page_no})",
        "file_path": pdf_path,
        "page": page_no,
        "source": f"AI scan ({model_label})",
        "so_hd": so,
        "ky_hieu": str(data.get("ky_hieu") or "").strip(),
        "ngay_hd": ngay,
        "seller_name": str(data.get("seller_name") or "").strip(),
        "seller_mst": re.sub(r"[^\d-]", "", str(data.get("seller_mst") or "")),
        "seller_address": str(data.get("seller_address") or "").strip(),
        "buyer_name": str(data.get("buyer_name") or "").strip(),
        "buyer_mst": re.sub(r"[^\d-]", "", str(data.get("buyer_mst") or "")),
        "total_qty": sum(i["qty"] for i in items),
        "total_amount": total_amount,
        "items": items,
        "page_count": 1,
    }


def read_invoice_pages_with_ai(pdf_path, provider=None, api_key=None, model=None, base_url=None,
                               cache_dir="cache", max_workers=4, log_cb=None):
    """
    Đọc các trang HÓA ĐƠN trong file scan bằng AI (bỏ qua trang không phải hóa đơn).
    Trả về (danh sách hóa đơn, thống kê).
    """
    log = log_cb or (lambda m: None)
    pages = classify_pages(pdf_path)
    to_read = [p for p in pages if p["label"] in ("invoice", "unsure")]
    n_skip = sum(1 for p in pages if p["label"] == "other")
    log(f"🧾 {os.path.basename(pdf_path)}: {len(pages)} trang — {len(to_read)} trang hóa đơn sẽ đọc bằng AI, "
        f"bỏ qua {n_skip} trang không phải hóa đơn (giấy cam kết, bảng kê...).")
    stats = {"pages": len(pages), "invoice_pages": len(to_read), "skipped": n_skip,
             "from_cache": 0, "ai_calls": 0, "errors": 0, "not_invoice": 0}
    if not to_read:
        return [], stats

    provider, key, model, base_url = _resolve_ai(provider, api_key, model, base_url)
    os.makedirs(cache_dir, exist_ok=True)

    with fitz.open(pdf_path) as doc:
        images = {p["page"]: doc[p["page"] - 1].get_pixmap(dpi=150).tobytes("jpeg") for p in to_read}

    def work(p):
        cache_f = os.path.join(cache_dir, f"inv_ai_{p['hash']}.json")
        if os.path.exists(cache_f):
            try:
                with open(cache_f, "r", encoding="utf-8") as f:
                    return p, json.load(f), True, None
            except Exception:
                pass
        err = None
        for _ in range(2):  # thử lại 1 lần nếu lỗi mạng / JSON hỏng
            try:
                data = _ask_vision(images[p["page"]], provider, key, model, base_url)
                if "is_invoice" in data:
                    with open(cache_f, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=1)
                    return p, data, False, None
                err = "AI trả kết quả không đúng định dạng"
            except Exception as e:
                err = str(e)
        return p, None, False, err

    results = []
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for p, data, cached, err in ex.map(work, to_read):
            done += 1
            if cached:
                stats["from_cache"] += 1
            else:
                stats["ai_calls"] += 1
            if data is None:
                stats["errors"] += 1
                log(f"   ⚠️ Trang {p['page']}: lỗi đọc AI — {err}")
                continue
            if not data.get("is_invoice"):
                stats["not_invoice"] += 1
                continue
            inv = _to_invoice(data, pdf_path, p["page"], model)
            results.append(inv)
            log(f"   [{done}/{len(to_read)}] Trang {p['page']}: HĐ số {inv['so_hd'] or '?'} • {inv['ngay_hd']} • "
                f"{inv['seller_name'][:40]} • {inv['total_qty']:,.0f} kg" + (" (cache)" if cached else ""))
    results.sort(key=lambda x: x["page"])
    return results, stats


def is_scanned_pdf(pdf_path, text_invoice=None):
    """File PDF là bản scan (có ảnh) mà bộ đọc chữ không lấy được số hóa đơn."""
    if text_invoice and text_invoice.get("so_hd"):
        return False
    try:
        with fitz.open(pdf_path) as doc:
            return any(page.get_images() for page in doc)
    except Exception:
        return False
