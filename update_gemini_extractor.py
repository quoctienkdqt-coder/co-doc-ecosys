import sys
sys.stdout.reconfigure(encoding='utf-8')

new_extract_func = '''def extract_co_data_from_files(
    api_key: str,
    file_paths: List[str],
    target_form: str = "EUR.1",
    model_name: str = "gemini-2.5-flash",
    api_source: str = "official",
    api_base_url: str = "",
    progress_cb = None
) -> Tuple[CODeclarationData, str]:
    """
    Trích xuất dữ liệu C/O từ danh sách file chứng từ sử dụng Google Gemini SDK hoặc APIZ Gateway
    """
    if not api_key:
        raise ValueError("Vui lòng nhập Google Gemini hoặc APIZ API Key để thực hiện.")
        
    if not file_paths:
        raise ValueError("Chưa có file chứng từ nào được chọn.")

    # 1. Định tuyến chuẩn xác: Phân biệt rõ Google Gemini Official và APIZ Vietnam Gateway
    # Key Google chính thức luôn bắt đầu bằng 'AIzaSy' hoặc người dùng chọn 'official'
    is_google = (api_source.lower() == "official") or api_key.startswith("AIzaSy")
    is_apiz = not is_google and ((api_source.lower() == "apiz") or api_key.startswith("sk-") or ("apiz" in (api_base_url or "").lower()))

    if is_apiz:
        apiz_model = model_name if model_name and "flash" in model_name else "gemini-3.8-flash"
        return extract_co_data_via_apiz(
            api_key=api_key,
            file_paths=file_paths,
            target_form=target_form,
            model_name=apiz_model,
            base_url=api_base_url or "https://api.apiz.vn/v1",
            progress_cb=progress_cb
        )

    # 2. Xử lý Google Gemini Official
    # Chuẩn hóa model cho Google Official (Google không có gemini-3.8-flash!)
    if not model_name or "3.8" in model_name or model_name == "default":
        model_name = "gemini-2.5-flash"

    candidate_models = [model_name]
    for fallback_m in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
        if fallback_m not in candidate_models:
            candidate_models.append(fallback_m)

    if progress_cb:
        progress_cb(15, f"Đang tối ưu hóa tài liệu và kết nối Google Gemini ({model_name})...")

    client = create_gemini_client(api_key, api_source="official", api_base_url="")

    contents = []
    total_files = len(file_paths)
    for idx, path in enumerate(file_paths):
        if not os.path.exists(path):
            continue
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            try:
                # Nén từng trang PDF thành ảnh JPEG nhẹ (DPI=90, quality=65) để giảm 90% dung lượng payload, chống quá tải token / 429
                doc = fitz.open(path)
                for page_idx in range(len(doc)):
                    page = doc[page_idx]
                    pix = page.get_pixmap(dpi=90)
                    jpg_bytes = pix.tobytes("jpeg", jpg_quality=65)
                    part = types.Part.from_bytes(data=jpg_bytes, mime_type="image/jpeg")
                    contents.append(part)
            except Exception as e:
                # Dự phòng đọc file nhị phân nếu fitz gặp sự cố
                with open(path, "rb") as f:
                    contents.append(types.Part.from_bytes(data=f.read(), mime_type="application/pdf"))
        elif ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
            try:
                from PIL import Image
                import io
                img = Image.open(path).convert("RGB")
                w, h = img.size
                max_dim = 1600
                if max(w, h) > max_dim:
                    scale = max_dim / max(w, h)
                    img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=70, optimize=True)
                contents.append(types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"))
            except Exception:
                with open(path, "rb") as f:
                    contents.append(types.Part.from_bytes(data=f.read(), mime_type=detect_mime_type(path)))
        else:
            mime_type = detect_mime_type(path)
            with open(path, "rb") as f:
                contents.append(types.Part.from_bytes(data=f.read(), mime_type=mime_type))

        if progress_cb:
            pct = 15 + int(((idx + 1) / total_files) * 25)
            progress_cb(pct, f"Đã tối ưu hóa file {idx + 1}/{total_files}: {os.path.basename(path)}")

    if progress_cb:
        progress_cb(45, f"Đang gửi {len(contents)} trang tài liệu đến Google Gemini...")

    prompt_text = (
        f"{SYSTEM_PROMPT}\\n\\n"
        f"LƯU Ý ĐẶC BIỆT CHO LÔ HÀNG NÀY:\\n"
        f"- Mẫu C/O cần làm: Form {target_form}\\n"
        f"- Hãy đọc tất cả các file đính kèm trên để trích xuất đầy đủ và điền vào JSON Schema theo yêu cầu.\\n"
    )
    contents.append(prompt_text)

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=CODeclarationData,
        temperature=0.1,
    )

    # 3. Cơ chế gọi AI kèm Retry & Tự động chuyển đổi Model dự phòng nếu Google báo bận (429/503)
    response = None
    last_api_err = None
    for target_m in candidate_models:
        for attempt in range(1, 4):
            try:
                if progress_cb:
                    if attempt == 1:
                        progress_cb(50, f"Google Gemini ({target_m}) đang phân tích hồ sơ C/O...")
                    else:
                        progress_cb(50, f"Đang thử lại với Google Gemini ({target_m}) lần {attempt}/3...")

                response = client.models.generate_content(
                    model=target_m,
                    contents=contents,
                    config=config,
                )
                if response and response.text:
                    break
            except Exception as e:
                last_api_err = e
                err_str = str(e).lower()
                is_busy = ("429" in err_str or "503" in err_str or "overloaded" in err_str or 
                           "resource_exhausted" in err_str or "quota" in err_str or "temporarily unavailable" in err_str)
                is_not_found = ("404" in err_str or "not found" in err_str)

                if is_busy:
                    wait_time = attempt * 2 + 1
                    if progress_cb:
                        progress_cb(55, f"⚠️ Google Gemini ({target_m}) đang bận (429/503), chờ {wait_time}s tự động thử lại...")
                    time.sleep(wait_time)
                    continue
                elif is_not_found:
                    # Model này không hỗ trợ trên key này, chuyển ngay sang model tiếp theo
                    break
                else:
                    raise e
        if response and response.text:
            break

    if not response or not response.text:
        raise Exception(f"Không nhận được phản hồi từ Google Gemini: {last_api_err}")

    raw_json = response.text
    clean_json = repair_and_extract_json(raw_json)
    
    try:
        co_data = CODeclarationData.model_validate_json(clean_json)
    except Exception as val_err:
        try:
            dict_data = json.loads(clean_json)
            co_data = CODeclarationData.model_validate(dict_data)
        except Exception:
            raise val_err
    
    if not co_data.form:
        co_data.form = target_form

    co_data = normalize_co_data(co_data)
    raw_json = co_data.model_dump_json(indent=2)

    return co_data, raw_json


'''

