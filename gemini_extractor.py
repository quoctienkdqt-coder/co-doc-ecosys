import requests
import time
"""
Module xử lý trích xuất chứng từ xuất nhập khẩu bằng Google Gemini API (Structured Outputs)
"""

import os
import mimetypes
import json
import base64
import re
import urllib.request
from typing import List, Tuple
import fitz  # PyMuPDF
from google import genai
from google.genai import types

from co_schema import CODeclarationData


SYSTEM_PROMPT = """Bạn là một Chuyên gia Cao cấp về Thủ tục Hải quan, Logistics và Cấp Chứng nhận Xuất xứ Hàng hóa (C/O) của Bộ Công Thương Việt Nam.

Nhiệm vụ của bạn:
Phân tích toàn diện tất cả các tài liệu chứng từ xuất khẩu được cung cấp bao gồm:
1. "ĐƠN ĐỀ NGHỊ CẤP C/O" (Mẫu số 04 của Bộ Công Thương)
2. "VẬN ĐƠN ĐƯỜNG BIỂN / VẬN TẢI ĐƠN" (Bill of Lading - B/L / Air Waybill)
3. "HÓA ĐƠN THƯƠNG MẠI & PHIẾU ĐÓNG GÓI" (Commercial Invoice & Packing List)
4. "BẢNG KÊ NGUYÊN PHỤ LIỆU / HÓA ĐƠN VAT / TỜ KHAI HẢI QUAN NHẬP KHẨU" (Raw Materials & Invoices)

Từ đó, tổng hợp và trích xuất chính xác 100% tất cả 30 trường dữ liệu theo quy chuẩn khai báo C/O điện tử trên cổng eCoSys (co.moit.gov.vn):

BẢNG ÁNH XẠ 30 TRƯỜNG DỮ LIỆU ĐẦU VÀO CHUẨN XÁC:
(1) MẪU C/O (form): Lấy từ tiêu đề "ĐƠN ĐỀ NGHỊ CẤP C/O MẪU..." (ví dụ: 'EUR.1', 'EAV', 'B', 'D', 'AANZ', 'CPTPP', 'VJ', 'AK', 'E'...).
(2) NƯỚC NHẬP KHẨU (importing_Country): Lấy chính xác tại Mục 14 "Nước Nhập khẩu" trên Đơn đề nghị Mẫu 04 (ví dụ: 'RUSSIA', 'LITHUANIA', 'JAPAN', 'GERMANY'...). Tuyệt đối không điền 'Vietnam'.
(3) SỐ TỜ KHAI HQ XUẤT KHẨU (declarationNumbers): Lấy tại Mục 16 trên Đơn đề nghị Mẫu 04 (ví dụ: '235602110812').
(4) NGÀY TỜ KHAI HQ XUẤT KHẨU (declarationDates): Lấy tại Mục 16 trên Đơn đề nghị Mẫu 04, định dạng DD/MM/YYYY (ví dụ: '23/12/2026').
(5) TÊN DN XUẤT KHẨU TIẾNG ANH (from_ExporterBusinessName): Lấy tại Mục 5 trên Đơn đề nghị Mẫu 04 (ví dụ: 'HAI VUONG COMPANY LIMITED (HAVUCO)').
(6) ĐỊA CHỈ DN XUẤT KHẨU (from_AddressLine1 & from_Addressline2): Lấy tại Mục 5 trên Đơn đề nghị Mẫu 04. Dòng 1 tối đa 70 ký tự, phần còn lại đưa vào dòng 2.
(7) TÊN NGƯỜI NHẬN HÀNG (to_ConsigneeName): Lấy tại Mục 7 trên Đơn đề nghị Mẫu 04 hoặc trên Bill of Lading (ví dụ: 'OOO MERIDIAN-TRADING').
(8) ĐỊA CHỈ NGƯỜI NHẬN HÀNG (to_Addressline1 & to_Addressline2): Lấy tại Mục 7 trên Đơn đề nghị Mẫu 04. Phân chia dòng 1 và dòng 2.
(9) CẢNG BỐC HÀNG (route_PortOfLoading): Lấy từ ô "Port of Loading" trên Bill of Lading (ví dụ: 'HO CHI MINH', 'HAI PHONG', 'DA NANG'...). Bắt buộc là cảng biển hoặc sân bay tại Việt Nam, viết in hoa không dấu.
(10) CẢNG DỠ HÀNG (route_PortOfDischange & route_PortOfDestination): Lấy từ ô "Port of Discharge" hoặc "Place of Delivery" trên Bill of Lading (ví dụ: 'CEBU', 'KLAIPEDA', 'ROTTERDAM'...). Viết in hoa không dấu.
(11) TÊN TÀU / PHƯƠNG TIỆN (route_TransportName): Lấy từ ô "Ocean Vessel/Voyage No" trên Bill of Lading (ví dụ: 'EVER OMNI 063A', 'SEASPAN BENEFACTOR 077W'). Phương thức vận chuyển: route_TransportationType = 'By Sea'.
(12) NGÀY KHỞI HÀNH (route_DepartureDepartureDate): Lấy tại Mục 15 trên Đơn đề nghị Mẫu 04 hoặc ngày Shipped on board trên Bill of Lading, định dạng DD/MM/YYYY (ví dụ: '27/10/2026' hoặc '21/10/2026').
(13) MÃ HS (exportingHsCode & importingHsCode):
    - Mã HS xuất khẩu (exportingHsCode): ĐÚNG 8 CHỮ SỐ từ Mục 8 trên Đơn đề nghị Mẫu 04 (ví dụ: '03048700').
    - Mã HS nhập khẩu (importingHsCode): ĐÚNG 6 CHỮ SỐ ĐẦU của mã HS (theo chuẩn tra cứu quốc tế trên eCoSys, ví dụ: '030487').
(14) MÔ TẢ HÀNG HÓA (goodsDescription): Tiếng Anh in hoa từ Mục 9 trên Đơn đề nghị Mẫu 04 (ví dụ: 'FROZEN YELLOWFIN TUNA TRIMMEAT').
(15) TIÊU CHÍ XUẤT XỨ (originCriterion): Lấy từ Mục 10 trên Đơn đề nghị Mẫu 04 (ví dụ: 'WO', 'CTC', 'CTH', 'PSR', 'RVC 40%'...).
(16) SỐ LƯỢNG / TRỌNG LƯỢNG TỊNH (quantity): Trọng lượng tịnh Net Weight (NW) từ Mục 11 trên Đơn đề nghị Mẫu 04 (ví dụ: 25000.0).
(17) ĐƠN VỊ TÍNH SỐ LƯỢNG (quantityUnit): CHỈ DÙNG 'KILOGRAM' (hoặc 'TONNE', 'PIECE', 'SET'). TUYỆT ĐỐI KHÔNG dùng 'KILOGRAM, INCLUDING CONTAINER' hay bất kỳ biến thể bao bì nào!
(18) TỔNG TRỌNG LƯỢNG CẢ BÌ (grossWeight): Trọng lượng Gross Weight (GW) từ Mục 11 trên Đơn đề nghị Mẫu 04 hoặc trên Bill of Lading (ví dụ: 27250.0).
(19) ĐƠN VỊ TRỌNG LƯỢNG TỔNG (grossWeightUnit): CHỈ DÙNG 'KILOGRAM' (hoặc 'KGM'). TUYỆT ĐỐI KHÔNG dùng 'KILOGRAM, INCLUDING CONTAINER'.
(20) TRỊ GIÁ FOB (value & goods_Total_FobValue): Trị giá FOB từ Mục 12 trên Đơn đề nghị Mẫu 04 (ví dụ: 72500.0). Đồng tiền: 'USD - Dollar Mỹ'.
(21) SỐ LƯỢNG KIỆN HÀNG (packageQuantity): Lấy từ ô Particulars trên Bill of Lading hoặc Packing List / Invoice (ví dụ: 2000 kiện/thùng).
(22) LOẠI KIỆN HÀNG (packageUnit): Lấy từ Bill of Lading (ví dụ: 'CARTON' cho CTNS, 'BAG', 'BOX', 'PALLET'...).
- KÝ MÃ HIỆU BAO BÌ (markAndNumberOnPackage): Mặc định là 'NO MARK' nếu trên chứng từ ghi 'N/M' hoặc không có ký hiệu.
(23) SỐ HÓA ĐƠN THƯƠNG MẠI (invoiceNumber): Lấy tại Mục 13 trên Đơn đề nghị Mẫu 04 hoặc trên Commercial Invoice (ví dụ: 'HV60625').
(24) NGÀY HÓA ĐƠN THƯƠNG MẠI (invoiceDate): Lấy tại Mục 13 trên Đơn đề nghị Mẫu 04, định dạng DD/MM/YYYY (ví dụ: '22/10/2026').
(25) TÊN NHÀ SẢN XUẤT (manu_Name): Lấy tại Mục 6 trên Đơn đề nghị Mẫu 04 (ví dụ: 'HAI VUONG COMPANY LIMITED (HAVUCO)').
(26) ĐỊA CHỈ NHÀ SẢN XUẤT (manu_AddressLine1 & manu_AddressLine2): Lấy tại Mục 6 trên Đơn đề nghị Mẫu 04.
(27) SỐ TỜ KHAI HQ NHẬP KHẨU NGUYÊN LIỆU (importDeclarationNumbers): Dùng khi nguyên liệu nhập khẩu, lấy từ chứng từ Tờ khai nhập khẩu.
(28) NGÀY TỜ KHAI HQ NHẬP KHẨU NGUYÊN LIỆU (importDeclarationDates): Ngày tờ khai nhập khẩu nguyên liệu (DD/MM/YYYY).
(29) & (30) HÓA ĐƠN VAT MUA NGUYÊN LIỆU TRONG NƯỚC (invoiceVATList, invoiceVATNumbers, invoiceVATDates):
    - Dùng khi dùng nguyên liệu mua trong nước, lấy từ BẢNG KÊ KHAI KÈM HÓA ĐƠN (Cột 10 'Số hóa đơn' và Cột 11 'Ngày').
    - QUY TẮC CỰC KỲ QUAN TRỌNG:
      Trong bảng kê có thể có nhiều dòng hàng dùng chung 1 hóa đơn, hoặc có nhiều hóa đơn khác nhau.
      Trên web eCoSys, mỗi hóa đơn sẽ được thể hiện là 1 DÒNG HÀNG RIÊNG BIỆT (Số hóa đơn + Ngày tương ứng).
      Do đó, BẮT BUỘC PHẢI LỌC TRÙNG THEO CẶP (SỐ HÓA ĐƠN, NGÀY HÓA ĐƠN) để tạo ra danh sách CÁC HÓA ĐƠN DUY NHẤT.
      * Xuất vào `invoiceVATList`: Danh sách các cặp hóa đơn duy nhất [ { "declarationNumber": "00000083", "declarationDate": "31/05/2026" }, ... ]
      * Xuất vào `invoiceVATNumbers`: Danh sách các số hóa đơn cách nhau bằng dấu phẩy (ví dụ: '00000083, 00000088, 00000086').
      * Xuất vào `invoiceVATDates`: Danh sách các ngày hóa đơn tương ứng cách nhau bằng dấu phẩy (ví dụ: '31/05/2026, 05/06/2026, 02/06/2026').
    - Tương tự, nếu có nhiều Tờ khai HQ nhập khẩu nguyên liệu (27, 28), hãy lọc trùng và xuất vào `importDeclarationList`.

ĐẶC BIỆT VỀ MỤC 4 "BỘ HỒ SƠ ĐỀ NGHỊ CẤP C/O" TRÊN ĐƠN ĐỀ NGHỊ MẪU SỐ 04:
- Quan sát kỹ các ô vuông (checkbox) trong Mục 4 xem ô nào được đánh dấu tích [v] hoặc [x].
- Trích xuất danh sách các mã chứng từ được tích chọn vào trường `deNghiHoSoDinhKem`:
  * 'Mẫu C/O đã khai hoàn chỉnh' -> 'MauCO'
  * 'Tờ khai hải quan' -> 'ToKhaiXuatKhau'
  * 'Hóa đơn thương mại' -> 'Invoice_attached_Doc'
  * 'Vận tải đơn/chứng từ tương đương' -> 'VanDon'
  * 'Tờ khai hải quan nhập khẩu nguyên liệu' -> 'ToKhaiHQNK_Document'
  * 'Giấy phép xuất khẩu' -> 'GiayPhepXuatKhau'
  * 'Hóa đơn mua bán nguyên liệu trong nước' -> 'HoaDonVAT'
  * 'Hợp đồng mua bán' -> 'HopDongMuaBan'
  * 'Bảng tính toán hàm lượng giá trị khu vực' -> 'BangKeChiPhi'
  * 'Bản mô tả quy trình sản xuất ra sản phẩm' -> 'QuyTrinhSanXuat'
  * 'Các chứng từ khác: giấy cam kết, hóa đơn cước tàu' -> 'TAILIEUCHUNGMINH'

C/O CẤP SAU (ISSUED RETROSPECTIVELY / ISSUED RETROACTIVELY):
- Nếu trên Đơn đề nghị (Mục 17 hoặc Mục 3), Invoice, B/L có đóng dấu hoặc tích chọn: 'Issued retroactively', 'Issued retrospectively', 'C/O cấp sau':
  + Đặt: isIssuedRetroactively = True
  + Nếu có lý do cấp sau, điền vào: issuedRetroactivelyReason
  + TUYỆT ĐỐI KHÔNG ghi cụm từ 'Issued retroactively' vào ô remarks.

Tuân thủ nghiêm ngặt 100% định dạng JSON Schema được yêu cầu, không thêm bất kỳ văn bản giải thích nào ngoài JSON.
"""


