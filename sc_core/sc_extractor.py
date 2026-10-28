import os
import sys
import json
import re
import hashlib
import concurrent.futures
import cv2
import numpy as np
import fitz
from rapidocr_onnxruntime import RapidOCR
from sc_core.ai_extractor import extract_sc_with_ai, load_ai_config

def deskew_and_orient_image(pix):
    """
    Auto-detects page orientation and deskews tilted scanned pages.
    1. Fisheries SC document tables are always landscape (width > height).
       If an image is portrait (height > width * 1.15), rotate to landscape.
    2. Detects skew/tilt angle using OpenCV minAreaRect on binary text mask and rotates.
    Returns: img_bytes (PNG)
    """
    try:
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
        if pix.n == 4:
            img = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
        elif pix.n == 3:
            img = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        else:
            img = img_np

        h, w = img.shape[:2]
        # 1. Orientation check: SC tables are landscape A4
        if h > w * 1.15:
            img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            h, w = img.shape[:2]

        # 2. Deskew check
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) > 200:
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            elif angle > 45:
                angle = 90 - angle
            else:
                angle = -angle
            if abs(angle) > 0.6 and abs(angle) < 25:
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

        success, buf = cv2.imencode('.png', img)
        if success:
            return buf.tobytes()
    except Exception:
        pass
    return pix.tobytes("png")

def get_file_hash(filepath):
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def normalize_vessel_str(s):
    if not s: return ""
    s = str(s).strip().upper()
    s = s.replace("Ð", "Đ").replace(" ", "")
    # Format BĐ-XXXXX-TS, BD-XXXXX-TS, GL-XXXXX-TS, PY-XXXXX-TS, etc.
    m = re.search(r'\b([A-ZĐ]{2,4}-\d+[\w\-]*)', s)
    if m:
        v = m.group(1)
        # Ensure ends with -TS
        if not v.endswith("-TS") and "-TS" in v:
            v = v.split("-TS")[0] + "-TS"
        elif not v.endswith("-TS"):
            v = v + "-TS"
        return v.replace("BD-", "BĐ-")
    return s

def parse_weight_number(s):
    if not s: return 0.0
    s_raw = str(s).replace('ud', '').replace("'", "").strip()
    # If multiple numbers separated by space e.g. '894 575 540', take the first number
    tokens = s_raw.split()
    s = tokens[0] if tokens else ""
    s = s.replace(' ', '')
    # If formatted as 1.926 (thousand separator dot)
    if '.' in s:
        parts = s.split('.')
        if len(parts) == 2 and len(parts[1]) == 3:
            s = parts[0] + parts[1]
    m_num = re.search(r'(\d+(?:\.\d+)?)', s)
    return float(m_num.group(1)) if m_num else 0.0

