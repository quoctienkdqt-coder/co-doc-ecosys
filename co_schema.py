"""
Định nghĩa Pydantic Schema cho Hồ sơ Khai báo C/O
Khớp 100% với cấu trúc trường của hệ thống eCoSys (https://co.moit.gov.vn/hoSo/KhaiBaoCO)
"""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class GoodItem(BaseModel):
    exportingHsCode: str = Field(
        default="", 
        description="Mã HS xuất khẩu đúng 8 chữ số, không có dấu chấm (ví dụ: 08013100, 09011110)"
    )
    importingHsCode: Optional[str] = Field(
        default="", 
        description="Mã HS nước nhập khẩu (Mục 13 trên eCoSys: lấy 6 số đầu của HS code)"
    )
    goodsDescription: str = Field(
        default="", 
        description="Tên và mô tả chi tiết hàng hóa bằng tiếng Anh in hoa không dấu"
    )
    originCriterion: str = Field(
        default="WO", 
        description="Tiêu chí xuất xứ C/O (ví dụ: WO, PE, RVC 40%, CTC, CTH, PSR...)"
    )
    countryOfOrigin: str = Field(
        default="VN", 
        description="Nước xuất xứ hàng hóa: VN"
    )
    quantity: float = Field(
        default=0.0, 
        description="Số lượng hàng hóa (số thập phân, ví dụ: 10.0)"
    )
    quantityUnit: str = Field(
        default="KILOGRAM", 
        description="Tên đơn vị tính số lượng chuẩn trên eCoSys: 'KILOGRAM', 'TONNE', 'PIECE', 'SET', 'DOZEN', 'PAIR'..."
    )
    markAndNumberOnPackage: Optional[str] = Field(
        default="NO MARK", 
        description="Ký mã hiệu bao bì (Marks and numbers). Mặc định 'N/M' (No Mark) nếu không có"
    )
    packageQuantity: Optional[int] = Field(
        default=1, 
        description="Số lượng kiện hàng (số nguyên, ví dụ: 200)"
    )
    packageUnit: Optional[str] = Field(
        default="BAG", 
        description="Loại kiện bao bì chuẩn trên eCoSys: 'BAG', 'CARTON', 'PALLET', 'PACKAGE', 'BOX', 'DRUM'..."
    )
    grossWeight: float = Field(
        default=0.0, 
        description="Tổng trọng lượng cả bì tính bằng kg (số thập phân, ví dụ: 10100.0)"
    )
    grossWeightUnit: str = Field(
        default="KILOGRAM", 
        description="Đơn vị trọng lượng tổng: 'KILOGRAM' hoặc 'TONNE'"
    )
    value: float = Field(
        default=0.0, 
        description="Trị giá FOB của hàng hóa (ví dụ: 16000.0)"
    )
    currency: str = Field(
        default="USD - Dollar Mỹ", 
        description="Đồng tiền thanh toán (ví dụ: 'USD - Dollar Mỹ' hoặc 'EUR - Đồng Euro')"
    )
    invoiceNumber: Optional[str] = Field(
        default="", 
        description="Số hóa đơn thương mại áp dụng cho mặt hàng này"
    )
    invoiceDate: Optional[str] = Field(
        default="", 
        description="Ngày hóa đơn thương mại (DD/MM/YYYY)"
    )


class AttachmentFile(BaseModel):
    fileName: str = Field(
        default="", 
        description="Tên tệp gốc kèm phần mở rộng (ví dụ: ToKhaiHQ_105678912340.pdf, Invoice_INV2026.pdf)"
    )
    fileType: str = Field(
        default="TAILIEUCHUNGMINH", 
        description="Loại chứng từ trên eCoSys: 'ToKhaiXuatKhau', 'HoaDonVAT', 'VanDon', 'BangKeChiPhi', 'TAILIEUCHUNGMINH'"
    )
    fileSize: Optional[int] = Field(
        default=0, 
        description="Dung lượng tệp (bytes)"
    )
    mimeType: Optional[str] = Field(
        default="application/pdf", 
        description="Định dạng MIME (application/pdf, image/jpeg, image/png)"
    )
    base64: Optional[str] = Field(
        default="", 
        description="Nội dung tệp nhị phân được mã hóa chuỗi Base64 để Extension nạp trực tiếp lên web"
    )


class InvoiceVATItem(BaseModel):
    declarationNumber: str = Field(
        default="", 
        description="Số hóa đơn VAT mua nguyên liệu trong nước (Mục 29 trên form)"
    )
    declarationDate: str = Field(
        default="", 
        description="Ngày hóa đơn VAT (DD/MM/YYYY) (Mục 30 trên form)"
    )


