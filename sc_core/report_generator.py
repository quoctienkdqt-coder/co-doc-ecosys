def safe_save_workbook(wb, target_path):
    import os
    import datetime
    try:
        wb.save(target_path)
        return target_path
    except PermissionError:
        base, ext = os.path.splitext(target_path)
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        alt_path = f"{base}_{ts}{ext or '.xlsx'}"
        wb.save(alt_path)
        return alt_path

import openpyxl
from copy import copy
import datetime
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import os
import shutil
from collections import defaultdict
import sys
sys.path.insert(0, '.')

# Palettes
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

fill_navy = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
fill_teal = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
fill_slate = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
font_white_bold = Font(name="Calibri", size=10, bold=True, color="FFFFFF")

fill_subtotal = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
font_subtotal = Font(name="Calibri", size=10, bold=True, color="1E3A8A")

fill_green = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
font_green = Font(name="Calibri", size=10, bold=True, color="15803D")

fill_blue = PatternFill(start_color="E0F2FE", end_color="E0F2FE", fill_type="solid")
font_blue = Font(name="Calibri", size=10, bold=True, color="0369A1")

fill_yellow = PatternFill(start_color="FEF9C3", end_color="FEF9C3", fill_type="solid")
font_yellow = Font(name="Calibri", size=10, bold=True, color="A16207")

fill_red = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
font_red = Font(name="Calibri", size=10, bold=True, color="B91C1C")

border_subtotal = Border(
    left=Side(style='thin', color='94A3B8'),
    right=Side(style='thin', color='94A3B8'),
    top=Side(style='thin', color='1E3A8A'),
    bottom=Side(style='medium', color='1E3A8A')
)


def populate_xnnl_diff_sheet(ws1, recon_results, summary_stats, sc_info=None, sheet_title="Bảng Đối Chiếu Sai Khác"):
    ws1.views.sheetView[0].showGridLines = True

    # Title Block
    ws1.merge_cells("A1:L1")
    title_cell = ws1["A1"]
    title_cell.value = "BÁO CÁO ĐỐI CHIẾU DỮ LIỆU XÁC NHẬN NGUYÊN LIỆU (XNNL) VỚI SC GỐC CẢNG CÁ"
    title_cell.font = Font(name="Calibri", size=15, bold=True, color="1F497D")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[1].height = 35

    ws1.merge_cells("A2:L2")
    sub_cell = ws1["A2"]
    sc_num = sc_info.get('sc_number', 'SC Cảng cá') if sc_info else 'SC Cảng cá'
    sub_cell.value = f"Căn cứ so sánh: Giấy xác nhận SC gốc số: {sc_num} | Kiểm tra tự động tính toàn vẹn dữ liệu IUU"
    sub_cell.font = Font(name="Calibri", size=11, italic=True, color="595959")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[2].height = 20

    # Summary KPI Cards
    ws1["A4"] = "TỔNG TÀU EXCEL"
    ws1["A5"] = summary_stats.get('total_excel_vessels', 0)
    ws1["C4"] = "KHỚP HOÀN TOÀN"
    ws1["C5"] = summary_stats.get('count_match', 0)
    ws1["E4"] = "SAI LỆCH CẦN SỬA"
    ws1["E5"] = summary_stats.get('count_conflict', 0)
    ws1["G4"] = "SỐ TÀU ĐÃ GỘP LƯỢNG"
    ws1["G5"] = summary_stats.get('count_merged', 0)
    ws1["I4"] = "TỔNG TÀU SC GỐC"
    ws1["I5"] = summary_stats.get('total_sc_vessels', 0)

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
        c2 = ws1.cell(current_row, 2, r.get('vessel_id', ''))
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
        st = r.get('status', 'MATCH')
        if st == 'MATCH':
            c3.value = "🟢 Khớp 100%"
            c3.fill = SUCCESS_FILL
            c3.font = SUCCESS_FONT
        elif st == 'WARNING':
            c3.value = "🟡 Cảnh báo"
            c3.fill = WARN_FILL
            c3.font = WARN_FONT
        elif st == 'CONFLICT':
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
        if r.get('is_merged', False):
            c4.value = f"Đã gộp {r.get('merged_count', 2)} dòng"
            c4.fill = WARN_FILL
            c4.font = WARN_FONT
        else:
            c4.value = "1 dòng"
            c4.font = Font(name="Calibri", size=10, color="595959")

        ex = r.get('excel_data') or {}
        sc = r.get('sc_data') or {}

        # Chủ tàu
        c5 = ws1.cell(current_row, 6)
        c5.border = BORDER_THIN
        c5.alignment = Alignment(vertical="center", wrap_text=True)
        ex_owner = ex.get('owner', '')
        sc_owner = sc.get('owner', '-')
        c5.value = f"Excel: {ex_owner}\nSC gốc: {sc_owner}"
        if any(d.get('field') == 'Tên Chủ tàu / Thuyền trưởng' and d.get('type') == 'CRITICAL' for d in r.get('diffs', [])):
            c5.fill = DIFF_CELL_FILL
            c5.font = DIFF_CELL_FONT

        # Số GPKTTS
        c6 = ws1.cell(current_row, 7)
        c6.border = BORDER_THIN
        c6.alignment = Alignment(vertical="center", wrap_text=True)
        c6.value = f"Excel: {ex.get('licence_no','')}\nSC gốc: {sc.get('licence_no','-')}"
        if any(d.get('field') == 'Số Giấy phép KTTS' and d.get('type') == 'CRITICAL' for d in r.get('diffs', [])):
            c6.fill = DIFF_CELL_FILL
            c6.font = DIFF_CELL_FONT

        # Hạn GP
        c7 = ws1.cell(current_row, 8)
        c7.border = BORDER_THIN
        c7.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c7.value = f"Excel: {ex.get('licence_exp','')}\nSC: {sc.get('licence_exp','-')}"
        if any(d.get('field') == 'Hạn Giấy phép KTTS' for d in r.get('diffs', [])):
            c7.fill = DIFF_CELL_FILL
            c7.font = DIFF_CELL_FONT

        # Thời gian KT
        c8 = ws1.cell(current_row, 9)
        c8.border = BORDER_THIN
        c8.alignment = Alignment(vertical="center", wrap_text=True)
        c8.value = f"Excel: {ex.get('catch_period','')}\nSC: {sc.get('catch_period','-')}"
        if any(d.get('field') == 'Thời gian khai thác' for d in r.get('diffs', [])):
            c8.fill = DIFF_CELL_FILL
            c8.font = DIFF_CELL_FONT

        # Ngày lên cá
        c9 = ws1.cell(current_row, 10)
        c9.border = BORDER_THIN
        c9.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c9.value = f"Excel: {ex.get('landing_date','')}\nSC: {sc.get('landing_date','-')}"
        if any(d.get('field') == 'Ngày lên cá / bốc dỡ' for d in r.get('diffs', [])):
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
        if r.get('action_needed'):
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