def detect_mime_type(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    mapping = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff"
    }
    return mapping.get(ext, mimetypes.guess_type(file_path)[0] or "application/octet-stream")


def normalize_co_data(co_data: CODeclarationData) -> CODeclarationData:
    """
    Chuẩn hóa các trường cốt lõi theo quy định nghiệp vụ của cổng eCoSys Bộ Công Thương:
    - Nước nhập khẩu: Tuyệt đối không phải Vietnam
    - Cảng bốc hàng: Bắt buộc là cảng tại Việt Nam (hàng xuất khẩu)
    - Cảng dỡ hàng: Bắt buộc là cảng tại Nước ngoài
    - Phương thức vận chuyển: Chuẩn hóa về 'By Sea', 'By Air', 'By Truck', 'By Train'
    """
    # 1. Liên kết Tầng 1: Mẫu C/O -> Nước nhập khẩu (Importing Country)
    form_clean = (co_data.form or "").upper()
    if "VJ" in form_clean or "AJ" in form_clean:
        co_data.importing_Country = "Japan"
    elif "AK" in form_clean or "VK" in form_clean:
        co_data.importing_Country = "Korea"
    elif form_clean == "E":
        co_data.importing_Country = "China"
    elif co_data.importing_Country and co_data.importing_Country.strip().lower() in ["vietnam", "viet nam", "vn"]:
        addr = f"{co_data.to_Addressline2 or ''} {co_data.to_Addressline1 or ''}".upper()
        found_country = None
        for country in [
            "SPAIN", "GERMANY", "AUSTRIA", "FRANCE", "ITALY", "NETHERLANDS", "BELGIUM",
            "CHINA", "JAPAN", "KOREA", "TAIWAN", "UNITED STATES", "USA", "UNITED KINGDOM",
            "AUSTRALIA", "SINGAPORE", "MALAYSIA", "THAILAND", "PHILIPPINES", "INDONESIA"
        ]:
            if country in addr:
                found_country = country.title()
                break
        if found_country:
            co_data.importing_Country = found_country
        else:
            co_data.importing_Country = "Spain" if "EUR" in (co_data.form or "") else "China"

    # 2. Chuẩn hóa Cảng bốc hàng (route_PortOfLoading) - BẮT BUỘC là cảng Việt Nam
    pol = (co_data.route_PortOfLoading or "").upper()
    vn_ports = ["CAT LAI", "HAI PHONG", "DA NANG", "CAI MEP", "QUY NHON", "HO CHI MINH", "HCM", "SAI GON", "TAN SON NHAT", "NOI BAI"]
    if not any(p in pol for p in vn_ports):
        if "HAI PHONG" in (co_data.declarationPlace or "").upper():
            co_data.route_PortOfLoading = "HAI PHONG"
        else:
            co_data.route_PortOfLoading = "CAT LAI"

    # 3. Liên kết Tầng 2: Nước nhập khẩu -> Cảng dỡ hàng (route_PortOfDischange)
    pod = (co_data.route_PortOfDischange or "").upper()
    c_lower = (co_data.importing_Country or "").lower()
    
    if "japan" in c_lower or "nhat" in c_lower:
        jp_ports = ["TOKYO", "YOKOHAMA", "OSAKA", "KOBE", "NAGOYA", "HAKATA", "MOJI", "CHIBA"]
        if not any(p in pod for p in jp_ports):
            co_data.route_PortOfDischange = "TOKYO"
    elif "lithuania" in c_lower or "litva" in c_lower:
        co_data.importing_Country = "Lithuania"
        lt_ports = ["KLAIPEDA"]
        if not any(p in pod for p in lt_ports):
            co_data.route_PortOfDischange = "KLAIPEDA"
    elif "spain" in c_lower or "tay ban nha" in c_lower:
        sp_ports = ["VALENCIA", "BARCELONA", "ALGECIRAS", "BILBAO", "VIGO"]
        if not any(p in pod for p in sp_ports):
            co_data.route_PortOfDischange = "VALENCIA"
    elif "germany" in c_lower or "duc" in c_lower:
        de_ports = ["HAMBURG", "BREMEN", "BREMERHAVEN"]
        if not any(p in pod for p in de_ports):
            co_data.route_PortOfDischange = "HAMBURG"
    elif "china" in c_lower or "trung quoc" in c_lower:
        cn_ports = ["SHANGHAI", "NINGBO", "SHENZHEN", "GUANGZHOU", "QINGDAO", "TIANJIN"]
        if not any(p in pod for p in cn_ports):
            co_data.route_PortOfDischange = "SHANGHAI"
    elif "korea" in c_lower or "han quoc" in c_lower:
        kr_ports = ["BUSAN", "INCHEON", "GWANGYANG", "PYEONGTAEK", "ULSAN"]
        if not any(p in pod for p in kr_ports):
            co_data.route_PortOfDischange = "BUSAN"
    elif any(p in pod for p in ["HO CHI MINH", "CAT LAI", "HAI PHONG", "DA NANG", "VIETNAM", "HCM", "SAI GON"]):
        co_data.route_PortOfDischange = "TOKYO" if "VJ" in form_clean else "VALENCIA"

    # 4. Chuẩn hóa Phương thức vận chuyển (route_TransportationType)
    trans = (co_data.route_TransportationType or "").lower()
    if "air" in trans or "hàng không" in trans or "bay" in trans:
        co_data.route_TransportationType = "By Air"
    elif "truck" in trans or "bộ" in trans or "oto" in trans or "xe" in trans:
        co_data.route_TransportationType = "By Truck"
    elif "train" in trans or "sắt" in trans or "hoa" in trans:
        co_data.route_TransportationType = "By Train"
    else:
        co_data.route_TransportationType = "By Sea"

    return co_data