class ImportDeclarationItem(BaseModel):
    declarationNumber: str = Field(
        default="", 
        description="Số tờ khai hải quan nhập khẩu nguyên liệu (Mục 27 trên form)"
    )
    declarationDate: str = Field(
        default="", 
        description="Ngày tờ khai hải quan nhập khẩu nguyên liệu (DD/MM/YYYY) (Mục 28 trên form)"
    )


class CODeclarationData(BaseModel):
    form: str = Field(
        default="EUR.1", 
        description="Mã mẫu C/O (EUR.1, E, D, AK, AJ, CPTPP, VJ...)"
    )
    issuing_Authority: Optional[str] = Field(
        default="Sở Công Thương tỉnh Khánh Hòa - Cấp sở", 
        description="Tổ chức/Phòng Quản lý XNK cấp C/O"
    )
    importing_Country: str = Field(
        default="Austria", 
        description="Tên quốc gia nhập khẩu bằng tiếng Anh (ví dụ: Austria, Germany, China, Japan...)"
    )
    declarationPlace: Optional[str] = Field(
        default="Khánh Hòa", 
        description="Nơi làm thủ tục khai báo (Tỉnh/Thành phố)"
    )
    
    # Doanh nghiệp xuất khẩu (Exporter)
    taxCode: Optional[str] = Field(
        default="", 
        description="Mã số thuế doanh nghiệp xuất khẩu"
    )
    maSoDN: Optional[str] = Field(
        default="", 
        description="Mã số doanh nghiệp"
    )
    from_ExporterBusinessName: str = Field(
        default="", 
        description="Tên doanh nghiệp xuất khẩu bằng tiếng Anh in hoa không dấu"
    )
    from_ExporterBusinessNameVN: Optional[str] = Field(
        default="", 
        description="Tên doanh nghiệp xuất khẩu bằng tiếng Việt có dấu"
    )
    from_AddressLine1: str = Field(
        default="", 
        description="Địa chỉ doanh nghiệp xuất khẩu dòng 1 (tiếng Anh không dấu)"
    )
    from_Addressline2: Optional[str] = Field(
        default="", 
        description="Địa chỉ doanh nghiệp xuất khẩu dòng 2"
    )
    
    # Người nhập khẩu (Consignee / Importer)
    to_ConsigneeName: str = Field(
        default="", 
        description="Tên công ty nhập khẩu (tiếng Anh in hoa)"
    )
    to_Addressline1: str = Field(
        default="", 
        description="Địa chỉ công ty nhập khẩu dòng 1"
    )
    to_Addressline2: Optional[str] = Field(
        default="", 
        description="Địa chỉ công ty nhập khẩu dòng 2"
    )

    # Nhà sản xuất (Manufacturer)
    manu_Name: Optional[str] = Field(
        default="", 
        description="Tên nhà sản xuất (Mục 6 trên Đơn đề nghị Mẫu số 04 - Mục 25)"
    )
    manu_AddressLine1: Optional[str] = Field(
        default="", 
        description="Địa chỉ nhà sản xuất dòng 1 (Mục 26)"
    )
    manu_AddressLine2: Optional[str] = Field(
        default="", 
        description="Địa chỉ nhà sản xuất dòng 2"
    )
    
    # Thông tin vận chuyển (Transportation)
    route_TransportationType: str = Field(
        default="By Sea", 
        description="Phương thức vận chuyển, BẮT BUỘC là 1 trong các giá trị: 'By Sea', 'By Air', 'By Truck', 'By Train', 'Others'"
    )
    route_TransportName: str = Field(
        default="", 
        description="Tên tàu và số chuyến (ví dụ: SITC FANGCHENG / V.2415N)"
    )
    route_PortOfLoading: str = Field(
        default="HAI PHONG", 
        description="Cảng bốc hàng in hoa không dấu (ví dụ: HAI PHONG, DA NANG, CAT LAI, HO CHI MINH...)"
    )
    route_PortOfDischange: str = Field(
        default="HAMBURG", 
        description="Cảng dỡ hàng in hoa không dấu (ví dụ: HAMBURG, ROTTERDAM, SHANGHAI, INCHEON...)"
    )
    route_PortOfDestination: Optional[str] = Field(
        default="HAMBURG", 
        description="Cảng hoặc điểm đến cuối cùng"
    )
    route_DepartureDepartureDate: Optional[str] = Field(
        default="", 
        description="Ngày khởi hành / Ngày tàu chạy (DD/MM/YYYY)"
    )
    bill: Optional[str] = Field(
        default="", 
        description="Số vận đơn (Bill of Lading số)"
    )
    
    # Hóa đơn thương mại (Commercial Invoice)
    invoiceNumber: str = Field(
        default="", 
        description="Số hóa đơn thương mại (Invoice No)"
    )
    invoiceDate: str = Field(
        default="", 
        description="Ngày phát hành hóa đơn (DD/MM/YYYY)"
    )
    currency: str = Field(
        default="USD - Dollar Mỹ", 
        description="Đồng tiền thanh toán: 'USD - Dollar Mỹ' hoặc 'EUR - Đồng Euro'"
    )
    goods_Total_FobValue: Optional[float] = Field(
        default=0.0, 
        description="Tổng trị giá FOB toàn bộ lô hàng"
    )
    
    # Tờ khai hải quan xuất khẩu (Export Declaration - Mục 3, 4)
    declarationNumbers: Optional[str] = Field(
        default="", 
        description="Số tờ khai hải quan xuất khẩu (11-12 chữ số) - Mục (3)"
    )
    declarationDates: Optional[str] = Field(
        default="", 
        description="Ngày tờ khai hải quan xuất khẩu (DD/MM/YYYY) - Mục (4)"
    )

    # Tờ khai hải quan nhập khẩu nguyên liệu (Import Declaration - Mục 27, 28)
    importDeclarationNumbers: Optional[str] = Field(
        default="", 
        description="Số tờ khai hải quan nhập khẩu nguyên liệu (dùng khi nguyên liệu nhập khẩu) - Mục (27)"
    )
    importDeclarationDates: Optional[str] = Field(
        default="", 
        description="Ngày tờ khai hải quan nhập khẩu nguyên liệu (DD/MM/YYYY) - Mục (28)"
    )

    # Danh sách hóa đơn VAT mua nguyên liệu trong nước (mỗi hóa đơn là 1 dòng trên eCoSys - Mục 29, 30)
    invoiceVATList: Optional[List[InvoiceVATItem]] = Field(
        default_factory=list,
        description="Danh sách các hóa đơn VAT mua nguyên liệu trong nước (đã lọc trùng từ Bảng kê: mỗi hóa đơn là 1 dòng trên eCoSys)"
    )
    invoiceVATNumbers: Optional[str] = Field(
        default="", 
        description="Danh sách số hóa đơn VAT (chuỗi hoặc phân cách dấu phẩy) - Mục (29)"
    )
    invoiceVATDates: Optional[str] = Field(
        default="", 
        description="Danh sách ngày hóa đơn VAT (chuỗi hoặc phân cách dấu phẩy) - Mục (30)"
    )

    # Danh sách tờ khai hải quan nhập khẩu nguyên liệu (mỗi tờ khai là 1 dòng trên eCoSys - Mục 27, 28)
    importDeclarationList: Optional[List[ImportDeclarationItem]] = Field(
        default_factory=list,
        description="Danh sách các tờ khai hải quan nhập khẩu nguyên liệu (mỗi tờ khai là 1 dòng trên eCoSys)"
    )
    
    # Ghi chú
    remarks: Optional[str] = Field(
        default="", 
        description="Ghi chú đặc biệt trên C/O (nếu có). TUYỆT ĐỐI KHÔNG ghi 'Issued retroactively' vào đây!"
    )
    isIssuedRetroactively: Optional[bool] = Field(
        default=False,
        description="Đánh dấu True nếu có yêu cầu C/O cấp sau (Issued Retrospectively / Issued Retroactively). Khi đó KHÔNG ghi vào ô remarks."
    )
    issuedRetroactivelyReason: Optional[str] = Field(
        default="",
        description="Lý do xin cấp sau nếu có"
    )
    
    # Danh mục hồ sơ đề nghị cấp C/O (Mục 4 trên Đơn đề nghị Mẫu số 04)
    deNghiHoSoDinhKem: Optional[List[str]] = Field(
        default_factory=list,
        description=(
            "Danh sách mã loại chứng từ được tích chọn (đánh dấu [v]/[x]) tại Mục 4 'Bộ hồ sơ đề nghị cấp C/O' "
            "trong Đơn đề nghị cấp C/O (Mẫu số 04). Gồm các mã: 'ToKhaiXuatKhau', 'Invoice_attached_Doc', "
            "'HoaDonVAT', 'VanDon', 'QuyTrinhSanXuat', 'ToKhaiHQNK_Document', 'BangKeChiPhi', 'HopDongMuaBan', "
            "'GiayPhepXuatKhau', 'TAILIEUCHUNGMINH'."
        )
    )

    # Danh sách mặt hàng chi tiết
    goodItems: List[GoodItem] = Field(
        default_factory=list, 
        description="Danh sách các dòng hàng hóa chi tiết khai báo trên C/O"
    )

    # Danh sách tệp đính kèm (Attachments)
    attachments: Optional[List[AttachmentFile]] = Field(
        default_factory=list,
        description="Danh sách các tệp tin đính kèm (base64) để Extension tự động nạp lên hệ thống eCoSys"
    )

    @field_validator(
        "importDeclarationList",
        "invoiceVATList",
        "goodItems",
        "attachments",
        "deNghiHoSoDinhKem",
        mode="before"
    )
    @classmethod
    def ensure_list_not_none(cls, v):
        if v is None:
            return []
        return v