def add_merged_vessels_sheet(wb, aggregation_logs, sheet_title="Tàu Đã Gộp Lượng"):
    ws2 = wb.create_sheet(sheet_title)
    ws2.views.sheetView[0].showGridLines = True
    ws2.merge_cells("A1:G1")
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
            ws2.cell(r_s2, 4, item.get('species', ''))
            ws2.cell(r_s2, 5, item['merged_count']).alignment = Alignment(horizontal="center")
            ws2.cell(r_s2, 6, " + ".join(f"{w:,.1f}" for w in item.get('weights', [])))
            ws2.cell(r_s2, 7, f"{item['sum_weight']:,.1f}").font = Font(bold=True, color="276A3C")
            for c in range(1, 8):
                ws2.cell(r_s2, c).border = BORDER_THIN
            r_s2 += 1
    else:
        ws2.merge_cells("A4:G4")
        ws2["A4"] = "Không có tàu nào trùng ngày lên cá cần gộp lượng trong đợt này."
        ws2["A4"].alignment = Alignment(horizontal="center", vertical="center")
        ws2["A4"].font = Font(italic=True, color="595959")


def add_all_sc_records_sheet(wb, sc_records, sc_num="SC Cảng cá", sheet_title="Toàn Bộ SC Gốc (Cảng cá)"):
    ws3 = wb.create_sheet(sheet_title)
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
        ws3.cell(r_s3, 2, sc.get('vessel_id', '')).font = Font(bold=True)
        ws3.cell(r_s3, 2).alignment = Alignment(horizontal="center", vertical="center")
        ws3.cell(r_s3, 3, sc.get('owner', '')).alignment = Alignment(vertical="center")
        ws3.cell(r_s3, 4, sc.get('licence_no', '')).alignment = Alignment(vertical="center")
        ws3.cell(r_s3, 5, sc.get('licence_exp', '')).alignment = Alignment(horizontal="center", vertical="center")
        ws3.cell(r_s3, 6, f"{sc.get('catch_area','')} {sc.get('catch_period','')}").alignment = Alignment(vertical="center")
        ws3.cell(r_s3, 7, sc.get('landing_date', '')).alignment = Alignment(horizontal="center", vertical="center")
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


