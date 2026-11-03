import openpyxl
import xlrd
from datetime import datetime, date
import datetime
import re
import os

def normalize_vessel_id(s):
    if not s: return ""
    s = str(s).strip().upper()
    s = s.replace("Ð", "Đ").replace(" ", "")
    m = re.search(r'\b([A-ZĐ]{2,4}-\d+[\w\-]*)', s)
    if m:
        v = m.group(1)
        if not v.endswith("-TS") and "-TS" in v:
            v = v.split("-TS")[0] + "-TS"
        elif not v.endswith("-TS"):
            v = v + "-TS"
        return v.replace("BD-", "BĐ-")
    return s

def normalize_date_str(val):
    if not val: return ""
    if hasattr(val, 'strftime'):
        return val.strftime("%d/%m/%Y")
    s = str(val).strip().replace("'", "").replace('"', '')
    m = re.search(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})', s)
    if m:
        d, m, y = m.group(1), m.group(2), m.group(3)
        return f"{int(d):02d}/{int(m):02d}/{y}"
    # Năm 2 chữ số (vd '26/06/26' -> '26/06/2026')
    m = re.fullmatch(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2})', s)
    if m:
        return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/20{m.group(3)}"
    return s

def parse_num(val):
    """
    Phân tích số thông minh: Hỗ trợ cả định dạng Quốc tế (1,250.50) và định dạng Việt Nam (1.250,50).
    Tuyệt đối không làm mất số thập phân khi gặp dấu phẩy (như 1250,5 kg).
    """
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip().replace(" ", "").replace("'", "")
    if not s:
        return 0.0

    # Nếu có cả dấu chấm và dấu phẩy
    if "." in s and "," in s:
        last_dot = s.rfind(".")
        last_comma = s.rfind(",")
        if last_comma > last_dot:
            # Định dạng Việt Nam / Châu Âu: 1.250,50 -> bỏ chấm, đổi phẩy thành chấm
            s = s.replace(".", "").replace(",", ".")
        else:
            # Định dạng Quốc tế: 1,250.50 -> bỏ phẩy
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2, 4):
            # Dấu phẩy thập phân (ví dụ 1250,5 hoặc 12,50) -> chuyển thành chấm
            s = s.replace(",", ".")
        elif len(parts) > 2:
            # Phân tách hàng nghìn (ví dụ 1,000,000) -> bỏ phẩy
            s = s.replace(",", "")
        elif len(parts) == 2 and len(parts[1]) == 3 and parts[0] != "0":
            # Dấu phẩy hàng nghìn (ví dụ 1,250) -> bỏ phẩy
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif "." in s:
        parts = s.split(".")
        if len(parts) > 2:
            # Nhiều dấu chấm phân tách hàng nghìn (ví dụ 1.250.000) -> bỏ chấm
            s = s.replace(".", "")

    try:
        return float(s)
    except Exception:
        return 0.0

