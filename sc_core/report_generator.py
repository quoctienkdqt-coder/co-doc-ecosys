import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import os
import shutil

# Color palette for modern reporting
HEADER_FILL = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid") # Dark Navy
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

SUCCESS_FILL = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid") # Light Green
SUCCESS_FONT = Font(name="Calibri", size=10, bold=True, color="276A3C")

DANGER_FILL = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid") # Light Red/Peach
DANGER_FONT = Font(name="Calibri", size=10, bold=True, color="C00000")

WARN_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid") # Light Yellow
WARN_FONT = Font(name="Calibri", size=10, bold=True, color="B25900")

INFO_FILL = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid") # Light Blue
INFO_FONT = Font(name="Calibri", size=10, bold=True, color="1F497D")

DIFF_CELL_FILL = PatternFill(start_color="F8CBAD", end_color="F8CBAD", fill_type="solid") # Soft Orange-Red
DIFF_CELL_FONT = Font(name="Calibri", size=10, bold=True, color="9C0006")

BORDER_THIN = Border(
    left=Side(style='thin', color='D9D9D9'),
    right=Side(style='thin', color='D9D9D9'),
    top=Side(style='thin', color='D9D9D9'),
    bottom=Side(style='thin', color='D9D9D9')
)

def create_reconciliation_excel_report(output_path, recon_results, summary_stats, aggregation_logs, sc_records, sc_info=None):
    wb = openpyxl.Workbook()
    # Sheet 1: Bang Doi Chieu Sai Khac
    ws1 = wb.active
    ws1.title = "Bảng Đối Chiếu Sai Khác"
    ws1.views.sheetView[0].showGridLines = True

    # Title Block
    ws1.merge_cells("A1:K1")
    title_cell = ws1["A1"]
    title_cell.value = "BÁO CÁO ĐỐI CHIẾU DỮ LIỆU XÁC NHẬN NGUYÊN LIỆU (XNNL) VỚI SC GỐC CẢNG CÁ"
    title_cell.font = Font(name="Calibri", size=15, bold=True, color="1F497D")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[1].height = 35

    ws1.merge_cells("A2:K2")
    sub_cell = ws1["A2"]
    sc_num = sc_info.get('sc_number', '00180/2026/SC-GL-TQ') if sc_info else 'SC Cảng cá'
    sub_cell.value = f"Căn cứ so sánh: Giấy xác nhận SC gốc số: {sc_num} | Kiểm tra tự động tính toàn vẹn dữ liệu IUU"
    sub_cell.font = Font(name="Calibri", size=11, italic=True, color="595959")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[2].height = 20

    # Summary KPI Cards
    ws1["A4"] = "TỔNG TÀU EXCEL"
    ws1["A5"] = summary_stats['total_excel_vessels']
    ws1["C4"] = "KHỚP HOÀN TOÀN"
    ws1["C5"] = summary_stats['count_match']
    ws1["E4"] = "SAI LỆCH CẦN SỬA"
    ws1["E5"] = summary_stats['count_conflict']
    ws1["G4"] = "SỐ TÀU ĐÃ GỘP LƯỢNG"
    ws1["G5"] = summary_stats['count_merged']
    ws1["I4"] = "TỔNG TÀU SC GỐC"
    ws1["I5"] = summary_stats['total_sc_vessels']

    card_positions = [("A4", "A5", INFO_FILL, INFO_FONT),
                      ("C4", "C5", SUCCESS_FILL, SUCCESS_FONT),
                      ("E4", "E5", DANGER_FILL, DANGER_FONT),
                      ("G4", "G5", WARN_FILL, WARN_FONT),
                      ("I4", "I5", INFO_FILL, INFO_FONT)]

    for label_pos, val_pos, fill, font in card_positions:
        c_label = ws1[label_pos]
        c_label.font = Font(name="Calibri", size=9, bold=True, color="595959")
        c_label.alignment = Alignment(horizontal="center", vertical="center")
        c_val = ws1[val_pos]
        c_val.font = Font(name="Calibri", size=16, bold=True, color=font.color.rgb)
        c_val.fill = fill
        c_val.alignment = Alignment(horizontal="center", vertical="center")
        c_val.border = BORDER_THIN

    ws1.row_dimensions[4].height = 18
    ws1.row_dimensions[5].height = 28

    # Table Header at Row 7
    headers = [
        "STT",
        "Số ĐK Tàu",
        "Số Giấy SC",
        "Trạng Thái",
        "Gộp Lượng?",
        "Tên Chủ Tàu (Excel / SC)",
        "Số Giấy Phép KTTS (Excel / SC)",
        "Hạn GP (Excel / SC)",
        "Thời Gian KT (Excel / SC)",
        "Ngày Lên Cá (Excel / SC)",
        "Khối Lượng Mua (Excel / SC / Lệch)",
        "Hành Động Khắc Phục Đề Xuất"
    ]

    for col_idx, h in enumerate(headers, 1):
        cell = ws1.cell(7, col_idx, h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER_THIN
    ws1.row_dimensions[7].height = 32

    # Fill Table Data
    current_row = 8
    for idx, r in enumerate(recon_results, 1):
        ws1.row_dimensions[current_row].height = 36
        
        # STT
        c1 = ws1.cell(current_row, 1, idx)
        c1.alignment = Alignment(horizontal="center", vertical="center")
        c1.border = BORDER_THIN
        
        # Số ĐK tàu
        c2 = ws1.cell(current_row, 2, r['vessel_id'])
        c2.font = Font(name="Calibri", size=10, bold=True)
        c2.alignment = Alignment(horizontal="center", vertical="center")
        c2.border = BORDER_THIN

        # Số Giấy SC
        c_sc = ws1.cell(current_row, 3, r.get('sc_number', ''))
        c_sc.alignment = Alignment(horizontal="center", vertical="center")
        c_sc.border = BORDER_THIN
        c_sc.font = Font(name="Calibri", size=9.5, italic=True)
        
        # Trạng thái
        c3 = ws1.cell(current_row, 4)
        c3.alignment = Alignment(horizontal="center", vertical="center")
        c3.border = BORDER_THIN
        if r['status'] == 'MATCH':
            c3.value = "🟢 Khớp 100%"
            c3.fill = SUCCESS_FILL
            c3.font = SUCCESS_FONT
        elif r['status'] == 'WARNING':
            c3.value = "🟡 Cảnh báo"
            c3.fill = WARN_FILL
            c3.font = WARN_FONT
        elif r['status'] == 'CONFLICT':
            c3.value = "🔴 Sai lệch"
            c3.fill = DANGER_FILL
            c3.font = DANGER_FONT
        else:
            c3.value = "⚠️ Ngoài SC"
            c3.fill = DANGER_FILL
            c3.font = DANGER_FONT

        # Gộp lượng
        c4 = ws1.cell(current_row, 5)
        c4.alignment = Alignment(horizontal="center", vertical="center")
        c4.border = BORDER_THIN
        if r['is_merged']:
            c4.value = f"Đã gộp {r['merged_count']} dòng"
            c4.fill = WARN_FILL
            c4.font = WARN_FONT
        else:
            c4.value = "1 dòng"
            c4.font = Font(name="Calibri", size=10, color="595959")

        ex = r['excel_data']
        sc = r['sc_data'] or {}

        # Chủ tàu
        c5 = ws1.cell(current_row, 6)
        c5.border = BORDER_THIN
        c5.alignment = Alignment(vertical="center", wrap_text=True)
        ex_owner = ex.get('owner', '')
        sc_owner = sc.get('owner', '-')
        c5.value = f"Excel: {ex_owner}\nSC gốc: {sc_owner}"
        if any(d['field'] == 'Tên Chủ tàu / Thuyền trưởng' and d['type'] == 'CRITICAL' for d in r['diffs']):
            c5.fill = DIFF_CELL_FILL
            c5.font = DIFF_CELL_FONT

        # Số GPKTTS
        c6 = ws1.cell(current_row, 7)
        c6.border = BORDER_THIN
        c6.alignment = Alignment(vertical="center", wrap_text=True)
        c6.value = f"Excel: {ex.get('licence_no','')}\nSC gốc: {sc.get('licence_no','-')}"
        if any(d['field'] == 'Số Giấy phép KTTS' and d['type'] == 'CRITICAL' for d in r['diffs']):
            c6.fill = DIFF_CELL_FILL
            c6.font = DIFF_CELL_FONT

        # Hạn GP
        c7 = ws1.cell(current_row, 8)
        c7.border = BORDER_THIN
        c7.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c7.value = f"Excel: {ex.get('licence_exp','')}\nSC: {sc.get('licence_exp','-')}"
        if any(d['field'] == 'Hạn Giấy phép KTTS' for d in r['diffs']):
            c7.fill = DIFF_CELL_FILL
            c7.font = DIFF_CELL_FONT

        # Thời gian KT
        c8 = ws1.cell(current_row, 9)
        c8.border = BORDER_THIN
        c8.alignment = Alignment(vertical="center", wrap_text=True)
        c8.value = f"Excel: {ex.get('catch_period','')}\nSC: {sc.get('catch_period','-')}"
        if any(d['field'] == 'Thời gian khai thác' for d in r['diffs']):
            c8.fill = DIFF_CELL_FILL
            c8.font = DIFF_CELL_FONT

        # Ngày lên cá
        c9 = ws1.cell(current_row, 10)
        c9.border = BORDER_THIN
        c9.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c9.value = f"Excel: {ex.get('landing_date','')}\nSC: {sc.get('landing_date','-')}"
        if any(d['field'] == 'Ngày lên cá / bốc dỡ' for d in r['diffs']):
            c9.fill = DIFF_CELL_FILL
            c9.font = DIFF_CELL_FONT

        # Khối lượng
        c10 = ws1.cell(current_row, 11)
        c10.border = BORDER_THIN
        c10.alignment = Alignment(vertical="center", wrap_text=True)
        ex_kg = ex.get('catch_kg', 0)
        sc_kg = sc.get('req_catch_kg') if sc.get('req_catch_kg') is not None else sc.get('total_catch_kg', 0)
        delta = ex_kg - sc_kg
        delta_str = f" (Lệch: {delta:+.1f} kg)" if abs(delta) > 0.1 else " (Khớp)"
        c10.value = f"Excel: {ex_kg:,.1f} kg\nSC: {sc_kg:,.1f} kg{delta_str}"
        if abs(delta) > 0.1:
            c10.fill = DIFF_CELL_FILL
            c10.font = DIFF_CELL_FONT

        # Đề xuất hành động
        c11 = ws1.cell(current_row, 12)
        c11.border = BORDER_THIN
        c11.alignment = Alignment(vertical="center", wrap_text=True)
        if r['action_needed']:
            c11.value = " • " + "\n • ".join(r['action_needed'])
            c11.font = Font(name="Calibri", size=9.5, color="C00000", bold=True)
        else:
            c11.value = "Dữ liệu hợp lệ, không cần chỉnh sửa."
            c11.font = Font(name="Calibri", size=9.5, color="276A3C")

        current_row += 1

    # Adjust Column Widths
    col_widths = {
        1: 6, 2: 15, 3: 22, 4: 15, 5: 15, 6: 28, 7: 26, 8: 16, 9: 25, 10: 16, 11: 24, 12: 36
    }
    for c_idx, w in col_widths.items():
        ws1.column_dimensions[get_column_letter(c_idx)].width = w

    # Sheet 2: Danh Sách Gộp Lượng (Aggregation details)
    ws2 = wb.create_sheet("Tàu Đã Gộp Lượng")
    ws2.views.sheetView[0].showGridLines = True
    ws2.merge_cells("A1:F1")
    ws2["A1"] = "DANH SÁCH CÁC TÀU ĐƯỢC TỰ ĐỘNG GỘP LƯỢNG (CÙNG NGÀY LÊN CÁ)"
    ws2["A1"].font = Font(name="Calibri", size=13, bold=True, color="1F497D")
    ws2.row_dimensions[1].height = 30
    
    headers_s2 = ["STT", "Số ĐK Tàu", "Ngày Lên Cá", "Tên Loài", "Số Dòng Gộp", "Khối Lượng Thành Phần", "Tổng Lượng Sau Gộp (kg)"]
    for c_idx, h in enumerate(headers_s2, 1):
        cell = ws2.cell(3, c_idx, h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER_THIN
    ws2.row_dimensions[3].height = 25

    if aggregation_logs:
        r_s2 = 4
        for idx, item in enumerate(aggregation_logs, 1):
            ws2.cell(r_s2, 1, idx).alignment = Alignment(horizontal="center")
            ws2.cell(r_s2, 2, item['vessel_id']).font = Font(bold=True)
            ws2.cell(r_s2, 3, item['landing_date']).alignment = Alignment(horizontal="center")
            ws2.cell(r_s2, 4, item['species'])
            ws2.cell(r_s2, 5, item['merged_count']).alignment = Alignment(horizontal="center")
            ws2.cell(r_s2, 6, " + ".join(f"{w:,.1f}" for w in item['weights']))
            ws2.cell(r_s2, 7, f"{item['sum_weight']:,.1f}").font = Font(bold=True, color="276A3C")
            for c in range(1, 8):
                ws2.cell(r_s2, c).border = BORDER_THIN
            r_s2 += 1
    else:
        ws2.merge_cells("A4:G4")
        ws2["A4"] = "Không có tàu nào trùng ngày lên cá cần gộp lượng trong đợt này."
        ws2["A4"].alignment = Alignment(horizontal="center", vertical="center")
        ws2["A4"].font = Font(italic=True, color="595959")

    # Sheet 3: Dữ Liệu SC Gốc (Full SC records for reference)
    ws3 = wb.create_sheet("Toàn Bộ SC Gốc (Cảng cá)")
    ws3.views.sheetView[0].showGridLines = True
    ws3.merge_cells("A1:J1")
    ws3["A1"] = f"DANH MỤC TOÀN BỘ TÀU TRONG GIẤY XÁC NHẬN SC: {sc_num}"
    ws3["A1"].font = Font(name="Calibri", size=13, bold=True, color="1F497D")
    ws3.row_dimensions[1].height = 30

    headers_s3 = [
        "STT", "Số ĐK Tàu", "Họ Tên Chủ Tàu", "Số GPKTTS", "Hạn Giấy Phép",
        "Vùng & Thời Gian KT", "Ngày Bốc Dỡ", "Tên Loài Thủy Sản",
        "KL Mua từ Tàu (kg)", "Tổng KL Khai Thác (kg)"
    ]
    for c_idx, h in enumerate(headers_s3, 1):
        cell = ws3.cell(3, c_idx, h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER_THIN
    ws3.row_dimensions[3].height = 28

    for idx, sc in enumerate(sc_records, 1):
        r_s3 = 3 + idx
        ws3.row_dimensions[r_s3].height = 20
        ws3.cell(r_s3, 1, idx).alignment = Alignment(horizontal="center", vertical="center")
        ws3.cell(r_s3, 2, sc['vessel_id']).font = Font(bold=True)
        ws3.cell(r_s3, 2).alignment = Alignment(horizontal="center", vertical="center")
        ws3.cell(r_s3, 3, sc['owner']).alignment = Alignment(vertical="center")
        ws3.cell(r_s3, 4, sc['licence_no']).alignment = Alignment(vertical="center")
        ws3.cell(r_s3, 5, sc['licence_exp']).alignment = Alignment(horizontal="center", vertical="center")
        ws3.cell(r_s3, 6, f"{sc['catch_area']} {sc['catch_period']}").alignment = Alignment(vertical="center")
        ws3.cell(r_s3, 7, sc['landing_date']).alignment = Alignment(horizontal="center", vertical="center")
        ws3.cell(r_s3, 8, sc.get('species', '')).alignment = Alignment(vertical="center")

        req_val = float(sc.get('req_catch_kg') if sc.get('req_catch_kg') is not None else 0.0)
        tot_val = float(sc.get('total_catch_kg') or req_val or 0.0)

        c_req = ws3.cell(r_s3, 9, req_val)
        c_req.number_format = '#,##0.0'
        c_req.alignment = Alignment(horizontal="right", vertical="center")

        c_tot = ws3.cell(r_s3, 10, tot_val)
        c_tot.number_format = '#,##0.0'
        c_tot.alignment = Alignment(horizontal="right", vertical="center")

        for c in range(1, 11):
            ws3.cell(r_s3, c).border = BORDER_THIN

    # Add Summary Total Row at the bottom of Sheet 3
    if sc_records:
        r_total = 4 + len(sc_records)
        ws3.row_dimensions[r_total].height = 26
        ws3.cell(r_total, 1, "TỔNG CỘNG HỒ SƠ SC:").font = Font(name="Calibri", size=11, bold=True, color="1F497D")
        ws3.merge_cells(f"A{r_total}:H{r_total}")
        ws3.cell(r_total, 1).alignment = Alignment(horizontal="right", vertical="center")

        c_sum_req = ws3.cell(r_total, 9, f"=SUM(I4:I{r_total-1})")
        c_sum_req.font = Font(name="Calibri", size=11, bold=True, color="002060")
        c_sum_req.number_format = '#,##0.0'
        c_sum_req.alignment = Alignment(horizontal="right", vertical="center")

        c_sum_tot = ws3.cell(r_total, 10, f"=SUM(J4:J{r_total-1})")
        c_sum_tot.font = Font(name="Calibri", size=11, bold=True, color="002060")
        c_sum_tot.number_format = '#,##0.0'
        c_sum_tot.alignment = Alignment(horizontal="right", vertical="center")

        for c in range(1, 11):
            cell_t = ws3.cell(r_total, c)
            cell_t.fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
            cell_t.border = BORDER_THIN

    # Set Column Widths for Sheet 3
    s3_widths = {1: 6, 2: 15, 3: 24, 4: 25, 5: 14, 6: 28, 7: 14, 8: 32, 9: 20, 10: 22}
    for col_i, w in s3_widths.items():
        ws3.column_dimensions[get_column_letter(col_i)].width = w

    wb.save(output_path)
    return output_path

def generate_corrected_excel_xnnl(original_excel_path, corrected_excel_path, recon_results):
    """
    Creates an updated version of the Excel XNNL file with:
    - Updated owner names in sheet 'Chu tau' matching SC baseline
    - Normalized dates and license numbers
    - Highlighted adjustments
    Works seamlessly for both modern .xlsx and legacy .xls files!
    """
    from sc_core.excel_processor import open_excel_workbook
    wb = open_excel_workbook(original_excel_path)
    
    # 1. Update Sheet Chủ Tàu
    sc_owner_map = {}
    for r in recon_results:
        if r['sc_data'] and r['sc_data'].get('owner'):
            v_clean = r['vessel_id'].replace(" ", "").upper()
            sc_owner_map[v_clean] = r['sc_data']['owner']

    for sname in wb.sheetnames:
        if 'chu' in sname.lower() or 'tau' in sname.lower():
            ws_chu = wb[sname]
            for row in range(3, ws_chu.max_row + 1):
                v_cell = ws_chu.cell(row, 3)
                if v_cell.value:
                    v_str = str(v_cell.value).strip().replace("Ð", "Đ").replace(" ", "").upper()
                    if v_str in sc_owner_map:
                        new_owner = sc_owner_map[v_str]
                        owner_cell = ws_chu.cell(row, 4)
                        old_owner = owner_cell.value
                        if old_owner != new_owner:
                            owner_cell.value = new_owner
                            owner_cell.fill = SUCCESS_FILL
                            owner_cell.font = Font(name="Calibri", size=10, bold=True, color="276A3C")

    # 2. Update PFI sheet if present
    if 'PFI' in wb.sheetnames:
        ws_pfi = wb['PFI']
        # Map of vessel -> sc_data
        sc_data_map = {r['vessel_id'].replace(" ", "").upper(): r['sc_data'] for r in recon_results if r['sc_data']}
        
        row = 22
        while row <= ws_pfi.max_row:
            v_val = ws_pfi.cell(row, 3).value
            if v_val and ('Tổng' in str(v_val) or 'Total' in str(v_val)):
                break
            if v_val:
                v_norm = str(v_val).strip().replace("Ð", "Đ").replace(" ", "").upper()
                if v_norm in sc_data_map:
                    sc = sc_data_map[v_norm]
                    # Check and fix licence no
                    if sc.get('licence_no'):
                        ws_pfi.cell(row, 7).value = sc['licence_no']
                    # Check and fix licence exp
                    if sc.get('licence_exp'):
                        ws_pfi.cell(row + 1, 7).value = sc['licence_exp']
                    # Check and fix landing date
                    if sc.get('landing_date'):
                        ws_pfi.cell(row, 11).value = sc['landing_date']
                    # Check and fix catch period
                    if sc.get('catch_period'):
                        ws_pfi.cell(row + 1, 8).value = sc['catch_period']
            row += 1

    wb.save(corrected_excel_path)
    return corrected_excel_path
