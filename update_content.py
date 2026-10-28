import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'extension\content.js', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update version strings
text = text.replace("v2.7.6", "v2.8.0")
text = text.replace("Phiên bản v2.7.6: Tối ưu hoá chọn Mẫu C/O (loại bỏ hoàn toàn chữ thừa 'Mẫu/Mã' trong ô chọn), liên kết chuẩn 3 tầng C/O -> Nước -> Cảng, tự động nạp chính xác 5 khu vực tệp đính kèm trên eCoSys.",
                    "Phiên bản v2.8.0: Chuyên gia Khai báo eCoSys - Loại bỏ 100% chữ thừa (Mã, By, CA), định vị chính xác tuyệt đối 6 nhóm chứng từ, liên kết mượt mà Tổ chức cấp -> Mẫu C/O -> Nước NK -> Cảng dỡ.")

# 2. Update goods modal units logic to avoid redundant warnings if bridge succeeds
old_unit_block = '''        await callMoitBridge("setGoodsModalUnits", {
          quantityUnit: qtyUnitTarget,
          grossWeightUnit: gwUnitTarget,
          packageUnit: pkgUnitTarget,
          currency: item.currency || "USD"
        });

        // g. Số lượng (Quantity)
        if (item.quantity !== undefined) {
          const qtyEl = modal.querySelector('input[placeholder="0.00"], [name="quantity"]');
          if (qtyEl) setNativeValue(qtyEl, String(item.quantity));
        }
        const qtyUnitSelect = modal.querySelector('input[placeholder="QuantityUnit"]')?.closest(".ant-select") ||
                              modal.querySelector('#formCreateUpdate_quantityUnit')?.closest(".ant-select");
        if (qtyUnitSelect) {
          await selectAntdOption(qtyUnitSelect, [qtyUnitTarget, "KILOGRAM"], "Đơn vị số lượng", modal, false);
        }

        // h. Ký mã hiệu bao bì (Mark and number on package - Mặc định NO MARK)
        const markVal = (item.markAndNumberOnPackage && item.markAndNumberOnPackage !== "N/M") ? item.markAndNumberOnPackage : "NO MARK";
        const markEl = modal.querySelector('input[placeholder="Mark and number on package"], [name="markAndNumberOnPackage"]');
        if (markEl) setNativeValue(markEl, markVal);

        // i. Số lượng kiện & Loại kiện (Package quantity & PackageUnit)
        if (item.packageQuantity !== undefined) {
          const pkgEl = modal.querySelector('input[placeholder="PackageQuantity"], [name="packageQuantity"]');
          if (pkgEl) setNativeValue(pkgEl, String(item.packageQuantity));
        }
        const pkgUnitSelect = modal.querySelector('input[placeholder="PackageUnit"]')?.closest(".ant-select") ||
                              modal.querySelector('#formCreateUpdate_packageUnit')?.closest(".ant-select");
        if (pkgUnitSelect) {
          await selectAntdOption(pkgUnitSelect, [pkgUnitTarget, "CARTON", "BAG"], "Loại kiện bao bì", modal, false);
        }

        // j. Trọng lượng tổng & Đơn vị tính (Gross weight & GrossWeightUnit)
        if (item.grossWeight !== undefined) {
          const gwInputs = Array.from(modal.querySelectorAll('input[placeholder="0.00"], [name="grossWeight"]'));
          const gwEl = gwInputs.find(inp => inp.name === "grossWeight" || inp.id?.includes("grossWeight")) || gwInputs[1];
          if (gwEl) setNativeValue(gwEl, String(item.grossWeight));
        }
        const gwUnitSelect = modal.querySelector('input[placeholder="GrossWeightUnit"]')?.closest(".ant-select") ||
                             modal.querySelector('#formCreateUpdate_grossWeightUnit')?.closest(".ant-select");
        if (gwUnitSelect) {
          await selectAntdOption(gwUnitSelect, [gwUnitTarget, "KILOGRAM"], "Đơn vị trọng lượng", modal, false);
        }'''

new_unit_block = '''        const modalUnitsRes = await callMoitBridge("setGoodsModalUnits", {
          quantityUnit: qtyUnitTarget,
          grossWeightUnit: gwUnitTarget,
          packageUnit: pkgUnitTarget,
          currency: item.currency || "USD"
        });

        // g. Số lượng (Quantity)
        if (item.quantity !== undefined) {
          const qtyEl = modal.querySelector('input[placeholder="0.00"], [name="quantity"]');
          if (qtyEl) setNativeValue(qtyEl, String(item.quantity));
        }
        if (!modalUnitsRes || !modalUnitsRes.success) {
          const qtyUnitSelect = modal.querySelector('input[placeholder="QuantityUnit"]')?.closest(".ant-select") ||
                                modal.querySelector('#formCreateUpdate_quantityUnit')?.closest(".ant-select");
          if (qtyUnitSelect) {
            await selectAntdOption(qtyUnitSelect, [qtyUnitTarget, "KILOGRAM"], "Đơn vị số lượng", modal, false);
          }
        }

        // h. Ký mã hiệu bao bì (Mark and number on package - Mặc định NO MARK)
        const markVal = (item.markAndNumberOnPackage && item.markAndNumberOnPackage !== "N/M") ? item.markAndNumberOnPackage : "NO MARK";
        const markEl = modal.querySelector('input[placeholder="Mark and number on package"], [name="markAndNumberOnPackage"]');
        if (markEl) setNativeValue(markEl, markVal);

        // i. Số lượng kiện & Loại kiện (Package quantity & PackageUnit)
        if (item.packageQuantity !== undefined) {
          const pkgEl = modal.querySelector('input[placeholder="PackageQuantity"], [name="packageQuantity"]');
          if (pkgEl) setNativeValue(pkgEl, String(item.packageQuantity));
        }
        if (!modalUnitsRes || !modalUnitsRes.success) {
          const pkgUnitSelect = modal.querySelector('input[placeholder="PackageUnit"]')?.closest(".ant-select") ||
                                modal.querySelector('#formCreateUpdate_packageUnit')?.closest(".ant-select");
          if (pkgUnitSelect) {
            await selectAntdOption(pkgUnitSelect, [pkgUnitTarget, "CARTON", "BAG"], "Loại kiện bao bì", modal, false);
          }
        }

        // j. Trọng lượng tổng & Đơn vị tính (Gross weight & GrossWeightUnit)
        if (item.grossWeight !== undefined) {
          const gwInputs = Array.from(modal.querySelectorAll('input[placeholder="0.00"], [name="grossWeight"]'));
          const gwEl = gwInputs.find(inp => inp.name === "grossWeight" || inp.id?.includes("grossWeight")) || gwInputs[1];
          if (gwEl) setNativeValue(gwEl, String(item.grossWeight));
        }
        if (!modalUnitsRes || !modalUnitsRes.success) {
          const gwUnitSelect = modal.querySelector('input[placeholder="GrossWeightUnit"]')?.closest(".ant-select") ||
                               modal.querySelector('#formCreateUpdate_grossWeightUnit')?.closest(".ant-select");
          if (gwUnitSelect) {
            await selectAntdOption(gwUnitSelect, [gwUnitTarget, "KILOGRAM"], "Đơn vị trọng lượng", modal, false);
          }
        }'''

if old_unit_block in text:
    text = text.replace(old_unit_block, new_unit_block)
    print("[OK] Replaced modal units block successfully!")
else:
    print("[WARN] old_unit_block not found exactly!")

with open(r'extension\content.js', 'w', encoding='utf-8') as f:
    f.write(text)

print("[OK] Updated content.js successfully!")
