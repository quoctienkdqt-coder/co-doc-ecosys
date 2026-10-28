import sys
sys.stdout.reconfigure(encoding='utf-8')

new_handleBridgeSetSelect = '''async function handleBridgeSetSelect(fieldName, targetKeywords) {
    const keywords = Array.isArray(targetKeywords) ? targetKeywords.filter(Boolean) : [targetKeywords];
    if (keywords.length === 0) return { success: false, reason: "No keywords provided" };

    let selectEl = null;
    const input = document.getElementById(`formCreateUpdate_${fieldName}`) ||
                  document.getElementById(fieldName) ||
                  document.querySelector(`[name="${fieldName}"]`);
    if (input) {
      selectEl = input.closest(".ant-select");
    }

    // Nếu không tìm thấy bằng ID/name, tìm theo text nhãn (Label) của Form.Item
    if (!selectEl) {
      const labels = Array.from(document.querySelectorAll("label, .ant-form-item-label"));
      for (const lbl of labels) {
        const t = cleanString(lbl.textContent || "");
        if (fieldName === "form" && (t === "form" || t.includes("formmauco") || t === "mauco")) {
          selectEl = lbl.closest(".ant-form-item, .ant-row")?.querySelector(".ant-select");
          if (selectEl) break;
        } else if (fieldName === "route_TransportationType" && (t.includes("transportationtype") || t.includes("loaihinhvanchuyen"))) {
          selectEl = lbl.closest(".ant-form-item, .ant-row")?.querySelector(".ant-select");
          if (selectEl) break;
        } else if (fieldName === "route_PortOfLoading" && (t.includes("portofloading") || t.includes("cangbochang"))) {
          selectEl = lbl.closest(".ant-form-item, .ant-row")?.querySelector(".ant-select");
          if (selectEl) break;
        } else if (fieldName === "issuing_Authority" && (t.includes("issuingauthority") || t.includes("tochuccapphep"))) {
          selectEl = lbl.closest(".ant-form-item, .ant-row")?.querySelector(".ant-select");
          if (selectEl) break;
        } else if (fieldName === "declarationPlace" && (t.includes("declarationplace") || t.includes("noikhaibao"))) {
          selectEl = lbl.closest(".ant-form-item, .ant-row")?.querySelector(".ant-select");
          if (selectEl) break;
        }
      }
    }

    if (!selectEl) return { success: false, reason: `selectEl not found for ${fieldName}` };

    // ========================================================
    // TRA CỨU OPTIONS TRỰC TIẾP TRONG REACT FIBER PROPS
    // Chờ tối đa 3 giây nếu options đang được tải bất đồng bộ (như ev của form sau khi chọn tổ chức cấp)
    // ========================================================
    const selectFiberKey = Object.keys(selectEl).find(k => k.startsWith("__reactFiber$") || k.startsWith("__reactInternalInstance$"));
    let foundFiberOpt = null;
    let fiberOnChange = null;
    let opts = null;

    if (selectFiberKey) {
      for (let attempt = 0; attempt < 15; attempt++) {
        let curFiber = selectEl[selectFiberKey];
        while (curFiber) {
          if (!opts && Array.isArray(curFiber.memoizedProps?.options) && curFiber.memoizedProps.options.length > 0) {
            opts = curFiber.memoizedProps.options;
          }
          if (!fiberOnChange && typeof curFiber.memoizedProps?.onChange === "function") {
            fiberOnChange = curFiber.memoizedProps.onChange;
          }
          if (opts && fiberOnChange) break;
          curFiber = curFiber.return;
        }
        if (opts && opts.length > 0) break;
        await new Promise(r => setTimeout(r, 200));
      }
    }

    // 1. Tìm option khớp trong opts
    if (Array.isArray(opts) && opts.length > 0) {
      // 1.1 Khớp chính xác
      for (const opt of opts) {
        const lClean = cleanString(opt.label || "");
        const vClean = cleanString(opt.value || "");
        for (const kw of keywords) {
          const ckw = cleanString(kw);
          if (lClean === ckw || vClean === ckw || lClean === ("mau" + ckw) || ("mau" + lClean) === ckw) {
            foundFiberOpt = opt;
            break;
          }
        }
        if (foundFiberOpt) break;
      }

      // 1.2 Đặc trị EUR.1 cho form
      if (!foundFiberOpt && (fieldName === "form" || keywords.some(k => cleanString(k).includes("eur")))) {
        foundFiberOpt = opts.find(o => {
          const l = cleanString(o.label || "");
          const v = cleanString(o.value || "");
          return l.includes("eur1") || v === "eur" || l === "maueur1";
        });
      }

      // 1.3 Khớp chứa từ khóa
      if (!foundFiberOpt) {
        for (const opt of opts) {
          const lClean = cleanString(opt.label || "");
          const vClean = cleanString(opt.value || "");
          for (const kw of keywords) {
            const ckw = cleanString(kw);
            if (ckw.length >= 3 && (lClean.includes(ckw) || vClean.includes(ckw))) {
              foundFiberOpt = opt;
              break;
            }
          }
          if (foundFiberOpt) break;
        }
      }
    }

    let finalVal = keywords[0];
    let finalLabel = keywords[0];

    if (foundFiberOpt) {
      finalVal = foundFiberOpt.value;
      finalLabel = foundFiberOpt.label || foundFiberOpt.value;
    } else {
      // Giá trị chuẩn dự phòng nếu options chưa kịp render
      if (fieldName === "form" || keywords.some(k => cleanString(k).includes("eur"))) {
        finalVal = "EUR";
        finalLabel = "Mẫu EUR.1";
      } else if (fieldName === "route_TransportationType") {
        finalVal = "By Sea";
        finalLabel = "By Sea";
      } else if (fieldName === "route_PortOfLoading") {
        finalVal = "CANG CAT LAI (HCM)";
        finalLabel = "CANG CAT LAI (HCM)";
      }
    }

    // Kích hoạt Fiber onChange trực tiếp (eCoSys kích hoạt Parent_country="EUR" ngay!)
    if (fiberOnChange) {
      try {
        fiberOnChange(finalVal, { value: finalVal, label: finalLabel, key: finalVal });
      } catch (e) {
        console.warn("[Fiber onChange error]", e);
      }
    }

    // Đồng bộ vào Form instance Ant Design
    try {
      const form = getMoitFormInstance();
      if (form) {
        form.setFieldsValue({
          [fieldName]: finalVal,
          [`${fieldName}_Txt`]: finalLabel
        });
      }
    } catch (e) {}

    // Cập nhật nhãn hiển thị trên DOM
    let itemText = selectEl.querySelector(".ant-select-selection-item");
    if (itemText) {
      itemText.textContent = finalLabel;
      itemText.title = finalLabel;
      itemText.style.display = "block";
    } else {
      const selBox = selectEl.querySelector(".ant-select-selector");
      if (selBox) {
        const span = document.createElement("span");
        span.className = "ant-select-selection-item";
        span.title = finalLabel;
        span.textContent = finalLabel;
        selBox.appendChild(span);
      }
    }

    // DỌN DẸP SẠCH SẼ 100% SEARCH INPUT VÀ DOM (XÓA TRIỆT ĐỂ CHỮ THỪA)
    // TUYỆT ĐỐI KHÔNG GÕ CHỮ VÀO SEARCH INPUT ĐỂ KHÔNG BAO GIỜ BỊ SÓT 'Mã', 'By', 'CA'
    forceClearSearchInput(selectEl);

    try {
      selectEl.classList.remove("ant-select-open", "ant-select-focused");
      const selBox = selectEl.querySelector(".ant-select-selector");
      if (selBox) selBox.classList.remove("ant-select-focused");
      const arrow = selectEl.querySelector(".ant-select-arrow");
      if (arrow) {
        arrow.style.display = "";
        arrow.style.opacity = "1";
        arrow.style.pointerEvents = "none";
      }
      document.body.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    } catch (e) {}

    await new Promise(r => setTimeout(r, 150));
    return { success: true, value: finalVal, label: finalLabel };
  }

  '''

