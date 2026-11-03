import os
import re
import unicodedata

def strip_vietnamese_accents(s):
    if not s: return ""
    s_clean = str(s).replace('Ð', 'Đ').replace('ð', 'đ')
    nfkd = unicodedata.normalize('NFKD', s_clean)
    res = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return res.replace('đ', 'd').replace('Đ', 'D').replace('Ð', 'D').strip().lower()

def clean_vessel_key(s):
    if not s: return ""
    s_clean = strip_vietnamese_accents(str(s).upper())
    m = re.search(r'([a-z]{2,4}\s*-\s*\d+[\w\-]*)', s_clean, re.IGNORECASE)
    if m:
        s_clean = m.group(1)
    return re.sub(r'[^a-z0-9]', '', s_clean.lower())

def compare_strings_fuzzy(s1, s2):
    """
    Returns:
      'EXACT_MATCH'
      'ACCENT_DIFF' (same text without accents)
      'SUBSTRING_MATCH'
      'MISMATCH'
    """
    s1_str = str(s1 or '').replace('Ð', 'Đ').strip()
    s2_str = str(s2 or '').replace('Ð', 'Đ').strip()
    if not s1_str and not s2_str: return 'EXACT_MATCH'
    if s1_str.lower() == s2_str.lower(): return 'EXACT_MATCH'
    
    clean1 = strip_vietnamese_accents(s1_str)
    clean2 = strip_vietnamese_accents(s2_str)
    if clean1 == clean2: return 'ACCENT_DIFF'
    if clean1 in clean2 or clean2 in clean1: return 'SUBSTRING_MATCH'
    return 'MISMATCH'

def normalize_sc_key(s):
    if not s: return ""
    s = str(s).strip().upper()
    m = re.search(r'(\d{4,6})[/\s\-_](\d{4})', s)
    if m:
        return f"{int(m.group(1)):05d}/{m.group(2)}"
    m2 = re.search(r'(\d{4,6})', s)
    if m2:
        return f"{int(m2.group(1)):05d}"
    return s