def open_excel_workbook(file_path):
    """
    Universally loads an Excel workbook (.xlsx, .xlsm, .xls).
    If file is old .xls (BIFF8/OLE2) format, uses xlrd to read and converts
    it to an openpyxl.Workbook object in memory.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

    is_xls = False
    try:
        with open(file_path, 'rb') as f:
            header = f.read(8)
            if header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
                is_xls = True
    except Exception:
        pass

    if not is_xls and not file_path.lower().endswith('.xls'):
        try:
            return openpyxl.load_workbook(file_path, data_only=True)
        except Exception:
            is_xls = True

    if is_xls or file_path.lower().endswith('.xls'):
        rb = xlrd.open_workbook(file_path)
        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # Remove default created sheet
        for sname in rb.sheet_names():
            rs = rb.sheet_by_name(sname)
            ws = wb.create_sheet(title=sname)
            for r in range(rs.nrows):
                row_vals = []
                for c in range(rs.ncols):
                    ctype = rs.cell_type(r, c)
                    val = rs.cell_value(r, c)
                    if ctype == xlrd.XL_CELL_DATE:
                        try:
                            val = datetime.datetime(*xlrd.xldate_as_tuple(val, rb.datemode))
                        except Exception:
                            pass
                    row_vals.append(val)
                ws.append(row_vals)
        return wb

def load_excel_xnnl(file_path):
    """
    Loads Excel file exported from PMSX / pm khai thác.
    Returns: (metadata, records, chu_tau_dict, format_type)
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

    wb = open_excel_workbook(file_path)
    
    # 1. Parse Sheet Chủ Tàu if exists
    chu_tau_map = {}
    for sname in wb.sheetnames:
        if 'chu' in sname.lower() or 'tau' in sname.lower():
            ws_chu = wb[sname]
            for r in range(1, ws_chu.max_row + 1):
                for c in range(1, min(10, ws_chu.max_column + 1)):
                    v = ws_chu.cell(r, c).value
                    if v and re.search(r'\b[A-ZĐa-zĐÐ]{2,4}-\d+', str(v), re.IGNORECASE) and not any(k in str(v).upper() for k in ['GPKT', 'FAO', 'SC']):
                        nv = normalize_vessel_id(v)
                        owner = ws_chu.cell(r, c+1).value or ""
                        gear = ws_chu.cell(r, c+2).value or ""
                        time_kt = ws_chu.cell(r, c+3).value or ""
                        chu_tau_map[nv] = {
                            'owner': str(owner).strip(),
                            'gear': str(gear).strip(),
                            'time_kt': str(time_kt).strip(),
                            'row': r
                        }

    # 2. Identify layout in main sheet
    ws = wb['PFI'] if 'PFI' in wb.sheetnames else wb.active
    
    is_pfi_2row = False
    for r in range(1, min(25, ws.max_row + 1)):
        for c in range(1, min(10, ws.max_column + 1)):
            v = str(ws.cell(r, c).value or '')
            if '02a' in v or 'Appendix' in v or 'Fishing vessel' in v:
                is_pfi_2row = True
                break
        if is_pfi_2row: break

    records = []
    
    if is_pfi_2row:
        format_type = "Appendix 02a (PFI 2 dòng)"
        # Find start row
        data_start_row = 22
        for r in range(10, 25):
            val2 = str(ws.cell(r, 2).value or '')
            if '(1)' in val2 or 'Số giấy' in val2:
                data_start_row = r + 1
                break
                
        r = data_start_row
        while r <= ws.max_row:
            vessel_val = ws.cell(r, 3).value
            if vessel_val and ('Tổng' in str(vessel_val) or 'Total' in str(vessel_val)):
                break
            if vessel_val and re.search(r'\b[A-ZĐa-zĐÐ]{2,4}-\d+', str(vessel_val), re.IGNORECASE) and not any(k in str(vessel_val).upper() for k in ['GPKT', 'FAO', 'SC']):
                sc_no = ws.cell(r, 2).value
                lic_no = ws.cell(r, 7).value
                area = ws.cell(r, 8).value
                species = ws.cell(r, 9).value
                landing_date = normalize_date_str(ws.cell(r, 11).value)
                catch_kg = parse_num(ws.cell(r, 12).value)
                proc_kg = parse_num(ws.cell(r, 13).value)
                exp_kg = parse_num(ws.cell(r, 14).value)
                
                # sub row
                gear = ws.cell(r+1, 3).value
                lic_exp = normalize_date_str(ws.cell(r+1, 7).value)
                catch_period = str(ws.cell(r+1, 8).value or '').strip()
                sci_name = str(ws.cell(r+1, 9).value or '').strip()
                
                v_norm = normalize_vessel_id(vessel_val)
                owner = chu_tau_map.get(v_norm, {}).get('owner', '')
                
                records.append({
                    'row_start': r,
                    'row_end': r + 1,
                    'sc_number': str(sc_no or '').strip(),
                    'vessel_id': v_norm,
                    'vessel_raw': str(vessel_val).strip(),
                    'owner': owner,
                    'gear': str(gear or 'LHP').strip(),
                    'licence_no': str(lic_no or '').strip(),
                    'licence_exp': lic_exp,
                    'catch_area': str(area or '').strip().replace('\n', ' '),
                    'catch_period': catch_period,
                    'species': str(species or '').strip(),
                    'sci_name': sci_name,
                    'landing_date': landing_date,
                    'catch_kg': catch_kg,
                    'proc_kg': proc_kg,
                    'exp_kg': exp_kg,
                })
                r += 2
                while r <= ws.max_row and not ws.cell(r, 3).value:
                    r += 1
            else:
                r += 1
    else:
        format_type = "Bảng phẳng (Flat Table)"
        # Try to find header columns
        header_row = 1
        col_map = {}
        for r in range(1, min(10, ws.max_row + 1)):
            row_vals = [str(ws.cell(r, c).value or '').lower() for c in range(1, ws.max_column + 1)]
            for c_idx, val in enumerate(row_vals, 1):
                if 'đăng ký' in val or 'số tàu' in val or 'vessel' in val:
                    col_map['vessel'] = c_idx
                elif 'giấy phép' in val or 'licence' in val:
                    col_map['licence'] = c_idx
                elif 'hạn' in val or 'cấp phép' in val:
                    col_map['lic_exp'] = c_idx
                elif 'thời gian' in val or 'period' in val:
                    col_map['catch_period'] = c_idx
                elif 'vùng' in val or 'area' in val:
                    col_map['catch_area'] = c_idx
                elif 'loài' in val or 'species' in val:
                    col_map['species'] = c_idx
                elif 'ngày lên' in val or 'landing' in val or 'bốc dỡ' in val:
                    col_map['landing_date'] = c_idx
                elif 'khối lượng' in val or 'sản lượng' in val or 'catch' in val:
                    col_map['catch_kg'] = c_idx
                elif 'xác nhận' in val or 'sc' in val:
                    col_map['sc_no'] = c_idx
            if 'vessel' in col_map:
                header_row = r
                break
                
        for r in range(header_row + 1, ws.max_row + 1):
            v_val = ws.cell(r, col_map.get('vessel', 2)).value
            if v_val and re.search(r'\b[A-ZĐa-zĐÐ]{2,4}-\d+', str(v_val), re.IGNORECASE) and not any(k in str(v_val).upper() for k in ['GPKT', 'FAO', 'SC']):
                v_norm = normalize_vessel_id(v_val)
                records.append({
                    'row_start': r,
                    'row_end': r,
                    'sc_number': str(ws.cell(r, col_map.get('sc_no', 1)).value or '').strip(),
                    'vessel_id': v_norm,
                    'vessel_raw': str(v_val).strip(),
                    'owner': chu_tau_map.get(v_norm, {}).get('owner', ''),
                    'gear': 'LHP',
                    'licence_no': str(ws.cell(r, col_map.get('licence', 3)).value or '').strip(),
                    'licence_exp': normalize_date_str(ws.cell(r, col_map.get('lic_exp', 4)).value),
                    'catch_area': str(ws.cell(r, col_map.get('catch_area', 5)).value or '').strip(),
                    'catch_period': str(ws.cell(r, col_map.get('catch_period', 6)).value or '').strip(),
                    'species': str(ws.cell(r, col_map.get('species', 7)).value or '').strip(),
                    'sci_name': '',
                    'landing_date': normalize_date_str(ws.cell(r, col_map.get('landing_date', 8)).value),
                    'catch_kg': parse_num(ws.cell(r, col_map.get('catch_kg', 9)).value),
                    'proc_kg': parse_num(ws.cell(r, col_map.get('catch_kg', 9)).value),
                    'exp_kg': parse_num(ws.cell(r, col_map.get('catch_kg', 9)).value) * 0.6,
                })

    metadata = {
        'file_name': os.path.basename(file_path),
        'format_type': format_type,
        'total_raw_rows': len(records),
        'total_raw_catch_kg': sum(r['catch_kg'] for r in records),
        'has_chu_tau_sheet': bool(chu_tau_map)
    }

    return metadata, records, chu_tau_map