def add_combined_hop_nhat_sheet(wb, master_result, sheet_title="DoiChieu_HopNhat_HD_SC", insert_index=None):
    from sc_core.reconciler import clean_vessel_key, normalize_sc_key

    if insert_index is not None:
        ws_comb = wb.create_sheet(title=sheet_title, index=insert_index)
    else:
        ws_comb = wb.create_sheet(title=sheet_title)
        
    ws_comb.views.sheetView[0].showGridLines = True

    # Title & Subtitle
    ws_comb.merge_cells("A1:P1")
    t_comb = ws_comb["A1"]
    t_comb.value = "BẢNG ĐỐI CHIẾU HỢP NHẤT TOÀN TRÌNH: HÓA ĐƠN VAT ↔ BẢNG KÊ THU MUA ↔ SC CẢNG CÁ"
    t_comb.font = Font(name="Calibri", size=13, bold=True, color="1E3A8A")
    t_comb.alignment = Alignment(horizontal="center", vertical="center")
    ws_comb.row_dimensions[1].height = 28

    ws_comb.merge_cells("A2:P2")
    sub_comb = ws_comb["A2"]
    sub_comb.value = "Truy xuất chéo đồng thời: Mỗi Hóa đơn mua từ những Tàu cá nào • Khối lượng phân bổ vs Sản lượng SC • Khối lượng xuất dùng vs Hóa đơn gốc"
    sub_comb.font = Font(name="Calibri", size=9.5, italic=True, color="475569")
    sub_comb.alignment = Alignment(horizontal="center", vertical="center")
    ws_comb.row_dimensions[2].height = 18

    # Tier 1 Header (Row 3)
    ws_comb.merge_cells("A3:H3")
    h_c_inv = ws_comb["A3"]
    h_c_inv.value = "1. THÔNG TIN HÓA ĐƠN VAT (PDF & BẢNG KÊ THU MUA)"
    h_c_inv.fill = fill_navy
    h_c_inv.font = font_white_bold
    h_c_inv.alignment = Alignment(horizontal="center", vertical="center")

    ws_comb.merge_cells("I3:N3")
    h_c_sc = ws_comb["I3"]
    h_c_sc.value = "2. THÔNG TIN TÀU CÁ & GIẤY XÁC NHẬN SC CẢNG CÁ"
    h_c_sc.fill = fill_teal
    h_c_sc.font = font_white_bold
    h_c_sc.alignment = Alignment(horizontal="center", vertical="center")

    ws_comb.merge_cells("O3:P3")
    h_c_eval = ws_comb["O3"]
    h_c_eval.value = "3. ĐÁNH GIÁ THẨM ĐỊNH TOÀN TRÌNH"
    h_c_eval.fill = fill_slate
    h_c_eval.font = font_white_bold
    h_c_eval.alignment = Alignment(horizontal="center", vertical="center")
    ws_comb.row_dimensions[3].height = 22

    # Tier 2 Header (Row 4)
    comb_cols = [
        ("STT", 6),
        ("Số HĐ", 9),
        ("Ngày HĐ", 12),
        ("Nhà Cung Cấp (Người Bán)", 28),
        ("Mã Số Thuế", 13),
        ("Tổng Kg HĐ (PDF)", 16),
        ("Lượng Dùng Lô Này (kg)", 18),
        ("Trạng Thái Hóa Đơn", 20),
        ("Số Giấy Xác Nhận SC", 20),
        ("Số Đăng Ký Tàu Cá", 15),
        ("Tên Chủ Tàu (Bảng Kê)", 20),
        ("Sản Lượng SC (kg)", 15),
        ("Lượng Tàu Theo HĐ (kg)", 18),
        ("Khớp Tàu & SC", 16),
        ("Đánh Giá Thẩm Định", 18),
        ("Chi Tiết Ghi Chú / Sai Lệch", 35)
    ]

    for col_idx, (col_name, col_w) in enumerate(comb_cols, start=1):
        c = ws_comb.cell(4, col_idx, col_name)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.font = font_white_bold
        c.border = BORDER_THIN
        col_letter = get_column_letter(col_idx)
        ws_comb.column_dimensions[col_letter].width = col_w
        if col_idx <= 8:
            c.fill = fill_navy
        elif col_idx <= 14:
            c.fill = fill_teal
        else:
            c.fill = fill_slate
    ws_comb.row_dimensions[4].height = 28

    # SC Lookup Map
    sc_lookup_map = {}
    bk_vs_sc = master_result.get('bk_vs_sc', {})
    for s in bk_vs_sc.get('recons', []):
        k = (normalize_sc_key(s.get('sc_no', '')), clean_vessel_key(s.get('vessel_id', '')))
        sc_lookup_map[k] = s

    c_cur_row = 5
    c_tot_used_kg = 0.0
    c_tot_pdf_kg = 0.0
    c_seen_pdf_invoices = set()
    c_unique_scs = set()
    c_unique_vessels = set()

    bk_vs_inv = master_result.get('bk_vs_invoices', {})
    recons_inv_list = bk_vs_inv.get('recons', [])
    for inv_idx, inv in enumerate(recons_inv_list, start=1):
        hd_no = inv.get('hd_no', '')
        sup_name = inv.get('bk_supplier', '')
        bk_date = inv.get('bk_date', '')
        pdf_date = inv.get('pdf_date', '')
        pdf_mst = inv.get('pdf_mst', '')
        pdf_qty = inv.get('pdf_qty', 0.0)
        bk_qty = inv.get('bk_qty', 0.0)
        alloc_pct = inv.get('alloc_pct', 0.0)
        inv_status = inv.get('status', 'MATCH')

        c_tot_used_kg += bk_qty
        if hd_no not in c_seen_pdf_invoices and pdf_qty > 0:
            c_tot_pdf_kg += pdf_qty
            c_seen_pdf_invoices.add(hd_no)

        ves_groups = defaultdict(float)
        ves_owners = {}
        for it in inv.get('items', []):
            k = (it.get('vessel_id', ''), it.get('sc_no', ''))
            ves_groups[k] += it.get('qty', 0.0)
            ves_owners[k] = it.get('owner', '')
            c_unique_vessels.add(clean_vessel_key(it.get('vessel_id', '')))
            c_unique_scs.add(normalize_sc_key(it.get('sc_no', '')))

        vessel_items = list(ves_groups.items())
        k_len = len(vessel_items)
        if k_len == 0:
            k_len = 1
            vessel_items = [(('', ''), 0.0)]

        start_r = c_cur_row
        end_r = c_cur_row + k_len - 1

        for v_i, ((v_id, sc_no), v_kg) in enumerate(vessel_items):
            r = start_r + v_i
            ws_comb.row_dimensions[r].height = 20

            # Cột 1 đến 8: Hóa đơn VAT
            ws_comb.cell(r, 1, str(inv_idx)).alignment = Alignment(horizontal="center", vertical="center")
            ws_comb.cell(r, 2, hd_no).alignment = Alignment(horizontal="center", vertical="center")

            c_date = ws_comb.cell(r, 3, bk_date)
            c_date.alignment = Alignment(horizontal="center", vertical="center")
            if pdf_date and bk_date != pdf_date:
                c_date.value = f"BK:{bk_date}\nPDF:{pdf_date}"
                c_date.font = font_yellow
                c_date.fill = fill_yellow

            ws_comb.cell(r, 4, sup_name).alignment = Alignment(horizontal="left", vertical="center")
            ws_comb.cell(r, 5, pdf_mst).alignment = Alignment(horizontal="center", vertical="center")

            c_pdf = ws_comb.cell(r, 6, pdf_qty)
            c_pdf.number_format = '#,##0.0'
            c_pdf.alignment = Alignment(horizontal="right", vertical="center")

            c_bk = ws_comb.cell(r, 7, bk_qty)
            c_bk.number_format = '#,##0.0'
            c_bk.alignment = Alignment(horizontal="right", vertical="center")

            c_st_hd = ws_comb.cell(r, 8)
            c_st_hd.alignment = Alignment(horizontal="center", vertical="center")
            if inv_status == 'MATCH':
                c_st_hd.value = f"{alloc_pct:.1f}% 🟢 Khớp 100%"
                c_st_hd.fill = fill_green
                c_st_hd.font = font_green
            elif inv_status == 'PARTIAL':
                c_st_hd.value = f"{alloc_pct:.1f}% 🔵 Dùng 1 phần"
                c_st_hd.fill = fill_blue
                c_st_hd.font = font_blue
            elif inv_status == 'OVER_ALLOCATED':
                c_st_hd.value = f"{alloc_pct:.1f}% 🔴 Kê vượt HĐ"
                c_st_hd.fill = fill_red
                c_st_hd.font = font_red
            else:
                c_st_hd.value = "🟡 Cảnh báo"
                c_st_hd.fill = fill_yellow
                c_st_hd.font = font_yellow

            # Cột 9 đến 14: Tàu & SC
            ws_comb.cell(r, 9, sc_no).alignment = Alignment(horizontal="center", vertical="center")
            ws_comb.cell(r, 10, v_id).alignment = Alignment(horizontal="center", vertical="center")
            ws_comb.cell(r, 11, ves_owners.get((v_id, sc_no), '')).alignment = Alignment(horizontal="left", vertical="center")

            sc_key = (normalize_sc_key(sc_no), clean_vessel_key(v_id))
            sc_info = sc_lookup_map.get(sc_key)
            sc_prod_kg = sc_info.get('sc_weight', 0.0) if sc_info else 0.0
            sc_st = sc_info.get('status', 'MATCH') if sc_info else 'MATCH'

            c_sc_prod = ws_comb.cell(r, 12, sc_prod_kg)
            c_sc_prod.number_format = '#,##0.0'
            c_sc_prod.alignment = Alignment(horizontal="right", vertical="center")

            c_v_kg = ws_comb.cell(r, 13, v_kg)
            c_v_kg.number_format = '#,##0.0'
            c_v_kg.alignment = Alignment(horizontal="right", vertical="center")

            c_st_sc = ws_comb.cell(r, 14)
            c_st_sc.alignment = Alignment(horizontal="center", vertical="center")
            if sc_st == 'MATCH':
                c_st_sc.value = "🟢 Khớp Tàu & SC"
                c_st_sc.fill = fill_green
                c_st_sc.font = font_green
            elif sc_st == 'WARNING':
                c_st_sc.value = "🟡 Cảnh báo"
                c_st_sc.fill = fill_yellow
                c_st_sc.font = font_yellow
            else:
                c_st_sc.value = "🔴 Lệch SC"
                c_st_sc.fill = fill_red
                c_st_sc.font = font_red

            # Cột 15 & 16: Đánh giá & Ghi chú
            c_eval = ws_comb.cell(r, 15)
            c_eval.alignment = Alignment(horizontal="center", vertical="center")
            if inv_status in ('OVER_ALLOCATED', 'MISSING') or sc_st == 'CONFLICT':
                c_eval.value = "🔴 SAI LỆCH"
                c_eval.fill = fill_red
                c_eval.font = font_red
            elif inv_status == 'WARNING' or sc_st == 'WARNING':
                c_eval.value = "🟡 CẦN LƯU Ý"
                c_eval.fill = fill_yellow
                c_eval.font = font_yellow
            else:
                c_eval.value = "🟢 HỢP LỆ"
                c_eval.fill = fill_green
                c_eval.font = font_green

            notes = []
            if inv.get('diffs'):
                for d in inv['diffs']:
                    if d.get('message') and d.get('type') != 'INFO':
                        notes.append(d.get('message'))
            if sc_info and sc_info.get('diffs'):
                for d in sc_info['diffs']:
                    if d.get('message') and d.get('type') != 'INFO' and d.get('message') not in notes:
                        notes.append(d.get('message'))
            if not notes:
                if inv_status == 'PARTIAL':
                    notes.append(f"HĐ xuất dùng 1 phần ({alloc_pct:.1f}%); Sản lượng tàu khớp SC.")
                else:
                    notes.append("Khớp toàn bộ 100% giữa HĐ, Bảng kê và SC.")

            ws_comb.cell(r, 16, "; ".join(notes)).alignment = Alignment(horizontal="left", vertical="center")

            for c_idx in range(1, 17):
                ws_comb.cell(r, c_idx).border = BORDER_THIN

        # Nếu hóa đơn có nhiều tàu (k_len > 1), gộp ô cột 1 đến 8 theo chiều dọc
        if k_len > 1:
            for col_idx in range(1, 9):
                ws_comb.merge_cells(start_row=start_r, start_column=col_idx, end_row=end_r, end_column=col_idx)

        c_cur_row = end_r + 1

    # Dòng TỔNG CỘNG LÔ HÀNG
    ws_comb.row_dimensions[c_cur_row].height = 24
    ws_comb.merge_cells(f"A{c_cur_row}:E{c_cur_row}")
    c_tot = ws_comb.cell(c_cur_row, 1, "TỔNG CỘNG TOÀN BỘ LÔ HÀNG XUẤT KHẨU:")
    c_tot.font = Font(name="Calibri", size=10, bold=True, color="1E3A8A")
    c_tot.alignment = Alignment(horizontal="right", vertical="center")
    c_tot.fill = fill_subtotal

    c_tot_pdf = ws_comb.cell(c_cur_row, 6, c_tot_pdf_kg)
    c_tot_pdf.font = font_subtotal
    c_tot_pdf.number_format = '#,##0.0'
    c_tot_pdf.fill = fill_subtotal
    c_tot_pdf.alignment = Alignment(horizontal="right", vertical="center")

    c_tot_used = ws_comb.cell(c_cur_row, 7, c_tot_used_kg)
    c_tot_used.font = font_subtotal
    c_tot_used.number_format = '#,##0.0'
    c_tot_used.fill = fill_subtotal
    c_tot_used.alignment = Alignment(horizontal="right", vertical="center")

    ws_comb.merge_cells(f"H{c_cur_row}:L{c_cur_row}")
    c_sub_label = ws_comb.cell(c_cur_row, 8, f"Tổng {len(recons_inv_list)} Hóa đơn • {len(c_unique_vessels)} Tàu cá • {len(c_unique_scs)} Giấy SC")
    c_sub_label.font = font_subtotal
    c_sub_label.alignment = Alignment(horizontal="center", vertical="center")
    c_sub_label.fill = fill_subtotal

    c_tot_v = ws_comb.cell(c_cur_row, 13, c_tot_used_kg)
    c_tot_v.font = font_subtotal
    c_tot_v.number_format = '#,##0.0'
    c_tot_v.fill = fill_subtotal
    c_tot_v.alignment = Alignment(horizontal="right", vertical="center")

    c_tot_st = ws_comb.cell(c_cur_row, 15, "🟢 HỢP LỆ")
    c_tot_st.font = font_green
    c_tot_st.fill = fill_green
    c_tot_st.alignment = Alignment(horizontal="center", vertical="center")

    ws_comb.cell(c_cur_row, 16, f"Khối lượng nguyên liệu đưa vào sản xuất: {c_tot_used_kg:,.1f} kg khớp định mức").fill = fill_subtotal

    for c_idx in range(1, 17):
        ws_comb.cell(c_cur_row, c_idx).border = border_subtotal

    return ws_comb




