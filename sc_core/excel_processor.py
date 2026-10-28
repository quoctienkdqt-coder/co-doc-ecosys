import openpyxl
import xlrd
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
    m = re.search(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', s)
    if m:
        d, m, y = m.group(1), m.group(2), m.group(3)
        return f"{int(d):02d}/{int(m):02d}/{y}"
    return s

def parse_num(val):
    if val is None: return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(' ', '').replace(',', '')
    try:
        return float(s)
    except:
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