def aggregate_and_validate_excel(records):
    """
    Business Rules:
    1. Kiểm tra dữ liệu thiếu (Missing fields).
    2. Gộp lượng nếu cùng 1 tàu + cùng 1 ngày lên cá/đánh bắt + cùng 1 Giấy SC (Group by vessel + landing_date + species + sc_number).
    3. Kiểm tra logic ngày tháng (Thời gian đánh bắt <= Ngày lên cá, Thời gian đánh bắt <= Hạn phép).
    """
    grouped = {}
    for r in records:
        sc_clean = str(r.get('sc_number', '')).strip().upper()
        key = (r['vessel_id'], r['landing_date'], r['species'], sc_clean)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(r)

    aggregated_records = []
    aggregation_logs = []

    for key, items in grouped.items():
        v_id, l_date, sp, sc_no = key
        if len(items) == 1:
            item = dict(items[0])
            item['is_merged'] = False
            item['merged_details'] = []
            aggregated_records.append(item)
        else:
            # Tiến hành gộp lượng
            base = dict(items[0])
            sum_catch = sum(i['catch_kg'] for i in items)
            sum_proc = sum(i['proc_kg'] for i in items)
            sum_exp = sum(i['exp_kg'] for i in items)
            
            base['is_merged'] = True
            base['merged_count'] = len(items)
            base['catch_kg'] = sum_catch
            base['proc_kg'] = sum_proc
            base['exp_kg'] = sum_exp
            base['merged_original_rows'] = [i['row_start'] for i in items]
            
            log_entry = {
                'vessel_id': v_id,
                'sc_number': sc_no,
                'landing_date': l_date,
                'species': sp,
                'merged_count': len(items),
                'weights': [i['catch_kg'] for i in items],
                'sum_weight': sum_catch
            }
            aggregation_logs.append(log_entry)
            aggregated_records.append(base)

    # Perform validation checks on aggregated records
    for r in aggregated_records:
        warnings = []
        errors = []
        
        # Missing data checks
        if not r['vessel_id']: errors.append("Thiếu số đăng ký tàu")
        if not r['licence_no']: errors.append("Thiếu số giấy phép khai thác")
        if not r['licence_exp']: errors.append("Thiếu ngày hết hạn giấy phép")
        if not r['landing_date']: errors.append("Thiếu ngày lên cá")
        if r['catch_kg'] <= 0: errors.append("Khối lượng khai thác không hợp lệ (<= 0)")
        if not r['species']: errors.append("Thiếu tên loài thủy sản")
        if not r['owner']: warnings.append("Chưa có thông tin chủ tàu trong phụ lục")

        # Temporal logic checks
        # Catch period vs landing date
        m_period = re.search(r'(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})', r['catch_period'])
        if m_period and r['landing_date']:
            try:
                d_start = datetime.strptime(m_period.group(1), "%d/%m/%Y")
                d_end = datetime.strptime(m_period.group(2), "%d/%m/%Y")
                d_land = datetime.strptime(r['landing_date'], "%d/%m/%Y")
                
                if d_start > d_end:
                    errors.append("Ngày bắt đầu khai thác lớn hơn ngày kết thúc")
                if d_end > d_land:
                    errors.append(f"Ngày kết thúc KT ({m_period.group(2)}) sau ngày lên cá ({r['landing_date']})")
                    
                if r['licence_exp']:
                    d_exp = datetime.strptime(r['licence_exp'], "%d/%m/%Y")
                    if d_end > d_exp:
                        errors.append(f"Chuyến biển KT vượt quá hạn giấy phép ({r['licence_exp']})")
            except Exception as e:
                warnings.append(f"Lỗi định dạng ngày khi kiểm tra logic: {e}")

        r['validation_errors'] = errors
        r['validation_warnings'] = warnings

    return aggregated_records, aggregation_logs