def add_designed_bang_ke_audit_sheet(wb, master_result, sheet_title="Đối Chiếu Bảng Kê (HĐ & SC)", insert_index=1):
    """
    Thiết kế Sheet báo cáo chuẩn đối chiếu Bảng kê thu mua (TT 05) với Hóa đơn VAT (Phần Tô Vàng)
    và Giấy xác nhận SC gốc PDF (Phần Tô Xanh).
    Mỗi ô trong phần Tô Vàng đều hiển thị 2 dòng:
      - Excel: <số liệu trên Bảng kê Excel>
      - HĐ gốc: <số liệu trên Hóa đơn VAT PDF> (kiểm tra đúng size cá, đơn giá và tổng lượng size <= HĐ)
    Mỗi ô trong phần Tô Xanh đều hiển thị 2 dòng:
      - Excel: <thông tin trên Bảng kê Excel>
      - SC gốc: <thông tin trên SC gốc PDF có đầy đủ dấu tiếng Việt>
    """
    from sc_core.reconciler import (normalize_fish_size, strip_vietnamese_accents, clean_vessel_key, normalize_sc_key,
                                    bk_size_key, match_invoice_item)
    from sc_core.invoice_extractor import find_invoice_in_repo, clean_supplier_text

    if insert_index is not None:
        ws = wb.create_sheet(title=sheet_title, index=insert_index)
    else:
        ws = wb.create_sheet(title=sheet_title)

    ws.views.sheetView[0].showGridLines = True

    bk_meta = master_result.get('bang_ke_meta', {})
    records = master_result.get('bang_ke_records', [])
    invoices_repo = master_result.get('invoices_repo', {})
    sc_recons = master_result.get('bk_vs_sc', {}).get('recons', [])
    sc_repo = master_result.get('sc_repo', {})

    # Styles đồng bộ với Bảng Đối Chiếu Sai Khác
    fill_header_navy = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    fill_header_yellow = PatternFill(start_color="D99500", end_color="D99500", fill_type="solid")
    fill_sub_yellow = PatternFill(start_color="FFE699", end_color="FFE699", fill_type="solid")
    fill_cell_yellow = PatternFill(start_color="FFF9E6", end_color="FFF9E6", fill_type="solid")

    fill_header_green = PatternFill(start_color="276A3C", end_color="276A3C", fill_type="solid")
    fill_sub_green = PatternFill(start_color="C6E0B4", end_color="C6E0B4", fill_type="solid")
    fill_cell_green = PatternFill(start_color="EBF5E6", end_color="EBF5E6", fill_type="solid")

    font_header_white = Font(name="Calibri", size=10.5, bold=True, color="FFFFFF")
    font_sub_yellow = Font(name="Calibri", size=10, bold=True, color="593E00")
    font_sub_green = Font(name="Calibri", size=10, bold=True, color="1B4D2B")
    font_data = Font(name="Calibri", size=10, color="111827")
    font_data_bold = Font(name="Calibri", size=10, bold=True, color="111827")

    # 1. Title & Subtitle
    ws.merge_cells("A1:P1")
    t_cell = ws["A1"]
    t_cell.value = "BÁO CÁO ĐỐI CHIẾU BẢNG KÊ THU MUA NGUYÊN LIỆU (TT 05) VỚI HÓA ĐƠN VAT & SC GỐC CẢNG CÁ"
    t_cell.font = Font(name="Calibri", size=15, bold=True, color="1F497D")
    t_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 34

    ws.merge_cells("A2:P2")
    sub_cell = ws["A2"]
    trader = bk_meta.get('trader_name') or 'Công ty TNHH Cá Ngừ Việt Nam'
    mst = bk_meta.get('trader_mst') or '4201620427'
    tkhq = bk_meta.get('customs_declaration') or '-'
    goods = bk_meta.get('goods_name') or '-'
    exp_qty = bk_meta.get('export_qty', 0.0)
    fob_val = bk_meta.get('fob_val', 0.0)
    sub_cell.value = f"Doanh nghiệp: {trader} (MST: {mst}) | TKHQ số: {tkhq} | Hàng hóa: {goods} | Lượng XK: {exp_qty:,.2f} kg | Trị giá FOB: {fob_val:,.2f} USD"
    sub_cell.font = Font(name="Calibri", size=10.5, italic=True, color="595959")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 20

    # 2. Pre-compute Size Totals on Excel per (hd_no, hd_date, supplier, size_key)
    excel_size_totals = {}
    excel_size_counts = {}
    for r in records:
        hd_no = str(r.get('hd_no', '')).lstrip("0") or "0"
        sz = bk_size_key(r)  # bảng kê không có cột Size -> nhóm theo đơn giá
        k = (hd_no, r.get('hd_date', ''), r.get('supplier', ''), sz)
        excel_size_totals[k] = excel_size_totals.get(k, 0.0) + float(r.get('qty', 0.0))
        excel_size_counts[k] = excel_size_counts.get(k, 0) + 1

    # Map SC records from bk_vs_sc and sc_repo
    sc_matched_map = {}
    for rec in sc_recons:
        k_sc = (normalize_sc_key(rec.get('sc_no', '')), clean_vessel_key(rec.get('vessel_id', '')))
        sc_matched_map[k_sc] = rec

    # Direct lookup from sc_repo for full vessel details (deduplicated)
    sc_vessel_lookup = {}
    seen_sc_v = set()
    for sc_k, sc_bundle in (sc_repo or {}).items():
        sc_num_real = sc_bundle.get('sc_info', {}).get('sc_number', sc_k)
        sck = normalize_sc_key(sc_num_real)
        for v_rec in sc_bundle.get('records', []):
            vk = clean_vessel_key(v_rec.get('vessel_id', ''))
            dedup_k = (sck, vk, v_rec.get('landing_date', ''), v_rec.get('req_catch_kg', 0))
            if dedup_k in seen_sc_v:
                continue
            seen_sc_v.add(dedup_k)
            if vk not in sc_vessel_lookup:
                sc_vessel_lookup[vk] = {
                    'sc_number': sc_num_real,
                    'vessel_id': v_rec.get('vessel_id', ''),
                    'owner': v_rec.get('owner', ''),
                    'req_catch_kg': float(v_rec.get('req_catch_kg', 0.0)),
                    'total_catch_kg': float(v_rec.get('total_catch_kg', 0.0))
                }
            else:
                sc_vessel_lookup[vk]['req_catch_kg'] += float(v_rec.get('req_catch_kg', 0.0))
                sc_vessel_lookup[vk]['total_catch_kg'] += float(v_rec.get('total_catch_kg', 0.0))

    # 3. Group Banners (Row 6) & Column Headers (Row 7)
    ws.merge_cells("A6:E6")
    b_info = ws["A6"]
    b_info.value = "THÔNG TIN NGUYÊN LIỆU TRÊN BẢNG KÊ (TT 05)"
    b_info.fill = fill_header_navy
    b_info.font = font_header_white
    b_info.alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("F6:L6")
    b_yel = ws["F6"]
    b_yel.value = "PHẦN TÔ VÀNG: ĐỐI CHIẾU BẢNG KÊ EXCEL ↔ HÓA ĐƠN VAT ĐIỆN TỬ (THEO TÊN CÁ, SIZE CÁ, ĐƠN GIÁ & TỔNG LƯỢNG)"
    b_yel.fill = fill_header_yellow
    b_yel.font = font_header_white
    b_yel.alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("M6:O6")
    b_grn = ws["M6"]
    b_grn.value = "PHẦN TÔ XANH: ĐỐI CHIẾU BẢNG KÊ EXCEL ↔ GIẤY XÁC NHẬN SC GỐC PDF"
    b_grn.fill = fill_header_green
    b_grn.font = font_header_white
    b_grn.alignment = Alignment(horizontal="center", vertical="center")

    b_st = ws["P6"]
    b_st.value = "KẾT LUẬN"
    b_st.fill = fill_header_navy
    b_st.font = font_header_white
    b_st.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[6].height = 24

    headers = [
        "STT\n(1)",
        "Tên Nguyên Liệu\n(2)",
        "Quy Cách / Size Cá\n(2b)",
        "Mã HS\n(3)",
        "Nơi Khai Thác\n(4)",
        "Số Lượng (KGS)\n(Excel / HĐ VAT) (5)",
        "Đơn Giá (VNĐ)\n(Excel / HĐ VAT) (6)",
        "Tổng Trị Giá (VNĐ)\n(Excel / HĐ VAT) (7)",
        "Tên Nhà Cung Cấp\n(Excel / HĐ VAT) (8)",
        "Địa Chỉ Nhà Cung Cấp\n(Excel / HĐ VAT) (9)",
        "Số Hóa Đơn\n(Excel / HĐ VAT) (10)",
        "Ngày Hóa Đơn\n(Excel / HĐ VAT) (11)",
        "Số Giấy Xác Nhận SC\n(Excel / SC gốc) (12)",
        "Tên, Số Đăng Ký Tàu\n(Excel / SC gốc) (13)",
        "Tên Chủ Tàu, Thuyền Trưởng\n(Excel / SC gốc) (14)",
        "Trạng Thái & Đánh Giá Đối Chiếu"
    ]

    for col_idx, h_text in enumerate(headers, 1):
        c_h = ws.cell(7, col_idx, h_text)
        c_h.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c_h.border = BORDER_THIN
        if col_idx <= 5 or col_idx == 16:
            c_h.fill = fill_header_navy
            c_h.font = font_header_white
        elif 6 <= col_idx <= 12:
            c_h.fill = fill_sub_yellow
            c_h.font = font_sub_yellow
        else:
            c_h.fill = fill_sub_green
            c_h.font = font_sub_green
    ws.row_dimensions[7].height = 34

    # 4. Populate Rows (Row 8+)
    cur_row = 8
    count_perfect = 0
    count_warn = 0
    count_err = 0

    for idx, r in enumerate(records, 1):
        ws.row_dimensions[cur_row].height = 38
        row_notes = []
        row_has_err = False
        row_has_warn = False

        hd_no = str(r.get('hd_no', '')).lstrip("0") or "0"
        hd_date = str(r.get('hd_date', '')).strip()
        supplier_bk = str(r.get('supplier', '')).strip()
        address_bk = str(r.get('address', '')).strip()
        spec_bk = str(r.get('spec', '')).strip()
        size_key = bk_size_key(r)

        ex_qty = float(r.get('qty', 0.0))
        ex_price = float(r.get('price', 0.0))
        ex_amt = ex_qty * ex_price

        k_sz = (hd_no, hd_date, supplier_bk, size_key)
        ex_size_sum = excel_size_totals.get(k_sz, ex_qty)
        ex_size_cnt = excel_size_counts.get(k_sz, 1)

        # Lookup Invoice + dòng hàng tương ứng (theo size, nếu bảng kê không có size thì theo đơn giá)
        inv = find_invoice_in_repo(invoices_repo, hd_no, supplier_hint=supplier_bk, date_hint=hd_date)
        matched_inv_item = match_invoice_item(inv, spec_bk, ex_price) if inv else None
        if not spec_bk and matched_inv_item:
            # Bảng kê không ghi size -> hiển thị size suy ra từ dòng hàng trên hóa đơn
            spec_bk = f"(HĐ: {matched_inv_item.get('item_name', '')})"

        inv_qty = float(matched_inv_item['qty']) if matched_inv_item else 0.0
        inv_price = float(matched_inv_item['price']) if matched_inv_item else 0.0
        inv_amt = float(matched_inv_item['amount']) if matched_inv_item else 0.0
        inv_seller = inv.get('seller_name', '-') if inv else 'Không tìm thấy HĐ'
        inv_address = inv.get('seller_address', '-') if inv else '-'
        inv_no_str = inv.get('so_hd', '-') if inv else '-'
        inv_date_str = inv.get('ngay_hd', '-') if inv else '-'

        price_ok = (abs(ex_price - inv_price) < 1.0) if (inv and matched_inv_item) else False
        qty_ok = (ex_size_sum <= inv_qty + 0.1) if (inv and matched_inv_item) else False
        date_ok = (hd_date.replace('-', '/') == inv_date_str.replace('-', '/')) if inv else False

        if not inv:
            row_has_err = True
            row_notes.append(f"Thiếu file PDF HĐ số {hd_no}")
        else:
            if not price_ok:
                row_has_err = True
                row_notes.append(f"Lệch đơn giá size {spec_bk} (Excel {ex_price:,.0f} != HĐ {inv_price:,.0f})")
            if not qty_ok:
                row_has_err = True
                row_notes.append(f"Tổng lượng size {spec_bk} ({ex_size_sum:,.0f} kg) vượt HĐ ({inv_qty:,.0f} kg)")
            if not date_ok:
                row_has_warn = True
                row_notes.append(f"Lệch ngày HĐ ({hd_date} vs {inv_date_str})")

        # Base Columns 1..5
        c1 = ws.cell(cur_row, 1, r.get('stt', idx))
        c1.alignment = Alignment(horizontal="center", vertical="center")
        c2 = ws.cell(cur_row, 2, r.get('material', 'Cá ngừ'))
        c2.alignment = Alignment(horizontal="center", vertical="center")
        c3 = ws.cell(cur_row, 3, spec_bk)
        c3.alignment = Alignment(horizontal="center", vertical="center")
        c3.font = font_data_bold
        c4 = ws.cell(cur_row, 4, r.get('hs', '030342'))
        c4.alignment = Alignment(horizontal="center", vertical="center")
        c5 = ws.cell(cur_row, 5, r.get('origin', 'Việt Nam'))
        c5.alignment = Alignment(horizontal="center", vertical="center")
        for ci in range(1, 6):
            ws.cell(cur_row, ci).border = BORDER_THIN

        # --- PHẦN TÔ VÀNG: CỘT 6..12 (Excel vs Hóa đơn VAT) ---
        # Col 6: Số lượng (KGS)
        c6 = ws.cell(cur_row, 6)
        if ex_size_cnt > 1:
            c6.value = f"Excel: {ex_qty:,.1f} kg (Tổng {ex_size_cnt} dòng: {ex_size_sum:,.1f} kg)\nHĐ gốc: {inv_qty:,.1f} kg"
        else:
            c6.value = f"Excel: {ex_qty:,.1f} kg\nHĐ gốc: {inv_qty:,.1f} kg"
        c6.alignment = Alignment(vertical="center", wrap_text=True)
        c6.fill = DIFF_CELL_FILL if not qty_ok else fill_cell_yellow
        c6.font = DIFF_CELL_FONT if not qty_ok else font_data
        c6.border = BORDER_THIN

        # Col 7: Đơn giá (VNĐ)
        c7 = ws.cell(cur_row, 7)
        c7.value = f"Excel: {ex_price:,.0f} đ\nHĐ gốc: {inv_price:,.0f} đ"
        c7.alignment = Alignment(vertical="center", wrap_text=True)
        c7.fill = DIFF_CELL_FILL if not price_ok else fill_cell_yellow
        c7.font = DIFF_CELL_FONT if not price_ok else font_data
        c7.border = BORDER_THIN

        # Col 8: Tổng trị giá (VNĐ)
        c8 = ws.cell(cur_row, 8)
        c8.value = f"Excel: {ex_amt:,.0f} đ\nHĐ gốc (Size): {inv_amt:,.0f} đ"
        c8.alignment = Alignment(vertical="center", wrap_text=True)
        c8.fill = fill_cell_yellow
        c8.font = font_data
        c8.border = BORDER_THIN

        # Col 9: Tên Nhà cung cấp
        c9 = ws.cell(cur_row, 9)
        c9.value = f"Excel: {supplier_bk}\nHĐ gốc: {inv_seller}"
        c9.alignment = Alignment(vertical="center", wrap_text=True)
        c9.fill = fill_cell_yellow
        c9.font = font_data
        c9.border = BORDER_THIN

        # Col 10: Địa chỉ Nhà cung cấp
        c10 = ws.cell(cur_row, 10)
        c10.value = f"Excel: {address_bk}\nHĐ gốc: {inv_address}"
        c10.alignment = Alignment(vertical="center", wrap_text=True)
        c10.fill = fill_cell_yellow
        c10.font = font_data
        c10.border = BORDER_THIN

        # Col 11: Số Hóa đơn
        c11 = ws.cell(cur_row, 11)
        c11.value = f"Excel: {hd_no}\nHĐ gốc: {inv_no_str}"
        c11.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c11.fill = DIFF_CELL_FILL if not inv else fill_cell_yellow
        c11.font = DIFF_CELL_FONT if not inv else font_data
        c11.border = BORDER_THIN

        # Col 12: Ngày Hóa đơn
        c12 = ws.cell(cur_row, 12)
        c12.value = f"Excel: {hd_date}\nHĐ gốc: {inv_date_str}"
        c12.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c12.fill = DIFF_CELL_FILL if not date_ok else fill_cell_yellow
        c12.font = DIFF_CELL_FONT if not date_ok else font_data
        c12.border = BORDER_THIN

        # --- PHẦN TÔ XANH: CỘT 13..15 (Excel vs SC Gốc PDF) ---
        sc_no_bk = str(r.get('sc_no', '')).strip()
        vessel_bk = str(r.get('vessel_id', '')).strip().upper()
        owner_bk = str(r.get('owner', '')).strip()

        vk_clean = clean_vessel_key(vessel_bk)
        sck_clean = normalize_sc_key(sc_no_bk)
        sc_rec = sc_matched_map.get((sck_clean, vk_clean))
        sc_v_info = sc_vessel_lookup.get(vk_clean)

        if sc_v_info:
            sc_no_goc = sc_v_info.get('sc_number', sc_no_bk)
            vessel_goc = sc_v_info.get('vessel_id', vessel_bk)
            owner_goc = sc_v_info.get('owner', '')
            sc_kg_goc = sc_v_info.get('req_catch_kg', 0.0)
        elif sc_rec:
            sc_no_goc = sc_rec.get('sc_no', sc_no_bk)
            vessel_goc = sc_rec.get('vessel_id', vessel_bk)
            owner_goc = sc_rec.get('owner_sc', '')
            sc_kg_goc = sc_rec.get('sc_weight', 0.0)
        else:
            sc_no_goc = "Không tìm thấy"
            vessel_goc = "Không tìm thấy"
            owner_goc = "Không tìm thấy"
            sc_kg_goc = 0.0

        sc_found = (sc_no_goc != "Không tìm thấy")
        sc_no_match = (normalize_sc_key(sc_no_bk) == normalize_sc_key(sc_no_goc)) if sc_found else False
        vessel_match = (clean_vessel_key(vessel_bk) == clean_vessel_key(vessel_goc)) if sc_found else False
        owner_exact = (owner_bk.lower() == owner_goc.lower()) if sc_found else False
        owner_partial = (strip_vietnamese_accents(owner_bk) == strip_vietnamese_accents(owner_goc) or owner_goc.lower() in owner_bk.lower() or owner_bk.lower() in owner_goc.lower()) if sc_found else False

        if not sc_found:
            row_has_err = True
            row_notes.append(f"Tàu {vessel_bk} không có trong SC gốc")
        else:
            if not sc_no_match:
                row_has_err = True
                row_notes.append(f"Lệch số SC ({sc_no_bk} vs {sc_no_goc})")
            if not owner_exact:
                row_has_warn = True
                row_notes.append(f"Chủ tàu: Excel '{owner_bk}' vs SC gốc '{owner_goc}'")

        # Col 13: Số giấy xác nhận SC
        c13 = ws.cell(cur_row, 13)
        c13.value = f"Excel: {sc_no_bk}\nSC gốc: {sc_no_goc}"
        c13.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c13.fill = DIFF_CELL_FILL if not sc_no_match else fill_cell_green
        c13.font = DIFF_CELL_FONT if not sc_no_match else font_data
        c13.border = BORDER_THIN

        # Col 14: Tên, số đăng ký tàu
        c14 = ws.cell(cur_row, 14)
        c14.value = f"Excel: {vessel_bk}\nSC gốc: {vessel_goc} ({sc_kg_goc:,.0f} kg)" if sc_found else f"Excel: {vessel_bk}\nSC gốc: Không tìm thấy"
        c14.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c14.fill = DIFF_CELL_FILL if not vessel_match else fill_cell_green
        c14.font = DIFF_CELL_FONT if not vessel_match else font_data
        c14.border = BORDER_THIN

        # Col 15: Tên chủ tàu, thuyền trưởng
        c15 = ws.cell(cur_row, 15)
        c15.value = f"Excel: {owner_bk}\nSC gốc: {owner_goc}"
        c15.alignment = Alignment(vertical="center", wrap_text=True)
        if not sc_found or not owner_partial:
            c15.fill = DIFF_CELL_FILL
            c15.font = DIFF_CELL_FONT
        elif not owner_exact:
            c15.fill = WARN_FILL
            c15.font = WARN_FONT
        else:
            c15.fill = fill_cell_green
            c15.font = font_data
        c15.border = BORDER_THIN

        # Col 16: Trạng thái & Đánh giá
        c16 = ws.cell(cur_row, 16)
        c16.alignment = Alignment(vertical="center", wrap_text=True)
        c16.border = BORDER_THIN
        if row_has_err:
            count_err += 1
            c16.value = "🔴 Sai lệch: " + "; ".join(row_notes)
            c16.fill = DANGER_FILL
            c16.font = DANGER_FONT
        elif row_has_warn:
            count_warn += 1
            c16.value = "🟡 Cảnh báo: " + "; ".join(row_notes)
            c16.fill = WARN_FILL
            c16.font = WARN_FONT
        else:
            count_perfect += 1
            c16.value = f"🟢 Khớp 100% (Đơn giá {ex_price:,.0f}đ & tổng size {ex_size_sum:,.0f}/{inv_qty:,.0f}kg đúng HĐ; Tàu & Chủ tàu đúng SC gốc)"
            c16.fill = SUCCESS_FILL
            c16.font = SUCCESS_FONT

        cur_row += 1

    # 5. Row Tổng cộng cuối bảng
    ws.row_dimensions[cur_row].height = 28
    ws.merge_cells(f"A{cur_row}:E{cur_row}")
    c_tot_lbl = ws.cell(cur_row, 1, "TỔNG CỘNG TOÀN BẢNG KÊ")
    c_tot_lbl.font = Font(name="Calibri", size=10.5, bold=True, color="1F497D")
    c_tot_lbl.alignment = Alignment(horizontal="center", vertical="center")

    tot_ex_kg = sum(float(r.get('qty', 0.0)) for r in records)
    tot_ex_amt = sum(float(r.get('qty', 0.0)) * float(r.get('price', 0.0)) for r in records)

    c_tot_qty = ws.cell(cur_row, 6, f"Tổng Excel: {tot_ex_kg:,.1f} kg")
    c_tot_qty.font = Font(name="Calibri", size=10.5, bold=True, color="1F497D")
    c_tot_qty.alignment = Alignment(horizontal="center", vertical="center")

    c_tot_amt = ws.cell(cur_row, 8, f"Tổng trị giá: {tot_ex_amt:,.0f} đ")
    c_tot_amt.font = Font(name="Calibri", size=10.5, bold=True, color="1F497D")
    c_tot_amt.alignment = Alignment(horizontal="center", vertical="center")

    for ci in range(1, 17):
        cell_b = ws.cell(cur_row, ci)
        cell_b.border = border_subtotal
        if cell_b.fill.fill_type is None:
            cell_b.fill = fill_subtotal

    # 6. KPI Cards at Row 4-5
    ws["A4"] = "TỔNG DÒNG BẢNG KÊ"
    ws["A5"] = len(records)
    ws["D4"] = "KHỚP HOÀN TOÀN"
    ws["D5"] = count_perfect
    ws["G4"] = "CẢNH BÁO NHẸ"
    ws["G5"] = count_warn
    ws["J4"] = "SAI LỆCH CẦN SỬA"
    ws["J5"] = count_err
    ws["M4"] = "TỔNG KHỐI LƯỢNG KÊ"
    ws["M5"] = f"{tot_ex_kg:,.1f} kg"

    kpi_cards = [
        ("A4", "A5", INFO_FILL, INFO_FONT),
        ("D4", "D5", SUCCESS_FILL, SUCCESS_FONT),
        ("G4", "G5", WARN_FILL, WARN_FONT),
        ("J4", "J5", DANGER_FILL, DANGER_FONT),
        ("M4", "M5", INFO_FILL, INFO_FONT),
    ]
    for l_pos, v_pos, fl, fn in kpi_cards:
        ws[l_pos].font = Font(name="Calibri", size=9, bold=True, color="595959")
        ws[l_pos].alignment = Alignment(horizontal="center", vertical="center")
        ws[v_pos].font = Font(name="Calibri", size=14, bold=True, color=fn.color.rgb)
        ws[v_pos].fill = fl
        ws[v_pos].alignment = Alignment(horizontal="center", vertical="center")
        ws[v_pos].border = BORDER_THIN
    ws.row_dimensions[4].height = 18
    ws.row_dimensions[5].height = 26

    # 7. Column Widths
    col_widths = {
        1: 7,   # STT
        2: 15,  # Tên NL
        3: 15,  # Quy cách / Size
        4: 11,  # Mã HS
        5: 13,  # Nơi KT
        6: 30,  # Số lượng (Excel / HĐ)
        7: 22,  # Đơn giá (Excel / HĐ)
        8: 26,  # Tổng trị giá (Excel / HĐ)
        9: 34,  # Tên NCC (Excel / HĐ)
        10: 42, # Địa chỉ NCC (Excel / HĐ)
        11: 16, # Số HĐ (Excel / HĐ)
        12: 18, # Ngày HĐ (Excel / HĐ)
        13: 26, # Số SC (Excel / SC)
        14: 26, # Số tàu (Excel / SC)
        15: 28, # Tên chủ tàu (Excel / SC)
        16: 46  # Trạng thái & Đánh giá
    }
    for c_i, w_val in col_widths.items():
        ws.column_dimensions[get_column_letter(c_i)].width = w_val

    return ws