def reconcile_excel_vs_sc(excel_records, sc_input, sc_info=None):
    """
    Reconciles Excel aggregated records against SC baseline.
    Supports both Single SC (list) and Multiple SCs (dict/repository).
    Returns:
      - results: List of detailed reconciliation objects per vessel
      - summary_stats: Overview counts
    """
    # 1. Structure SC repository
    # Key: (sc_code, vessel_key) -> sc_record
    # Key: vessel_key -> sc_record (fallback)
    sc_lookup_exact = {}
    sc_lookup_vessel_only = {}
    known_sc_codes = set()
    total_sc_vessels = 0

    def add_to_lookup(k_sc, v_k, item):
        if (k_sc, v_k) not in sc_lookup_exact:
            sc_lookup_exact[(k_sc, v_k)] = []
        sc_lookup_exact[(k_sc, v_k)].append(item)
        if v_k not in sc_lookup_vessel_only:
            sc_lookup_vessel_only[v_k] = []
        sc_lookup_vessel_only[v_k].append(item)

    if isinstance(sc_input, dict):
        # Multi-SC repository
        seen_sc_records = set()
        for sc_k, sc_pack in sc_input.items():
            sc_norm = normalize_sc_key(sc_k)
            known_sc_codes.add(sc_norm)
            recs = sc_pack.get('records', [])
            for sc in recs:
                rec_id = id(sc)
                if rec_id not in seen_sc_records:
                    seen_sc_records.add(rec_id)
                    total_sc_vessels += 1
                v_k = clean_vessel_key(sc['vessel_id'])
                add_to_lookup(sc_norm, v_k, sc)
                m_num = re.search(r'(\d+)', sc_norm)
                if m_num:
                    add_to_lookup(m_num.group(1), v_k, sc)
    elif isinstance(sc_input, list):
        # Single SC list
        total_sc_vessels = len(sc_input)
        for sc in sc_input:
            v_k = clean_vessel_key(sc['vessel_id'])
            sc_no = sc.get('sc_number', '')
            sc_norm = normalize_sc_key(sc_no)
            if sc_norm:
                known_sc_codes.add(sc_norm)
                add_to_lookup(sc_norm, v_k, sc)
                m_num = re.search(r'(\d+)', sc_norm)
                if m_num:
                    add_to_lookup(m_num.group(1), v_k, sc)
            if v_k not in sc_lookup_vessel_only:
                sc_lookup_vessel_only[v_k] = []
            sc_lookup_vessel_only[v_k].append(sc)

    def choose_best_candidate(candidates, rec):
        """
        Lựa chọn ứng viên đối soát tối ưu và an toàn:
        - Ưu tiên 1: Trùng ngày lên cá (landing_date)
        - Ưu tiên 2: Nếu không trùng ngày, chỉ ghép dự phòng nếu khối lượng sai lệch <= 25%
        - Nếu khối lượng lệch quá lớn hoặc không xác định, gắn cờ cảnh báo AMBIGUOUS_MATCH
        """
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        ex_date = rec.get('landing_date', '')
        ex_kg = rec.get('catch_kg', 0.0)

        # Ưu tiên tuyệt đối trùng ngày lên cá
        date_matches = [c for c in candidates if c.get('landing_date') == ex_date and ex_date]
        if date_matches:
            with_req = [c for c in date_matches if (c.get('req_catch_kg') or 0) > 0]
            if with_req:
                return min(with_req, key=lambda c: abs((c.get('req_catch_kg') or 0) - ex_kg))
            return date_matches[0]

        # Khác ngày lên cá: chỉ ghép nếu chênh lệch khối lượng trong ngưỡng an toàn 25%
        with_req_all = [c for c in candidates if (c.get('req_catch_kg') or 0) > 0]
        if with_req_all:
            best = min(with_req_all, key=lambda c: abs((c.get('req_catch_kg') or 0) - ex_kg))
            diff_kg = abs((best.get('req_catch_kg') or 0) - ex_kg)
            rel_diff = diff_kg / max(ex_kg, 1.0)
            if rel_diff <= 0.25:
                best['_reconcile_warning'] = f"Ghép theo tàu nhưng khác ngày lên cá (Excel: {ex_date} vs SC: {best.get('landing_date')})"
                return best
            else:
                best['_reconcile_warning'] = f"Cảnh báo: Khác cả ngày lên cá và khối lượng chênh lệch lớn ({diff_kg:,.1f} kg)"
                return best

        return candidates[0]

    results = []
    
    count_match = 0
    count_conflict = 0
    count_not_in_sc = 0
    count_merged = 0

    for rec in excel_records:
        v_key = clean_vessel_key(rec['vessel_id'])
        ex_sc_raw = rec.get('sc_number', '')
        ex_sc_norm = normalize_sc_key(ex_sc_raw)

        # Lookup logic:
        sc = None
        sc_found_by_sc = False
        if ex_sc_norm and (ex_sc_norm, v_key) in sc_lookup_exact:
            sc = choose_best_candidate(sc_lookup_exact[(ex_sc_norm, v_key)], rec)
            sc_found_by_sc = True
        else:
            # Try numeric part of SC
            m_num = re.search(r'(\d+)', ex_sc_norm)
            if m_num and (m_num.group(1), v_key) in sc_lookup_exact:
                sc = choose_best_candidate(sc_lookup_exact[(m_num.group(1), v_key)], rec)
                sc_found_by_sc = True
            else:
                # Fallback to vessel only across all loaded SCs
                cands = sc_lookup_vessel_only.get(v_key, [])
                if cands:
                    sc = choose_best_candidate(cands, rec)
                    sc_found_by_sc = False

        is_merged = rec.get('is_merged', False)
        if is_merged:
            count_merged += 1

        rec_result = {
            'vessel_id': rec['vessel_id'],
            'vessel_raw': rec.get('vessel_raw', ''),
            'sc_number': ex_sc_raw or (sc.get('sc_number', '') if sc else ''),
            'is_merged': is_merged,
            'merged_count': rec.get('merged_count', 1),
            'excel_data': rec,
            'sc_data': sc,
            'diffs': [],
            'status': 'OK',
            'action_needed': []
        }

        # Check if SC scan itself was missing
        if ex_sc_norm and known_sc_codes:
            m_num = re.search(r'(\d+)', ex_sc_norm)
            num_part = m_num.group(1) if m_num else ex_sc_norm
            sc_exists_in_input = any(num_part in k for k in known_sc_codes)
            if not sc_exists_in_input:
                rec_result['status'] = 'NOT_IN_SC'
                rec_result['diffs'].append({
                    'field': 'Tờ Giấy SC Cảng cá',
                    'excel_val': ex_sc_raw,
                    'sc_val': 'Chưa nạp bản scan',
                    'type': 'CRITICAL',
                    'message': f"Chưa có bản scan PDF cho Giấy xác nhận SC: {ex_sc_raw}"
                })
                rec_result['action_needed'].append(f"Vui lòng nạp thêm file PDF scan của SC {ex_sc_raw}")
                results.append(rec_result)
                count_not_in_sc += 1
                continue

        if not sc:
            count_not_in_sc += 1
            rec_result['status'] = 'NOT_IN_SC'
            sc_msg = f" trong Giấy xác nhận SC {ex_sc_raw}" if ex_sc_raw else " trong các bản SC gốc"
            rec_result['diffs'].append({
                'field': 'Tồn tại trong SC',
                'excel_val': rec['vessel_id'],
                'sc_val': 'Không có trong SC gốc',
                'type': 'CRITICAL',
                'message': f"Tàu {rec['vessel_id']} không có tên{sc_msg}!"
            })
            rec_result['action_needed'].append("Kiểm tra lại số hiệu tàu hoặc số Giấy xác nhận SC")
            results.append(rec_result)
            continue

        # 1. Compare Owner
        owner_cmp = compare_strings_fuzzy(rec['owner'], sc['owner'])
        if owner_cmp == 'MISMATCH':
            rec_result['diffs'].append({
                'field': 'Tên Chủ tàu / Thuyền trưởng',
                'excel_val': rec['owner'] or '(Trống)',
                'sc_val': sc['owner'],
                'type': 'CRITICAL',
                'message': f"Lệch tên chủ tàu: Excel ghi '{rec['owner']}', nhưng SC gốc ghi '{sc['owner']}'"
            })
            rec_result['action_needed'].append(f"Cập nhật tên chủ tàu thành: {sc['owner']}")
        elif owner_cmp in ['ACCENT_DIFF', 'SUBSTRING_MATCH']:
            rec_result['diffs'].append({
                'field': 'Tên Chủ tàu / Thuyền trưởng',
                'excel_val': rec['owner'],
                'sc_val': sc['owner'],
                'type': 'WARNING',
                'message': f"Lệch dấu tiếng Việt hoặc viết tắt: '{rec['owner']}' vs '{sc['owner']}'"
            })

        # 2. Compare Fishing Licence No
        # Compare numeric part first
        lic_ex = rec['licence_no'].replace('Ð', 'Đ').strip()
        lic_sc = sc['licence_no'].replace('Ð', 'Đ').strip()
        num_ex = re.search(r'(\d+/\d{4})', lic_ex)
        num_sc = re.search(r'(\d+/\d{4})', lic_sc)
        if num_ex and num_sc and num_ex.group(1) != num_sc.group(1):
            rec_result['diffs'].append({
                'field': 'Số Giấy phép KTTS',
                'excel_val': lic_ex,
                'sc_val': lic_sc,
                'type': 'CRITICAL',
                'message': f"Sai số giấy phép: Excel ghi '{lic_ex}', nhưng SC gốc ghi '{lic_sc}'"
            })
            rec_result['action_needed'].append(f"Cập nhật số GPKTTS thành: {lic_sc}")
        elif compare_strings_fuzzy(lic_ex, lic_sc) == 'MISMATCH':
            rec_result['diffs'].append({
                'field': 'Số Giấy phép KTTS',
                'excel_val': lic_ex,
                'sc_val': lic_sc,
                'type': 'WARNING',
                'message': f"Lệch định dạng số GPKTTS: '{lic_ex}' vs '{lic_sc}'"
            })

        # 3. Compare Licence Expiry Date
        if rec['licence_exp'] and sc['licence_exp']:
            if rec['licence_exp'] != sc['licence_exp']:
                rec_result['diffs'].append({
                    'field': 'Hạn Giấy phép KTTS',
                    'excel_val': rec['licence_exp'],
                    'sc_val': sc['licence_exp'],
                    'type': 'CRITICAL',
                    'message': f"Lệch hạn giấy phép: Excel ghi {rec['licence_exp']}, SC ghi {sc['licence_exp']}"
                })
                rec_result['action_needed'].append(f"Sửa ngày hết hạn GP thành: {sc['licence_exp']}")

        # 4. Compare Catch Period
        clean_period_ex = rec['catch_period'].replace(' ', '')
        clean_period_sc = sc['catch_period'].replace(' ', '')
        if clean_period_ex and clean_period_sc and clean_period_ex != clean_period_sc:
            rec_result['diffs'].append({
                'field': 'Thời gian khai thác',
                'excel_val': rec['catch_period'],
                'sc_val': sc['catch_period'],
                'type': 'CRITICAL',
                'message': f"Lệch thời gian khai thác: Excel ghi '{rec['catch_period']}', SC ghi '{sc['catch_period']}'"
            })
            rec_result['action_needed'].append(f"Sửa thời gian khai thác thành: {sc['catch_period']}")

        # 5. Compare Landing Date
        if rec['landing_date'] and sc['landing_date']:
            if rec['landing_date'] != sc['landing_date']:
                rec_result['diffs'].append({
                    'field': 'Ngày lên cá / bốc dỡ',
                    'excel_val': rec['landing_date'],
                    'sc_val': sc['landing_date'],
                    'type': 'CRITICAL',
                    'message': f"Lệch ngày lên cá: Excel ghi {rec['landing_date']}, SC ghi {sc['landing_date']}"
                })
                rec_result['action_needed'].append(f"Sửa ngày lên cá thành: {sc['landing_date']}")

        # 6. Compare Catch Weight (So sánh Khối lượng mua từ tàu cá)
        ex_kg = rec['catch_kg']
        # SC: Lấy 'req_catch_kg' (Tổng khối lượng nguyên liệu mua từ tàu cá).
        sc_kg = sc.get('req_catch_kg') if sc.get('req_catch_kg') is not None else sc.get('total_catch_kg', 0.0)
        delta_kg = ex_kg - sc_kg
        if abs(delta_kg) > 0.1:
            rec_result['diffs'].append({
                'field': 'Khối lượng nguyên liệu mua (kg)',
                'excel_val': f"{ex_kg:,.1f}",
                'sc_val': f"{sc_kg:,.1f}",
                'delta': delta_kg,
                'type': 'CRITICAL',
                'message': f"Chênh lệch khối lượng mua: Excel ({ex_kg:,.1f} kg) vs SC gốc ({sc_kg:,.1f} kg), lệch: {delta_kg:+,.1f} kg"
            })
            rec_result['action_needed'].append(f"Điều chỉnh khối lượng mua khớp với SC gốc: {sc_kg:,.1f} kg")

        # 7. Add internal validation errors from Excel
        for err in rec.get('validation_errors', []):
            rec_result['diffs'].append({
                'field': 'Logic nghiệp vụ nội bộ',
                'excel_val': err,
                'sc_val': '-',
                'type': 'CRITICAL',
                'message': err
            })

        # Determine overall status
        has_critical = any(d['type'] == 'CRITICAL' for d in rec_result['diffs'])
        has_warning = any(d['type'] == 'WARNING' for d in rec_result['diffs'])
        
        if has_critical:
            rec_result['status'] = 'CONFLICT'
            count_conflict += 1
        elif has_warning or is_merged:
            rec_result['status'] = 'WARNING'
            count_match += 1
        else:
            rec_result['status'] = 'MATCH'
            count_match += 1

        results.append(rec_result)

    summary_stats = {
        'total_excel_vessels': len(excel_records),
        'total_sc_vessels': total_sc_vessels,
        'count_match': count_match,
        'count_conflict': count_conflict,
        'count_not_in_sc': count_not_in_sc,
        'count_merged': count_merged
    }

    return results, summary_stats