def repair_and_extract_json(raw: str) -> str:
    """
    Trích xuất và tự động sửa lỗi JSON bị cắt cụt (truncated/EOF) do AI chạm trần max_tokens.
    Bảo toàn toàn bộ dữ liệu đã sinh ra mà không làm sập ứng dụng.
    """
    text = (raw or "").strip()
    if "```" in text:
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
        text = text.strip()

    start_idx = text.find("{")
    if start_idx == -1:
        return text
    text = text[start_idx:]

    # 1. Thử parse trực tiếp
    try:
        json.loads(text)
        return text
    except Exception:
        pass

    # 2. Thuật toán phân tích cú pháp ký tự và sửa lỗi cắt cụt
    in_string = False
    escape = False
    cleaned_chars = []

    for c in text:
        if escape:
            escape = False
            cleaned_chars.append(c)
            continue
        if c == "\\":
            escape = True
            cleaned_chars.append(c)
            continue
        if c == '"':
            in_string = not in_string
            cleaned_chars.append(c)
            continue
        cleaned_chars.append(c)

    if in_string:
        cleaned_chars.append('"')

    working = "".join(cleaned_chars).rstrip()

    # Xóa các phần dở dang ở cuối và dấu phẩy thừa trước ngoặc đóng
    for _ in range(5):
        working = working.rstrip()
        working = re.sub(r',\s*$', '', working)
        working = re.sub(r',\s*([\}\]])', r'\1', working)
        working = re.sub(r',?\s*"[^"]*"\s*:\s*$', '', working)
        working = re.sub(r',?\s*"[^"]*"\s*$', '', working)
        working = re.sub(r',\s*$', '', working)

    # 3. Đếm số ngoặc còn thiếu để đóng
    in_str = False
    esc = False
    stack = []
    for c in working:
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if not in_str:
            if c in ("{", "["):
                stack.append(c)
            elif c == "}" and stack and stack[-1] == "{":
                stack.pop()
            elif c == "]" and stack and stack[-1] == "[":
                stack.pop()

    close_tags = []
    for b in reversed(stack):
        if b == "{":
            close_tags.append("}")
        elif b == "[":
            close_tags.append("]")

    repaired = working + "".join(close_tags)

    try:
        json.loads(repaired)
        return repaired
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            cand = match.group(0)
            try:
                json.loads(cand)
                return cand
            except Exception:
                pass
        return repaired