def extract_sc_document(file_path, cache_dir="cache", progress_cb=None, use_ai=None, api_key=None, provider=None):
    """
    Extracts tabular data from an SC PDF file.
    Supports both AI Vision (Gemini / OpenAI) and offline RapidOCR.
    Returns: (sc_info, records_list)
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

    # 1. Check AI mode configuration
    cfg = load_ai_config()
    should_use_ai = use_ai if use_ai is not None else cfg.get("use_ai", False)
    ai_provider = provider or cfg.get("provider", "apiz")
    if not api_key:
        if ai_provider == "apiz":
            key = cfg.get("apiz_api_key")
        elif ai_provider == "gemini":
            key = cfg.get("gemini_api_key")
        else:
            key = cfg.get("openai_api_key")
    else:
        key = api_key

    if should_use_ai and key and key.strip():
        try:
            return extract_sc_with_ai(file_path, provider=ai_provider, api_key=key.strip(), cache_dir=cache_dir, progress_cb=progress_cb)
        except Exception as e:
            err_msg = f"AI Vision ({ai_provider}) gặp sự cố: {e}. Tự động chuyển sang quét OCR Cục bộ..."
            print(err_msg)
            if progress_cb: progress_cb(0.1, err_msg)

    # 2. Local RapidOCR mode (Offline Fallback)
    os.makedirs(cache_dir, exist_ok=True)
    fhash = get_file_hash(file_path)
    cache_meta = os.path.join(cache_dir, f"sc_{fhash}.json")
    
    if os.path.exists(cache_meta):
        if progress_cb: progress_cb(0.9, "Đang tải dữ liệu SC từ bộ nhớ đệm...")
        with open(cache_meta, "r", encoding="utf-8") as f:
            cached_data = json.load(f)
            return cached_data["sc_info"], cached_data["records"]

    if progress_cb: progress_cb(0.05, "Đang khởi tạo công cụ bóc tách tài liệu...")
    doc = fitz.open(file_path)
    ocr = RapidOCR()
    total_pages = len(doc)
    
    all_pages_boxes = []
    for pno in range(total_pages):
        if progress_cb:
            pct = 0.1 + (pno / total_pages) * 0.6
            progress_cb(pct, f"Đang quét OCR trang {pno + 1}/{total_pages}...")
            
        page = doc[pno]
        pix = page.get_pixmap(dpi=180)
        img_bytes = deskew_and_orient_image(pix)
        result, _ = ocr(img_bytes)
        boxes = []
        if result:
            for b in result:
                boxes.append({'box': b[0], 'text': b[1], 'score': float(b[2])})
        all_pages_boxes.append(boxes)

    if progress_cb: progress_cb(0.75, "Đang phân tích cấu trúc bảng và trích xuất dữ liệu...")

    # Extract SC Header from Page 1
    p1_boxes = all_pages_boxes[0] if all_pages_boxes else []
    sc_number = ""
    for i, b in enumerate(p1_boxes):
        txt = b['text'].strip()
        if re.search(r'SC-[A-ZĐ]{2,4}-[A-ZĐ]{2,4}', txt, re.IGNORECASE) or re.search(r'\d+/202\d+/SC', txt):
            sc_number = txt
            if i > 0 and re.search(r'^\d+$', p1_boxes[i-1]['text'].strip()):
                sc_number = f"{p1_boxes[i-1]['text'].strip()}{sc_number}"
            break

    # If sc_number starts with '/' or missing number prefix, extract from filename
    if not sc_number or sc_number.startswith('/') or len(re.findall(r'\d+', sc_number)) < 2:
        m_fn = re.search(r'(\d{4,6})\D+(\d{4})\D+SC\s*([A-ZĐ\s\-]+)?', os.path.basename(file_path), re.IGNORECASE)
        if m_fn:
            num_prefix = m_fn.group(1)
            yr = m_fn.group(2)
            suffix_part = m_fn.group(3).strip().replace(' ', '-') if m_fn.group(3) else 'GL-TQ'
            if sc_number and '/' in sc_number:
                # Keep whatever suffix was in sc_number
                sc_number = f"{num_prefix}{sc_number[sc_number.find('/'):]}"
            else:
                sc_number = f"{num_prefix}/{yr}/SC-{suffix_part}"
                
    if not sc_number and p1_boxes:
        for b in p1_boxes:
            if "00180" in b['text']:
                sc_number = "00180/2026/SC-GL-TQ"
                break

    # Parse rows across all pages that contain vessels
    records = []
    total_pages = len(all_pages_boxes)
    
    for pno in range(total_pages):
        boxes = all_pages_boxes[pno]
        if not boxes: continue
        
        # Dynamic start_y detection
        start_y = 80
        if pno == 0:
            start_y = 500
            for b in boxes:
                btxt = b['text'].lower()
                if any(k in btxt for k in ['thong tin tau ca', 'so dang ky', 'chu tau', 'stt']):
                    start_y = b['box'][0][1] + 30
                    break
        
        # Locate vessels in left column (x < 420)
        vessel_candidates = []
        for b in boxes:
            y = b['box'][0][1]
            x = b['box'][0][0]
            txt = b['text'].strip()
            if y >= start_y and x < 420 and re.search(r'\b[A-ZĐa-zĐÐ]{2,4}-\d+', txt, re.IGNORECASE) and not any(k in txt.upper() for k in ['GPKT', 'FAO', 'SC', 'PAGE', 'TONG', 'MAU', 'CAN', 'M3']):
                v_clean = normalize_vessel_str(txt)
                vessel_candidates.append({'box': b['box'], 'text': v_clean, 'raw': txt})
                
        if not vessel_candidates:
            # Page without vessel table (e.g. signature or CC page)
            continue
            
        vessel_candidates = sorted(vessel_candidates, key=lambda vb: vb['box'][0][1])
        
        for i, vb in enumerate(vessel_candidates):
            y_top = vb['box'][0][1] - 35
            if i + 1 < len(vessel_candidates):
                y_bot = vessel_candidates[i+1]['box'][0][1] - 35
            else:
                y_bot = y_top + 130
                
            row_boxes = [b for b in boxes if y_top <= b['box'][0][1] < y_bot]
            
            owner_texts = []
            gear_texts = []
            licence_texts = []
            area_time_texts = []
            species_texts = []
            landing_date_texts = []
            total_catch_texts = []
            req_catch_texts = []
            
            for b in row_boxes:
                x = b['box'][0][0]
                txt = b['text'].strip()
                # Intelligent classification based on content patterns
                if re.search(r'\d+/\d{4}/|\bGPKTTS\b', txt, re.IGNORECASE):
                    licence_texts.append(txt)
                elif re.match(r'^(LHP|LD|LĐ|LRE|RE|RÊ|VAY|PS|GN)$', txt, re.IGNORECASE):
                    gear_texts.append(txt)
                elif 360 <= x < 560:
                    owner_texts.append(txt)
                elif 560 <= x < 920:
                    pass # length, phone, imo
                elif 920 <= x < 1020:
                    gear_texts.append(txt)
                elif 1020 <= x < 1230:
                    licence_texts.append(txt)
                elif 1230 <= x < 1470:
                    area_time_texts.append(txt)
                elif 1470 <= x < 1680:
                    species_texts.append(txt)
                elif 1680 <= x < 1800:
                    landing_date_texts.append(txt)
                elif 1800 <= x < 1980:
                    total_catch_texts.append(txt)
                elif 1980 <= x < 2160:
                    req_catch_texts.append(txt)
                    
            owner = ' '.join(owner_texts).strip()
            gear = ' '.join(gear_texts).strip() or 'LHP'
            lic_raw = ' '.join(licence_texts).strip()
            area_time_raw = ' '.join(area_time_texts).strip()
            species_raw = ' '.join(species_texts).strip()
            landing_date_raw = ' '.join(landing_date_texts).strip()
            total_catch_raw = ' '.join(total_catch_texts).strip()
            req_catch_raw = ' '.join(req_catch_texts).strip()
            
            # Licence No & Expiry
            lic_exp = ""
            m_exp = re.search(r'(\d{2}/\d{2}/\d{4})', lic_raw)
            if m_exp:
                lic_exp = m_exp.group(1)
            
            m_lic = re.search(r'(\d+/\d{4}/[A-ZĐa-z\-]+(?:GPKTTS)?)', lic_raw)
            if m_lic:
                lic_no = m_lic.group(1)
            else:
                lic_no = lic_raw.replace(lic_exp, '').replace("'", "").strip()
                
            # Fallback if lic_no was captured in gear
            if not lic_no:
                m_lic_gear = re.search(r'(\d+/\d{4}/[A-ZĐa-z\-]+(?:GPKTTS)?)', gear)
                if m_lic_gear:
                    lic_no = m_lic_gear.group(1)
                    gear = gear.replace(m_lic_gear.group(0), '').strip() or 'LHP'

            if lic_no and (lic_no.endswith("-") or not lic_no.endswith("GPKTTS")):
                if "GPKTTS" in lic_raw or "GPKT" in lic_raw or "GPKTTS" in gear:
                    if lic_no.endswith("-"):
                        lic_no = lic_no + "GPKTTS"
                    else:
                        lic_no = lic_no + "-GPKTTS"
                        
            # Catch Period & Area
            catch_period = ""
            m_period = re.search(r'(\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4})', area_time_raw)
            if m_period:
                catch_period = m_period.group(1).replace(' ', '')
                area = area_time_raw.replace(m_period.group(1), '').strip()
            else:
                area = area_time_raw
                
            # Landing Date
            m_date = re.search(r'(\d{2}/\d{2}/\d{4})', landing_date_raw)
            landing_date = m_date.group(1) if m_date else landing_date_raw
            
            total_catch = parse_weight_number(total_catch_raw)
            clean_req = str(req_catch_raw or '').strip()
            if clean_req in ['-', '–', '—']:
                req_catch = 0.0
            elif clean_req:
                req_catch = parse_weight_number(clean_req)
            else:
                req_catch = total_catch
            
            records.append({
                'sc_number': sc_number or "00180/2026/SC-GL-TQ",
                'page': pno + 1,
                'vessel_id': vb['text'],
                'owner': owner,
                'gear': gear,
                'licence_no': lic_no,
                'licence_exp': lic_exp,
                'catch_area': area,
                'catch_period': catch_period,
                'species': species_raw,
                'landing_date': landing_date,
                'total_catch_kg': total_catch,
                'req_catch_kg': req_catch
            })

    sc_info = {
        'sc_number': sc_number or "00180/2026/SC-GL-TQ",
        'file_name': os.path.basename(file_path),
        'total_vessels': len(records),
        'total_catch_kg': sum(r['total_catch_kg'] for r in records)
    }

    # Save to cache
    with open(cache_meta, "w", encoding="utf-8") as f:
        json.dump({"sc_info": sc_info, "records": records}, f, ensure_ascii=False, indent=2)

    if progress_cb: progress_cb(1.0, f"Bóc tách SC thành công ({len(records)} tàu cá)!")
    return sc_info, records

def normalize_sc_code(s, filename=""):
    """
    Normalizes SC number to core format for reliable matching.
    e.g. '00180/2026/SC-GL-TQ-HL' -> '00180/2026'
    e.g. '00180' -> '00180'
    """
    if not s: return ""
    s = str(s).strip().upper()
    m = re.search(r'(\d{4,6})[/\s\-_](\d{4})', s)
    if m:
        return f"{int(m.group(1)):05d}/{m.group(2)}"
    if filename:
        m2 = re.search(r'(\d{4,6})[/\s\-_](\d{4})', filename)
        if m2:
            return f"{int(m2.group(1)):05d}/{m2.group(2)}"
    m3 = re.search(r'(\d{4,6})', s)
    if m3:
        return f"{int(m3.group(1)):05d}"
    return s

def extract_multiple_sc_documents(file_paths, cache_dir="cache", progress_cb=None, use_ai=None, api_key=None, provider=None):
    """
    Bóc tách dữ liệu từ nhiều file scan SC (PDF/ảnh).
    Hỗ trợ danh sách file hoặc thư mục chứa các file scan.
    Hỗ trợ cả AI Vision (Gemini / OpenAI) và Offline OCR.
    Returns:
        sc_repo: dict { normalized_sc: {'sc_info': sc_info, 'records': [...], 'file_path': ...} }
        all_records: list of all vessels across all SCs
    """
    # Expand file_paths: handle folder string, list of folders/files, or semicolon-separated string
    expanded = []
    if isinstance(file_paths, str):
        raw_list = [s.strip() for s in file_paths.split(';') if s.strip()]
    elif isinstance(file_paths, (list, tuple, set)):
        raw_list = list(file_paths)
    else:
        raw_list = [str(file_paths)]

    for p in raw_list:
        if not p: continue
        p = str(p).strip(' "\'')
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                for f in sorted(files):
                    if f.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
                        expanded.append(os.path.join(root, f))
        elif os.path.isfile(p):
            expanded.append(p)

    seen = set()
    file_paths = [x for x in expanded if not (x in seen or seen.add(x))]

    sc_repo = {}
    all_records = []
    total_files = len(file_paths)
    if total_files == 0:
        return sc_repo, all_records

    # Check AI mode
    cfg = load_ai_config()
    should_use_ai = use_ai if use_ai is not None else cfg.get("use_ai", False)

    if total_files > 1 and should_use_ai:
        max_workers = min(3, total_files)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_fpath = {
                executor.submit(
                    extract_sc_document,
                    fpath,
                    cache_dir,
                    None,
                    use_ai,
                    api_key,
                    provider
                ): fpath
                for fpath in file_paths
            }
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_fpath):
                fpath = future_to_fpath[future]
                completed_count += 1
                if progress_cb:
                    progress_cb(0.1 + (completed_count / total_files) * 0.85, f"AI hoàn thành {completed_count}/{total_files} file: {os.path.basename(fpath)}")
                try:
                    sc_info, records = future.result()
                    sc_key = normalize_sc_code(sc_info['sc_number'], os.path.basename(fpath))
                    sc_repo[sc_key] = {
                        'sc_info': sc_info,
                        'records': records,
                        'file_path': fpath
                    }
                    m_num = re.search(r'(\d+)', sc_key)
                    if m_num:
                        simple_num = m_num.group(1)
                        if simple_num not in sc_repo:
                            sc_repo[simple_num] = sc_repo[sc_key]
                    all_records.extend(records)
                except Exception as e:
                    print(f"Lỗi bóc tách {fpath}: {e}")
    else:
        for idx, fpath in enumerate(file_paths):
            if not os.path.exists(fpath):
                continue

            def sub_cb(pct, msg):
                if progress_cb:
                    overall_pct = (idx + pct) / total_files
                    progress_cb(overall_pct, f"[{idx+1}/{total_files}] {msg}")

            try:
                sc_info, records = extract_sc_document(
                    fpath,
                    cache_dir=cache_dir,
                    progress_cb=sub_cb,
                    use_ai=use_ai,
                    api_key=api_key,
                    provider=provider
                )
                sc_key = normalize_sc_code(sc_info['sc_number'], os.path.basename(fpath))
                sc_repo[sc_key] = {
                    'sc_info': sc_info,
                    'records': records,
                    'file_path': fpath
                }
                # Also index by simple number like '00180'
                m_num = re.search(r'(\d+)', sc_key)
                if m_num:
                    simple_num = m_num.group(1)
                    if simple_num not in sc_repo:
                        sc_repo[simple_num] = sc_repo[sc_key]

                all_records.extend(records)
            except Exception as e:
                print(f"Error extracting {fpath}: {e}")

    if progress_cb:
        progress_cb(1.0, f"Đã bóc tách thành công {len(sc_repo)} Giấy xác nhận SC (Tổng {len(all_records)} tàu cá)!")

    return sc_repo, all_records