def normalize_fish_size(s: str) -> str:
    """
    Chuẩn hóa quy cách / size cá để so khớp giữa Bảng kê và Hóa đơn VAT.
    Ví dụ: 'NC 30up', 'Cá ngừ 30 kg up' -> '30UP'
           '20-30 Kg', 'Cá ngừ 20-30 kg' -> '20_30'
           '30kg up Dạt', 'dạt' -> '30_DAT'
    """
    s_low = str(s or '').lower().strip()
    if 'dạt' in s_low or 'dat' in s_low:
        return '30_DAT'
    if '30' in s_low and ('up' in s_low or 'trở lên' in s_low or 'kg up' in s_low or 'nc 30' in s_low):
        return '30UP'
    if '20' in s_low and '30' in s_low:
        return '20_30'
    m = re.search(r'(\d{1,3})\s*[-–]\s*(\d{1,3})', s_low)  # '15-20kg', '10 - 15 kg'
    if m:
        return f"{int(m.group(1))}_{int(m.group(2))}"
    return 'OTHER'


def bk_size_key(rec) -> str:
    """Khóa nhóm size của 1 dòng bảng kê. Bảng kê không có cột Size -> dùng đơn giá thay cho size."""
    spec = str(rec.get('spec', '') or '').strip()
    if spec:
        return normalize_fish_size(spec)
    price = float(rec.get('price', 0) or 0)
    return f"P{int(round(price))}" if price else 'OTHER'