new_advisor_func = '''def ask_co_advisor(
    api_key: str,
    question: str,
    history: List[dict] = None,
    api_source: str = "official",
    api_base_url: str = "",
    model_name: str = "gemini-2.5-flash"
) -> str:
    """
    Gửi câu hỏi nghiệp vụ C/O hoặc hướng dẫn thao tác eCoSys tới Trợ lý AI Chuyên gia
    """
    is_google = (api_source.lower() == "official") or api_key.startswith("AIzaSy")
    is_apiz = not is_google and ((api_source.lower() == "apiz") or api_key.startswith("sk-") or ("apiz" in (api_base_url or "").lower()))

    if is_apiz:
        apiz_model = model_name if model_name and "flash" in model_name else "gemini-3.8-flash"
        return ask_co_advisor_via_apiz(
            api_key=api_key,
            question=question,
            history=history,
            model_name=apiz_model,
            base_url=api_base_url or "https://api.apiz.vn/v1"
        )

    if not model_name or "3.8" in model_name or model_name == "default":
        model_name = "gemini-2.5-flash"

    candidate_models = [model_name]
    for fallback_m in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
        if fallback_m not in candidate_models:
            candidate_models.append(fallback_m)

    client = create_gemini_client(api_key, api_source="official", api_base_url="")
    
    contents = []
    if history:
        for msg in history[-8:]:
            role = msg.get("role", "user")
            text = msg.get("text", "")
            if text:
                contents.append(f"{'Người dùng' if role == 'user' else 'Trợ lý AI'}: {text}")
                
    contents.append(f"Người dùng hỏi: {question}")
    
    cfg = types.GenerateContentConfig(
        system_instruction=CO_ADVISOR_SYSTEM_PROMPT,
        temperature=0.3
    )

    last_err = None
    for target_m in candidate_models:
        for attempt in range(1, 3):
            try:
                response = client.models.generate_content(
                    model=target_m,
                    contents="\\n\\n".join(contents),
                    config=cfg
                )
                if response and response.text:
                    return response.text
            except Exception as e:
                last_err = e
                err_str = str(e).lower()
                if "429" in err_str or "503" in err_str or "overloaded" in err_str or "resource_exhausted" in err_str:
                    time.sleep(2)
                    continue
                elif "404" in err_str or "not found" in err_str:
                    break
                else:
                    return f"❌ Lỗi Google Gemini API: {e}"

    return f"❌ Không nhận được phản hồi từ Google Gemini: {last_err}"
'''

with open('gemini_extractor.py', 'r', encoding='utf-8') as f:
    code = f.read()

pos1 = code.find('def extract_co_data_from_files(')
pos2 = code.find('CO_ADVISOR_SYSTEM_PROMPT =')
code = code[:pos1] + new_extract_func + code[pos2:]

pos3 = code.find('def ask_co_advisor(')
code = code[:pos3] + new_advisor_func

with open('gemini_extractor.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("[OK] Successfully updated gemini_extractor.py!")