def create_reconciliation_excel_report(output_path, recon_results, summary_stats, aggregation_logs, sc_records, sc_info=None, master_result=None):
    """
    Xuất DUY NHẤT 1 file báo cáo chuẩn gồm các Sheet:
      - Sheet 1: Bảng Đối Chiếu Sai Khác (XNNL ↔ SC Gốc Cảng cá)
      - Sheet 2: Đối Chiếu Bảng Kê (HĐ & SC) (Thiết kế chuẩn: Phần Vàng đối chiếu Hóa đơn VAT, Phần Xanh đối chiếu SC Gốc PDF)
      - Sheet 3: Tàu Đã Gộp Lượng
      - Sheet 4: Toàn Bộ SC Gốc (Cảng cá)
    """
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Bảng Đối Chiếu Sai Khác"
    populate_xnnl_diff_sheet(ws1, recon_results, summary_stats, sc_info, "Bảng Đối Chiếu Sai Khác")

    # Sheet 2: Đối Chiếu Bảng Kê (HĐ & SC) do hệ thống thiết kế
    if master_result and master_result.get('bang_ke_records'):
        add_designed_bang_ke_audit_sheet(wb, master_result, sheet_title="Đối Chiếu Bảng Kê (HĐ & SC)", insert_index=1)

    # Sheet: Đối chiếu SC Excel ↔ SC scan PDF (nếu có)
    if master_result:
        from sc_core.sc_excel_vs_pdf import add_sc_excel_vs_pdf_sheets
        # 1 hoặc nhiều file SC Excel: nhiều file -> thêm sheet Tổng hợp + mỗi SC 1 sheet chi tiết
        add_sc_excel_vs_pdf_sheets(wb, master_result.get('sc_excel_vs_pdf', []),
                                   sc_repo=master_result.get('sc_repo'),
                                   insert_index=len(wb.sheetnames))

    # Sheet 3: Tàu Đã Gộp Lượng
    add_merged_vessels_sheet(wb, aggregation_logs, "Tàu Đã Gộp Lượng")

    # Sheet 4: Toàn Bộ SC Gốc (Cảng cá)
    sc_num = sc_info.get('sc_number', 'SC Cảng cá') if sc_info else 'SC Cảng cá'
    add_all_sc_records_sheet(wb, sc_records, sc_num, "Toàn Bộ SC Gốc (Cảng cá)")

    return safe_save_workbook(wb, output_path)


