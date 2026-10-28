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
    s = strip_vietnamese_accents(s)
    return re.sub(r'[^a-z0-9]', '', s)

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
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        ex_date = rec.get('landing_date', '')
        ex_kg = rec.get('catch_kg', 0.0)
        date_matches = [c for c in candidates if c.get('landing_date') == ex_date]
        if date_matches:
            with_req = [c for c in date_matches if (c.get('req_catch_kg') or 0) > 0]
            if with_req:
                return min(with_req, key=lambda c: abs((c.get('req_catch_kg') or 0) - ex_kg))
            return date_matches[0]
        with_req_all = [c for c in candidates if (c.get('req_catch_kg') or 0) > 0]
        if with_req_all:
            return min(with_req_all, key=lambda c: abs((c.get('req_catch_kg') or 0) - ex_kg))
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
