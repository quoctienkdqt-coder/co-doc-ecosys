# 🚢 Hệ Thống Quản Trị Xuất Nhập Khẩu & Thủy Sản Toàn Diện (v3.1.0)
### Hợp nhất eCoSys C/O (Bộ Công Thương) & Đối Chiếu Xác Nhận Nguyên Liệu SC Cảng Cá (Bộ NN&PTNT)

> ⚠️ **CHÚ Ý QUAN TRỌNG VỀ TRÍ TUỆ NHÂN TẠO (AI):**  
> Trí tuệ nhân tạo (AI Gemini 3.8 Flash) chỉ mang tính chất **tham khảo và hỗ trợ nghiệp vụ**. Mọi quyết định, số liệu phê duyệt và kết quả kiểm tra cuối cùng **hoàn toàn do con người** rà soát trước khi ký số nộp hồ sơ lên cơ quan chức năng.
> 
> © **BẢN QUYỀN PHẦN MỀM VÀ PHÁT TRIỂN BỞI:**  
> **Ngô Quốc Tiến** • Hotline / Zalo: **0905387808**

---

## 🌟 Các Phân Hệ Nghiệp Vụ Trọng Yếu

1. **Phân hệ 1: Khai báo C/O Điện tử eCoSys (Bộ Công Thương)**
   * Đọc hiểu và trích xuất đồng thời toàn bộ chứng từ (Đơn Mẫu 04, Invoice, Packing List, Tờ khai xuất khẩu, Vận đơn B/L, Bảng kê chi phí BOM, Hóa đơn VAT, Tờ khai nhập khẩu NVL).
   * Khóa cứng chuẩn đơn vị tính `KILOGRAM` theo yêu cầu eCoSys.
   * Tự động lọc trùng và tạo danh sách đa dòng cho Hóa đơn VAT và Tờ khai nhập khẩu.
   * Điền tự động siêu tốc qua Chrome / Edge Extension **v2.8.0** kết hợp công nghệ **Direct Stream Bridge (Cổng 14008)** đính kèm tệp tức thì.

2. **Phân hệ 2: Đối Chiếu Giấy SC Cảng Cá & XNNL PMSX (Hồ sơ IUU)**
   * Tự động quét và đọc hiểu Giấy SC gốc cảng cá bằng thị giác AI Gemini 3.8 Flash.
   * Đọc bảng Excel Phần mềm sản xuất (PMSX) và tự động gộp sản lượng các tàu cá cập cảng trùng ngày.
   * Đối chiếu chéo 7 tiêu chí trọng yếu: Số hiệu tàu cá, Chủ tàu, Nghề khai thác, Số GPKTTS, Hạn GPKTTS, Ngày bốc dỡ, Khối lượng nguyên liệu mua (kg).
   * Xuất báo cáo Excel phân tích màu trực quan (Khớp 100%, Lệch trọng yếu, Thiếu hồ sơ) và tự động tạo File Excel đã chuẩn hóa.

3. **Phân hệ 3: Trợ Lý Chuyên Gia AI Copilot Song Hành**
   * Giải đáp cặn kẽ quy tắc xuất xứ các hiệp định FTA (EVFTA - Form EUR.1, ATIGA - Form D, ACFTA - Form E, CPTPP, RCEP...).
   * Hướng dẫn nghiệp vụ xử lý hồ sơ IUU thủy sản xuất khẩu sang EU, Mỹ, Nhật Bản.

4. **Phân hệ 4: Tự Động Cập Nhật Phần Mềm Qua GitHub**
   * Cho phép kiểm tra phiên bản mới trực tiếp từ kho lưu trữ GitHub.
   * Tự động sao lưu an toàn toàn bộ mã nguồn cũ vào `backups_update/` trước khi áp dụng bản mới.

---

## 🛠️ Hướng Dẫn Cài Đặt & Sử Dụng

### Cách 1: Cài đặt bằng File Setup Tự Động (.exe)
1. Tải file `CaiDat_XNK_eCoSys_SC_v3.1.exe` từ mục **Releases** trên GitHub.
2. Mở file cài đặt, chọn thư mục muốn lưu và bấm **Bắt đầu cài đặt**.
3. Phần mềm sẽ tự động tạo biểu tượng trên **Màn hình Desktop** và **Start Menu**.

### Cách 2: Chạy trực tiếp từ mã nguồn Python
```powershell
# 1. Cài đặt các thư viện cần thiết
pip install PyQt6 openpyxl pymupdf google-genai requests pillow rapidocr_onnxruntime

# 2. Khởi chạy ứng dụng hợp nhất
python app_unified_suite.py
```

---

## 🌐 Hướng Dẫn Cài Tiện Ích Chrome Extension (v2.8.0)
1. Mở trình duyệt Chrome hoặc Edge, truy cập: `chrome://extensions` (hoặc `edge://extensions`).
2. Bật công tắc **"Chế độ dành cho nhà phát triển" (Developer mode)** ở góc trên bên phải.
3. Bấm nút **"Tải tiện ích đã giải nén" (Load unpacked)** ➔ Trỏ vào thư mục `extension/`.
4. Mở trang khai báo C/O trên eCoSys (`https://co.moit.gov.vn/hoSo/KhaiBaoCO`), bấm biểu tượng tiện ích để điền toàn bộ hồ sơ trong 2 giây.

---

## 📞 Hỗ Trợ Kỹ Thuật & Bản Quyền
* **Tác giả & Phát triển:** Ngô Quốc Tiến
* **Hotline / Zalo:** `0905387808`
* **Cập nhật & Báo lỗi:** Sử dụng tính năng **`🔄 Cập nhật GitHub`** trực tiếp trong ứng dụng.