def generate_corrected_excel_xnnl(original_excel_path, corrected_excel_path, recon_results):
    from sc_core.excel_processor import open_excel_workbook
    wb = open_excel_workbook(original_excel_path)
    
    # 1. Update Sheet Chủ Tàu
    sc_owner_map = {}
    for r in recon_results:
        if r.get('sc_data') and r['sc_data'].get('owner'):
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
        sc_data_map = {r['vessel_id'].replace(" ", "").upper(): r['sc_data'] for r in recon_results if r.get('sc_data')}
        
        row = 22
        while row <= ws_pfi.max_row:
            v_val = ws_pfi.cell(row, 3).value
            if v_val and ('Tổng' in str(v_val) or 'Total' in str(v_val)):
                break
            if v_val:
                v_norm = str(v_val).strip().replace("Ð", "Đ").replace(" ", "").upper()
                if v_norm in sc_data_map:
                    sc = sc_data_map[v_norm]
                    if sc.get('licence_no'):
                        ws_pfi.cell(row, 7).value = sc['licence_no']
                    if sc.get('licence_exp'):
                        ws_pfi.cell(row + 1, 7).value = sc['licence_exp']
                    if sc.get('landing_date'):
                        ws_pfi.cell(row, 11).value = sc['landing_date']
                    if sc.get('catch_period'):
                        ws_pfi.cell(row + 1, 8).value = sc['catch_period']
            row += 1

    return safe_save_workbook(wb, corrected_excel_path)




def create_full_suite_excel_report(output_path, master_result):
    """
    Hợp nhất về cùng 1 mẫu báo cáo duy nhất (4 Sheet chuẩn) để người dùng chỉ cần mở 1 file duy nhất.
    """
    xnnl_vs_sc = master_result.get('xnnl_vs_sc', {})
    recon_results = xnnl_vs_sc.get('recons', [])
    summary_stats = xnnl_vs_sc.get('summary', {})
    aggregation_logs = xnnl_vs_sc.get('merge_logs', [])
    all_sc_records = master_result.get('all_sc_records', [])
    sc_repo = master_result.get('sc_repo', {})
    first_sc_info = next(iter(sc_repo.values())).get('sc_info', {}) if sc_repo else None

    return create_reconciliation_excel_report(
        output_path=output_path,
        recon_results=recon_results,
        summary_stats=summary_stats,
        aggregation_logs=aggregation_logs,
        sc_records=all_sc_records,
        sc_info=first_sc_info,
        master_result=master_result
    )
