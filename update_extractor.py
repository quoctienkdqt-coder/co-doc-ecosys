import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('app_co_extractor.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = 'tools_layout.addWidget(btn_organize_folder)'
if target in text:
    replacement = '''tools_layout.addWidget(btn_organize_folder)
        btn_guide_naming = QPushButton("💡 Hướng dẫn đặt tên chứng từ")
        btn_guide_naming.setStyleSheet("font-weight: bold; color: #047857; background-color: #d1fae5; border: 1px solid #6ee7b7; padding: 4px 10px; border-radius: 4px;")
        btn_guide_naming.clicked.connect(self.show_attachment_naming_guide)
        tools_layout.addWidget(btn_guide_naming)'''
    text = text.replace(target, replacement, 1)

guide_method = '''    def show_attachment_naming_guide(self):
        guide = (
            "📌 QUY TẮC ĐẶT TÊN CHỨNG TỪ ĐỂ ĐÍNH KÈM CHÍNH XÁC 100% LÊN ECOSYS:\\n\\n"
            "1️⃣ Bảng kê chi phí / BOM / TT 05:\\n"
            "   • Đặt tên chứa: 'bang ke', 'bangke', 'bom', 'phuluc'\\n"
            "   • Ví dụ: bang ke WO_HL.pdf, bang_ke_chi_phi.pdf\\n"
            "   • Vị trí eCoSys: Dòng 1 bảng Document Proving (Bảng phụ lục theo Thông tư 05)\\n\\n"
            "2️⃣ Vận đơn (B/L / Sea Waybill):\\n"
            "   • Đặt tên chứa: 'bill', 'bl', 'vandon', 'waybill'\\n"
            "   • Ví dụ: bill.pdf, bill_tau.pdf, BL_Sea.pdf\\n"
            "   • Vị trí eCoSys: Mục 21, 22 (Tài liệu vận tải đính kèm / TRANSPORT_INFO)\\n\\n"
            "3️⃣ Hóa đơn thương mại / Đơn đề nghị cấp C/O:\\n"
            "   • Đặt tên chứa: 'inv', 'invoice', 'don', 'denghi'\\n"
            "   • Ví dụ: don CO,inv.pdf, Commercial_Invoice.pdf\\n"
            "   • Vị trí eCoSys: Mục 24 (Invoice attached) hoặc Dòng 4 bảng Document Proving\\n\\n"
            "4️⃣ Hóa đơn VAT mua nguyên phụ liệu trong nước:\\n"
            "   • Đặt tên chứa: 'vat' HOẶC chính là SỐ HÓA ĐƠN\\n"
            "   • Ví dụ: 00000457.pdf, vat_00000457.pdf, HD_457.pdf\\n"
            "   • Vị trí eCoSys: Tự động gắn vào đúng dòng HĐ VAT có số 00000457 ở Mục 29, 30\\n\\n"
            "5️⃣ Quy trình sản xuất:\\n"
            "   • Đặt tên chứa: 'quytrinh', 'sanxuat', 'process'\\n"
            "   • Ví dụ: quy trinh san xuat.pdf\\n"
            "   • Vị trí eCoSys: Dòng 2 bảng Document Proving (Bản mô tả quy trình sản xuất)\\n\\n"
            "6️⃣ Tờ khai hải quan nhập khẩu NVL:\\n"
            "   • Đặt tên chứa: 'nhap' HOẶC chính là SỐ TỜ KHAI\\n"
            "   • Ví dụ: TK_Nhap_1056789.pdf, 1056789.pdf\\n"
            "   • Vị trí eCoSys: Tự động gắn vào dòng Tờ khai NK tương ứng ở Mục 27, 28\\n\\n"
            "7️⃣ Tờ khai hải quan xuất khẩu:\\n"
            "   • Đặt tên chứa: 'to khai xuat', 'tk_xuat'\\n"
            "   • Vị trí eCoSys: Mục 25 (Export declaration attached)\\n\\n"
            "💡 MẸO: Bạn có thể bấm nút '📁 Gom & Chuẩn hóa thư mục chứng từ' để phần mềm tự động đổi tên và gom toàn bộ file thành chuẩn 01_..., 02_... trong 1 giây!"
        )
        QMessageBox.information(self, "Hướng dẫn đặt tên chứng từ eCoSys", guide)

'''

pos_org = text.find('def organize_attachment_folder')
if pos_org != -1:
    text = text[:pos_org] + guide_method + text[pos_org:]

with open('app_co_extractor.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("[OK] Successfully added naming guide to app_co_extractor.py!")
