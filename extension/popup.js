/**
 * eCoSys C/O AutoFill Pro - Popup Script v2.5.0
 */

const TARGET_HOST = "co.moit.gov.vn";

const SAMPLE_DATA = {
  "form": "EUR.1",
  "issuing_Authority": "Sở Công Thương Tỉnh Khánh Hòa",
  "importing_Country": "Lithuania",
  "declarationPlace": "Khánh Hòa",
  "taxCode": "4200722962",
  "maSoDN": "4200722962",
  "from_ExporterBusinessName": "NHA TRANG BAY JOINT STOCK COMPANY",
  "from_ExporterBusinessNameVN": "CÔNG TY CỔ PHẦN VỊNH NHA TRANG",
  "from_AddressLine1": "LOT K1, K2, K3 AND A PART OF K4, SUOI DAU INDUSTRIAL ZONE",
  "from_Addressline2": "CAM LAM COMMUNE, KHANH HOA PROVINCE, VIETNAM",
  "to_ConsigneeName": "MARISO SEAFOOD LLC",
  "to_Addressline1": "VABADUSE PST 8/1, KIVIOLI",
  "to_Addressline2": "LUGANUSE VALD, ESTONIA 43125",
  "manu_Name": "",
  "manu_AddressLine1": "",
  "route_TransportationType": "By Sea",
  "route_TransportName": "SEASPAN BENEFACTOR 077W",
  "route_PortOfLoading": "HO CHI MINH",
  "route_PortOfDischange": "KLAIPEDA",
  "route_PortOfDestination": "KLAIPEDA",
  "route_DepartureDepartureDate": "09/10/2026",
  "bill": "YMJAN490421110",
  "invoiceNumber": "NT60195",
  "invoiceDate": "01/10/2026",
  "currency": "USD - Dollar Mỹ",
  "goods_Total_FobValue": 251081.55,
  "declarationNumbers": "309017425640",
  "declarationDates": "01/10/2026",
  "remarks": "",
  "isIssuedRetroactively": true,
  "issuedRetroactivelyReason": "tàu delay",
  "goodItems": [
    {
      "exportingHsCode": "03048700",
      "importingHsCode": "03048700",
      "goodsDescription": "FROZEN RED TUNA LOIN",
      "originCriterion": "WO",
      "countryOfOrigin": "VN",
      "quantity": 15000.0,
      "quantityUnit": "KILOGRAM",
      "markAndNumberOnPackage": "N/M",
      "packageQuantity": 600,
      "packageUnit": "CARTON",
      "grossWeight": 16320.0,
      "grossWeightUnit": "KGM",
      "value": 150161.75,
      "currency": "USD - Dollar Mỹ",
      "invoiceNumber": "NT60195",
      "invoiceDate": "01/10/2026"
    },
    {
      "exportingHsCode": "03048700",
      "importingHsCode": "03048700",
      "goodsDescription": "FROZEN RED TUNA SAKU",
      "originCriterion": "WO",
      "countryOfOrigin": "VN",
      "quantity": 2400.0,
      "quantityUnit": "KILOGRAM",
      "markAndNumberOnPackage": "N/M",
      "packageQuantity": 240,
      "packageUnit": "CARTON",
      "grossWeight": 2688.0,
      "grossWeightUnit": "KGM",
      "value": 45865.88,
      "currency": "USD - Dollar Mỹ",
      "invoiceNumber": "NT60195",
      "invoiceDate": "01/10/2026"
    },
    {
      "exportingHsCode": "03048700",
      "importingHsCode": "03048700",
      "goodsDescription": "FROZEN RED TUNA STEAK",
      "originCriterion": "WO",
      "countryOfOrigin": "VN",
      "quantity": 5000.0,
      "quantityUnit": "KILOGRAM",
      "markAndNumberOnPackage": "N/M",
      "packageQuantity": 500,
      "packageUnit": "CARTON",
      "grossWeight": 5600.0,
      "grossWeightUnit": "KGM",
      "value": 55053.92,
      "currency": "USD - Dollar Mỹ",
      "invoiceNumber": "NT60195",
      "invoiceDate": "01/10/2026"
    }
  ],
  "attachments": []
};

document.addEventListener("DOMContentLoaded", async () => {
  const statusDot = document.getElementById("status-dot");
  const statusText = document.getElementById("status-text");

  // Kiểm tra tab hiện tại
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const isOnSite = tab && tab.url && tab.url.includes(TARGET_HOST);

  if (isOnSite) {
    statusDot.className = "status-dot active";
    statusText.textContent = "Đang mở: co.moit.gov.vn";
  } else {
    statusDot.className = "status-dot inactive";
    statusText.textContent = "Chưa mở trang co.moit.gov.vn";
  }

  // 1. Dán từ Clipboard & Điền
  document.getElementById("btn-paste-fill").addEventListener("click", async () => {
    if (!isOnSite) {
      alert("Vui lòng mở trang https://co.moit.gov.vn/hoSo/KhaiBaoCO trước khi điền!");
      return;
    }

    try {
      const text = await navigator.clipboard.readText();
      if (!text || !text.trim().startsWith("{")) {
        alert("Clipboard chưa có dữ liệu JSON hợp lệ! Vui lòng bấm 'Sao chép JSON' từ App Desktop trước.");
        return;
      }
      const data = JSON.parse(text);
      chrome.tabs.sendMessage(tab.id, { action: "fillData", data });
      window.close();
    } catch (e) {
      alert("Lỗi đọc Clipboard: " + e.message);
    }
  });

  // 2. Bật / Ẩn bảng trợ lý trên trang
  document.getElementById("btn-toggle-widget").addEventListener("click", () => {
    if (!isOnSite) {
      alert("Vui lòng mở trang https://co.moit.gov.vn/hoSo/KhaiBaoCO trước!");
      return;
    }
    chrome.tabs.sendMessage(tab.id, { action: "toggleWidget" });
    window.close();
  });

  // 3. Nạp thử dữ liệu mẫu
  document.getElementById("btn-demo").addEventListener("click", () => {
    if (!isOnSite) {
      alert("Vui lòng mở trang https://co.moit.gov.vn/hoSo/KhaiBaoCO trước!");
      return;
    }
    chrome.tabs.sendMessage(tab.id, { action: "fillData", data: SAMPLE_DATA });
    window.close();
  });

  // 4. Mở trang MoIT
  document.getElementById("btn-open-site").addEventListener("click", () => {
    chrome.tabs.create({ url: "https://co.moit.gov.vn/hoSo/KhaiBaoCO" });
  });
});