def extract_json_from_response(text: str) -> str:
    """Wrapper tương thích ngược gọi thuật toán sửa lỗi JSON thông minh"""
    return repair_and_extract_json(text)



def extract_co_data_via_apiz(
    api_key: str,
    file_paths: List[str],
    target_form: str = "EUR.1",
    model_name: str = "gemini-3.8-flash",
    base_url: str = "https://api.apiz.vn/v1",
    progress_cb = None
) -> Tuple[CODeclarationData, str]:
    """Trích xuất dữ liệu C/O qua cổng APIZ Vietnam Gateway (OpenAI-compatible HTTP Endpoint)"""
    if not base_url:
        base_url = "https://api.apiz.vn/v1"
    base_url = base_url.rstrip("/")

    if progress_cb:
        progress_cb(15, "Đang chuẩn bị và tối ưu hóa hình ảnh chứng từ...")

    user_contents = []

    prompt_text = (
        f"{SYSTEM_PROMPT}\n\n"
        f"LƯU Ý ĐẶC BIỆT CHO LÔ HÀNG NÀY:\n"
        f"- Mẫu C/O cần làm: Form {target_form}\n"
        f"- Hãy đọc tất cả các file đính kèm trên để trích xuất đầy đủ và điền vào JSON Schema theo yêu cầu.\n\n"
        f"YÊU CẦU ĐỊNH DẠNG: Bắt buộc trả về đúng định dạng JSON tuân thủ schema sau (không thêm văn bản giải thích ngoài JSON):\n"
        f"{json.dumps(CODeclarationData.model_json_schema(), ensure_ascii=False)}"
    )
    user_contents.append({"type": "text", "text": prompt_text})

    total_files = len(file_paths)
    for f_idx, p in enumerate(file_paths):
        if not os.path.exists(p):
            continue
        ext = os.path.splitext(p)[1].lower()
        if ext == ".pdf":
            try:
                doc = fitz.open(p)
                for page_idx in range(len(doc)):
                    page = doc[page_idx]
                    # Tối ưu hóa DPI=110 và chất lượng JPEG 75 để giảm 80% dung lượng payload, tăng tốc độ truyền
                    pix = page.get_pixmap(dpi=80)
                    b64 = base64.b64encode(pix.tobytes("jpeg", jpg_quality=60)).decode("utf-8")
                    user_contents.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                    })
            except Exception as e:
                print(f"Lỗi đọc PDF {p}: {e}")
        elif ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
            try:
                from PIL import Image
                import io
                img = Image.open(p).convert("RGB")
                w, h = img.size
                max_dim = 1280
                if max(w, h) > max_dim:
                    scale = max_dim / max(w, h)
                    img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=65, optimize=True)
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                user_contents.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                })
            except Exception as e:
                print(f"Lỗi nén ảnh {p}: {e}")

        if progress_cb:
            pct = 15 + int(((f_idx + 1) / total_files) * 25)
            progress_cb(pct, f"Đã nén chuẩn bị {f_idx + 1}/{total_files} chứng từ...")

    page_count = len(user_contents) - 1
    if progress_cb:
        progress_cb(45, f"Đang gửi {page_count} trang tài liệu đến AI {model_name}...")

    # Không giới hạn cứng token (để AI sinh tự nhiên theo toàn bộ dung lượng hồ sơ)
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": user_contents}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    url = f"{base_url}/chat/completions"
    max_retries = 3
    raw_text = None
    last_err = None

    for attempt in range(1, max_retries + 1):
        try:
            if progress_cb:
                msg = f"AI {model_name} đang phân tích 30 trường dữ liệu C/O..."
                if attempt > 1:
                    msg = f"Đang thử kết nối lại máy chủ AI lần {attempt}/{max_retries}..."
                progress_cb(55 + (attempt - 1) * 5, msg)

            resp = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=(30, 240)
            )

            if resp.status_code == 200:
                res = resp.json()
                raw_text = res["choices"][0]["message"]["content"]
                break
            elif resp.status_code in [500, 502, 503, 504]:
                last_err = f"Máy chủ AI phản hồi mã lỗi {resp.status_code}: {resp.text[:200]}"
                if attempt < max_retries:
                    time.sleep(3)
                    continue
            else:
                resp.raise_for_status()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as net_err:
            last_err = net_err
            if attempt < max_retries:
                if progress_cb:
                    progress_cb(55, f"⚠️ Mạng gián đoạn (10054), tự động kết nối lại lần {attempt + 1}/{max_retries}...")
                time.sleep(3)
            else:
                raise Exception(
                    f"Kết nối đến máy chủ AI bị gián đoạn (WinError 10054). "
                    f"Nguyên nhân do đường truyền mạng không ổn định hoặc máy chủ AI tạm thời quá tải. Vui lòng thử lại sau vài giây! Chi tiết: {net_err}"
                )

    if not raw_text:
        raise Exception(f"Không nhận được phản hồi từ AI: {last_err}")

    if progress_cb:
        progress_cb(85, "Đang bóc tách và chuẩn hóa định dạng JSON eCoSys...")

    clean_json = repair_and_extract_json(raw_text)
    try:
        co_data = CODeclarationData.model_validate_json(clean_json)
    except Exception as val_err:
        try:
            # Fallback parse dict để chấp nhận bỏ qua phần lỗi cục bộ nếu có
            dict_data = json.loads(clean_json)
            co_data = CODeclarationData.model_validate(dict_data)
        except Exception:
            raise val_err

    if not co_data.form:
        co_data.form = target_form

    co_data = normalize_co_data(co_data)
    raw_json = co_data.model_dump_json(indent=2)
    return co_data, raw_json