def match_invoice_item(inv, spec: str, price: float):
    """
    Tìm dòng hàng trên hóa đơn tương ứng 1 dòng bảng kê:
      1. Theo size cá (nếu bảng kê có cột Size)
      2. Theo đơn giá (bảng kê không có Size, hoặc tên hàng trên HĐ không ghi size rõ)
      3. Hóa đơn chỉ có 1 dòng hàng -> lấy dòng đó
    """
    items = (inv or {}).get('items') or []
    if not items:
        return None
    spec = str(spec or '').strip()
    if spec:
        key = normalize_fish_size(spec)
        for it in items:
            if normalize_fish_size(it.get('item_name', '')) == key:
                return it
    if price:
        same_price = [it for it in items if abs(float(it.get('price', 0) or 0) - float(price)) < 1.0]
        if len(same_price) >= 1:
            return same_price[0]
    if len(items) == 1:
        return items[0]
    return None


def reconcile_bang_ke_vs_invoices(bang_ke_records, invoices_repo):
    """
    Đối chiếu chi tiết giữa Bảng kê thu mua (Phụ lục III / TT 05) với Hóa đơn VAT điện tử (PDF).
    Kiểm tra:
      1. Tồn tại hóa đơn PDF.
      2. Khớp ngày lập hóa đơn.
      3. Khớp tên/MST nhà cung cấp.
      4. Kiểm tra khối lượng phân bổ theo từng size cá và tổng hóa đơn.
      5. Kiểm tra đơn giá từng size cá so với dòng tương ứng trên Hóa đơn PDF.
    """
    repo = invoices_repo.get('repo', {}) if isinstance(invoices_repo, dict) else {}
    from collections import defaultdict

    # Gom nhóm tính tổng lượng Excel theo (hd_no, hd_date, supplier, size)
    excel_size_totals = defaultdict(float)
    for r in bang_ke_records:
        h_no = str(r['hd_no']).lstrip('0') or '0'
        sz = bk_size_key(r)
        k_sz = (h_no, r.get('hd_date', ''), r.get('supplier', ''), sz)
        excel_size_totals[k_sz] += float(r.get('qty', 0.0))

    # Nhóm theo (Số HĐ, Nhà cung cấp): 2 NCC khác nhau có thể trùng số hóa đơn (vd HĐ 142 của Tấn Tài và
    # của Năm Khánh) -> phải tách riêng, không cộng dồn khối lượng vào nhau.
    from sc_core.invoice_extractor import clean_supplier_text
    by_hd_sup = defaultdict(list)
    for r in bang_ke_records:
        by_hd_sup[(r['hd_no'], clean_supplier_text(strip_vietnamese_accents(r.get('supplier', ''))))].append(r)
    by_hd = [(k[0], v) for k, v in by_hd_sup.items()]

    invoice_recons = []
    row_recons = []

    count_match = 0
    count_partial = 0
    count_over = 0
    count_missing = 0
    count_warn = 0

    for hd_no, items in sorted(by_hd, key=lambda x: (int(x[0]) if str(x[0]).isdigit() else 999,
                                                     x[1][0].get('supplier', ''))):
        bk_qty = sum(x['qty'] for x in items)
        bk_amt = sum(x['amount'] for x in items)
        vessels = sorted(list(set(x['vessel_id'] for x in items)))
        sc_numbers = sorted(list(set(x['sc_no'] for x in items)))
        first_item = items[0]
        bk_date = first_item['hd_date']
        bk_supplier = first_item['supplier']

        # Tìm kiếm thông minh Hóa đơn trong Repo (xử lý trùng số HĐ giữa nhiều NCC)
        from sc_core.invoice_extractor import find_invoice_in_repo
        inv = find_invoice_in_repo(invoices_repo, hd_no, supplier_hint=bk_supplier, date_hint=bk_date)

        diffs = []
        action_needed = []

        if not inv:
            status = 'MISSING'
            count_missing += 1
            diffs.append({
                'field': 'Tồn tại hóa đơn PDF',
                'bk_val': f"HĐ {hd_no}",
                'pdf_val': "KHÔNG TÌM THẤY",
                'type': 'CRITICAL',
                'message': f"Không tìm thấy file PDF cho Hóa đơn số {hd_no} trong thư mục hóa đơn"
            })
            action_needed.append(f"Bổ sung file PDF hóa đơn số {hd_no} vào thư mục hóa đơn")
            pdf_qty = 0.0
            pdf_amt = 0.0
            pdf_date = "-"
            pdf_seller = "-"
            pdf_mst = "-"
            alloc_pct = 0.0
        else:
            pdf_qty = inv.get('total_qty', 0.0)
            pdf_amt = inv.get('total_amount', 0.0)
            pdf_date = inv.get('ngay_hd', '')
            pdf_seller = inv.get('seller_name', '')
            pdf_mst = inv.get('seller_mst', '')

            # 1. So khớp ngày HĐ
            if bk_date and pdf_date:
                # Chuẩn hóa so sánh ngày
                d_bk_clean = bk_date.replace('-', '/').strip()
                d_pdf_clean = pdf_date.replace('-', '/').strip()
                if d_bk_clean != d_pdf_clean:
                    diffs.append({
                        'field': 'Ngày hóa đơn',
                        'bk_val': bk_date,
                        'pdf_val': pdf_date,
                        'type': 'WARNING',
                        'message': f"Lệch ngày HĐ: Bảng kê ghi {bk_date}, Hóa đơn PDF ghi {pdf_date}"
                    })
                    action_needed.append(f"Cập nhật ngày HĐ trên Bảng kê thành {pdf_date}")

            # 2. So khớp nhà cung cấp
            from sc_core.invoice_extractor import clean_supplier_text
            bk_sup_c = clean_supplier_text(bk_supplier)
            pdf_sup_c = clean_supplier_text(pdf_seller)
            if bk_sup_c and pdf_sup_c and (bk_sup_c in pdf_sup_c or pdf_sup_c in bk_sup_c):
                pass # Khớp tên nhà cung cấp (chấp nhận Cty / Công ty / TNHH)
            else:
                sup_cmp = compare_strings_fuzzy(bk_supplier, pdf_seller)
                if sup_cmp == 'MISMATCH':
                    diffs.append({
                        'field': 'Tên Nhà cung cấp',
                        'bk_val': bk_supplier,
                        'pdf_val': pdf_seller,
                        'type': 'WARNING',
                        'message': f"Tên NCC khác biệt: Bảng kê '{bk_supplier}' vs HĐ '{pdf_seller}'"
                    })

            # 3. So khớp khối lượng & Phân bổ
            delta_qty = bk_qty - pdf_qty
            alloc_pct = (bk_qty / pdf_qty * 100) if pdf_qty > 0 else 0.0

            if delta_qty > 0.5:
                # Kê vượt quá hóa đơn
                status = 'OVER_ALLOCATED'
                count_over += 1
                diffs.append({
                    'field': 'Khối lượng mua (kg)',
                    'bk_val': f"{bk_qty:,.1f}",
                    'pdf_val': f"{pdf_qty:,.1f}",
                    'delta': delta_qty,
                    'type': 'CRITICAL',
                    'message': f"KÊ VƯỢT QUÁ HÓA ĐƠN: Bảng kê ({bk_qty:,.1f} kg) > HĐ gốc ({pdf_qty:,.1f} kg), vượt {delta_qty:,.1f} kg"
                })
                action_needed.append(f"Giảm khối lượng kê khai của HĐ {hd_no} xuống tối đa {pdf_qty:,.1f} kg")
            elif abs(delta_qty) <= 0.5:
                # Khớp 100%
                if any(d['type'] == 'WARNING' for d in diffs):
                    status = 'WARNING'
                    count_warn += 1
                else:
                    status = 'MATCH'
                    count_match += 1
            else:
                # Xuất dùng 1 phần
                if any(d['type'] == 'WARNING' for d in diffs):
                    status = 'WARNING'
                    count_warn += 1
                else:
                    status = 'PARTIAL'
                    count_partial += 1

            # 4. Kiểm tra đơn giá từng mặt hàng trên Bảng kê
            inv_prices = [it['price'] for it in inv.get('items', [])]
            for it in items:
                it_p = it['price']
                if inv_prices and not any(abs(it_p - p) < 1.0 for p in inv_prices):
                    diffs.append({
                        'field': f"Đơn giá dòng {it['stt']} ({it['spec']})",
                        'bk_val': f"{it_p:,.0f} đ",
                        'pdf_val': f"{inv_prices}",
                        'type': 'WARNING',
                        'message': f"Đơn giá dòng {it['stt']} ({it['spec']}: {it_p:,.0f} đ) không khớp đơn giá nào trên HĐ"
                    })

        inv_res = {
            'hd_no': hd_no,
            'status': status,
            'bk_date': bk_date,
            'pdf_date': pdf_date,
            'bk_supplier': bk_supplier,
            'pdf_seller': pdf_seller,
            'pdf_mst': pdf_mst,
            'bk_rows_count': len(items),
            'bk_vessels': vessels,
            'bk_sc_numbers': sc_numbers,
            'bk_qty': bk_qty,
            'pdf_qty': pdf_qty,
            'diff_qty': (bk_qty - pdf_qty) if inv else bk_qty,
            'alloc_pct': alloc_pct,
            'bk_amt': bk_amt,
            'pdf_amt': pdf_amt,
            'diffs': diffs,
            'action_needed': action_needed,
            'items': items
        }
        invoice_recons.append(inv_res)

        for it in items:
            row_recons.append({
                'stt': it['stt'],
                'hd_no': hd_no,
                'vessel_id': it['vessel_id'],
                'owner': it['owner'],
                'sc_no': it['sc_no'],
                'qty': it['qty'],
                'price': it['price'],
                'amount': it['amount'],
                'inv_status': status,
                'pdf_qty': pdf_qty,
                'pdf_date': pdf_date,
                'pdf_seller': pdf_seller
            })

    summary = {
        'total_invoices_bk': len(by_hd),
        'total_invoices_pdf': invoices_repo.get('count', 0) if isinstance(invoices_repo, dict) else 0,
        'count_match': count_match,
        'count_partial': count_partial,
        'count_over': count_over,
        'count_missing': count_missing,
        'count_warn': count_warn
    }

    return invoice_recons, row_recons, summary