def _num_token(v):
    """'-5' / '(12)' / -5 -> 5 ; còn lại -> None. (Số dương thuần không tính để tránh nhầm với dòng dữ liệu.)"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(-v) if v < 0 and float(v).is_integer() and -v <= 20 else None
    s = str(v).strip()
    m = re.fullmatch(r'\(\s*(\d{1,2})\s*\)|-\s*(\d{1,2})', s)
    if not m:
        return None
    return int(m.group(1) or m.group(2))


def _next_value(ws, r, c, span=3):
    """Giá trị đầu tiên khác rỗng trong `span` ô bên phải (ô nhãn và ô giá trị có thể cách nhau ô trống/gộp)."""
    for cc in range(c + 1, min(c + span, ws.max_column) + 1):
        v = ws.cell(r, cc).value
        if v is not None and str(v).strip() != '':
            return v
    return None


def _find_numbering_row(ws, max_scan=45):
    """Tìm dòng đánh số cột (1)...(14) của Bảng kê. Trả về (số dòng, {số thứ tự cột: chỉ số cột Excel})."""
    for r in range(1, min(max_scan, ws.max_row) + 1):
        found = {}
        for c in range(1, min(30, ws.max_column) + 1):
            k = _num_token(ws.cell(r, c).value)
            if k is not None and k not in found:
                found[k] = c
        needed = {1, 2, 3, 5, 6, 7, 10, 11, 12, 13}
        if not needed.issubset(found):
            continue
        ks = sorted(k for k in found if k <= 14)
        if all(found[a] < found[b] for a, b in zip(ks, ks[1:])):  # cột tăng dần theo số thứ tự
            return r, found
    return None, {}


def load_bang_ke_excel(file_path):
    """
    Bóc tách Bảng kê thu mua nguyên liệu theo Thông tư 05/2018/TT-BCT (Phụ lục III - Tiêu chí WO).
    Hỗ trợ tự động nhận diện Sheet, quét tiêu đề động và gom nhóm dữ liệu theo Hóa đơn, Tàu cá, và SC.
    Returns:
      - meta: Thông tin chung tờ khai (Doanh nghiệp, MST, TKHQ, Tên hàng, HS, Khối lượng xuất, FOB)
      - records: Danh sách các dòng chi tiết nguyên liệu
      - by_invoice: Dict gom nhóm theo Số Hóa đơn GTGT
      - by_vessel: Dict gom nhóm theo Số hiệu tàu cá
      - by_sc: Dict gom nhóm theo Số giấy xác nhận SC
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Không tìm thấy file Bảng kê: {file_path}")

    wb = open_excel_workbook(file_path)

    # 1. Tìm Sheet Bảng Kê
    ws = None
    target_sheet_name = ""
    for sname in wb.sheetnames:
        s_low = sname.lower()
        if any(k in s_low for k in ['tv', 'bangke', 'bang ke', 'bảng kê', 'wo', 'phụ lục iii', 'phu luc iii', 'tt05']):
            ws = wb[sname]
            target_sheet_name = sname
            break

    if ws is None:
        # Quét nội dung các sheet
        for sname in wb.sheetnames:
            candidate_ws = wb[sname]
            found = False
            for r in range(1, min(12, candidate_ws.max_row + 1)):
                for c in range(1, min(10, candidate_ws.max_column + 1)):
                    val = str(candidate_ws.cell(r, c).value or '').upper()
                    if 'THÔNG TƯ SỐ 05' in val or 'TIÊU CHÍ "WO"' in val or 'BẢNG KÊ KHAI' in val or 'PHỤ LỤC III' in val:
                        ws = candidate_ws
                        target_sheet_name = sname
                        found = True
                        break
                if found:
                    break
            if ws:
                break

    if ws is None:
        ws = wb.active
        target_sheet_name = wb.sheetnames[0]

    # 2. Bóc tách Metadata (Thông tin chung)
    meta = {
        'sheet_name': target_sheet_name,
        'trader_name': '',
        'trader_mst': '',
        'customs_declaration': '',
        'goods_name': '',
        'hs_code': '',
        'export_qty': 0.0,
        'fob_val': 0.0,
        'fob_unit': 'USD',
        'criterion': 'WO'
    }

    for r in range(1, min(15, ws.max_row + 1)):
        for c in range(1, min(15, ws.max_column + 1)):
            v = str(ws.cell(r, c).value or '').strip()
            v_low = v.lower()
            if 'tên thương nhân' in v_low:
                if ':' in v:
                    meta['trader_name'] = v.split(':', 1)[1].strip()
                elif c + 1 <= ws.max_column and ws.cell(r, c + 1).value:
                    meta['trader_name'] = str(ws.cell(r, c + 1).value).strip()
            elif 'mã số thuế' in v_low:
                if ':' in v:
                    meta['trader_mst'] = v.split(':', 1)[1].strip()
                elif c + 1 <= ws.max_column and ws.cell(r, c + 1).value:
                    meta['trader_mst'] = str(ws.cell(r, c + 1).value).strip()
            elif 'tkhq' in v_low or 'tờ khai' in v_low:
                if ':' in v:
                    meta['customs_declaration'] = v.split(':', 1)[1].strip()
                elif c + 1 <= ws.max_column and ws.cell(r, c + 1).value:
                    meta['customs_declaration'] = str(ws.cell(r, c + 1).value).strip()
            elif 'tên hàng hóa' in v_low:
                if ':' in v:
                    meta['goods_name'] = v.split(':', 1)[1].strip()
                elif c + 1 <= ws.max_column and ws.cell(r, c + 1).value:
                    meta['goods_name'] = str(ws.cell(r, c + 1).value).strip()
            elif 'mã hs của hàng hóa' in v_low:
                m_hs = re.search(r'(\d{4,8})', v.split(':', 1)[-1])
                if m_hs:
                    meta['hs_code'] = m_hs.group(1)
                else:
                    nxt = _next_value(ws, r, c)
                    if nxt is not None and re.search(r'\d{4,8}', str(nxt)):
                        meta['hs_code'] = str(nxt).strip()
            elif 'số lượng (kg)' in v_low or 'số lượng:' in v_low:
                nxt = _next_value(ws, r, c)
                if nxt is not None:
                    meta['export_qty'] = parse_num(nxt)
            elif 'trị giá (fob)' in v_low or 'trị giá fob' in v_low:
                nxt = _next_value(ws, r, c)
                if nxt is not None:
                    meta['fob_val'] = parse_num(nxt)

    # 3. Nhận diện các cột dữ liệu
    col_map = {
        'stt': 2,
        'material': 3,
        'spec': 4,
        'hs': 5,
        'origin': 6,
        'qty': 7,
        'price': 8,
        'amount': 9,
        'supplier': 10,
        'address': 11,
        'hd_no': 12,
        'hd_date': 14,
        'sc_no': 15,
        'vessel': 16,
        'owner': 17,
        'tp_qty': 18,
        'norm': 19
    }

    header_row = 16
    # 3a. Cách chắc chắn nhất: dò DÒNG ĐÁNH SỐ CỘT theo mẫu Thông tư (-1, -2, ... hoặc (1), (2), ... (14)).
    #     Dùng được cho mọi biến thể: bảng bắt đầu ở cột A hay B, có/không có cột Size, ô HĐ gộp/tách...
    num_row, num_cols = _find_numbering_row(ws)
    if num_row:
        header_row = num_row
        nc = num_cols
        col_map.update({
            'stt': nc[1], 'material': nc[2], 'hs': nc[3], 'origin': nc[4], 'qty': nc[5],
            'price': nc[6], 'amount': nc[7], 'supplier': nc[8], 'address': nc[9],
            'hd_no': nc[10], 'hd_date': nc[11], 'sc_no': nc[12], 'vessel': nc[13],
        })
        col_map['owner'] = nc.get(14, nc[13] + 1)
        # Cột Size/quy cách (không đánh số) nằm giữa (2) Tên NL và (3) Mã HS nếu có
        col_map['spec'] = nc[2] + 1 if nc[3] - nc[2] > 1 else None
        col_map['tp_qty'] = col_map['owner'] + 1
        col_map['norm'] = col_map['owner'] + 2

    # 3b. Dự phòng: dò theo chữ tiêu đề (mẫu cũ)
    for r in ([] if num_row else range(1, min(40, ws.max_row + 1))):
        row_txt = " ".join([str(ws.cell(r, c).value or '') for c in range(1, min(25, ws.max_column + 1))]).lower()
        if 'đơn giá' in row_txt and 'số lượng' in row_txt and 'hóa đơn' in row_txt:
            header_row = r
            for c in range(1, min(25, ws.max_column + 1)):
                c_val = str(ws.cell(r, c).value or '').lower()
                c_above = str(ws.cell(r - 1, c).value or '').lower() if r > 1 else ''
                c_above2 = str(ws.cell(r - 2, c).value or '').lower() if r > 2 else ''
                combined = f"{c_above2} {c_above} {c_val}"

                if ('stt' in combined or c_val == '-1') and 'hóa đơn' not in combined:
                    col_map['stt'] = c
                elif ('tên nguyên liệu' in combined or c_val == '-2') and 'hóa đơn' not in combined:
                    col_map['material'] = c
                elif 'mã hs' in combined and 'hóa đơn' not in combined:
                    col_map['hs'] = c
                elif ('số lượng' in combined and ('kgs' in combined or 'kg' in combined or c_val == '-5')) and 'hóa đơn' not in combined:
                    col_map['qty'] = c
                elif (('đơn giá' in combined and 'hóa đơn' not in combined) or c_val == '-6'):
                    col_map['price'] = c
                elif (('tổng trị giá' in combined or 'trị giá (vnđ)' in combined) and 'hóa đơn' not in combined) or c_val == '-7':
                    col_map['amount'] = c
                elif (('nhà sản xuất' in combined or 'tên' in c_val) and ('cung cấp' in combined or c_val == '-8')) and 'hóa đơn' not in combined:
                    col_map['supplier'] = c
                elif ('địa chỉ' in combined or c_val == '-9') and 'hóa đơn' not in combined:
                    col_map['address'] = c
                elif ('số' in c_val or c_val == '-10') and ('hóa đơn' in combined or 'giá trị gia tăng' in combined):
                    col_map['hd_no'] = c
                elif ('ngày' in c_val or c_val == '-11') and ('hóa đơn' in combined or 'giá trị gia tăng' in combined or 'ngày' in c_val):
                    col_map['hd_date'] = c
                elif 'số giấy xác nhận' in combined or 'số giấy' in combined or c_val == '-12':
                    col_map['sc_no'] = c
                elif 'số đăng ký' in combined or 'nghề khai thác' in combined or c_val == '-13':
                    col_map['vessel'] = c
                elif 'chủ tàu' in combined or 'thuyền trưởng' in combined or c_val == '-14':
                    col_map['owner'] = c
            break

    # 4. Trích xuất từng dòng dữ liệu
    records = []
    data_start_row = header_row + 1
    for r in range(data_start_row, ws.max_row + 1):
        stt_val = ws.cell(r, col_map['stt']).value
        if stt_val is None or not str(stt_val).strip().isdigit():
            c_check = " ".join([str(ws.cell(r, c).value or '') for c in range(1, 10)]).lower()
            if 'tổng' in c_check or 'total' in c_check:
                break
            continue

        stt = int(stt_val)
        material = str(ws.cell(r, col_map['material']).value or '').strip()
        spec = str(ws.cell(r, col_map['spec']).value or '').strip() if col_map.get('spec') else ''
        hs = str(ws.cell(r, col_map['hs']).value or '').strip()
        origin = str(ws.cell(r, col_map['origin']).value or '').strip()
        qty = parse_num(ws.cell(r, col_map['qty']).value)
        price = parse_num(ws.cell(r, col_map['price']).value)
        amount = parse_num(ws.cell(r, col_map['amount']).value)
        supplier = str(ws.cell(r, col_map['supplier']).value or '').strip()
        address = str(ws.cell(r, col_map['address']).value or '').strip()
        
        hd_raw = str(ws.cell(r, col_map['hd_no']).value or '').strip()
        hd_clean = hd_raw.lstrip('0') if hd_raw.isdigit() else hd_raw
        if not hd_clean and hd_raw:
            hd_clean = "0"
            
        hd_date = normalize_date_str(ws.cell(r, col_map['hd_date']).value)
        sc_no = str(ws.cell(r, col_map['sc_no']).value or '').strip()
        vessel_raw = str(ws.cell(r, col_map['vessel']).value or '').strip()
        vessel_norm = normalize_vessel_id(vessel_raw)
        owner = str(ws.cell(r, col_map['owner']).value or '').strip()
        
        tp_qty = parse_num(ws.cell(r, col_map.get('tp_qty', 18)).value)
        norm = parse_num(ws.cell(r, col_map.get('norm', 19)).value)

        rec = {
            'row_idx': r,
            'stt': stt,
            'material': material,
            'spec': spec,
            'hs': hs,
            'origin': origin,
            'qty': qty,
            'price': price,
            'amount': amount,
            'supplier': supplier,
            'address': address,
            'hd_no': hd_clean,
            'hd_no_raw': hd_raw,
            'hd_date': hd_date,
            'sc_no': sc_no,
            'vessel_id': vessel_norm,
            'vessel_raw': vessel_raw,
            'owner': owner,
            'tp_qty': tp_qty,
            'norm': norm
        }
        records.append(rec)

    from collections import defaultdict
    by_invoice = defaultdict(list)
    by_vessel = defaultdict(list)
    by_sc = defaultdict(list)

    for rec in records:
        by_invoice[rec['hd_no']].append(rec)
        by_vessel[rec['vessel_id']].append(rec)
        by_sc[rec['sc_no']].append(rec)

    return meta, records, dict(by_invoice), dict(by_vessel), dict(by_sc)
