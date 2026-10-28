/**
 * eCoSys C/O AutoFill Pro - Content Script v2.9.0 (Fixed)
 * - Đồng bộ 100% với MAIN World Bridge (injected_proxy.js)
 * - Sửa lỗi mất Base64 khi tải qua Stream Bridge (port 14008)
 * - Đảo thứ tự chọn Tổ chức cấp & Mẫu C/O lên trước để chống React reset form
 * - Thêm tính năng chọn trực tiếp nhiều file PDF từ máy tính để đính kèm tự động
 */

(function () {
  if (window.__ecosysAutoFillInjected) return;
  window.__ecosysAutoFillInjected = true;

  // Chuyển tiếp request ký số từ MAIN world sang Background Service Worker
  window.addEventListener("__moit_proxy_req", (e) => {
    const detail = e.detail;
    if (!detail || !chrome.runtime?.sendMessage) return;

    chrome.runtime.sendMessage({ action: "proxyMoit", data: detail }, (res) => {
      window.dispatchEvent(new CustomEvent("__moit_proxy_resp", {
        detail: {
          reqId: detail.reqId,
          res: res || { status: 0, responseText: "" }
        }
      }));
    });
  });

  function isMoitSignBusy() {
    return document.documentElement?.dataset?.moitBusy === "1";
  }

  const SAMPLE_DATA = {
    form: "EUR.1",
    issuing_Authority: "Sở Công Thương Tỉnh Khánh Hòa",
    importing_Country: "Lithuania",
    declarationPlace: "Khánh Hòa",
    taxCode: "4200722962",
    maSoDN: "4200722962",
    from_ExporterBusinessName: "NHA TRANG BAY JOINT STOCK COMPANY",
    from_ExporterBusinessNameVN: "CÔNG TY CỔ PHẦN VỊNH NHA TRANG",
    from_AddressLine1: "LOT K1, K2, K3 AND A PART OF K4, SUOI DAU INDUSTRIAL ZONE",
    from_Addressline2: "CAM LAM COMMUNE, KHANH HOA PROVINCE, VIETNAM",
    to_ConsigneeName: "MARISO SEAFOOD LLC",
    to_Addressline1: "VABADUSE PST 8/1, KIVIOLI",
    to_Addressline2: "LUGANUSE VALD, ESTONIA 43125",
    manu_Name: "",
    manu_AddressLine1: "",
    route_TransportationType: "By Sea",
    route_TransportName: "SEASPAN BENEFACTOR 077W",
    route_PortOfLoading: "HO CHI MINH",
    route_PortOfDischange: "KLAIPEDA",
    route_PortOfDestination: "KLAIPEDA",
    route_DepartureDepartureDate: "09/10/2026",
    bill: "YMJAN490421110",
    invoiceNumber: "NT60195",
    invoiceDate: "01/10/2026",
    currency: "USD - Dollar Mỹ",
    goods_Total_FobValue: 251081.55,
    declarationNumbers: "309017425640",
    declarationDates: "01/10/2026",
    remarks: "",
    isIssuedRetroactively: true,
    issuedRetroactivelyReason: "tàu delay",
    goodItems: [
      {
        exportingHsCode: "03048700",
        importingHsCode: "03048700",
        goodsDescription: "FROZEN RED TUNA LOIN",
        originCriterion: "WO",
        countryOfOrigin: "VN",
        quantity: 15000.0,
        quantityUnit: "KILOGRAM",
        markAndNumberOnPackage: "NO MARK",
        packageQuantity: 600,
        packageUnit: "CARTON",
        grossWeight: 16320.0,
        grossWeightUnit: "KGM",
        value: 150161.75,
        currency: "USD - Dollar Mỹ",
        invoiceNumber: "NT60195",
        invoiceDate: "01/10/2026"
      },
      {
        exportingHsCode: "03048700",
        importingHsCode: "03048700",
        goodsDescription: "FROZEN RED TUNA SAKU",
        originCriterion: "WO",
        countryOfOrigin: "VN",
        quantity: 2400.0,
        quantityUnit: "KILOGRAM",
        markAndNumberOnPackage: "NO MARK",
        packageQuantity: 240,
        packageUnit: "CARTON",
        grossWeight: 2688.0,
        grossWeightUnit: "KGM",
        value: 45865.88,
        currency: "USD - Dollar Mỹ",
        invoiceNumber: "NT60195",
        invoiceDate: "01/10/2026"
      },
      {
        exportingHsCode: "03048700",
        importingHsCode: "03048700",
        goodsDescription: "FROZEN RED TUNA STEAK",
        originCriterion: "WO",
        countryOfOrigin: "VN",
        quantity: 5000.0,
        quantityUnit: "KILOGRAM",
        markAndNumberOnPackage: "NO MARK",
        packageQuantity: 500,
        packageUnit: "CARTON",
        grossWeight: 5600.0,
        grossWeightUnit: "KGM",
        value: 55053.92,
        currency: "USD - Dollar Mỹ",
        invoiceNumber: "NT60195",
        invoiceDate: "01/10/2026"
      }
    ]
  };

  // ========================================================
  // 1. TẠO FLOATING WIDGET TRÊN TRANG
  // ========================================================
  function createFloatingWidget() {
    if (document.getElementById("ecosys-autofill-widget")) return;

    const widget = document.createElement("div");
    widget.id = "ecosys-autofill-widget";
    widget.innerHTML = `
      <div class="ecosys-widget-header" id="ecosys-drag-handle">
        <div class="ecosys-widget-title">
          <span>⚡</span> eCoSys C/O AutoFill v2.9.0
        </div>
        <div class="ecosys-widget-controls">
          <button class="ecosys-ctrl-btn" id="ecosys-btn-minimize" title="Thu nhỏ / Mở rộng">−</button>
          <button class="ecosys-ctrl-btn" id="ecosys-btn-close" title="Đóng">✕</button>
        </div>
      </div>
      
      <div class="ecosys-widget-body">
        <div id="ecosys-plugin-status" style="font-size: 11px; padding: 6px 10px; border-radius: 6px; margin-bottom: 2px; display: flex; align-items: center; justify-content: space-between; background: #fef2f2; border: 1px solid #fecaca; color: #991b1b;">
          <span id="ecosys-plugin-status-text">🔌 Ký số (14005): <b>Đang kiểm tra...</b></span>
          <button type="button" id="ecosys-btn-check-plugin" style="background: transparent; border: none; text-decoration: underline; color: #1d4ed8; cursor: pointer; font-size: 11px; font-weight: 600;">Kiểm tra</button>
        </div>

        <div id="ecosys-stream-status" style="font-size: 11px; padding: 6px 10px; border-radius: 6px; margin-bottom: 2px; display: flex; align-items: center; justify-content: space-between; background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af;">
          <span id="ecosys-stream-status-text">⚡ App Stream (14008): <b>Đang kiểm tra...</b></span>
          <button type="button" id="ecosys-btn-check-stream" style="background: transparent; border: none; text-decoration: underline; color: #2563eb; cursor: pointer; font-size: 11px; font-weight: 600;">Kiểm tra</button>
        </div>

        <div style="font-size: 11px; padding: 4px 8px; border-radius: 6px; margin-bottom: 2px; display: flex; align-items: center; justify-content: space-between; background: #f8fafc; border: 1px solid #e2e8f0;">
          <span style="color: #334155; font-weight: 600;">Khớp file HĐ/TK:</span>
          <select id="ecosys-matching-mode" style="font-size: 11px; padding: 2px 4px; border-radius: 4px; border: 1px solid #cbd5e1; background: #fff; cursor: pointer; color: #1e293b;">
            <option value="by_number" selected>🔢 Khớp theo Số HĐ / Tờ khai</option>
            <option value="by_order">➡️ Gán tuần tự dòng 1, 2, 3...</option>
          </select>
        </div>

        <button class="ecosys-btn-primary" id="ecosys-btn-paste-fill">
          📋 Dán từ Clipboard & Điền Ngay
        </button>

        <div class="ecosys-grid-btns">
          <button class="ecosys-btn-secondary" id="ecosys-btn-upload">
            📂 Chọn file JSON
          </button>
          <button class="ecosys-btn-secondary" id="ecosys-btn-demo">
            🧪 Nạp thử Demo
          </button>
        </div>

        <button class="ecosys-btn-secondary" id="ecosys-btn-pick-pdfs" style="width: 100%; margin-top: 2px; background: #eff6ff; border-color: #93c5fd; color: #1d4ed8; font-weight: 600;">
          📎 Chọn thêm các tệp PDF chứng từ (Đính kèm)
        </button>

        <input type="file" id="ecosys-file-input" accept=".json" style="display: none;" />
        <input type="file" id="ecosys-pdf-input" multiple accept=".pdf,.png,.jpg,.jpeg,.doc,.docx,.xls,.xlsx" style="display: none;" />

        <textarea class="ecosys-textarea" id="ecosys-json-input" placeholder="Dán nội dung JSON vào đây hoặc dùng nút ở trên..."></textarea>

        <button class="ecosys-btn-primary" id="ecosys-btn-fill" style="background: #0f9d58;">
          🚀 BẮT ĐẦU ĐIỀN & ĐÍNH KÈM TỰ ĐỘNG
        </button>

        <div style="font-size: 11px; font-weight: bold; color: #475569; margin-top: 4px;">
          Nhật ký thực hiện:
        </div>
        <div class="ecosys-logs-box" id="ecosys-logs">
          <div class="ecosys-log-line ecosys-log-info">[Sẵn sàng] Đang chờ nạp dữ liệu C/O...</div>
        </div>
      </div>
    `;

    document.body.appendChild(widget);
    setupWidgetEvents(widget);
  }

  function logMessage(msg, type = "info") {
    const box = document.getElementById("ecosys-logs");
    if (!box) return;
    const time = new Date().toLocaleTimeString();
    const line = document.createElement("div");
    line.className = `ecosys-log-line ecosys-log-${type}`;
    line.textContent = `[${time}] ${msg}`;
    box.appendChild(line);
    box.scrollTop = box.scrollHeight;
  }

  function classifyFileTypeByName(fileName) {
    const fn = removeVietnameseTones(fileName || "").toLowerCase();
    const baseNoExt = fn.replace(/\.[^/.]+$/, "").trim();

    if (fn.includes("vat") || fn.includes("gtgt") || fn.includes("hdvat")) return "HoaDonVAT";
    if (fn.includes("tknk") || fn.includes("nhapkhau") || fn.includes("tk_nhap") || fn.includes("import")) return "ToKhaiHQNK_Document";
    if (fn.includes("tkxk") || fn.includes("xuatkhau") || fn.includes("tk_xuat") || (fn.includes("tokhai") && !fn.includes("nk"))) return "ToKhaiXuatKhau";
    if (fn.includes("bl") || fn.includes("bill") || fn.includes("vandon") || fn.includes("waybill")) return "VanDon";
    if (fn.includes("bangke") || fn.includes("chiphi") || fn.includes("phuluc") || fn.includes("tt05") || fn.includes("bom") || fn.includes("wo")) return "BangKeChiPhi";
    if (fn.includes("quytrinh") || fn.includes("sanxuat") || fn.includes("qtsx")) return "QuyTrinhSanXuat";
    if (fn.includes("inv") || fn.includes("commercial")) return "Invoice_attached_Doc";

    // Nếu tên file chỉ chứa số (ví dụ: 612.pdf, 46883.pdf, 0000122.pdf) -> Mặc định là Hóa đơn VAT (hoặc Tờ khai nếu đủ 12 số)
    if (/^\d+$/.test(baseNoExt)) {
      return baseNoExt.length >= 11 ? "ToKhaiHQNK_Document" : "HoaDonVAT";
    }
    return "TAILIEUCHUNGMINH";
  }

  function setupWidgetEvents(widget) {
    const handle = widget.querySelector("#ecosys-drag-handle");
    let isDragging = false, startX, startY, initialLeft, initialTop;

    handle.addEventListener("mousedown", (e) => {
      if (e.target.tagName === "BUTTON") return;
      isDragging = true;
      startX = e.clientX;
      startY = e.clientY;
      const rect = widget.getBoundingClientRect();
      initialLeft = rect.left;
      initialTop = rect.top;
      widget.style.right = "auto";
      widget.style.left = `${initialLeft}px`;
      widget.style.top = `${initialTop}px`;
      handle.style.cursor = "grabbing";
    });

    document.addEventListener("mousemove", (e) => {
      if (!isDragging) return;
      widget.style.left = `${initialLeft + (e.clientX - startX)}px`;
      widget.style.top = `${initialTop + (e.clientY - startY)}px`;
    });

    document.addEventListener("mouseup", () => {
      if (isDragging) {
        isDragging = false;
        handle.style.cursor = "grab";
      }
    });

    widget.querySelector("#ecosys-btn-minimize").addEventListener("click", () => {
      widget.classList.toggle("minimized");
      const btn = widget.querySelector("#ecosys-btn-minimize");
      btn.textContent = widget.classList.contains("minimized") ? "+" : "−";
    });

    widget.querySelector("#ecosys-btn-close").addEventListener("click", () => {
      widget.style.display = "none";
    });

    widget.querySelector("#ecosys-btn-demo").addEventListener("click", () => {
      widget.querySelector("#ecosys-json-input").value = JSON.stringify(SAMPLE_DATA, null, 2);
      logMessage("Đã nạp bộ dữ liệu mẫu chuẩn (EUR.1 / Khánh Hòa)!", "success");
    });

    const fileInput = widget.querySelector("#ecosys-file-input");
    widget.querySelector("#ecosys-btn-upload").addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (event) => {
        widget.querySelector("#ecosys-json-input").value = event.target.result;
        logMessage(`Đã nạp file JSON: ${file.name}`, "success");
      };
      reader.readAsText(file);
    });

    // Nút chọn trực tiếp nhiều tệp PDF chứng từ từ máy tính
    const pdfInput = widget.querySelector("#ecosys-pdf-input");
    widget.querySelector("#ecosys-btn-pick-pdfs").addEventListener("click", () => pdfInput.click());
    pdfInput.addEventListener("change", async (e) => {
      const files = Array.from(e.target.files || []);
      if (files.length === 0) return;

      let currentJson = {};
      const txtEl = widget.querySelector("#ecosys-json-input");
      try {
        if (txtEl.value.trim()) currentJson = JSON.parse(txtEl.value.trim());
      } catch (err) {
        currentJson = {};
      }

      if (!Array.isArray(currentJson.attachments)) currentJson.attachments = [];

      for (const f of files) {
        const b64 = await new Promise((resolve) => {
          const r = new FileReader();
          r.onload = () => resolve(r.result);
          r.onerror = () => resolve("");
          r.readAsDataURL(f);
        });
        if (b64) {
          const detectedType = classifyFileTypeByName(f.name);
          currentJson.attachments.push({
            fileName: f.name,
            fileType: detectedType,
            mimeType: f.type || "application/pdf",
            base64: b64
          });
          logMessage(`📎 Đã nạp tệp '${f.name}' -> Phân loại: [${detectedType}]`, "info");
        }
      }

      txtEl.value = JSON.stringify(currentJson, null, 2);
      logMessage(`✅ Đã thêm ${files.length} tệp chứng từ vào danh sách chờ đính kèm!`, "success");
      pdfInput.value = "";
    });

    widget.querySelector("#ecosys-btn-paste-fill").addEventListener("click", async () => {
      try {
        const text = await navigator.clipboard.readText();
        if (!text || !text.trim().startsWith("{")) {
          logMessage("Clipboard không chứa dữ liệu JSON hợp lệ!", "warn");
          alert("Bộ nhớ tạm (Clipboard) chưa có dữ liệu JSON.");
          return;
        }
        widget.querySelector("#ecosys-json-input").value = text;
        logMessage("Đã đọc JSON từ Clipboard!", "info");
        executeAutoFill();
      } catch (err) {
        logMessage(`Không thể đọc Clipboard: ${err.message}`, "error");
      }
    });

    widget.querySelector("#ecosys-btn-fill").addEventListener("click", executeAutoFill);

    widget.querySelector("#ecosys-btn-check-plugin")?.addEventListener("click", (e) => {
      e.preventDefault();
      updatePluginStatusUI(true);
    });

    widget.querySelector("#ecosys-btn-check-stream")?.addEventListener("click", (e) => {
      e.preventDefault();
      updateStreamStatusUI(true);
    });

    setTimeout(() => {
      updatePluginStatusUI(false);
      updateStreamStatusUI(false);
    }, 600);
  }

  // ========================================================
  // 2. HÀM TIỆN ÍCH & KIỂM TRA KẾT NỐI
  // ========================================================
  function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function callMoitBridge(action, payload) {
    return new Promise((resolve) => {
      const reqId = "bridge_" + Math.random().toString(36).slice(2) + Date.now();
      const handler = (evt) => {
        if (evt.detail && evt.detail.reqId === reqId) {
          window.removeEventListener("__moit_bridge_res", handler);
          resolve(evt.detail.result || { success: true });
        }
      };
      window.addEventListener("__moit_bridge_res", handler);
      window.dispatchEvent(new CustomEvent("__moit_bridge_req", {
        detail: { reqId, action, payload }
      }));
      setTimeout(() => {
        window.removeEventListener("__moit_bridge_res", handler);
        resolve({ success: false, timeout: true });
      }, 8000);
    });
  }

  async function checkMoitSignPluginRunning() {
    try {
      if (chrome.runtime?.sendMessage) {
        const bgRes = await new Promise((resolve) => {
          chrome.runtime.sendMessage({ action: "checkMoitPlugin" }, (response) => {
            resolve(chrome.runtime.lastError ? null : response);
          });
        });
        if (bgRes && bgRes.online) return true;
      }
    } catch (e) {}
    return false;
  }

  async function updatePluginStatusUI(showLog = false) {
    const textEl = document.getElementById("ecosys-plugin-status-text");
    const boxEl = document.getElementById("ecosys-plugin-status");
    if (!textEl || !boxEl) return false;

    textEl.innerHTML = `🔌 Ký số (14005): <i>Đang kiểm tra...</i>`;
    const isOnline = await checkMoitSignPluginRunning();

    if (isOnline) {
      boxEl.style.background = "#f0fdf4";
      boxEl.style.borderColor = "#bbf7d0";
      boxEl.style.color = "#166534";
      textEl.innerHTML = `🔌 Ký số (14005): <b>Sẵn sàng</b> ✅`;
      if (showLog) logMessage("✅ MOITSignPlugin (cổng 14005) đang hoạt động tốt!", "success");
    } else {
      boxEl.style.background = "#fef2f2";
      boxEl.style.borderColor = "#fecaca";
      boxEl.style.color = "#991b1b";
      textEl.innerHTML = `🔌 Ký số (14005): <b>Chưa bật</b>`;
      if (showLog) logMessage("⚠️ MOITSignPlugin chưa bật!", "warn");
    }
    return isOnline;
  }

  function updateStreamStatusUI(showLog = false) {
    const textEl = document.getElementById("ecosys-stream-status-text");
    const boxEl = document.getElementById("ecosys-stream-status");
    if (!textEl || !boxEl) return;
    textEl.innerHTML = "⚡ App Stream (14008): <b>Đang kiểm tra...</b>";

    chrome.runtime?.sendMessage?.({ action: "checkLocalStream" }, (res) => {
      if (res && res.online) {
        boxEl.style.background = "#f0fdf4";
        boxEl.style.borderColor = "#bbf7d0";
        boxEl.style.color = "#166534";
        textEl.innerHTML = `⚡ App Stream: <b style="color: #15803d;">Sẵn sàng (cổng ${res.port})</b> ✅`;
        if (showLog) logMessage(`✅ Kết nối App Stream thành công tại cổng ${res.port}!`, "success");
      } else {
        boxEl.style.background = "#fffbeb";
        boxEl.style.borderColor = "#fef3c7";
        boxEl.style.color = "#b45309";
        textEl.innerHTML = `⚡ App Stream: <b>Chưa mở App (vẫn dùng được JSON/PDF)</b>`;
        if (showLog) logMessage("ℹ️ Cổng 14008 chưa mở. Bạn vẫn có thể đính kèm qua Base64 hoặc nút Chọn PDF.", "info");
      }
    });
  }

  function removeVietnameseTones(str) {
    if (!str) return "";
    return String(str)
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[đĐ]/g, (m) => (m === "đ" ? "d" : "D"));
  }

  function cleanString(str) {
    if (!str) return "";
    return removeVietnameseTones(str).toLowerCase().replace(/[^a-z0-9]/g, "");
  }

  function normalizeUnit(unitStr) {
    if (!unitStr) return "KILOGRAM";
    const clean = cleanString(unitStr);
    if (clean === "kg" || clean === "kgm" || clean.includes("kilo")) return "KILOGRAM";
    if (clean === "ctn" || clean.includes("carton") || clean.includes("thung")) return "CARTON";
    if (clean === "bx" || clean === "box" || clean.includes("hop")) return "BOX";
    if (clean === "bag" || clean === "bg" || clean.includes("bao") || clean.includes("sack")) return "BAG";
    if (clean === "pkg" || clean === "pk" || clean.includes("package") || clean.includes("kien")) return "PACKAGE";
    if (clean === "plt" || clean.includes("pallet")) return "PALLET";
    if (clean === "ton" || clean === "tonne" || clean === "tne" || clean === "tan") return "TONNE";
    if (clean === "pce" || clean.includes("piece") || clean.includes("cai") || clean.includes("chiec")) return "PIECE";
    if (clean === "set" || clean.includes("bo")) return "SET";
    return unitStr.toUpperCase().trim();
  }

  function normalizeCurrency(currStr) {
    if (!currStr) return "USD - Dollar Mỹ";
    const clean = cleanString(currStr);
    if (clean.includes("usd") || clean.includes("dollar")) return "USD - Dollar Mỹ";
    if (clean.includes("eur") || clean.includes("euro")) return "EUR - Đồng Euro";
    if (clean.includes("vnd") || clean.includes("dong")) return "VND - Đồng Việt Nam";
    if (clean.includes("cny") || clean.includes("rmb")) return "CNY - Nhân dân tệ";
    if (clean.includes("jpy") || clean.includes("yen")) return "JPY - Yên Nhật";
    return currStr;
  }

  function getCountryKeywords(countryStr) {
    if (!countryStr) return ["Japan", "Nhật Bản", "JP"];
    const c = countryStr.trim();
    const clean = cleanString(c);
    const countryMap = {
      "jp": ["Japan", "Nhật Bản", "JP"],
      "japan": ["Japan", "Nhật Bản", "JP"],
      "lt": ["Lithuania", "Litva", "Lít-va", "LT"],
      "lithuania": ["Lithuania", "Litva", "Lít-va", "LT"],
      "ee": ["Estonia", "EE"],
      "estonia": ["Estonia", "EE"],
      "es": ["Spain", "Tây Ban Nha", "ES"],
      "spain": ["Spain", "Tây Ban Nha", "ES"],
      "cn": ["China", "Trung Quốc", "CN"],
      "china": ["China", "Trung Quốc", "CN"],
      "kr": ["Korea", "Hàn Quốc", "KR"],
      "korea": ["Korea", "Hàn Quốc", "KR"],
      "de": ["Germany", "Đức", "DE"],
      "germany": ["Germany", "Đức", "DE"],
      "fr": ["France", "Pháp", "FR"],
      "france": ["France", "Pháp", "FR"],
      "nl": ["Netherlands", "Hà Lan", "NL"],
      "netherlands": ["Netherlands", "Hà Lan", "NL"],
      "it": ["Italy", "Ý", "IT"],
      "italy": ["Italy", "Ý", "IT"],
      "be": ["Belgium", "Bỉ", "BE"],
      "belgium": ["Belgium", "Bỉ", "BE"],
      "us": ["United States", "Mỹ", "Hoa Kỳ", "US"],
      "th": ["Thailand", "Thái Lan", "TH"],
      "au": ["Australia", "Úc", "AU"],
      "gb": ["United Kingdom", "Anh", "GB"],
      "uk": ["United Kingdom", "Anh", "GB"]
    };
    return countryMap[clean] || [c, removeVietnameseTones(c)];
  }

  function formatDateToVN(dateStr) {
    if (!dateStr) return "";
    const s = String(dateStr).trim();
    const isoMatch = s.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/);
    if (isoMatch) {
      return `${isoMatch[3].padStart(2, "0")}/${isoMatch[2].padStart(2, "0")}/${isoMatch[1]}`;
    }
    const vnMatch = s.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})/);
    if (vnMatch) {
      return `${vnMatch[1].padStart(2, "0")}/${vnMatch[2].padStart(2, "0")}/${vnMatch[3]}`;
    }
    return s;
  }

  /**
   * Điền DatePicker thông qua MAIN World Bridge để kích hoạt đúng React Fiber của rc-picker
   */
  async function setDatePickerValue(dateInput, dateStr) {
    if (!dateInput || !dateStr) return false;
    const formatted = formatDateToVN(dateStr);
    if (!formatted) return false;

    if (!dateInput.id) {
      dateInput.id = "ecosys_dp_" + Math.random().toString(36).slice(2, 9);
    }
    const res = await callMoitBridge("setDatePicker", {
      id: dateInput.id,
      formattedDate: formatted
    });
    return Boolean(res && res.success);
  }

  function setNativeValue(element, value) {
    if (!element) return false;
    try {
      const proto = element.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
      if (setter) setter.call(element, value);
      else element.value = value;
      element.dispatchEvent(new Event("input", { bubbles: true }));
      element.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    } catch (e) {
      return false;
    }
  }

  // ========================================================
  // 3. QUẢN LÝ DÒNG TỜ KHAI NHẬP KHẨU & HÓA ĐƠN VAT
  // ========================================================
  async function ensureVatRowsCount(requiredCount) {
    if (requiredCount <= 1) return;
    const getVatInputs = () => Array.from(document.querySelectorAll(
      'input[placeholder*="hóa đơn VAT" i], input[placeholder*="hoá đơn VAT" i], input[placeholder*="Invoice VAT" i], [id*="invoiceVATs"][id*="declarationNumber"]'
    ));
    let currentInputs = getVatInputs();
    let loops = 0;
    while (currentInputs.length < requiredCount && loops < requiredCount + 2) {
      loops++;
      const allBtns = Array.from(document.querySelectorAll("button, .ant-btn"));
      const addBtn = allBtns.find(b => {
        const t = (b.textContent || "").toLowerCase().trim();
        return t.includes("thêm ho") || t.includes("thêm hoá đơn") || t.includes("thêm hóa đơn") || t.includes("invoice vat");
      });
      if (!addBtn) break;
      const prevLen = currentInputs.length;
      addBtn.click();
      for (let w = 0; w < 12; w++) {
        await delay(150);
        currentInputs = getVatInputs();
        if (currentInputs.length > prevLen) break;
      }
    }
  }

  async function ensureImportRowsCount(requiredCount) {
    if (requiredCount <= 1) return;
    const getImpInputs = () => Array.from(document.querySelectorAll(
      'input[placeholder*="Import Declaration" i], input[placeholder*="tờ khai nhập" i], [id*="importDeclarations"][id*="declarationNumber"]'
    ));
    let currentInputs = getImpInputs();
    let loops = 0;
    while (currentInputs.length < requiredCount && loops < requiredCount + 2) {
      loops++;
      const allBtns = Array.from(document.querySelectorAll("button, .ant-btn")).filter(b =>
        (b.textContent || "").toLowerCase().includes("thêm tờ khai")
      );
      const addBtn = allBtns.length > 1 ? allBtns[allBtns.length - 1] : allBtns[0];
      if (!addBtn) break;
      const prevLen = currentInputs.length;
      addBtn.click();
      for (let w = 0; w < 12; w++) {
        await delay(150);
        currentInputs = getImpInputs();
        if (currentInputs.length > prevLen) break;
      }
    }
  }

  function findRowDateInput(numInput, listName, idx) {
    let el = document.getElementById(`formCreateUpdate_${listName}_${idx}_declarationDate`) ||
             document.getElementById(`${listName}_${idx}_declarationDate`) ||
             document.querySelector(`[id$="${listName}_${idx}_declarationDate"]`);
    if (el) return el;
    const col = numInput?.closest(".ant-col");
    if (col && col.nextElementSibling) {
      el = col.nextElementSibling.querySelector(".ant-picker input, input");
      if (el) return el;
    }
    const outerRow = numInput?.closest(".ant-row:not(.ant-form-item-row)");
    return outerRow ? outerRow.querySelector(".ant-picker input") : null;
  }

  // ========================================================
  // 4. XỬ LÝ TẢI LÊN TỆP ĐÍNH KÈM (ĐÃ SỬA LỖI MẤT BASE64)
  // ========================================================
  async function handleUploadAttachment(attInfo, matchingMode = "by_number") {
    if (!attInfo || !attInfo.base64 || !attInfo.fileName) return false;

    const fileType = attInfo.fileType || classifyFileTypeByName(attInfo.fileName);
    const isToKhaiXuat = fileType === "ToKhaiXuatKhau" ||
      (fileType.toLowerCase().includes("tokhai") && !fileType.toLowerCase().includes("nhapkhau") && !fileType.toLowerCase().includes("hqnk"));

    // Đợi spinner tải file trước đó kết thúc
    let waitSpin = 0;
    while (waitSpin < 20) {
      const hasSpinner = !!document.querySelector(".anticon-loading, .ant-upload-list-item-uploading, .ant-spin-spinning");
      if (!hasSpinner && !isMoitSignBusy()) break;
      await delay(500);
      waitSpin++;
    }

    const bridgeResult = await callMoitBridge("uploadAttachmentViaBridge", {
      fileName: attInfo.fileName,
      fileType: fileType,
      mimeType: attInfo.mimeType || "application/pdf",
      base64: attInfo.base64,
      targetRow: attInfo.targetRow,
      linkedNumber: attInfo.linkedNumber,
      matchingMode: matchingMode
    });

    if (bridgeResult && bridgeResult.success) {
      logMessage(`📤 Đã nạp tệp vào ô đính kèm: ${attInfo.fileName} [${fileType}]`, "info");

      if (isToKhaiXuat) {
        logMessage(`⏳ Đang chờ ký số USB Token cho '${attInfo.fileName}'...`, "info");
        await delay(2000);
        let elapsed = 0;
        while (elapsed < 90) {
          await delay(1000);
          elapsed++;
          const hasSpinner = !!document.querySelector(".anticon-loading, .ant-upload-list-item-uploading, .ant-spin-spinning");
          if (!hasSpinner && !isMoitSignBusy() && elapsed >= 3) break;
        }
        await delay(2500);
      } else {
        let elapsed = 0;
        while (elapsed < 15) {
          await delay(600);
          elapsed++;
          const hasSpinner = !!document.querySelector(".anticon-loading, .ant-upload-list-item-uploading, .ant-spin-spinning");
          if (!hasSpinner && elapsed >= 2) break;
        }
        await delay(800);
      }
      return true;
    } else {
      logMessage(`⚠️ Bridge không tìm thấy ô cho '${attInfo.fileName}': ${bridgeResult?.reason || "Unknown"}`, "warn");
      return false;
    }
  }

  // ========================================================
  // 5. QUY TRÌNH ĐIỀN TỰ ĐỘNG TOÀN DIỆN (MAIN ENGINE)
  // ========================================================
  async function executeAutoFill() {
    const rawText = document.getElementById("ecosys-json-input").value.trim();
    if (!rawText) {
      alert("Chưa có dữ liệu JSON! Hãy bấm 'Nạp thử Demo', 'Dán từ Clipboard' hoặc 'Chọn thêm tệp PDF'.");
      return;
    }

    let data;
    try {
      data = JSON.parse(rawText);
    } catch (e) {
      logMessage("Lỗi cú pháp JSON: " + e.message, "error");
      return;
    }

    logMessage("🚀 Bắt đầu điền tự động v2.9.0...", "info");

    // ----------------------------------------------------
    // BƯỚC 1: CHỌN TỔ CHỨC CẤP & MẪU C/O TRƯỚC TIÊN (TRÁNH REACT RESET FORM)
    // ----------------------------------------------------
    if (data.issuing_Authority) {
      logMessage(`Đang chọn [Tổ chức cấp phép]: ${data.issuing_Authority}...`, "info");
      await callMoitBridge("setSelect", { field: "issuing_Authority", keywords: [data.issuing_Authority] });
      await delay(1500);
    }

    if (data.form) {
      const rawForm = String(data.form).trim();
      let fClean = removeVietnameseTones(rawForm).replace(/^(Mau|Form)\s*/i, "").trim().toUpperCase();
      let formCode = fClean.includes("EUR") ? "EUR" : fClean;
      logMessage(`Đang chọn [Mẫu C/O]: ${rawForm}...`, "info");
      await callMoitBridge("setSelect", { field: "form", keywords: [formCode, fClean, "EUR.1", `Mẫu ${fClean}`, rawForm] });
      await delay(1500);
    }

    // 2. Nước nhập khẩu (importing_Country)
    if (data.importing_Country) {
      const countryKeywords = getCountryKeywords(data.importing_Country);
      logMessage(`Đang chọn [Nước nhập khẩu]: ${data.importing_Country}...`, "info");
      await callMoitBridge("setCustomDropdown", { field: "importing_Country", keywords: countryKeywords, inModal: false });
      await delay(1200);
    }

    // 3. Phương thức vận chuyển & Cảng bốc / dỡ / nơi khai báo
    if (data.route_TransportationType) {
      await callMoitBridge("setSelect", { field: "route_TransportationType", keywords: [data.route_TransportationType, "By Sea"] });
      await delay(300);
    }

    if (data.route_PortOfLoading) {
      const polRaw = removeVietnameseTones(data.route_PortOfLoading).toUpperCase();
      let polKws = [data.route_PortOfLoading, "CANG CAT LAI (HCM)", "CAT LAI"];
      if (polRaw.includes("HAI PHONG")) polKws = ["CANG HAI PHONG", "HAI PHONG"];
      else if (polRaw.includes("DA NANG")) polKws = ["CANG DA NANG", "DA NANG"];
      else if (polRaw.includes("QUY NHON")) polKws = ["CANG QUY NHON", "QUY NHON"];
      await callMoitBridge("setSelect", { field: "route_PortOfLoading", keywords: polKws });
      await delay(300);
    }

    if (data.route_PortOfDischange) {
      await callMoitBridge("setCustomDropdown", {
        field: "route_PortOfDischange",
        keywords: [data.route_PortOfDischange.trim()],
        inModal: false
      });
      await delay(500);
    }

    const destPort = data.route_PortOfDestination || data.route_PortOfDischange;
    if (destPort) {
      await callMoitBridge("setCustomDropdown", {
        field: "route_PortOfDestination",
        keywords: [destPort.trim()],
        inModal: false
      });
      await delay(350);
    }

    if (data.declarationPlace) {
      await callMoitBridge("setSelect", { field: "declarationPlace", keywords: [data.declarationPlace, "Khánh Hòa"] });
      await delay(300);
    }

    // ----------------------------------------------------
    // BƯỚC 2: ĐIỀN CÁC Ô VĂN BẢN & ĐỒNG BỘ VÀO ANT DESIGN FORMSTORE
    // ----------------------------------------------------
    const isRetroactive = Boolean(data.isIssuedRetroactively || (data.remarks && /issued\s*retro/i.test(data.remarks)));
    let cleanRemarks = data.remarks || "";
    if (isRetroactive && cleanRemarks) {
      cleanRemarks = cleanRemarks.replace(/issued\s*retro(actively|spectively)/gi, "").replace(/^[,\s;.-]+|[,\s;.-]+$/g, "").trim();
    }

    const basicFieldsObj = {
      from_ExporterBusinessName: data.from_ExporterBusinessName,
      from_ExporterBusinessNameVN: data.from_ExporterBusinessNameVN,
      from_AddressLine1: data.from_AddressLine1,
      from_Addressline2: data.from_Addressline2,
      taxCode: data.taxCode,
      maSoDN: data.maSoDN || data.taxCode,
      to_ConsigneeName: data.to_ConsigneeName,
      to_Addressline1: data.to_Addressline1,
      to_Addressline2: data.to_Addressline2,
      route_TransportName: data.route_TransportName,
      bill: data.bill,
      invoiceNumber: data.invoiceNumber,
      goods_Total_FobValue: data.goods_Total_FobValue,
      remarks: cleanRemarks,
      manu_Name: data.manu_Name,
      manu_AddressLine1: data.manu_AddressLine1,
      manu_AddressLine2: data.manu_AddressLine2 || data.manu_Addressline2
    };

    const syncRes = await callMoitBridge("syncFormFields", { fields: basicFieldsObj });
    logMessage(`✅ Đã đồng bộ các trường thông tin chung vào FormStore!`, "success");

    // Ngày khởi hành & Ngày hóa đơn
    if (data.route_DepartureDepartureDate) {
      const depDate = document.getElementById("formCreateUpdate_route_DepartureDepartureDate") ||
                      document.querySelector('[id$="route_DepartureDepartureDate"]');
      if (depDate) await setDatePickerValue(depDate, data.route_DepartureDepartureDate);
    }

    if (data.invoiceDate) {
      const invDate = document.getElementById("formCreateUpdate_invoiceDate") ||
                      document.querySelector('[id$="_invoiceDate"]');
      if (invDate) await setDatePickerValue(invDate, data.invoiceDate);
    }

    // Tờ khai xuất khẩu (Mục 25, 26)
    if (data.declarationNumbers) {
      const decInput = document.querySelector('input[placeholder="Export Declaration"], [id*="declarations"][id*="declarationNumber"]');
      if (decInput) setNativeValue(decInput, String(data.declarationNumbers));
    }
    if (data.declarationDates) {
      const expDateInput = document.getElementById("formCreateUpdate_declarations_0_declarationDate") ||
                           document.querySelector('[id$="declarations_0_declarationDate"]');
      if (expDateInput) await setDatePickerValue(expDateInput, String(data.declarationDates));
    }

    // C/O cấp sau (Issued Retrospectively)
    if (isRetroactive) {
      const reasonVal = data.issuedRetroactivelyReason || data.reason || "tàu delay";
      await callMoitBridge("setRetroactive", { checked: true, reason: reasonVal });
      await delay(300);
    }

    // Tờ khai nhập khẩu (Mục 27, 28)
    let impList = Array.isArray(data.importDeclarationList) ? data.importDeclarationList : [];
    if (impList.length === 0 && data.importDeclarationNumbers) {
      const nos = String(data.importDeclarationNumbers).split(",").map(s => s.trim()).filter(Boolean);
      const dts = data.importDeclarationDates ? String(data.importDeclarationDates).split(",").map(s => s.trim()) : [];
      impList = nos.map((no, i) => ({ declarationNumber: no, declarationDate: dts[i] || "" }));
    }

    if (impList.length > 0) {
      await ensureImportRowsCount(impList.length);
      await callMoitBridge("syncImportDeclarations", { list: impList });
      const impInputs = Array.from(document.querySelectorAll('input[placeholder*="Import Declaration" i], [id*="importDeclarations"][id*="declarationNumber"]'));
      for (let i = 0; i < impList.length; i++) {
        if (impInputs[i] && impList[i].declarationNumber) {
          setNativeValue(impInputs[i], String(impList[i].declarationNumber));
          if (impList[i].declarationDate) {
            const dInp = findRowDateInput(impInputs[i], "importDeclarations", i);
            if (dInp) await setDatePickerValue(dInp, impList[i].declarationDate);
          }
        }
      }
    }

    // Hóa đơn VAT (Mục 29, 30)
    let vatList = Array.isArray(data.invoiceVATList) ? data.invoiceVATList : [];
    if (vatList.length === 0 && data.invoiceVATNumbers) {
      const nos = String(data.invoiceVATNumbers).split(",").map(s => s.trim()).filter(Boolean);
      const dts = data.invoiceVATDates ? String(data.invoiceVATDates).split(",").map(s => s.trim()) : [];
      vatList = nos.map((no, i) => ({ declarationNumber: no, declarationDate: dts[i] || "" }));
    }

    const vatAttachments = (data.attachments || []).filter(a =>
      (a.fileType || "").includes("HoaDonVAT") || (a.fileName || "").toLowerCase().includes("vat")
    );
    const requiredVatRows = Math.max(vatList.length, vatAttachments.length);
    if (requiredVatRows > 1) await ensureVatRowsCount(requiredVatRows);

    if (vatList.length > 0) {
      await callMoitBridge("syncInvoiceVATs", { list: vatList });
      const vatInputs = Array.from(document.querySelectorAll(
        'input[placeholder*="hóa đơn VAT" i], input[placeholder*="hoá đơn VAT" i], input[placeholder*="Invoice VAT" i], [id*="invoiceVATs"][id*="declarationNumber"]'
      ));
      for (let i = 0; i < vatList.length; i++) {
        if (vatInputs[i] && vatList[i].declarationNumber) {
          setNativeValue(vatInputs[i], String(vatList[i].declarationNumber));
          if (vatList[i].declarationDate) {
            const dInp = findRowDateInput(vatInputs[i], "invoiceVATs", i);
            if (dInp) await setDatePickerValue(dInp, vatList[i].declarationDate);
          }
        }
      }
    }

    // ----------------------------------------------------
    // BƯỚC 3: ĐIỀN DANH SÁCH HÀNG HÓA (MODAL)
    // ----------------------------------------------------
    if (Array.isArray(data.goodItems) && data.goodItems.length > 0) {
      logMessage(`Đang điền ${data.goodItems.length} dòng hàng hóa...`, "info");

      for (let i = 0; i < data.goodItems.length; i++) {
        const item = data.goodItems[i];
        let modal = document.querySelector(".ant-modal:not([style*='display: none'])");
        if (!modal) {
          const addItemBtn = Array.from(document.querySelectorAll("button, .ant-btn")).find(b => {
            const text = (b.textContent || "").toLowerCase().trim();
            const title = (b.getAttribute("title") || "").toLowerCase();
            return text === "add item" || title.includes("thêm mới sản phẩm") || text.includes("add item");
          });
          if (addItemBtn) {
            addItemBtn.click();
            await delay(700);
            modal = document.querySelector(".ant-modal:not([style*='display: none'])");
          }
        }

        if (!modal) {
          logMessage("⚠️ Không mở được Modal hàng hóa!", "error");
          break;
        }

        if (item.exportingHsCode) {
          const hsCode = String(item.exportingHsCode).replace(/\D/g, "").substring(0, 8);
          await callMoitBridge("setCustomDropdown", { field: "exportingHsCode", keywords: [hsCode], inModal: true });
          await callMoitBridge("syncGoodsHsCode", { exportingHsCode: hsCode, importingHsCode: item.importingHsCode || hsCode });
          await delay(400);
        }

        const markVal = (item.markAndNumberOnPackage && item.markAndNumberOnPackage !== "N/M") ? item.markAndNumberOnPackage : "NO MARK";
        const modalPatch = {
          goodsDescription: item.goodsDescription || "",
          originCriterion: item.originCriterion || "WO",
          quantity: item.quantity,
          markAndNumberOnPackage: markVal,
          packageQuantity: item.packageQuantity,
          grossWeight: item.grossWeight,
          value: item.value,
          invoiceNumber: item.invoiceNumber || data.invoiceNumber || ""
        };

        // Điền trên DOM và đồng bộ vào FormStore của Modal
        await callMoitBridge("syncGoodsModalFields", { fields: modalPatch });

        const qtyUnitTarget = normalizeUnit(item.quantityUnit || "KILOGRAM");
        const gwUnitTarget = normalizeUnit(item.grossWeightUnit || "KILOGRAM");
        const pkgUnitTarget = normalizeUnit(item.packageUnit || "CARTON");

        await callMoitBridge("setGoodsModalUnits", {
          quantityUnit: qtyUnitTarget,
          grossWeightUnit: gwUnitTarget,
          packageUnit: pkgUnitTarget,
          currency: normalizeCurrency(item.currency)
        });

        const invDateStr = item.invoiceDate || data.invoiceDate;
        if (invDateStr) {
          const invDateEl = modal.querySelector('input[placeholder="InvoiceDate"], .ant-picker input');
          if (invDateEl) await setDatePickerValue(invDateEl, invDateStr);
        }

        await delay(350);

        const saveBtn = Array.from(modal.querySelectorAll("button, .ant-btn")).find(b => {
          const t = (b.textContent || "").trim().toLowerCase();
          return t === "lưu" || b.classList.contains("ant-btn-primary");
        });
        if (saveBtn) {
          saveBtn.click();
          logMessage(`✅ Đã lưu mặt hàng ${i + 1}: ${item.goodsDescription?.substring(0, 25)}`, "success");
          await delay(850);
        }
      }

      // Tự động đóng bảng Modal Hàng hóa sau khi đã lưu xong toàn bộ các mặt hàng
      await delay(400);
      await callMoitBridge("closeGoodsModal", {});
      const openModal = document.querySelector(".ant-modal:not([style*='display: none'])");
      if (openModal) {
        const closeBtn = openModal.querySelector("button.ant-modal-close, .ant-modal-close, .ant-modal-close-x") ||
                         Array.from(openModal.querySelectorAll("button, .ant-btn")).find(b => {
                           const t = (b.textContent || "").trim().toLowerCase();
                           return t === "đóng" || t === "hủy" || t === "close" || t === "cancel";
                         });
        if (closeBtn) closeBtn.click();
      }
      logMessage("🔒 Đã tự động đóng bảng thêm mới mặt hàng!", "info");
      await delay(500);
    }

    // ----------------------------------------------------
    // BƯỚC 4: ĐÍNH KÈM & TẢI LÊN CÁC TỆP CHỨNG TỪ
    // ----------------------------------------------------
    await callMoitBridge("resetUsedInputs", {});

    if (Array.isArray(data.attachments) && data.attachments.length > 0) {
      const activeMode = document.getElementById("ecosys-matching-mode")?.value || "by_number";
      logMessage(`📎 Bắt đầu đính kèm ${data.attachments.length} tệp chứng từ...`, "info");

      let vatOrderIdx = 0;
      let impOrderIdx = 0;

      for (let idx = 0; idx < data.attachments.length; idx++) {
        const att = { ...data.attachments[idx] };
        let fileBase64 = att.base64 || "";

        // Nếu chưa có Base64 đầy đủ -> tải từ Local Companion Stream Bridge (cổng 14008)
        if (att.streamUrl || !fileBase64 || fileBase64.startsWith("<Base64")) {
          const fetchUrl = att.streamUrl || `http://127.0.0.1:14008/file?key=${encodeURIComponent(att.fileName)}`;
          try {
            const streamRes = await new Promise((resolve) => {
              chrome.runtime.sendMessage({ action: "fetchLocalFile", url: fetchUrl }, resolve);
            });
            if (streamRes && streamRes.success && streamRes.dataUrl) {
              fileBase64 = streamRes.dataUrl;
              logMessage(`📥 Đã tải '${att.fileName}' (${(streamRes.size / 1024).toFixed(1)} KB) từ cổng 14008!`, "success");
            }
          } catch (stErr) {}
        }

        if (!fileBase64 || fileBase64.startsWith("<Base64")) {
          logMessage(`⚠️ Bỏ qua '${att.fileName}' vì không có dữ liệu Base64 và cổng 14008 đang tắt.`, "warn");
          continue;
        }

        // QUAN TRỌNG: Gán ngược lại Base64 thực tế vào att.base64 trước khi truyền qua Bridge!
        att.base64 = fileBase64;
        if (!att.fileType) att.fileType = classifyFileTypeByName(att.fileName);

        if (att.fileType.includes("HoaDonVAT") && typeof att.targetRow !== "number") {
          att.targetRow = vatOrderIdx++;
        } else if (att.fileType.includes("ToKhaiHQNK") && typeof att.targetRow !== "number") {
          att.targetRow = impOrderIdx++;
        }

        let uploaded = false;
        for (let attempt = 1; attempt <= 2; attempt++) {
          uploaded = await handleUploadAttachment(att, activeMode);
          if (uploaded) {
            logMessage(`✅ [${idx + 1}/${data.attachments.length}] Đã đính kèm: ${att.fileName}`, "success");
            break;
          }
          await delay(2000);
        }
        await delay(1500);
      }
    }

    logMessage("🎉 HOÀN TẤT ĐIỀN DỮ LIỆU & ĐÍNH KÈM CHỨNG TỪ!", "success");
  }

  // ========================================================
  // 6. KHỞI CHẠY WIDGET
  // ========================================================
  if (document.readyState === "complete") {
    setTimeout(createFloatingWidget, 300);
  } else {
    window.addEventListener("load", () => setTimeout(createFloatingWidget, 300));
  }

  chrome.runtime?.onMessage?.addListener((request, sender, sendResponse) => {
    if (request.action === "toggleWidget") {
      const widget = document.getElementById("ecosys-autofill-widget");
      if (widget) widget.style.display = widget.style.display === "none" ? "flex" : "none";
      else createFloatingWidget();
      sendResponse({ status: "ok" });
    } else if (request.action === "fillData" && request.data) {
      const txt = document.getElementById("ecosys-json-input");
      if (txt) {
        txt.value = JSON.stringify(request.data, null, 2);
        executeAutoFill();
      }
      sendResponse({ status: "filling" });
    }
  });
})();