def ask_co_advisor_via_apiz(
    api_key: str,
    question: str,
    history: List[dict] = None,
    model_name: str = "gemini-3.8-flash",
    base_url: str = "https://api.apiz.vn/v1"
) -> str:
    """Tư vấn nghiệp vụ C/O qua cổng APIZ Vietnam Gateway"""
    if not base_url:
        base_url = "https://api.apiz.vn/v1"
    base_url = base_url.rstrip("/")

    messages = [{"role": "system", "content": CO_ADVISOR_SYSTEM_PROMPT}]
    if history:
        for msg in history[-8:]:
            role = "user" if msg.get("role") == "user" else "assistant"
            txt = msg.get("text", "")
            if txt:
                messages.append({"role": role, "content": txt})

    messages.append({"role": "user", "content": question})

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.3
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    url = f"{base_url}/chat/completions"
    for attempt in range(1, 3):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=(15, 90))
            if resp.status_code == 200:
                res = resp.json()
                return res["choices"][0]["message"]["content"]
            elif resp.status_code in [500, 502, 503, 504] and attempt < 2:
                time.sleep(2)
                continue
            else:
                resp.raise_for_status()
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue
            return f"❌ Lỗi kết nối trợ lý AI (10054/Timeout): {e}. Vui lòng thử lại!"
    return "❌ Không thể kết nối đến trợ lý AI."


