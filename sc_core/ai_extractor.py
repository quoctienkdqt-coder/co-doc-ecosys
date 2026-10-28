import os
import sys
import json
import re
import hashlib
import fitz

CONFIG_FILE_NAME = "ai_config.json"

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
            pass
            
    # Auto-upgrade any legacy gemini-2.5 or 1.5 references
    if "3.8" in str(default_cfg.get("gemini_model", "")):
        default_cfg["gemini_model"] = "gemini-2.5-flash"
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
        m_req = model_name if (model_name and "3.8" not in model_name) else "gemini-2.5-flash"
        candidate_models = [m_req, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

        last_err = ""
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
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

        # Fallback test with older generativeai if needed
        try:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=api_key)
            for lm in ["gemini-1.5-flash", "gemini-1.5-pro"]:
                try:
                    m_leg = legacy_genai.GenerativeModel(lm)
                    res = m_leg.generate_content("Ping")
                    if res and res.text:
                        return True, f"Kết nối Gemini thành công! (Model: {lm})", lm
                except Exception:
                    pass
        except Exception:
            pass

        return False, f"Lỗi kết nối Gemini: {last_err}", None

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
      "total_catch_kg": 620.0,
      "req_catch_kg": 489.0
    }
  ]
}

QUY TẮC BẮT BUỘC ĐẢM BẢO CHÍNH XÁC 100%:
1. Đọc đúng từng cột của từng dòng tàu trong bảng.
2. Cột 'Thời hạn giấy phép đến' là ngày hết hạn của Giấy phép KTTS (thường là một ngày trong tương lai 2026-2030). KHÔNG ĐƯỢC lấy ngày bốc dỡ hay ngày chuyến biển đưa vào cột hạn phép!
3. PHÂN BIỆT RÕ 2 CỘT KHỐI LƯỢNG TRONG GIẤY SC:
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
      "total_catch_kg": 620.0,
      "req_catch_kg": 489.0
    }
  ]
}

QUY TẮC BẮT BUỘC ĐẢM BẢO CHÍNH XÁC 100%:
1. ĐỌC ĐẦY ĐỦ TẤT CẢ CÁC TRANG: Duyệt toàn bộ tài liệu từ trang 1 đến trang cuối cùng, không bỏ sót bất kỳ dòng tàu nào.
2. HƯỚNG QUÉT & GÓC NGHIÊNG: Tài liệu scan có thể bị xoay ngang (90°, 270°), xoay ngược (180°), hoặc bị scan nghiêng góc. Hãy tự động nhận diện chiều chữ, xoay đúng chiều để đọc chính xác tuyệt đối chữ và số.
3. CỘT 'THỜI HẠN GIẤY PHÉP ĐẾN': Là ngày hết hạn của Giấy phép KTTS (thường là một ngày trong tương lai 2026-2030). KHÔNG ĐƯỢC nhầm với ngày bốc dỡ hay ngày chuyến biển.
4. PHÂN BIỆT RÕ 2 CỘT KHỐI LƯỢNG TRONG GIẤY SC:
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

    client = genai.Client(api_key=api_key)

    m_cur = model if (model and "3.8" not in model) else "gemini-2.5-flash"
    candidate_models = [m_cur, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
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
        "records": all_vessels
    }

def _extract_sc_gemini_page_by_page(file_path, client, models_to_try, progress_cb=None):
    from google.genai import types
    doc = fitz.open(file_path)
    total_pages = len(doc)
    all_vessels = []
    sc_number = None
    port_name = None
    issue_date = None

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

        for v in data.get("vessels", []):
            v["page"] = pno + 1
            all_vessels.append(v)

    return {
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
                pass
        if not data:
            for fix in [']}', '}', '"]}', '0]}']:
                try:
                    data = json.loads(raw_text + fix)
                    if data: break
                except Exception:
                    pass

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
        "vessels": vessels
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
        model_name = model or cfg.get("gemini_model", "gemini-2.5-flash")
        if "3.8" in str(model_name):
            model_name = "gemini-2.5-flash"
        b_url = None
    else:
        key = api_key or cfg.get("openai_api_key", "")
        model_name = model or cfg.get("openai_model", "gpt-4o-mini")
        b_url = base_url or cfg.get("openai_base_url", "https://api.openai.com/v1")

    if not key:
        raise ValueError(f"Chưa cấu hình API Key cho {provider.upper()}! Vui lòng nhập API Key trong phần Cấu hình AI.")

    # 1. Check cache
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        hasher.update(f.read(65536))
    fhash = hasher.hexdigest()
    
    os.makedirs(cache_dir, exist_ok=True)
    cache_meta = os.path.join(cache_dir, f"sc_ai_{fhash}.json")
    
    if os.path.exists(cache_meta):
        try:
            with open(cache_meta, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                cached_records = cached_data.get("records", [])
                if cached_records and len(cached_records) > 0:
                    if progress_cb: progress_cb(0.9, "Đang tải dữ liệu AI từ bộ nhớ đệm...")
                    return cached_data["sc_info"], cached_records
        except Exception:
            pass

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
    # Fallback to filename if missing
    if not sc_number or sc_number.startswith("/") or len(sc_number) < 5:
        m_fn = re.search(r'(\d{4,6})\D+(\d{4})\D+SC\s*([A-ZĐ\s\-]+)?', os.path.basename(file_path), re.IGNORECASE)
        if m_fn:
            num_pref = m_fn.group(1)
            yr = m_fn.group(2)
            suf = m_fn.group(3).strip().replace(" ", "-") if m_fn.group(3) else "GL-TQ"
            sc_number = f"{num_pref}/{yr}/SC-{suf}"

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
            "gear": str(r.get("gear", "")).strip() or "LHP",
            "licence_no": str(r.get("licence_no", "")).strip(),
            "licence_exp": str(r.get("licence_exp", "")).strip(),
            "catch_area": str(r.get("catch_area", "")).strip(),
            "catch_period": str(r.get("catch_period", "")).strip(),
            "species": str(r.get("species", "")).strip(),
            "landing_date": str(r.get("landing_date", "")).strip(),
            "total_catch_kg": tot_kg,
            "req_catch_kg": req_kg
        })

    sc_info = {
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