new_findBridgeFileInput = '''function isExportDeclarationInput(inp) {
    if (!inp) return false;
    let p = inp.parentElement;
    for (let i = 0; i < 6 && p; i++) {
      const t = cleanString(p.textContent || "");
      if (t.includes("exportdeclarationattached") || t.includes("tokhaixuatkhauattached") || (t.includes("exportdeclaration") && t.includes("toida"))) {
        return true;
      }
      p = p.parentElement;
    }
    return false;
  }

  function findBridgeFileInput(fileType, fileName, targetRow, linkedNumber, matchingMode) {
    const fType = (fileType || "").toLowerCase();
    const fName = (fileName || "").toLowerCase();
    const allInputs = Array.from(document.querySelectorAll('input[type="file"]'));
    if (allInputs.length === 0) return null;

    // Helper: Tìm các dòng tài liệu trong Card "DOCUMENT_PROVING" (Chứng từ chứng minh xuất xứ - Module 72293)
    function getDocProvingRows() {
      const cards = Array.from(document.querySelectorAll(".ant-card, .ant-col-12, .ant-col"));
      for (const card of cards) {
        const text = cleanString(card.textContent || "");
        if ((text.includes("documentproving") || text.includes("chungtuchungminh") || text.includes("bangphuluc")) && !text.includes("invoiceattached")) {
          const rows = Array.from(card.querySelectorAll(".ant-row")).filter(r => {
            const rt = cleanString(r.textContent || "");
            return !rt.includes("stt") && !rt.includes("tentailieu") && r.querySelector('input[type="file"]');
          });
          if (rows.length > 0) return rows;
        }
      }
      return [];
    }

    // Helper: Tìm ô file trong Card "Invoice_attached_Doc" (Tài liệu hóa đơn đính kèm - Module 72293)
    function getInvoiceAttachedInput() {
      const cards = Array.from(document.querySelectorAll(".ant-card, .ant-col-12, .ant-col"));
      for (const card of cards) {
        const text = cleanString(card.textContent || "");
        if (text.includes("invoiceattached") || (text.includes("hoadon") && text.includes("attached"))) {
          const inp = card.querySelector('input[type="file"]');
          if (inp && !isExportDeclarationInput(inp) && !window.__moit_used_inputs.has(inp)) return inp;
        }
      }
      return null;
    }

    // Helper: Tìm ô file Vận đơn "TRANSPORT_INFO" (Tài liệu vận tải - Module 66527)
    function getTransportationInput() {
      // 1. Cùng cột với tên tàu / số chuyến (route_TransportName)
      const vesselInput = document.querySelector('#formCreateUpdate_route_TransportName, input[placeholder*="Vessel" i]');
      if (vesselInput) {
        const col = vesselInput.closest(".ant-col-12, .ant-col");
        if (col) {
          const inp = col.querySelector('input[type="file"]');
          if (inp && !isExportDeclarationInput(inp) && !window.__moit_used_inputs.has(inp)) return inp;
        }
      }
      // 2. Quét theo nhãn chứa text vận tải
      for (const inp of allInputs) {
        if (isExportDeclarationInput(inp) || window.__moit_used_inputs.has(inp)) continue;
        let p = inp.parentElement;
        for (let d = 0; d < 6 && p; d++) {
          const text = cleanString(p.textContent || "");
          if (text.includes("transportationdocument") || text.includes("tailieuvantai") || text.includes("vantaidon")) {
            return inp;
          }
          p = p.parentElement;
        }
      }
      return null;
    }

    // ========================================================
    // 1. HÓA ĐƠN VAT (HoaDonVAT / Invoice VAT - Mục 29, 30)
    // ========================================================
    if (fType.includes("hoadonvat") || fType.includes("vat") || fName.includes("vat") || fName.includes("gtgt")) {
      const vatNumInputs = Array.from(document.querySelectorAll(
        'input[placeholder*="hóa đơn VAT" i], input[placeholder*="hoá đơn VAT" i], input[placeholder*="Invoice VAT" i], [id*="invoiceVATs"][id*="declarationNumber"]'
      ));

      let matchedRowIdx = -1;
      const targetNo = String(linkedNumber || "").trim().toLowerCase();
      const numsInName = (fileName.match(/\\d+/g) || []);

      if (vatNumInputs.length > 0) {
        for (let i = 0; i < vatNumInputs.length; i++) {
          const val = (vatNumInputs[i].value || "").trim().toLowerCase();
          if (!val) continue;
          const isMatch = (targetNo && (val === targetNo || val.includes(targetNo) || targetNo.includes(val) || val.replace(/^0+/, "") === targetNo.replace(/^0+/, ""))) ||
                          numsInName.some(n => val === n || val.includes(n) || n.includes(val) || val.replace(/^0+/, "") === n.replace(/^0+/, ""));
          if (isMatch) {
            matchedRowIdx = i;
            console.log(`[Bridge] 🎯 Khớp số HĐ VAT '${fileName}' vào dòng ${i + 1} (Số HĐ: ${val})`);
            break;
          }
        }
      }

      if (matchedRowIdx === -1) {
        matchedRowIdx = (typeof targetRow === "number" && targetRow >= 0) ? targetRow : 0;
      }

      if (vatNumInputs[matchedRowIdx]) {
        const row = vatNumInputs[matchedRowIdx].closest(".ant-row:not(.ant-form-item-row)") ||
                    vatNumInputs[matchedRowIdx].closest(".ant-row") ||
                    vatNumInputs[matchedRowIdx].parentElement?.parentElement;
        if (row) {
          const inp = row.querySelector('input[type="file"]');
          if (inp && !window.__moit_used_inputs.has(inp) && !isExportDeclarationInput(inp)) return inp;
        }
      }

      // Theo ID
      const directIds = [
        `formCreateUpdate_invoiceVATs_${matchedRowIdx}_file`,
        `invoiceVATs_${matchedRowIdx}_file`,
        `formCreateUpdate_invoiceVATs_${matchedRowIdx}_attachedFile`,
        `invoiceVATs_${matchedRowIdx}_attachedFile`
      ];
      for (const id of directIds) {
        const el = document.getElementById(id) || document.querySelector(`[id$="${id}"]`);
        if (el) {
          const inp = el.tagName === "INPUT" ? el : el.querySelector('input[type="file"]');
          if (inp && !window.__moit_used_inputs.has(inp) && !isExportDeclarationInput(inp)) return inp;
        }
      }
    }

    // ========================================================
    // 2. VẬN ĐƠN (VanDon / B/L / Transportation Document - Mục 21, 22)
    // ========================================================
    if (fType.includes("vandon") || fType.includes("transport") || fType.includes("bill") || fName.includes("bl") || fName.includes("bill") || fName.includes("vandon") || fName.includes("waybill")) {
      const transInp = getTransportationInput();
      if (transInp) return transInp;
    }

    // ========================================================
    // 3. BẢNG KÊ CHI PHÍ / NGUYÊN LIỆU (BangKeChiPhi / BOM / Phụ lục TT 05) -> DOCUMENT_PROVING Dòng 1
    // ========================================================
    if (fType.includes("bangke") || fType.includes("chiphi") || fType.includes("bom") || fName.includes("bangke") || fName.includes("bang ke") || fName.includes("chiphi") || fName.includes("bom") || fName.includes("cost") || fName.includes("phuluc") || fName.includes("wo")) {
      const docRows = getDocProvingRows();
      if (docRows.length >= 1) {
        const inp = docRows[0].querySelector('input[type="file"]');
        if (inp && !window.__moit_used_inputs.has(inp) && !isExportDeclarationInput(inp)) return inp;
      }
    }

    // ========================================================
    // 4. BẢN MÔ TẢ QUY TRÌNH SẢN XUẤT (QuyTrinhSanXuat) -> DOCUMENT_PROVING Dòng 2
    // ========================================================
    if (fType.includes("quytrinh") || fType.includes("sanxuat") || fType.includes("qtsx") || fName.includes("quytrinh") || fName.includes("quy trinh") || fName.includes("sanxuat") || fName.includes("qtsx") || fName.includes("process")) {
      const docRows = getDocProvingRows();
      if (docRows.length >= 2) {
        const inp = docRows[1].querySelector('input[type="file"]');
        if (inp && !window.__moit_used_inputs.has(inp) && !isExportDeclarationInput(inp)) return inp;
      }
    }

    // ========================================================
    // 5. TỜ KHAI HẢI QUAN NHẬP KHẨU (ToKhaiHQNK_Document - Mục 27, 28)
    // ========================================================
    if (fType.includes("tokhaihqnk") || fType.includes("nhapkhau") || fName.includes("nhapkhau") || fName.includes("nk") || fName.includes("tk_nhap")) {
      const impNumInputs = Array.from(document.querySelectorAll(
        'input[placeholder*="Import Declaration" i], input[placeholder*="tờ khai nhập" i], input[placeholder*="to khai nhap" i], [id*="importDeclarations"][id*="declarationNumber"]'
      ));

      let matchedRowIdx = -1;
      const targetNo = String(linkedNumber || "").trim().toLowerCase();
      const numsInName = (fileName.match(/\\d{5,}/g) || []);

      if (impNumInputs.length > 0) {
        for (let i = 0; i < impNumInputs.length; i++) {
          const val = (impNumInputs[i].value || "").trim().toLowerCase();
          if (!val) continue;
          const isMatch = (targetNo && (val === targetNo || val.includes(targetNo) || targetNo.includes(val) || val.replace(/^0+/, "") === targetNo.replace(/^0+/, ""))) ||
                          numsInName.some(n => val === n || val.includes(n) || n.includes(val) || val.replace(/^0+/, "") === n.replace(/^0+/, ""));
          if (isMatch) {
            matchedRowIdx = i;
            break;
          }
        }
      }

      if (matchedRowIdx === -1) {
        matchedRowIdx = (typeof targetRow === "number" && targetRow >= 0) ? targetRow : 0;
      }

      if (impNumInputs[matchedRowIdx]) {
        const row = impNumInputs[matchedRowIdx].closest(".ant-row:not(.ant-form-item-row)") ||
                    impNumInputs[matchedRowIdx].closest(".ant-row") ||
                    impNumInputs[matchedRowIdx].parentElement?.parentElement;
        if (row) {
          const inp = row.querySelector('input[type="file"]');
          if (inp && !window.__moit_used_inputs.has(inp) && !isExportDeclarationInput(inp)) return inp;
        }
      }

      // Hoặc dòng 3 của DOCUMENT_PROVING
      const docRows = getDocProvingRows();
      if (docRows.length >= 3) {
        const inp = docRows[2].querySelector('input[type="file"]');
        if (inp && !window.__moit_used_inputs.has(inp) && !isExportDeclarationInput(inp)) return inp;
      }
    }

    // ========================================================
    // 6. HÓA ĐƠN THƯƠNG MẠI (Invoice_attached_Doc - Mục 24)
    // ========================================================
    if (fType.includes("invoice_attached") || fType === "invoicethuongmai" || fType === "commercialinvoice" || (fName.includes("inv") && !fName.includes("vat") && !fName.includes("don"))) {
      const invInp = getInvoiceAttachedInput();
      if (invInp) return invInp;
    }

    // ========================================================
    // 7. ĐƠN ĐỀ NGHỊ CẤP C/O & CHỨNG TỪ KHÁC (TAILIEUCHUNGMINH) -> DOCUMENT_PROVING Dòng 4 hoặc Invoice_attached_Doc
    // ========================================================
    if (fType.includes("don") || fType.includes("tailieuchungminh") || fName.includes("don") || fName.includes("mau 04") || fName.includes("mau04") || fName.includes("denghi") || fName.includes("chungtu")) {
      // Nếu tên chứa 'inv' hoặc 'don co,inv' thì ưu tiên gắn vào Invoice_attached_Doc nếu ô đó chưa dùng
      if (fName.includes("inv")) {
        const invInp = getInvoiceAttachedInput();
        if (invInp) return invInp;
      }
      // Dòng 4 của DOCUMENT_PROVING (Chứng từ khác / Đơn đề nghị)
      const docRows = getDocProvingRows();
      if (docRows.length >= 4) {
        const inp = docRows[3].querySelector('input[type="file"]');
        if (inp && !window.__moit_used_inputs.has(inp) && !isExportDeclarationInput(inp)) return inp;
      }
    }

    // ========================================================
    // 8. TỜ KHAI HẢI QUAN XUẤT KHẨU (CHỈ KHI LOẠI TỆP LÀ ToKhaiXuatKhau)
    // ========================================================
    if (fType === "tokhaixuatkhau" || (fType.includes("tokhaixuat") && !fType.includes("nhapkhau"))) {
      for (const inp of allInputs) {
        if (isExportDeclarationInput(inp) && !window.__moit_used_inputs.has(inp)) {
          return inp;
        }
      }
    }

    // ========================================================
    // 9. DỰ PHÒNG AN TOÀN TUYỆT ĐỐI (KHÔNG BAO GIỜ CHẠM VÀO Ô TỜ KHAI XUẤT KHẨU!)
    // ========================================================
    const unused = allInputs.find(inp => !inp.disabled && !window.__moit_used_inputs.has(inp) && !isExportDeclarationInput(inp));
    if (unused) return unused;

    return null;
  }

  '''

with open(r'extension\injected_proxy.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace handleBridgeSetSelect
start_select = content.find('async function handleBridgeSetSelect(')
end_select = content.find('async function handleBridgeSetCustomDropdown(')

content = content[:start_select] + new_handleBridgeSetSelect + content[end_select:]

# Now find findBridgeFileInput
start_file = content.find('function findBridgeFileInput(')
if start_file == -1:
    start_file = content.find('function isExportDeclarationInput(')
end_file = content.find('async function handleBridgeUploadAttachment(')

content = content[:start_file] + new_findBridgeFileInput + content[end_file:]

with open(r'extension\injected_proxy.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("[OK] Successfully updated injected_proxy.js!")