def create_gemini_client(api_key: str, api_source: str = "official", api_base_url: str = "") -> genai.Client:
    """Khởi tạo Gemini Client hỗ trợ Google Gemini Official"""
    if not api_key:
        raise ValueError("Vui lòng nhập API Key (Google Gemini hoặc APIZ) để tiếp tục.")
    
    return genai.Client(api_key=api_key)


def extract_co_data_from_files(
    api_key: str,
    file_paths: List[str],
    target_form: str = "EUR.1",
    model_name: str = "gemini-3.8-flash",
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

    # 2. Xử lý Google Gemini Official (Model chính thức: gemini-3.8-flash)
    if not model_name or model_name == "default":
        model_name = "gemini-3.8-flash"

    candidate_models = [model_name]
    for fallback_m in ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
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
        f"{SYSTEM_PROMPT}\n\n"
        f"LƯU Ý ĐẶC BIỆT CHO LÔ HÀNG NÀY:\n"
        f"- Mẫu C/O cần làm: Form {target_form}\n"
        f"- Hãy đọc tất cả các file đính kèm trên để trích xuất đầy đủ và điền vào JSON Schema theo yêu cầu.\n"
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


CO_ADVISOR_SYSTEM_PROMPT = """Bạn là Trợ lý AI Chuyên gia Cấp cao Toàn diện về 2 nghiệp vụ Xuất Nhập Khẩu trọng yếu:
1. Nghiệp vụ Khai báo C/O Điện tử (eCoSys) thuộc Bộ Công Thương Việt Nam.
2. Nghiệp vụ Chống khai thác hải sản bất hợp pháp (IUU) & Đối chiếu Xác nhận Nguyên liệu Thủy sản (Giấy SC Cảng cá - Mẫu 01 / XNNL) thuộc Bộ Nông nghiệp & PTNT.

NHIỆM VỤ CỤ THỂ CỦA BẠN:

A. VỀ NGHIỆP VỤ C/O & ECOSYS (BỘ CÔNG THƯƠNG):
1. Tư vấn nghiệp vụ xuất xứ hàng hóa chính xác theo các văn bản quy phạm pháp luật:
   - Nghị định 31/2018/NĐ-CP (Quy định chi tiết Luật Quản lý ngoại thương về xuất xứ hàng hóa).
   - Thông tư 11/2020/TT-BCT (Quy tắc xuất xứ EVFTA - Mẫu EUR.1).
   - Thông tư 05/2018/TT-BCT (Quy định chung về xuất xứ hàng hóa).
   - Các hiệp định FTA: Form D (ATIGA), Form E (ACFTA), Form AK/VK (Hàn Quốc), Form AJ/VJ (Nhật Bản), CPTPP, AANZFTA, RCEP...
2. Giải thích cặn kẽ các Tiêu chí xuất xứ:
   - WO (Wholly Obtained - Xuất xứ thuần túy): Thủy hải sản đánh bắt bởi tàu treo cờ Việt Nam trong vùng biển Việt Nam hoặc vùng đặc quyền kinh tế.
   - CTC (Change in Tariff Classification): Chuyển đổi mã HS ở cấp 2 số (CC), 4 số (CTH), 6 số (CTSH).
   - RVC (Regional Value Content): Hàm lượng giá trị khu vực >= 40%, công thức tính trực tiếp và gián tiếp.
   - De Minimis (Tỷ lệ không đáp ứng CTC linh hoạt không quá 10% giá FOB).
   - PSR (Product Specific Rules - Quy tắc cụ thể mặt hàng).
3. Hướng dẫn hồ sơ C/O Mẫu 04:
   - Đơn Mẫu 04, Bảng kê chi phí BOM, Tờ khai xuất khẩu, Vận đơn (B/L) có ngày On Board, Commercial Invoice.
   - Khóa cứng đơn vị tính KILOGRAM theo chuẩn form eCoSys.
   - Bảng đa dòng Tờ khai nhập khẩu NVL và Hóa đơn VAT mua NVL nội địa.
   - Tự động điền qua Extension Chrome v2.6.0 và xử lý lỗi chữ ký số Token.

B. VỀ NGHIỆP VỤ IUU & XÁC NHẬN NGUYÊN LIỆU THỦY SẢN (SC CẢNG CÁ):
1. Căn cứ pháp lý IUU:
   - Luật Thủy sản 2017, Nghị định 26/2019/NĐ-CP, Nghị định 37/2024/NĐ-CP.
   - Thông tư 21/2018/TT-BNNPTNT và Thông tư 01/2022/TT-BNNPTNT về quản lý hồ sơ truy xuất nguồn gốc thủy sản khai thác.
2. Thẩm định Giấy xác nhận SC gốc (Mẫu 01 Cảng cá):
   - Kiểm tra số hiệu tàu cá, tên chủ tàu, tên thuyền trưởng, số Giấy phép khai thác thủy sản (GPKTTS), hạn phép khai thác (phải còn hiệu lực trong suốt chuyến biển).
   - Kiểm tra vùng biển khai thác, thời gian chuyến biển (từ ngày... đến ngày...), ngày cập cảng / lên cá.
   - Khối lượng khai thác từng loài cá cập cảng (kg).
3. Hướng dẫn xử lý sai lệch giữa SC gốc và Phần mềm sản xuất (PMSX) / Excel Phụ lục 02a:
   - Sai tên Chủ tàu / Thuyền trưởng: Giải thích nguyên nhân do chuyển nhượng quyền sở hữu tàu chưa sang tên trên hệ thống, hoặc chủ tàu thuê thuyền trưởng điều khiển tàu; hướng dẫn lập bản cam kết / giải trình kèm theo.
   - Sai hạn GPKTTS: Kiểm tra lại ngày cấp gia hạn giấy phép tại Chi cục Thủy sản.
   - Quy tắc gộp lượng tàu cá (Aggregation Rule): Khi cùng 1 tàu cập cảng/lên cá cùng ngày, phần mềm tự động cộng dồn khối lượng thành 1 dòng duy nhất để tránh trùng lặp dòng hàng.
   - Chuẩn bị hồ sơ nộp cho Chi cục Thủy sản hoặc NAFIQPM để cấp Giấy chứng nhận nguồn gốc thủy sản (Catch Certificate - CC) xuất sang thị trường Châu Âu (EU), Mỹ, Nhật Bản.
4. Mối liên kết giữa SC và C/O:
   - Giấy xác nhận SC gốc là chứng từ đầu vào bắt buộc để chứng minh nguồn gốc hợp pháp của lô cá; sau đó số liệu khối lượng và giá trị sẽ được nạp vào Bảng kê BOM để xin cấp C/O Mẫu EUR.1 (EVFTA) với tiêu chí WO.

PHONG CÁCH TRẢ LỜI:
- Chuyên nghiệp, nhã nhặn, am hiểu sâu sắc cả 2 nghiệp vụ ngoại thương và thủy sản.
- Viện dẫn căn cứ pháp lý, nghị định, thông tư rõ ràng.
- Trình bày mạch lạc bằng gạch đầu dòng, bảng biểu, in đậm Markdown dễ đọc, dễ áp dụng ngay vào thực tế."""


def ask_co_advisor(
    api_key: str,
    question: str,
    history: List[dict] = None,
    api_source: str = "official",
    api_base_url: str = "",
    model_name: str = "gemini-3.8-flash"
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

    if not model_name or model_name == "default":
        model_name = "gemini-3.8-flash"

    candidate_models = [model_name]
    for fallback_m in ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
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
                    contents="\n\n".join(contents),
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