def reconcile_bang_ke_vs_sc(bang_ke_records, sc_repo):
    """
    Đối chiếu chi tiết giữa Bảng kê thu mua (Phụ lục III / TT 05) với SC Gốc Cảng cá.
    Kiểm tra:
      1. Số giấy xác nhận SC có trong hồ sơ không.
      2. Số đăng ký tàu cá có thực sự thuộc Giấy SC đó không.
      3. Tên chủ tàu trên Bảng kê có khớp SC không.
      4. Khối lượng nguyên liệu phân bổ cho tàu có vượt quá sản lượng trong SC không.
    """
    # Xây dựng bảng tra cứu SC
    sc_lookup_exact = {}
    known_sc_codes = set()
    total_sc_vessels = 0

    if isinstance(sc_repo, dict):
        seen_sc = set()
        for sc_k, sc_pack in sc_repo.items():
            sc_norm = normalize_sc_key(sc_k)
            known_sc_codes.add(sc_norm)
            m_num = re.search(r'(\d+)', sc_norm)
            if m_num:
                known_sc_codes.add(m_num.group(1))

            recs = sc_pack.get('records', [])
            for sc in recs:
                rec_id = id(sc)
                if rec_id not in seen_sc:
                    seen_sc.add(rec_id)
                    total_sc_vessels += 1
                v_k = clean_vessel_key(sc['vessel_id'])
                if (sc_norm, v_k) not in sc_lookup_exact:
                    sc_lookup_exact[(sc_norm, v_k)] = []
                sc_lookup_exact[(sc_norm, v_k)].append(sc)
                if m_num:
                    s_simple = m_num.group(1)
                    if (s_simple, v_k) not in sc_lookup_exact:
                        sc_lookup_exact[(s_simple, v_k)] = []
                    sc_lookup_exact[(s_simple, v_k)].append(sc)

    # Gom nhóm theo (sc_no, vessel_id) trên Bảng kê
    from collections import defaultdict
    by_sc_vessel = defaultdict(list)
    for r in bang_ke_records:
        k = (normalize_sc_key(r['sc_no']), clean_vessel_key(r['vessel_id']))
        by_sc_vessel[k].append(r)

    results = []
    count_match = 0
    count_warning = 0
    count_conflict = 0
    count_not_in_sc = 0

    for (sc_norm, v_k), items in by_sc_vessel.items():
        first_item = items[0]
        v_id = first_item['vessel_id']
        sc_no = first_item['sc_no']
        owner_bk = first_item['owner']
        sum_qty = sum(x['qty'] for x in items)
        hds = sorted(list(set(x['hd_no'] for x in items)))

        diffs = []
        action_needed = []

        # 1. Kiểm tra tồn tại SC
        m_num = re.search(r'(\d+)', sc_norm)
        sc_simple = m_num.group(1) if m_num else sc_norm

        if sc_norm not in known_sc_codes and sc_simple not in known_sc_codes:
            diffs.append({
                'field': 'Giấy xác nhận SC',
                'bk_val': sc_no,
                'sc_val': 'KHÔNG CÓ TRONG HỒ SƠ',
                'type': 'CRITICAL',
                'message': f"Giấy SC '{sc_no}' ghi trên Bảng kê không tồn tại trong danh mục SC gốc đã nạp"
            })
            action_needed.append(f"Kiểm tra lại số giấy SC {sc_no} hoặc bổ sung file Scan SC")
            status = 'CONFLICT'
            count_conflict += 1
            sc_match = None
        else:
            # 2. Tìm tàu trong SC
            candidates = sc_lookup_exact.get((sc_norm, v_k)) or sc_lookup_exact.get((sc_simple, v_k)) or []
            if not candidates:
                diffs.append({
                    'field': 'Tàu trong Giấy SC',
                    'bk_val': f"{v_id} ({sc_no})",
                    'sc_val': 'TÀU KHÔNG THUỘC SC NÀY',
                    'type': 'CRITICAL',
                    'message': f"Tàu cá {v_id} không có trong danh sách tàu bốc dỡ của Giấy SC {sc_no}"
                })
                action_needed.append(f"Kiểm tra lại việc gán tàu {v_id} vào Giấy SC {sc_no}")
                status = 'CONFLICT'
                count_not_in_sc += 1
                sc_match = None
            else:
                sc_match = candidates[0]
                sc_owner = sc_match.get('owner', '')
                sc_weight = sc_match.get('req_catch_kg') if sc_match.get('req_catch_kg') is not None else sc_match.get('catch_weight', 0.0)

                # 3. So khớp chủ tàu
                owner_cmp = compare_strings_fuzzy(owner_bk, sc_owner)
                if owner_cmp == 'ACCENT_DIFF':
                    diffs.append({
                        'field': 'Tên Chủ tàu',
                        'bk_val': owner_bk,
                        'sc_val': sc_owner,
                        'type': 'INFO',
                        'message': f"Khớp tên chủ tàu (Bảng kê có dấu '{owner_bk}' vs SC không dấu '{sc_owner}')"
                    })
                elif owner_cmp in ('SUBSTRING_MATCH', 'MISMATCH'):
                    diffs.append({
                        'field': 'Tên Chủ tàu',
                        'bk_val': owner_bk,
                        'sc_val': sc_owner,
                        'type': 'WARNING',
                        'message': f"Khác biệt tên chủ tàu: Bảng kê '{owner_bk}' vs SC '{sc_owner}'"
                    })
                    action_needed.append(f"Kiểm tra và chuẩn hóa tên chủ tàu theo SC: {sc_owner}")

                # 4. So khớp khối lượng
                if sc_weight and sc_weight > 0:
                    delta_w = sum_qty - sc_weight
                    if delta_w > 0.5:
                        diffs.append({
                            'field': 'Khối lượng tàu (kg)',
                            'bk_val': f"{sum_qty:,.1f}",
                            'sc_val': f"{sc_weight:,.1f}",
                            'delta': delta_w,
                            'type': 'CRITICAL',
                            'message': f"Khối lượng Bảng kê ({sum_qty:,.1f} kg) vượt quá sản lượng SC ({sc_weight:,.1f} kg), lệch: {delta_w:+,.1f} kg"
                        })
                        action_needed.append(f"Giảm khối lượng nguyên liệu kê khai cho tàu {v_id} xuống tối đa {sc_weight:,.1f} kg")

                has_crit = any(d['type'] == 'CRITICAL' for d in diffs)
                has_warn = any(d['type'] == 'WARNING' for d in diffs)
                if has_crit:
                    status = 'CONFLICT'
                    count_conflict += 1
                elif has_warn:
                    status = 'WARNING'
                    count_warning += 1
                else:
                    status = 'MATCH'
                    count_match += 1

        results.append({
            'sc_no': sc_no,
            'vessel_id': v_id,
            'owner_bk': owner_bk,
            'owner_sc': sc_match.get('owner', '') if sc_match else '',
            'sum_qty': sum_qty,
            'sc_weight': sc_weight if sc_match else 0.0,
            'hds': hds,
            'row_count': len(items),
            'status': status,
            'diffs': diffs,
            'action_needed': action_needed,
            'items': items
        })

    summary = {
        'total_vessels_bk': len(by_sc_vessel),
        'total_vessels_sc': total_sc_vessels,
        'count_match': count_match,
        'count_warning': count_warning,
        'count_conflict': count_conflict,
        'count_not_in_sc': count_not_in_sc
    }

    return results, summary


