// injected_proxy.js - Runs in MAIN world of co.moit.gov.vn
// Bridges React Fiber & Ant Design Form instance, Modal Closing & Exact Row File Upload

(function () {
  if (window.__moit_proxy_active) return;
  window.__moit_proxy_active = true;

  function setBusyState(isBusy) {
    window.__moit_is_busy = isBusy;
    if (document.documentElement) {
      document.documentElement.dataset.moitBusy = isBusy ? "1" : "0";
    }
  }

  // ========================================================
  // 1. XHR PROXY CHO MOIT CARD PLUGIN (PORT 14005 / 14405)
  // ========================================================
  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  const origSetHeader = XMLHttpRequest.prototype.setRequestHeader;

  XMLHttpRequest.prototype.open = function (method, url) {
    if (typeof url === "string" && (url.includes(":14005") || url.includes(":14405"))) {
      this._isMoit = true;
      this._moitMethod = method || "POST";
      this._moitUrl = url;
      this._moitHeaders = {};
      return;
    }
    return origOpen.apply(this, arguments);
  };

  XMLHttpRequest.prototype.setRequestHeader = function (header, value) {
    if (this._isMoit) {
      this._moitHeaders[header] = value;
      return;
    }
    return origSetHeader.apply(this, arguments);
  };

  XMLHttpRequest.prototype.send = function (body) {
    if (this._isMoit) {
      const xhr = this;
      const reqId = "moit_" + Math.random().toString(36).slice(2) + Date.now().toString(36);

      window.__moit_active_ops = (window.__moit_active_ops || 0) + 1;
      setBusyState(true);

      const onResponse = (evt) => {
        if (evt.detail && evt.detail.reqId === reqId) {
          window.removeEventListener("__moit_proxy_resp", onResponse);
          const res = evt.detail.res || {};

          window.__moit_active_ops = Math.max(0, (window.__moit_active_ops || 1) - 1);
          if (window.__moit_active_ops === 0) {
            setBusyState(false);
          }

          Object.defineProperty(xhr, "readyState", { value: 4, writable: true, configurable: true });
          Object.defineProperty(xhr, "status", { value: res.status || 200, writable: true, configurable: true });
          Object.defineProperty(xhr, "statusText", { value: "OK", writable: true, configurable: true });
          Object.defineProperty(xhr, "responseText", { value: res.responseText || "", writable: true, configurable: true });
          Object.defineProperty(xhr, "response", { value: res.responseText || "", writable: true, configurable: true });

          if (typeof xhr.onreadystatechange === "function") {
            try { xhr.onreadystatechange(); } catch (e) {}
          }
          if (typeof xhr.onload === "function") {
            try { xhr.onload(); } catch (e) {}
          }
        }
      };

      window.addEventListener("__moit_proxy_resp", onResponse);
      window.dispatchEvent(new CustomEvent("__moit_proxy_req", {
        detail: {
          reqId: reqId,
          url: xhr._moitUrl,
          method: xhr._moitMethod,
          headers: xhr._moitHeaders,
          body: body || ""
        }
      }));
      return;
    }
    return origSend.apply(this, arguments);
  };

  // ========================================================
  // 2. TIỆN ÍCH TRUY XUẤT REACT FIBER & ANT DESIGN FORM
  // ========================================================
  function cleanString(str) {
    if (!str) return "";
    return String(str)
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[đĐ]/g, "d")
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "");
  }

  function getFiberKey(el) {
    if (!el) return null;
    return Object.keys(el).find(k => k.startsWith("__reactFiber$") || k.startsWith("__reactInternalInstance$"));
  }

  function getMoitFormInstance() {
    const formEl = document.getElementById("formCreateUpdate") || document.querySelector("form.ant-form") || document.querySelector("form");
    if (!formEl) return null;
    const fiberKey = getFiberKey(formEl);
    if (!fiberKey) return null;
    let fiber = formEl[fiberKey];
    while (fiber) {
      if (fiber.memoizedProps?.form && typeof fiber.memoizedProps.form.setFieldsValue === "function") {
        return fiber.memoizedProps.form;
      }
      if (fiber.memoizedState?.form && typeof fiber.memoizedState.form.setFieldsValue === "function") {
        return fiber.memoizedState.form;
      }
      fiber = fiber.return;
    }
    return null;
  }

  function getGoodsModalFormInstance() {
    const modalEl = document.querySelector(".ant-modal:not([style*='display: none']) form") ||
                    document.querySelector(".ant-modal form") ||
                    document.querySelector(".ant-modal");
    if (!modalEl) return null;
    const fiberKey = getFiberKey(modalEl);
    if (!fiberKey) return null;
    let fiber = modalEl[fiberKey];
    while (fiber) {
      if (fiber.memoizedProps?.form && typeof fiber.memoizedProps.form.setFieldsValue === "function") {
        return fiber.memoizedProps.form;
      }
      if (fiber.memoizedState?.form && typeof fiber.memoizedState.form.setFieldsValue === "function") {
        return fiber.memoizedState.form;
      }
      fiber = fiber.return;
    }
    return null;
  }

  function setNativeInputInMainWorld(el, value) {
    if (!el) return false;
    try {
      const lastVal = el.value;
      const proto = el.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
      const nativeSetter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
      if (nativeSetter) {
        nativeSetter.call(el, value);
      } else {
        el.value = value;
      }
      if (el._valueTracker) {
        el._valueTracker.setValue(lastVal === String(value) ? "___force_diff___" : lastVal);
      }
      el.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
      el.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
      return true;
    } catch (e) {
      return false;
    }
  }

  // ========================================================
  // 3. XỬ LÝ DATEPICKER TRONG MAIN WORLD
  // ========================================================
  async function handleBridgeSetDatePicker(payload) {
    const { selector, id, formattedDate } = payload || {};
    if (!formattedDate) return { success: false };

    let dateInput = null;
    if (id) dateInput = document.getElementById(id) || document.querySelector(`[id$="${id}"]`);
    if (!dateInput && selector) dateInput = document.querySelector(selector);
    if (!dateInput) return { success: false, reason: "DateInput not found" };

    try {
      dateInput.focus();
      dateInput.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
      dateInput.click();
      await new Promise(r => setTimeout(r, 80));

      setNativeInputInMainWorld(dateInput, formattedDate);

      const enterInit = { key: "Enter", code: "Enter", keyCode: 13, which: 13, charCode: 13, bubbles: true, cancelable: true };
      dateInput.dispatchEvent(new KeyboardEvent("keydown", enterInit));
      dateInput.dispatchEvent(new KeyboardEvent("keypress", enterInit));
      dateInput.dispatchEvent(new KeyboardEvent("keyup", enterInit));

      const pickerBox = dateInput.closest(".ant-picker") || dateInput;
      const fiberKey = getFiberKey(pickerBox) || getFiberKey(dateInput);
      if (fiberKey) {
        let fiber = pickerBox[fiberKey] || dateInput[fiberKey];
        while (fiber) {
          if (fiber.memoizedProps && typeof fiber.memoizedProps.onChange === "function") {
            try {
              const existingVal = fiber.memoizedProps.value || fiber.memoizedProps.defaultPickerValue;
              const parts = formattedDate.split("/");
              if (parts.length === 3 && existingVal && typeof existingVal.clone === "function") {
                const dateObj = existingVal.clone()
                  .year(parseInt(parts[2], 10))
                  .month(parseInt(parts[1], 10) - 1)
                  .date(parseInt(parts[0], 10))
                  .hour(12).minute(0).second(0).millisecond(0);
                fiber.memoizedProps.onChange(dateObj, formattedDate);
                break;
              }
            } catch (e) {}
          }
          fiber = fiber.return;
        }
      }

      dateInput.blur();
      await new Promise(r => setTimeout(r, 60));
      document.body.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
      return { success: true };
    } catch (e) {
      return { success: false, error: e.message };
    }
  }

  // ========================================================
  // 4. XỬ LÝ ANT DESIGN SELECT & CUSTOM DROPDOWN (KHÔNG NHÂN ĐÔI SPAN)
  // ========================================================
  async function handleBridgeSetSelect(fieldName, targetKeywords) {
    const keywords = Array.isArray(targetKeywords) ? targetKeywords.filter(Boolean) : [targetKeywords];
    if (keywords.length === 0) return { success: false, reason: "No keywords provided" };

    let selectEl = null;
    const input = document.getElementById(`formCreateUpdate_${fieldName}`) ||
                  document.getElementById(fieldName) ||
                  document.querySelector(`[name="${fieldName}"]`);
    if (input) {
      selectEl = input.closest(".ant-select");
    }

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

    const selectFiberKey = getFiberKey(selectEl);
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

    if (Array.isArray(opts) && opts.length > 0) {
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

      if (!foundFiberOpt && (fieldName === "form" || keywords.some(k => cleanString(k).includes("eur")))) {
        foundFiberOpt = opts.find(o => {
          const l = cleanString(o.label || "");
          const v = cleanString(o.value || "");
          return l.includes("eur1") || v === "eur" || l === "maueur1";
        });
      }

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
      if (fieldName === "form" && keywords.some(k => cleanString(k).includes("eur"))) {
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

    if (fiberOnChange) {
      try {
        fiberOnChange(finalVal, { value: finalVal, label: finalLabel, key: finalVal });
      } catch (e) {}
    }

    try {
      const form = getMoitFormInstance();
      if (form) {
        form.setFieldsValue({
          [fieldName]: finalVal,
          [`${fieldName}_Txt`]: finalLabel
        });
      }
    } catch (e) {}

    // Chờ React 18 tự render thẻ span chuẩn, tuyệt đối không dùng appendChild gây nhân đôi chữ "By" / "CA"
    await new Promise(r => setTimeout(r, 100));

    const allItems = Array.from(selectEl.querySelectorAll(".ant-select-selection-item"));
    if (allItems.length > 1) {
      allItems.slice(1).forEach(dup => dup.remove());
    }
    if (allItems[0]) {
      allItems[0].textContent = finalLabel;
      allItems[0].title = finalLabel;
    }

    try {
      const searchInp = selectEl.querySelector(".ant-select-selection-search-input");
      if (searchInp && searchInp.value) {
        setNativeInputInMainWorld(searchInp, "");
        searchInp.blur();
      }
      selectEl.classList.remove("ant-select-open", "ant-select-focused");
      document.body.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    } catch (e) {}

    await new Promise(r => setTimeout(r, 80));
    return { success: true, value: finalVal, label: finalLabel };
  }

  async function handleBridgeSetCustomDropdown(fieldName, targetKeywords, inModal = false) {
    const keywords = Array.isArray(targetKeywords) ? targetKeywords.filter(Boolean) : [targetKeywords];
    if (keywords.length === 0) return { success: false, reason: "No keywords provided" };

    const scopeRoot = inModal ? (document.querySelector(".ant-modal:not([style*='display: none'])") || document) : document;
    let formItem = scopeRoot.querySelector(`label[for*="${fieldName}"]`)?.closest(".ant-form-item") ||
                   scopeRoot.querySelector(`[name="${fieldName}"]`)?.closest(".ant-form-item");

    if (!formItem) {
      const labels = Array.from(scopeRoot.querySelectorAll("label, .ant-form-item-label"));
      for (const lbl of labels) {
        const t = cleanString(lbl.textContent || "");
        if (fieldName === "importing_Country" && (t.includes("importingcountry") || t.includes("nuocnhapkhau"))) {
          formItem = lbl.closest(".ant-form-item"); break;
        } else if (fieldName === "route_PortOfDischange" && (t.includes("portofdischarge") || t.includes("cangdohang"))) {
          formItem = lbl.closest(".ant-form-item"); break;
        } else if (fieldName === "route_PortOfDestination" && (t.includes("portofdestination") || t.includes("cangden"))) {
          formItem = lbl.closest(".ant-form-item"); break;
        } else if (fieldName === "exportingHsCode" && (t.includes("exportinghscode") || t.includes("mahsxuatkhau"))) {
          formItem = lbl.closest(".ant-form-item"); break;
        }
      }
    }

    if (!formItem) return { success: false, reason: `formItem not found for ${fieldName}` };

    const trigger = formItem.querySelector("div.cursor-pointer, div[style*='border-color'], div[style*='borderColor'], .relative > div");
    if (trigger) {
      trigger.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
      trigger.click();
      await new Promise(r => setTimeout(r, 350));
    }

    const searchInput = formItem.querySelector("input[placeholder*='Tìm kiếm' i]") ||
                        formItem.querySelector("input:not([readonly])") ||
                        scopeRoot.querySelector("div.animate-dropdown input, div.absolute input");

    let chosenEl = null;

    function scanDropdownItems(kws) {
      const popupScopes = [
        ...Array.from(formItem.querySelectorAll(".absolute, div.animate-dropdown, div[class*='dropdown'], ul")),
        ...Array.from(scopeRoot.querySelectorAll("div.animate-dropdown, div.absolute.z-50, div[class*='popover'], ul"))
      ];
      for (const kw of kws) {
        const ckw = cleanString(kw);
        if (!ckw) continue;
        for (const scope of popupScopes) {
          const items = Array.from(scope.querySelectorAll("li, div.cursor-pointer, p, span, a, [role='option']"));
          for (const el of items) {
            if (el.tagName === "INPUT" || el.tagName === "BUTTON" || el.tagName === "LABEL") continue;
            if (el.closest(".ant-form-item-label") || el.closest("label") || el.querySelector("input")) continue;
            const text = cleanString(el.textContent || "");
            if (!text || text.includes("khongtimthay") || text.includes("nodata") || text.includes("tatcaban") || text === "11") continue;
            if (text === ckw || (ckw.length >= 3 && (text.startsWith(ckw) || text.includes(ckw)))) {
              const rect = el.getBoundingClientRect();
              if (rect.width > 0 && rect.height > 0) return el;
            }
          }
        }
      }
      return null;
    }

    chosenEl = scanDropdownItems(keywords);

    if (!chosenEl && searchInput) {
      for (const kw of keywords) {
        const primaryKey = String(kw).trim();
        if (!primaryKey) continue;
        searchInput.focus();
        setNativeInputInMainWorld(searchInput, primaryKey);
        searchInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", keyCode: 13, which: 13, bubbles: true }));
        searchInput.dispatchEvent(new KeyboardEvent("keyup", { key: "Enter", keyCode: 13, which: 13, bubbles: true }));

        for (let w = 0; w < 10; w++) {
          await new Promise(r => setTimeout(r, 200));
          chosenEl = scanDropdownItems([primaryKey, ...keywords]);
          if (chosenEl) break;
        }
        if (chosenEl) break;
      }
    }

    if (chosenEl) {
      const selectedLabel = (chosenEl.textContent || "").trim();
      chosenEl.scrollIntoView?.({ block: "nearest" });
      chosenEl.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true }));
      chosenEl.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
      chosenEl.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true }));
      chosenEl.click();

      const propsKey = Object.keys(chosenEl).find(k => k.startsWith("__reactProps$"));
      if (propsKey && typeof chosenEl[propsKey]?.onClick === "function") {
        try { chosenEl[propsKey].onClick({ preventDefault: () => {}, stopPropagation: () => {} }); } catch (e) {}
      }
      const parentPropsKey = Object.keys(chosenEl.parentElement || {}).find(k => k.startsWith("__reactProps$"));
      if (parentPropsKey && typeof chosenEl.parentElement[parentPropsKey]?.onClick === "function") {
        try { chosenEl.parentElement[parentPropsKey].onClick({ preventDefault: () => {}, stopPropagation: () => {} }); } catch (e) {}
      }
      await new Promise(r => setTimeout(r, 350));
      return { success: true, label: selectedLabel };
    }

    document.body.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    return { success: false, reason: "No matching option found" };
  }

  // ========================================================
  // 5. ĐỒNG BỘ FORM CHÍNH, MODAL HÀNG HÓA & ĐÓNG MODAL TỰ ĐỘNG
  // ========================================================
  function handleBridgeSyncFormFields(fields) {
    try {
      const form = getMoitFormInstance();
      let synced = 0;
      if (fields && typeof fields === "object") {
        for (const [key, val] of Object.entries(fields)) {
          if (val === undefined || val === null || val === "") continue;
          const el = document.getElementById(`formCreateUpdate_${key}`) ||
                     document.getElementById(key) ||
                     document.querySelector(`[name="${key}"]`);
          if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) {
            setNativeInputInMainWorld(el, String(val));
            synced++;
          }
        }
        if (form) {
          const cleanFields = {};
          for (const [k, v] of Object.entries(fields)) {
            if (v !== undefined && v !== null && v !== "") cleanFields[k] = v;
          }
          form.setFieldsValue(cleanFields);
        }
      }
      return { success: true, synced };
    } catch (e) {
      return { success: false, error: e.message };
    }
  }

  async function handleBridgeSyncGoodsHsCode(payload) {
    const { exportingHsCode, importingHsCode } = payload || {};
    const modalForm = getGoodsModalFormInstance();
    const expHs = String(exportingHsCode || "").replace(/\D/g, "").substring(0, 8);
    const impHs = String(importingHsCode || exportingHsCode || "").replace(/\D/g, "").substring(0, 6);

    if (modalForm) {
      const patch = {};
      if (expHs) patch.exportingHsCode = expHs;
      if (impHs) patch.importingHsCode = impHs;
      try { modalForm.setFieldsValue(patch); } catch (e) {}
    }
    return { success: true, expHs, impHs };
  }

  async function handleBridgeSyncGoodsModalFields(payload) {
    const modalEl = document.querySelector(".ant-modal:not([style*='display: none'])");
    if (!modalEl) return { success: false, reason: "Modal not open" };

    // Điền cả trên DOM trong Modal lẫn trong FormStore của Modal
    if (payload && typeof payload === "object") {
      const mapSelectors = {
        goodsDescription: 'textarea, [placeholder="GoodsDescription"], [name="goodsDescription"]',
        originCriterion: 'input[placeholder="OriginCriterion"], [name="originCriterion"]',
        quantity: 'input[placeholder="0.00"], [name="quantity"]',
        markAndNumberOnPackage: 'input[placeholder="Mark and number on package"], [name="markAndNumberOnPackage"]',
        packageQuantity: 'input[placeholder="PackageQuantity"], [name="packageQuantity"]',
        value: 'input[name="value"], [id*="value"]',
        invoiceNumber: 'input[placeholder="InvoiceNumber"], [name="invoiceNumber"]'
      };
      for (const [k, sel] of Object.entries(mapSelectors)) {
        if (payload[k] !== undefined && payload[k] !== null) {
          const el = modalEl.querySelector(sel);
          if (el) setNativeInputInMainWorld(el, String(payload[k]));
        }
      }
      if (payload.grossWeight !== undefined && payload.grossWeight !== null) {
        const gwInputs = Array.from(modalEl.querySelectorAll('input[placeholder="0.00"], [name="grossWeight"]'));
        const gwEl = gwInputs.find(inp => inp.name === "grossWeight" || inp.id?.includes("grossWeight")) || gwInputs[1];
        if (gwEl) setNativeInputInMainWorld(gwEl, String(payload.grossWeight));
      }
    }

    const modalForm = getGoodsModalFormInstance();
    if (modalForm && payload && typeof payload === "object") {
      try { modalForm.setFieldsValue(payload); } catch (e) {}
    }
    return { success: true };
  }

  /**
   * ĐÓNG MODAL HÀNG HÓA TRIỆT ĐỂ SAU KHI ĐÃ LƯU XONG TẤT CẢ MẶT HÀNG
   */
  async function handleBridgeCloseGoodsModal() {
    const modals = Array.from(document.querySelectorAll(".ant-modal")).filter(m => {
      const r = m.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && !m.closest("[style*='display: none']");
    });
    if (modals.length === 0) return { success: true, alreadyClosed: true };

    const modal = modals[modals.length - 1];

    // 1. Thử kích hoạt hàm onCancel trong React Fiber của Modal
    const fiberKey = getFiberKey(modal);
    if (fiberKey) {
      let cur = modal[fiberKey];
      while (cur) {
        if (typeof cur.memoizedProps?.onCancel === "function") {
          try {
            cur.memoizedProps.onCancel({ preventDefault: () => {}, stopPropagation: () => {} });
          } catch (e) {}
          break;
        }
        cur = cur.return;
      }
    }

    // 2. Click trực tiếp nút X (.ant-modal-close) hoặc nút Đóng / Hủy
    const closeBtn = modal.querySelector("button.ant-modal-close, .ant-modal-close, .ant-modal-close-x") ||
                     Array.from(modal.querySelectorAll("button, .ant-btn")).find(b => {
                       const t = (b.textContent || "").trim().toLowerCase();
                       return t === "đóng" || t === "hủy" || t === "hủy bỏ" || t === "thoát" || t === "close" || t === "cancel";
                     });

    if (closeBtn) {
      closeBtn.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
      closeBtn.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true }));
      closeBtn.click();
      const propsKey = Object.keys(closeBtn).find(k => k.startsWith("__reactProps$"));
      if (propsKey && typeof closeBtn[propsKey]?.onClick === "function") {
        try { closeBtn[propsKey].onClick({ preventDefault: () => {}, stopPropagation: () => {} }); } catch (e) {}
      }
    }

    // 3. Gửi thêm phím Escape dự phòng
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, which: 27, bubbles: true }));
    await new Promise(r => setTimeout(r, 300));
    return { success: true };
  }

  function isCompoundUnit(str) {
    const s = String(str || "").toUpperCase();
    return s.includes("PER") || s.includes("METRE") || s.includes("METER") ||
           s.includes("SQUARE") || s.includes("SECOND") || s.includes("HOUR") ||
           s.includes("DRY") || s.includes("DRAINED") || s.includes("CONTAINER") ||
           s.includes("INCLUDING") || s.includes("TOTAL") || s.includes("/");
  }

  async function handleBridgeSetGoodsModalUnits(payload) {
    const { quantityUnit, grossWeightUnit, packageUnit } = payload || {};
    const modalEl = document.querySelector(".ant-modal:not([style*='display: none'])");
    if (!modalEl) return { success: false, reason: "Modal not open" };

    const modalForm = getGoodsModalFormInstance();
    const units = window.__moit_goods_dropdowns?.UNIT || [];

    function findUnitOption(unitStr, fallbackCode, fallbackLabel) {
      if (!unitStr) return { value: fallbackCode, label: fallbackLabel };
      const uClean = cleanString(unitStr);
      const isKg = uClean.includes("kg") || uClean.includes("kilo");

      if (Array.isArray(units) && units.length > 0) {
        for (const opt of units) {
          const lClean = cleanString(opt.label || "");
          const vClean = cleanString(opt.value || "");
          if (isKg) {
            if ((lClean === "kilogram" || vClean === "kgm" || vClean === "kg") && !isCompoundUnit(opt.label)) {
              return opt;
            }
          } else if (lClean === uClean || vClean === uClean) {
            return opt;
          }
        }
      }

      if (isKg) return { value: "KGM", label: "KILOGRAM" };
      if (uClean.includes("carton") || uClean.includes("thung") || uClean === "ct") return { value: "CT", label: "CARTON" };
      if (uClean.includes("bag") || uClean.includes("bao") || uClean === "bg") return { value: "BG", label: "BAG" };
      if (uClean.includes("piece") || uClean.includes("chiec") || uClean === "pce") return { value: "PCE", label: "PIECE" };
      return { value: fallbackCode || unitStr, label: fallbackLabel || unitStr };
    }

    const kgOpt = findUnitOption(quantityUnit || "KILOGRAM", "KGM", "KILOGRAM");
    const gwOpt = findUnitOption(grossWeightUnit || "KILOGRAM", "KGM", "KILOGRAM");
    const pkgOpt = findUnitOption(packageUnit || "CARTON", "CT", "CARTON");

    if (modalForm) {
      try {
        modalForm.setFieldsValue({
          quantityUnit: kgOpt.value,
          quantityUnitTxt: kgOpt.label,
          grossWeightUnit: gwOpt.value,
          grossWeightUnitTxt: gwOpt.label,
          packageUnit: pkgOpt.value,
          packageUnitTxt: pkgOpt.label
        });
      } catch (e) {}
    }

    function triggerSelectFiber(placeholder, opt) {
      const selectEl = modalEl.querySelector(`input[placeholder="${placeholder}"]`)?.closest(".ant-select");
      if (!selectEl) return;
      const fiberKey = getFiberKey(selectEl);
      if (fiberKey) {
        let fiber = selectEl[fiberKey];
        while (fiber) {
          if (typeof fiber.memoizedProps?.onChange === "function") {
            try { fiber.memoizedProps.onChange(opt.value, opt); break; } catch (e) {}
          }
          fiber = fiber.return;
        }
      }
      const allItems = Array.from(selectEl.querySelectorAll(".ant-select-selection-item"));
      if (allItems.length > 1) allItems.slice(1).forEach(d => d.remove());
      if (allItems[0]) {
        allItems[0].textContent = opt.label;
        allItems[0].title = opt.label;
      }
    }

    triggerSelectFiber("QuantityUnit", kgOpt);
    triggerSelectFiber("GrossWeightUnit", gwOpt);
    triggerSelectFiber("PackageUnit", pkgOpt);

    return { success: true, kgOpt, gwOpt, pkgOpt };
  }

  async function handleBridgeSetRetroactive(shouldCheck, reason) {
    let targetWrapper = null;
    let targetInput = null;

    for (let wait = 0; wait < 15; wait++) {
      const wrappers = Array.from(document.querySelectorAll("label.ant-checkbox-wrapper, .ant-checkbox-wrapper"));
      for (const w of wrappers) {
        if (/issued\s*retro/i.test(w.textContent || "")) {
          targetWrapper = w;
          targetInput = w.querySelector('input[type="checkbox"]');
          break;
        }
      }
      if (targetWrapper && targetInput) break;
      await new Promise(r => setTimeout(r, 200));
    }

    if (!targetWrapper || !targetInput) return { success: false, reason: "Checkbox not found" };

    const fiberKey = getFiberKey(targetInput);
    if (fiberKey) {
      let fiber = targetInput[fiberKey];
      while (fiber) {
        if (typeof fiber.memoizedProps?.onChange === "function") {
          try { fiber.memoizedProps.onChange({ target: { checked: shouldCheck } }); break; } catch (e) {}
        }
        fiber = fiber.return;
      }
    }

    targetInput.checked = shouldCheck;
    if (shouldCheck) {
      targetWrapper.classList.add("ant-checkbox-wrapper-checked");
      targetWrapper.querySelector(".ant-checkbox")?.classList.add("ant-checkbox-checked");
    }

    if (shouldCheck && reason) {
      await new Promise(r => setTimeout(r, 350));
      const reasonInput = document.querySelector('input[placeholder*="Lý do xin" i], input[placeholder*="Reason" i]');
      if (reasonInput) {
        setNativeInputInMainWorld(reasonInput, reason);
        const form = getMoitFormInstance();
        if (form) {
          try { form.setFieldsValue({ issuedRetroactivelyReason: reason }); } catch (e) {}
        }
      }
    }
    return { success: true };
  }

  async function handleBridgeSyncImportDeclarations(impList) {
    try {
      const form = getMoitFormInstance();
      if (form && Array.isArray(impList)) {
        const currentVals = (typeof form.getFieldValue === "function" && form.getFieldValue("importDeclarations")) || [];
        const merged = impList.map((item, idx) => ({
          ...(currentVals[idx] || {}),
          declarationNumber: item.declarationNumber || ""
        }));
        form.setFieldsValue({ importDeclarations: merged });
        return { success: true };
      }
    } catch (e) {
      return { success: false, error: e.message };
    }
    return { success: false };
  }

  async function handleBridgeSyncInvoiceVATs(vatList) {
    try {
      const form = getMoitFormInstance();
      if (form && Array.isArray(vatList)) {
        const currentVals = (typeof form.getFieldValue === "function" && form.getFieldValue("invoiceVATs")) || [];
        const merged = vatList.map((item, idx) => ({
          ...(currentVals[idx] || {}),
          declarationNumber: item.declarationNumber || ""
        }));
        form.setFieldsValue({ invoiceVATs: merged });
        return { success: true };
      }
    } catch (e) {
      return { success: false, error: e.message };
    }
    return { success: false };
  }

  // ========================================================
  // 6. ĐỊNH VỊ CHÍNH XÁC Ô UPLOAD CHO TỪNG DÒNG (ĐÃ SỬA TRIỆT ĐỂ)
  // ========================================================
  window.__moit_used_row_inputs = window.__moit_used_row_inputs || new Set();

  function resetBridgeUsedInputs() {
    window.__moit_used_row_inputs.clear();
    return { success: true };
  }

  function getPageFileInputs() {
    return Array.from(document.querySelectorAll('input[type="file"]')).filter(
      inp => !inp.closest("#ecosys-autofill-widget") && !inp.disabled
    );
  }

  /**
   * TÌM Ô INPUT[TYPE="FILE"] NẰM CÙNG HÀNG NGANG VỚI Ô TEXT INPUT (SỐ HĐ VAT / SỐ TỜ KHAI)
   * Khắc phục hoàn toàn lỗi .closest(".ant-row") dừng nhầm ở .ant-form-item!
   */
  function findFileInputForRowInput(textInput) {
    if (!textInput) return null;

    // Bước 1: Leo ngược lên các thẻ cha cho đến khi gặp container chứa đúng 1 ô input[type="file"]
    let cur = textInput.parentElement;
    for (let depth = 0; depth < 9 && cur && cur !== document.body; depth++) {
      const fInputs = Array.from(cur.querySelectorAll('input[type="file"]')).filter(
        inp => !inp.closest("#ecosys-autofill-widget")
      );
      if (fInputs.length === 1) {
        return fInputs[0];
      }
      if (fInputs.length > 1) {
        // Bước 2: Nếu nhảy lên tới vùng chứa nhiều dòng -> Đối chiếu tọa độ ngang Y (top) trên màn hình
        const targetRect = textInput.getBoundingClientRect();
        if (targetRect.height > 0) {
          let bestInp = null;
          let minDiffY = 9999;
          for (const fInp of fInputs) {
            const visualEl = fInp.closest("button, .ant-btn, .ant-upload, span") || fInp.parentElement;
            const r = visualEl ? visualEl.getBoundingClientRect() : fInp.getBoundingClientRect();
            if (r.height > 0) {
              const diffY = Math.abs(r.top - targetRect.top);
              if (diffY < 45 && diffY < minDiffY) {
                minDiffY = diffY;
                bestInp = fInp;
              }
            }
          }
          if (bestInp) return bestInp;
        }
        break;
      }
      cur = cur.parentElement;
    }
    return null;
  }

  function getIsolatedInputContextText(inp) {
    if (!inp) return "";
    const tr = inp.closest("tr");
    if (tr) return cleanString(tr.textContent || "");

    let cur = inp.parentElement;
    let lastSingleContainer = cur;
    for (let depth = 0; depth < 7 && cur && cur !== document.body; depth++) {
      const cnt = Array.from(cur.querySelectorAll('input[type="file"]')).filter(
        i => !i.closest("#ecosys-autofill-widget")
      ).length;
      if (cnt === 1) {
        lastSingleContainer = cur;
      } else if (cnt > 1) {
        break;
      }
      cur = cur.parentElement;
    }
    return cleanString(lastSingleContainer ? lastSingleContainer.textContent : "");
  }

  function normalizeNumberStr(s) {
    return String(s || "").trim().toLowerCase().replace(/^0+/, "");
  }

  /**
   * Khớp số hiệu từ tên tệp (VD: "612.pdf" -> "612") với danh sách các ô Input Số HĐ VAT hoặc Số Tờ khai NK
   */
  function matchRowInputByNumber(numInputs, fileName, linkedNumber) {
    if (!numInputs || numInputs.length === 0) return -1;

    const baseName = String(fileName || "").replace(/\.[^/.]+$/, "").trim();
    const candidates = [];
    if (linkedNumber) candidates.push(String(linkedNumber).trim());
    if (baseName) candidates.push(baseName);

    const extractedNums = baseName.match(/\d+/g) || [];
    for (const n of extractedNums) {
      if (!candidates.includes(n)) candidates.push(n);
    }

    // Ưu tiên 1: Khớp chính xác 100% số hóa đơn / tờ khai (đã bỏ số 0 ở đầu)
    for (const cand of candidates) {
      const cNorm = normalizeNumberStr(cand);
      if (!cNorm) continue;
      for (let i = 0; i < numInputs.length; i++) {
        const valNorm = normalizeNumberStr(numInputs[i].value);
        if (valNorm && valNorm === cNorm) {
          return i;
        }
      }
    }

    // Ưu tiên 2: Khớp chứa chuỗi đối với số dài (>= 3 ký tự)
    for (const cand of candidates) {
      const cNorm = normalizeNumberStr(cand);
      if (cNorm.length < 3) continue;
      for (let i = 0; i < numInputs.length; i++) {
        const valNorm = normalizeNumberStr(numInputs[i].value);
        if (valNorm && valNorm.length >= 3 && (valNorm === cNorm || valNorm.endsWith(cNorm) || cNorm.endsWith(valNorm))) {
          return i;
        }
      }
    }

    return -1;
  }

  function findBridgeFileInput(fileType, fileName, targetRow, linkedNumber, matchingMode) {
    const fType = (fileType || "").toLowerCase();
    const fName = (fileName || "").toLowerCase();
    const baseNameNoExt = fName.replace(/\.[^/.]+$/, "").trim();
    const allInputs = getPageFileInputs();
    if (allInputs.length === 0) return { input: null, isSingleRow: false };

    const vatNumInputs = Array.from(document.querySelectorAll(
      'input[placeholder*="hóa đơn VAT" i], input[placeholder*="hoá đơn VAT" i], input[placeholder*="Invoice VAT" i], [id*="invoiceVATs"][id*="declarationNumber"]'
    ));
    const impNumInputs = Array.from(document.querySelectorAll(
      'input[placeholder*="Import Declaration" i], input[placeholder*="tờ khai nhập" i], [id*="importDeclarations"][id*="declarationNumber"]'
    ));
    const expDecInput = document.querySelector('input[placeholder="Export Declaration"], [id*="declarations"][id*="declarationNumber"]');
    const expDecFileInput = findFileInputForRowInput(expDecInput);

    // ========================================================
    // BƯỚC 0: KHỚP TRỰC TIẾP THEO SỐ HÓA ĐƠN VAT HOẶC SỐ TỜ KHAI NK ĐÃ ĐIỀN TRÊN TRANG
    // (Xử lý chuẩn xác các file đặt tên dạng số như "612.pdf", "613.pdf", "46883.pdf"...)
    // ========================================================
    const isExplicitOtherType = fType.includes("vandon") || fType.includes("bill") ||
                                fType.includes("bangke") || fType.includes("quytrinh") ||
                                fType === "tokhaixuatkhau" || fType.includes("invoice_attached");

    if (!isExplicitOtherType) {
      // 0.1 Kiểm tra xem tên file / linkedNumber có khớp với dòng Hóa đơn VAT nào trên trang không
      const matchedVatIdx = matchRowInputByNumber(vatNumInputs, fileName, linkedNumber);
      if (matchedVatIdx >= 0) {
        const vatFileInp = findFileInputForRowInput(vatNumInputs[matchedVatIdx]);
        if (vatFileInp) {
          console.log(`[Bridge] 🎯 Đã khớp file '${fileName}' vào dòng Hóa đơn VAT số '${vatNumInputs[matchedVatIdx].value}' (dòng ${matchedVatIdx + 1})`);
          return { input: vatFileInp, isSingleRow: true };
        }
      }

      // 0.2 Kiểm tra xem tên file / linkedNumber có khớp với dòng Tờ khai NK nào trên trang không
      const matchedImpIdx = matchRowInputByNumber(impNumInputs, fileName, linkedNumber);
      if (matchedImpIdx >= 0) {
        const impFileInp = findFileInputForRowInput(impNumInputs[matchedImpIdx]);
        if (impFileInp) {
          console.log(`[Bridge] 🎯 Đã khớp file '${fileName}' vào dòng Tờ khai NK số '${impNumInputs[matchedImpIdx].value}' (dòng ${matchedImpIdx + 1})`);
          return { input: impFileInp, isSingleRow: true };
        }
      }
    }

    // ========================================================
    // 1. HÓA ĐƠN VAT (HoaDonVAT / hoặc file chỉ có số thuần túy như 612.pdf)
    // ========================================================
    const isPureNumberFileName = /^\d+$/.test(baseNameNoExt);
    if (fType.includes("hoadonvat") || fType.includes("vat") || fName.includes("vat") || fName.includes("gtgt") || (isPureNumberFileName && vatNumInputs.length > 0)) {
      let rowIdx = matchRowInputByNumber(vatNumInputs, fileName, linkedNumber);

      if (rowIdx === -1 && matchingMode === "by_order" && typeof targetRow === "number" && targetRow >= 0) {
        rowIdx = targetRow;
      }

      if (rowIdx >= 0 && vatNumInputs[rowIdx]) {
        const inp = findFileInputForRowInput(vatNumInputs[rowIdx]);
        if (inp) return { input: inp, isSingleRow: true };
      }

      // Nếu chọn chế độ gán tuần tự, tìm dòng VAT đầu tiên chưa gắn file
      if (matchingMode === "by_order") {
        for (let i = 0; i < vatNumInputs.length; i++) {
          const inp = findFileInputForRowInput(vatNumInputs[i]);
          if (inp && !window.__moit_used_row_inputs.has(inp)) {
            return { input: inp, isSingleRow: true };
          }
        }
      }

      // TUYỆT ĐỐI KHÔNG cho phép file Hóa đơn VAT rơi xuống mục "Chứng từ khác"!
      return { input: null, isSingleRow: true, reason: `Không tìm thấy dòng Số hóa đơn VAT khớp với tệp '${fileName}'` };
    }

    // ========================================================
    // 2. TỜ KHAI HẢI QUAN NHẬP KHẨU (ToKhaiHQNK_Document - Mục 27, 28)
    // ========================================================
    if (fType.includes("tokhaihqnk") || fType.includes("nhapkhau") || fName.includes("nhapkhau") || fName.includes("tknk") || fName.includes("tk_nhap")) {
      let rowIdx = matchRowInputByNumber(impNumInputs, fileName, linkedNumber);

      if (rowIdx === -1 && typeof targetRow === "number" && targetRow >= 0) {
        rowIdx = targetRow;
      }

      if (rowIdx >= 0 && impNumInputs[rowIdx]) {
        const inp = findFileInputForRowInput(impNumInputs[rowIdx]);
        if (inp) return { input: inp, isSingleRow: true };
      }

      for (let i = 0; i < impNumInputs.length; i++) {
        const inp = findFileInputForRowInput(impNumInputs[i]);
        if (inp && !window.__moit_used_row_inputs.has(inp)) {
          return { input: inp, isSingleRow: true };
        }
      }

      return { input: null, isSingleRow: true, reason: `Không tìm thấy dòng Tờ khai NK cho '${fileName}'` };
    }

    // ========================================================
    // 3. TỜ KHAI HẢI QUAN XUẤT KHẨU (ToKhaiXuatKhau - Mục 25, 26)
    // ========================================================
    if (fType === "tokhaixuatkhau" || (fType.includes("tokhai") && !fType.includes("nhapkhau") && !fType.includes("hqnk"))) {
      if (expDecFileInput) return { input: expDecFileInput, isSingleRow: true };
    }

    // ========================================================
    // 4. VẬN ĐƠN / BILL OF LADING (VanDon / TRANSPORT_INFO)
    // ========================================================
    if (fType.includes("vandon") || fType.includes("transport") || fType.includes("bill") || fName.includes("bl") || fName.includes("bill") || fName.includes("vandon") || fName.includes("waybill")) {
      for (const inp of allInputs) {
        const ctx = getIsolatedInputContextText(inp);
        if (ctx.includes("transportationdocument") || ctx.includes("tailieuvantai") || ctx.includes("vantaidon") || ctx.includes("billoflading")) {
          return { input: inp, isSingleRow: false };
        }
      }
      const vesselInput = document.querySelector('#formCreateUpdate_route_TransportName, input[placeholder*="Vessel" i]');
      if (vesselInput) {
        const col = vesselInput.closest(".ant-col-12, .ant-col");
        const inp = col?.querySelector('input[type="file"]');
        if (inp && inp !== expDecFileInput) return { input: inp, isSingleRow: false };
      }
    }

    // ========================================================
    // 5. HÓA ĐƠN THƯƠNG MẠI (Invoice_attached_Doc)
    // ========================================================
    if (fType.includes("invoice_attached") || fType === "invoicethuongmai" || fType === "commercialinvoice" || (fName.includes("inv") && !fName.includes("vat") && !fType.includes("vat"))) {
      for (const inp of allInputs) {
        const ctx = getIsolatedInputContextText(inp);
        if ((ctx.includes("invoiceattached") || ctx.includes("invoicetoida") || (ctx.includes("invoice") && ctx.includes("5file"))) && !ctx.includes("vat")) {
          return { input: inp, isSingleRow: false };
        }
      }
    }

    // ========================================================
    // 6. BẢNG KÊ CHI PHÍ / BẢNG PHỤ LỤC TT05 (BangKeChiPhi - Dòng 1 bảng Chứng từ)
    // ========================================================
    if (fType.includes("bangke") || fType.includes("chiphi") || fType.includes("bom") || fName.includes("bangke") || fName.includes("chiphi") || fName.includes("bom") || fName.includes("phuluc") || fName.includes("tt05") || fName.includes("wo")) {
      for (const inp of allInputs) {
        const ctx = getIsolatedInputContextText(inp);
        if (ctx.includes("bangphuluc") || ctx.includes("tt05") || ctx.includes("bangke") || ctx.includes("hamluong")) {
          return { input: inp, isSingleRow: false };
        }
      }
    }

    // ========================================================
    // 7. QUY TRÌNH SẢN XUẤT (QuyTrinhSanXuat - Dòng 2 bảng Chứng từ)
    // ========================================================
    if (fType.includes("quytrinh") || fType.includes("sanxuat") || fType.includes("qtsx") || fName.includes("quytrinh") || fName.includes("sanxuat") || fName.includes("qtsx") || fName.includes("process")) {
      for (const inp of allInputs) {
        const ctx = getIsolatedInputContextText(inp);
        if (ctx.includes("quytrinhsanxuat") || ctx.includes("quytrinh")) {
          return { input: inp, isSingleRow: false };
        }
      }
    }

    // ========================================================
    // 8. ĐƠN ĐỀ NGHỊ CẤP C/O & CHỨNG TỪ KHÁC (TAILIEUCHUNGMINH - Dòng 4 bảng Chứng từ)
    // ========================================================
    for (const inp of allInputs) {
      const ctx = getIsolatedInputContextText(inp);
      if (ctx.includes("chungtukhac") || ctx.includes("dondenghi") || ctx.includes("tailieuchungminh") || ctx.includes("otherdocument")) {
        return { input: inp, isSingleRow: false };
      }
    }

    return { input: null, isSingleRow: false, reason: "Không xác định được vị trí ô đính kèm" };
  }

  async function handleBridgeUploadAttachment(payload) {
    const { fileName, fileType, mimeType, base64, targetRow, linkedNumber, matchingMode } = payload || {};
    if (!base64 || !fileName || String(base64).startsWith("<Base64")) {
      return { success: false, reason: "Missing valid base64 data" };
    }

    let fileObj = null;
    try {
      const cleanB64 = base64.includes(",") ? base64.split(",")[1] : base64;
      const byteCharacters = atob(cleanB64.trim());
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: mimeType || "application/pdf" });
      fileObj = new File([blob], fileName, { type: mimeType || "application/pdf", lastModified: Date.now() });
    } catch (e) {
      return { success: false, reason: `Invalid base64: ${e.message}` };
    }

    const { input: targetInput, isSingleRow, reason } = findBridgeFileInput(fileType, fileName, targetRow, linkedNumber, matchingMode);
    if (!targetInput) {
      return { success: false, reason: reason || "FileInput not found" };
    }

    if (isSingleRow) {
      window.__moit_used_row_inputs.add(targetInput);
    }

    try {
      if (targetInput._valueTracker) {
        targetInput._valueTracker.setValue("");
      }

      const dt = new DataTransfer();
      dt.items.add(fileObj);
      targetInput.files = dt.files;

      targetInput.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
      return { success: true, fileName };
    } catch (err) {
      return { success: false, reason: err.message };
    }
  }

  // ========================================================
  // 7. LẮNG NGHE LỆNH CẦU NỐI TỪ CONTENT SCRIPT
  // ========================================================
  window.addEventListener("__moit_bridge_req", async (evt) => {
    const detail = evt.detail;
    if (!detail || !detail.reqId) return;
    const { reqId, action, payload } = detail;
    let result = { success: false };

    try {
      if (action === "setSelect") {
        result = await handleBridgeSetSelect(payload.field, payload.keywords);
      } else if (action === "setCustomDropdown") {
        result = await handleBridgeSetCustomDropdown(payload.field, payload.keywords, payload.inModal);
      } else if (action === "setDatePicker") {
        result = await handleBridgeSetDatePicker(payload);
      } else if (action === "setRetroactive") {
        result = await handleBridgeSetRetroactive(payload.checked, payload.reason);
      } else if (action === "syncFormFields") {
        result = handleBridgeSyncFormFields(payload.fields);
      } else if (action === "syncGoodsHsCode") {
        result = await handleBridgeSyncGoodsHsCode(payload);
      } else if (action === "syncGoodsModalFields") {
        result = await handleBridgeSyncGoodsModalFields(payload.fields);
      } else if (action === "setGoodsModalUnits") {
        result = await handleBridgeSetGoodsModalUnits(payload);
      } else if (action === "closeGoodsModal") {
        result = await handleBridgeCloseGoodsModal();
      } else if (action === "syncImportDeclarations") {
        result = await handleBridgeSyncImportDeclarations(payload.list);
      } else if (action === "syncInvoiceVATs") {
        result = await handleBridgeSyncInvoiceVATs(payload.list);
      } else if (action === "uploadAttachmentViaBridge") {
        result = await handleBridgeUploadAttachment(payload);
      } else if (action === "resetUsedInputs") {
        result = resetBridgeUsedInputs();
      }
    } catch (err) {
      result = { success: false, error: err.message };
    }

    window.dispatchEvent(new CustomEvent("__moit_bridge_res", {
      detail: { reqId, result }
    }));
  });

  // ========================================================
  // 8. MASTER DATA DROPDOWNS PREFETCH
  // ========================================================
  async function loadMoitDropdowns() {
    try {
      const res = await fetch("/HoSo_MauCO/GetDropdowns");
      if (res.ok) {
        const json = await res.json();
        if (json?.data) window.__moit_dropdowns = json.data;
      }
    } catch (e) {}

    try {
      const resGoods = await fetch("/Goods/GetDropdowns");
      if (resGoods.ok) {
        const jsonGoods = await resGoods.json();
        if (jsonGoods?.data) window.__moit_goods_dropdowns = jsonGoods.data;
      }
    } catch (e) {}
  }

  setTimeout(loadMoitDropdowns, 1000);
  console.log("🚀 [eCoSys AutoFill] MAIN World Bridge v2.9.2 đã kích hoạt!");
})();