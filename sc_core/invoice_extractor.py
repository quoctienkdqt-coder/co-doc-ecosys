"""
Mô-đun bóc tách hóa đơn điện tử VAT (PDF) cho đối chiếu hồ sơ C/O & Thủy sản.
Hỗ trợ các nhà cung cấp hóa đơn phổ biến tại Việt Nam (Viettel vinvoice, VNPT, MISA meInvoice, Softdreams, ...).
"""

import os
import re
import glob
from typing import Dict, List, Any, Optional
import fitz  # PyMuPDF


def parse_vn_number(val: Any) -> float:
    """Chuyển đổi chuỗi số định dạng VN (1.250,50 hoặc 1.250) sang float."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(" ", "").replace("'", "")
    if not s:
        return 0.0
    if "." in s and "," in s:
        last_dot = s.rfind(".")
        last_comma = s.rfind(",")
        if last_comma > last_dot:
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "." in s:
        parts = s.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            s = s.replace(".", "")
        else:
            pass
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return 0.0


def extract_single_invoice_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Bóc tách thông tin một file PDF hóa đơn điện tử VAT.
    Trả về dict chuẩn hóa chứa thông tin hóa đơn.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Không tìm thấy file hóa đơn: {pdf_path}")

    with fitz.open(pdf_path) as doc:
        text_p1 = doc[0].get_text() if len(doc) > 0 else ""
        page_count = len(doc)  # lấy trong khối 'with' — sau khi đóng file gọi len(doc) sẽ lỗi "document closed"
    lines = [line.strip() for line in text_p1.split("\n") if line.strip()]

    # 1. Số hóa đơn
    so_hd = ""
    m_no = re.search(r'(?:Số\s*\([Nn]o\.?\):|Số:)\s*(\d+)', text_p1)
    if m_no:
        so_hd = m_no.group(1).lstrip("0") or "0"
    else:
        for i, l in enumerate(lines):
            if any(k in l for k in ["Số (No.):", "Số:", "Số hóa đơn:"]) and i + 1 < len(lines):
                next_val = lines[i + 1].strip()
                if re.match(r'^\d+$', next_val):
                    so_hd = next_val.lstrip("0") or "0"
                    break
    if not so_hd:
        base_name = os.path.basename(pdf_path)
        m_fn = re.search(r'(\d+)\s*TN', base_name, re.IGNORECASE)
        if m_fn:
            so_hd = m_fn.group(1).lstrip("0") or "0"

    # 2. Ký hiệu hóa đơn (Serial)
    ky_hieu = ""
    m_kh = re.search(r'(?:Ký hiệu\s*\([Ss]erial\):|Ký hiệu:)\s*([A-Z0-9]+)', text_p1)
    if m_kh:
        ky_hieu = m_kh.group(1)
    else:
        for i, l in enumerate(lines):
            if "Ký hiệu" in l and i + 1 < len(lines):
                cand = lines[i + 1].strip()
                if re.match(r'^[12][A-Z]\d{2}[A-Z]{2,4}$', cand):
                    ky_hieu = cand
                    break

    # 3. Ngày lập hóa đơn
    ngay_hd = ""
    m_date = re.search(
        r'Ngày\s*(?:\([a-z]+\))?\s*(\d{1,2})\s*tháng\s*(?:\([a-z]+\))?\s*(\d{1,2})\s*năm\s*(?:\([a-z]+\))?\s*(\d{4})',
        text_p1, re.IGNORECASE
    )
    if m_date:
        ngay_hd = f"{int(m_date.group(1)):02d}/{int(m_date.group(2)):02d}/{m_date.group(3)}"
    else:
        m_d2 = re.search(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', text_p1)
        if m_d2:
            ngay_hd = f"{int(m_d2.group(1)):02d}/{int(m_d2.group(2)):02d}/{m_d2.group(3)}"

    # 4. Đơn vị bán hàng (Seller)
    seller_name = ""
    for line in lines:
        l_upper = line.upper()
        if ("CÔNG TY" in l_upper or "CTY" in l_upper or "DNTN" in l_upper or "HẢI SẢN" in l_upper or "HẢI NGUYÊN" in l_upper or "TÂN XUÂN LỘC" in l_upper or "NĂM KHÁNH" in l_upper) and "CÁ NGỪ" not in l_upper:
            clean_s = re.sub(r'^(?:Đơn vị bán hàng|Người bán hàng|Đơn vị bán|Issued|Seller)\s*\([A-Za-z\s]+\)?[:\s]*', '', line, flags=re.IGNORECASE).strip()
            if len(clean_s) > 5 and not clean_s.startswith("MST"):
                seller_name = clean_s
                break

    # 5. Mã số thuế người bán & Địa chỉ người bán
    seller_mst = ""
    m_mst = re.search(r'(?:Mã số thuế|Tax code)[^\n:]*[:\n]\s*(\d{10}(?:-\d{3})?)', text_p1)
    if m_mst:
        seller_mst = m_mst.group(1)

    seller_address = ""
    for i, line in enumerate(lines):
        if any(k in line.upper() for k in ["NGƯỜI MUA HÀNG", "CÁ NGỪ VIỆT NAM", "SUỐI DẦU"]):
            break
        if re.match(r'^Địa chỉ\s*(?:\([A-Za-z\s]+\))?\s*:', line, re.IGNORECASE):
            addr_val = re.sub(r'^Địa chỉ\s*(?:\([A-Za-z\s]+\))?\s*:\s*', '', line, flags=re.IGNORECASE).strip()
            if not addr_val and i + 1 < len(lines):
                addr_val = lines[i + 1].strip()
            if addr_val and "SUỐI DẦU" not in addr_val.upper():
                seller_address = addr_val
                break

    # 6. Đơn vị mua hàng (Buyer)
    buyer_name = ""
    for line in lines:
        if "CÁ NGỪ VIỆT NAM" in line.upper():
            buyer_name = "CÔNG TY TNHH CÁ NGỪ VIỆT NAM"
            break

    buyer_mst = ""
    m_bmst = re.search(r'(?:MST/CCCD|Mã số thuế\s*\(Tax code\))[^\n:]*[:\n]\s*(4201620427|\d{10})', text_p1)
    if m_bmst:
        buyer_mst = m_bmst.group(1)

    # 7. Bóc tách các dòng mặt hàng (Line Items)
    items = []
    for i, l in enumerate(lines):
        if l.lower() == 'kg' and i > 0:
            item_name = lines[i - 1]
            try:
                qty = parse_vn_number(lines[i + 1])
                price = parse_vn_number(lines[i + 2])
                amount = parse_vn_number(lines[i + 3])
                if qty > 0 and price > 0:
                    items.append({
                        'item_name': item_name,
                        'unit': 'kg',
                        'qty': qty,
                        'price': price,
                        'amount': amount
                    })
            except Exception:
                pass

    total_qty = sum(it['qty'] for it in items)
    
    total_amount = 0.0
    m_amt = re.search(r'(?:Tổng cộng tiền thanh toán|Cộng tiền hàng)[^\n:]*[:\n]\s*([\d.,]+)', text_p1)
    if m_amt:
        total_amount = parse_vn_number(m_amt.group(1))
    elif items:
        total_amount = sum(it['amount'] for it in items)

    return {
        'file_name': os.path.basename(pdf_path),
        'file_path': pdf_path,
        'so_hd': so_hd,
        'ky_hieu': ky_hieu,
        'ngay_hd': ngay_hd,
        'seller_name': seller_name,
        'seller_mst': seller_mst,
        'seller_address': seller_address,
        'buyer_name': buyer_name,
        'buyer_mst': buyer_mst,
        'total_qty': total_qty,
        'total_amount': total_amount,
        'items': items,
        'page_count': page_count
    }


def clean_supplier_text(s: str) -> str:
    """Chuẩn hóa tên NCC để so khớp: bỏ dấu tiếng Việt ('Thuỷ' = 'Thủy'), bỏ 'Công ty/TNHH/DNTN'."""
    if not s: return ""
    import unicodedata
    t = unicodedata.normalize("NFD", s.lower().replace("đ", "d"))
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    t = t.replace("cong ty", "").replace("cty", "").replace("tnhh", "").replace("dntn", "")
    return re.sub(r'[^a-z0-9]', '', t)


def extract_invoices_repository(source_dir_or_files, use_ai: bool = False, ai_provider: str = None,
                                api_key: str = None, ai_model: str = None, base_url: str = None,
                                cache_dir: str = "cache", log_cb=None) -> Dict[str, Any]:
    """
    Quét và trích xuất toàn bộ hóa đơn trong thư mục hoặc danh sách file.
    - Hóa đơn điện tử PDF có chữ: đọc trực tiếp (không tốn API).
    - Hóa đơn BẢN SCAN (ảnh, có thể gộp nhiều trang/nhiều loại giấy tờ): nếu use_ai=True thì lọc ra trang hóa đơn
      rồi đọc bằng AI (sc_core.invoice_ai); nếu không thì ghi vào 'scanned_skipped' để cảnh báo.
    Hỗ trợ xử lý trường hợp trùng số hóa đơn giữa nhiều nhà cung cấp khác nhau.
    """
    log = log_cb or (lambda m: None)
    file_paths = []
    if isinstance(source_dir_or_files, str):
        if os.path.isdir(source_dir_or_files):
            for root, dirs, files in os.walk(source_dir_or_files):
                for f in sorted(files):
                    if f.lower().endswith('.pdf') and not f.startswith('~$'):
                        file_paths.append(os.path.join(root, f))
        elif os.path.isfile(source_dir_or_files):
            file_paths.append(source_dir_or_files)
    elif isinstance(source_dir_or_files, (list, tuple)):
        for item in source_dir_or_files:
            if os.path.isdir(item):
                for root, dirs, files in os.walk(item):
                    for f in sorted(files):
                        if f.lower().endswith('.pdf') and not f.startswith('~$'):
                            file_paths.append(os.path.join(root, f))
            elif os.path.isfile(item) and item.lower().endswith('.pdf'):
                file_paths.append(item)

    from collections import defaultdict
    by_number = defaultdict(list)
    by_number_and_seller = {}
    list_all: List[Dict[str, Any]] = []

    scanned_skipped: List[str] = []
    ai_stats: Dict[str, Any] = {}

    def add(inv):
        so = inv['so_hd']
        by_number[so].append(inv)
        by_number[so.zfill(7)].append(inv)
        by_number[so.zfill(8)].append(inv)
        seller_k = clean_supplier_text(inv.get('seller_name', ''))
        if seller_k:
            for k in (so, so.zfill(7), so.zfill(8)):
                by_number_and_seller.setdefault((k, seller_k), inv)
        list_all.append(inv)

    for fpath in file_paths:
        inv = None
        try:
            inv = extract_single_invoice_pdf(fpath)
        except Exception as e:
            print(f"Lỗi khi đọc file hóa đơn {fpath}: {e}")

        from sc_core.invoice_ai import is_scanned_pdf
        if inv and inv.get('so_hd'):
            add(inv)  # Hóa đơn điện tử có chữ (giữ nguyên cách đọc cũ, không tốn API)
            continue
        if not is_scanned_pdf(fpath, inv):
            continue
        # Bản scan
        if not use_ai:
            scanned_skipped.append(fpath)
            continue
        try:
            from sc_core.invoice_ai import read_invoice_pages_with_ai
            invs, st = read_invoice_pages_with_ai(fpath, provider=ai_provider, api_key=api_key, model=ai_model,
                                                  base_url=base_url, cache_dir=cache_dir, log_cb=log)
            ai_stats[os.path.basename(fpath)] = st
            for x in invs:
                if x.get('so_hd'):
                    add(x)
                else:
                    log(f"   ⚠️ Trang {x.get('page')}: AI không đọc được số hóa đơn — bỏ qua")
        except Exception as e:
            log(f"⚠️ Không đọc được hóa đơn scan '{os.path.basename(fpath)}' bằng AI: {e}")
            scanned_skipped.append(fpath)

    return {
        'by_number': dict(by_number),
        'by_number_and_seller': by_number_and_seller,
        'invoices': list_all,
        'count': len(list_all),
        'scanned_skipped': scanned_skipped,
        'ai_stats': ai_stats,
    }


def find_invoice_in_repo(repo_dict: Dict[str, Any], so_hd: str, supplier_hint: str = "", date_hint: str = "") -> Optional[Dict[str, Any]]:
    """
    Tìm kiếm thông minh hóa đơn trong kho theo Số HĐ, kết hợp tên Nhà cung cấp hoặc Ngày lập để giải quyết trùng số.
    """
    if not repo_dict:
        return None

    by_num_seller = repo_dict.get('by_number_and_seller', {})
    by_num = repo_dict.get('by_number', {})

    # 1. Thử khớp chính xác cả Số HĐ lẫn Nhà cung cấp
    if supplier_hint:
        sup_k = clean_supplier_text(supplier_hint)
        for cand_key in [(so_hd, sup_k), (so_hd.zfill(7), sup_k), (so_hd.zfill(8), sup_k)]:
            if cand_key in by_num_seller:
                return by_num_seller[cand_key]
        # Thử tìm kiếm mờ trong tên nhà cung cấp
        candidates = by_num.get(so_hd) or by_num.get(so_hd.zfill(7)) or by_num.get(so_hd.zfill(8)) or []
        for inv in candidates:
            inv_sup_k = clean_supplier_text(inv.get('seller_name', ''))
            if sup_k in inv_sup_k or inv_sup_k in sup_k:
                return inv

    # 2. Thử khớp Số HĐ và Ngày
    candidates = by_num.get(so_hd) or by_num.get(so_hd.zfill(7)) or by_num.get(so_hd.zfill(8)) or []
    if date_hint and len(candidates) > 1:
        d_clean = date_hint.replace('-', '/').strip()
        for inv in candidates:
            if inv.get('ngay_hd', '').replace('-', '/').strip() == d_clean:
                return inv

    # 3. Fallback: trả về ứng viên đầu tiên
    if candidates:
        return candidates[0]

    return None