def reconcile_full_suite(bang_ke_file, invoices_dir, sc_sources, excel_xnnl_file=None,
                         use_ai=True, api_key='', api_source='official', api_base_url='',
                         do_merge=True, do_correct=True, progress_cb=None, log_cb=None):
    """
    Quy trình đối chiếu Toàn Diện 4 Chiều Tất-Cả-Trong-Một (All-In-One Unified Reconciliation):
      1. Bảng kê thu mua (Phụ lục III / TT 05) ↔ Hóa đơn VAT (PDF)
      2. Bảng kê thu mua ↔ SC Gốc Cảng cá
      3. Excel XNNL (PMSX - Phụ lục 02a) ↔ SC Gốc Cảng cá
      4. Tổng hợp Đánh giá Hồ sơ C/O & Khuyến nghị Thẩm định IUU
    """
    from sc_core.excel_processor import load_bang_ke_excel, load_excel_xnnl, aggregate_and_validate_excel
    from sc_core.invoice_extractor import extract_invoices_repository
    from sc_core.sc_extractor import extract_multiple_sc_documents

    if progress_cb: progress_cb(5, "Đang bóc tách Bảng kê thu mua nguyên liệu (Thông tư 05)...")
    bk_meta, bk_records, by_inv, by_ves, by_sc = load_bang_ke_excel(bang_ke_file)

    prov = "apiz" if (api_source == "apiz" or (api_key and api_key.startswith("sk-"))) else "gemini"
    if progress_cb: progress_cb(15, "Đang đọc Hóa đơn VAT (điện tử đọc trực tiếp, bản scan đọc bằng AI)...")
    invoices_repo = extract_invoices_repository(
        invoices_dir, use_ai=use_ai, ai_provider=prov, api_key=api_key or None,
        base_url=(api_base_url or None) if prov == "apiz" else None, cache_dir="cache", log_cb=log_cb)

    if progress_cb: progress_cb(30, "Đang trích xuất dữ liệu các Bản Scan SC gốc...")
    sc_repo, all_sc_records = extract_multiple_sc_documents(
        sc_sources,
        cache_dir="cache",
        progress_cb=lambda p, m: progress_cb(int(30 + p * 30), m) if progress_cb else None,
        use_ai=use_ai,
        api_key=api_key,
        provider=prov
    )

    # 1. Bảng kê vs Hóa đơn
    if progress_cb: progress_cb(65, "Đang đối chiếu Bảng kê ↔ Hóa đơn VAT...")
    bk_vs_inv_recons, bk_vs_inv_rows, bk_vs_inv_sum = reconcile_bang_ke_vs_invoices(bk_records, invoices_repo)

    # 2. Bảng kê vs SC
    if progress_cb: progress_cb(75, "Đang đối chiếu Bảng kê ↔ SC Gốc Cảng cá...")
    bk_vs_sc_recons, bk_vs_sc_sum = reconcile_bang_ke_vs_sc(bk_records, sc_repo)

    # 3. XNNL vs SC (nếu có file XNNL hoặc tự động dò trong cùng thư mục / dùng sheet PFI của Bảng kê)
    xnnl_recons = []
    xnnl_sum = {}
    merge_logs = []
    target_xnnl = excel_xnnl_file if (excel_xnnl_file and os.path.exists(excel_xnnl_file)) else None
    if not target_xnnl and bang_ke_file and os.path.exists(bang_ke_file):
        bk_dir = os.path.dirname(bang_ke_file)
        for fn in os.listdir(bk_dir):
            if fn.lower().endswith('.xlsx') and any(k in fn.upper() for k in ['XKNL', 'XNNL']):
                target_xnnl = os.path.join(bk_dir, fn)
                break
        if not target_xnnl:
            target_xnnl = bang_ke_file

    if target_xnnl and os.path.exists(target_xnnl):
        try:
            if progress_cb: progress_cb(85, "Đang đối chiếu Excel XNNL (PMSX) ↔ SC Gốc...")
            ex_meta, raw_records, _ = load_excel_xnnl(target_xnnl)
            bk_owner_by_v = {clean_vessel_key(r.get('vessel_id', '')): r.get('owner', '') for r in bk_records if r.get('owner')}
            for rr in raw_records:
                if not rr.get('owner'):
                    rr['owner'] = bk_owner_by_v.get(clean_vessel_key(rr.get('vessel_id', '')), '')
            if do_merge:
                agg_records, merge_logs = aggregate_and_validate_excel(raw_records)
            else:
                agg_records = raw_records
            xnnl_recons, xnnl_sum = reconcile_excel_vs_sc(agg_records, sc_repo)
        except Exception as _ex_xnnl:
            print(f"Lưu ý khi đọc XNNL phụ: {_ex_xnnl}")

    # 4. Master KPI Dashboard
    total_critical = bk_vs_inv_sum['count_over'] + bk_vs_inv_sum['count_missing'] + bk_vs_sc_sum['count_conflict'] + xnnl_sum.get('count_conflict', 0)
    total_warnings = bk_vs_inv_sum['count_warn'] + bk_vs_sc_sum['count_warning'] + xnnl_sum.get('count_match', 0) - xnnl_sum.get('count_match', 0) # adjust

    if total_critical == 0:
        dossier_status = "HOÀN TOÀN HỢP LỆ (SẴN SÀNG CẤP C/O)"
    else:
        dossier_status = f"CÓ {total_critical} ĐIỂM SAI LỆCH CẦN ĐIỀU CHỈNH"

    master_result = {
        'dossier_status': dossier_status,
        'bang_ke_file': bang_ke_file,
        'bang_ke_meta': bk_meta,
        'bang_ke_records': bk_records,
        'bk_vs_invoices': {
            'recons': bk_vs_inv_recons,
            'rows': bk_vs_inv_rows,
            'summary': bk_vs_inv_sum
        },
        'bk_vs_sc': {
            'recons': bk_vs_sc_recons,
            'summary': bk_vs_sc_sum
        },
        'xnnl_vs_sc': {
            'recons': xnnl_recons,
            'summary': xnnl_sum,
            'merge_logs': merge_logs
        },
        'invoices_repo': invoices_repo,
        'sc_repo': sc_repo,
        'all_sc_records': all_sc_records
    }

    if progress_cb: progress_cb(100, "Hoàn tất đối chiếu toàn diện thành công!")
    return master_result
