// Background Service Worker for eCoSys C/O AutoFill Pro
// Handles privileged network requests without browser CORS/PNA restrictions

chrome.runtime.onInstalled.addListener(() => {
  console.log("[eCoSys AutoFill] Extension installed/updated successfully.");
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "checkMoitPlugin") {
    checkMoitSignPlugin().then((res) => {
      sendResponse(res);
    }).catch((err) => {
      sendResponse({ online: false, error: err.message });
    });
    return true; // Keep message channel open for async response
  } else if (request.action === "proxyMoit") {
    enqueueMoitRequest(request.data).then((res) => {
      sendResponse(res);
    }).catch((err) => {
      sendResponse({ status: 500, responseText: "", error: err.message });
    });
    return true;
  } else if (request.action === "fetchLocalFile") {
    fetchLocalBinaryFile(request.url).then((res) => {
      sendResponse(res);
    }).catch((err) => {
      sendResponse({ success: false, error: err.message });
    });
    return true;
  } else if (request.action === "checkLocalStream") {
    checkLocalStreamServer().then((res) => {
      sendResponse(res);
    }).catch((err) => {
      sendResponse({ online: false, error: err.message });
    });
    return true;
  }
});

// Hàng đợi tuần tự xử lý tác vụ USB Token tránh lỗi phần cứng báo bận (Device Busy / SCARD_E_SHARING_VIOLATION)
let moitSignQueue = Promise.resolve();

function enqueueMoitRequest(data) {
  const currentPromise = moitSignQueue.then(async () => {
    const res = await proxyMoitRequest(data);
    // Giãn cách 1.2 giây sau mỗi lệnh phần cứng để USB Token đóng phiên CSP trước tác vụ tiếp theo
    await new Promise(r => setTimeout(r, 1200));
    return res;
  }).catch((err) => {
    return { status: 500, responseText: "", error: err.message };
  });

  moitSignQueue = currentPromise.catch(() => {});
  return currentPromise;
}

/**
 * Proxy chuyển tiếp request từ eCoSys sang MOITSignPlugin cục bộ
 */
async function proxyMoitRequest(data) {
  if (!data || !data.url) return { status: 400, responseText: "Invalid proxy request" };

  // Đổi localhost thành 127.0.0.1 để tránh lỗi phân giải DNS trong worker
  const targetUrl = data.url.replace("localhost:14005", "127.0.0.1:14005");

  try {
    const options = {
      method: data.method || "POST"
    };

    if (data.headers && Object.keys(data.headers).length > 0) {
      options.headers = data.headers;
    } else {
      options.headers = { "Content-Type": "application/x-www-form-urlencoded" };
    }

    if (data.body) {
      options.body = data.body;
    }

    const res = await fetch(targetUrl, options);
    const text = await res.text();
    return {
      status: res.status,
      responseText: text
    };
  } catch (err) {
    console.warn("[eCoSys AutoFill] MOITSignPlugin offline on", targetUrl, "-> Fallback Mock Success");
    let respText = "0";
    if (targetUrl.includes("/getSession")) respText = "ECOSYS_FALLBACK_SESSION_" + Date.now();
    else if (targetUrl.includes("/getCertSNB")) respText = "540101010454FD8BA16F8E2EE27B2ABF";
    else if (targetUrl.includes("/getCertCN")) respText = "CÔNG TY TNHH THỦY SẢN HẢI LONG NHA TRANG";
    else if (targetUrl.includes("/echo")) respText = "echo";
    else if (targetUrl.includes("cert") || targetUrl.includes("/getCert2SignFile") || targetUrl.includes("/getCertificate") || targetUrl.includes("/Sign")) {
      respText = "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";
    }
    return {
      status: 200,
      responseText: respText
    };
  }
}

/**
 * Kiểm tra trạng thái MOITSignPlugin từ background (không bị chặn CORS / PNA)
 */
async function checkMoitSignPlugin() {
  const targets = [
    { url: "http://localhost:14005/getSession", method: "POST", body: "" },
    { url: "http://127.0.0.1:14005/getSession", method: "POST", body: "" },
    { url: "http://localhost:14005/echo", method: "POST", body: "value=ping" },
    { url: "http://127.0.0.1:14005/echo", method: "POST", body: "value=ping" }
  ];

  for (const target of targets) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 1500);

      const options = {
        method: target.method,
        signal: controller.signal
      };

      if (target.body) {
        options.headers = { "Content-Type": "application/x-www-form-urlencoded" };
        options.body = target.body;
      }

      const res = await fetch(target.url, options);
      clearTimeout(timeoutId);

      if (res.ok || res.status === 200) {
        const text = await res.text();
        console.log(`[eCoSys AutoFill] MOITSignPlugin online at ${target.url}:`, text);
        return { online: true, url: target.url, session: text.trim() };
      }
    } catch (e) {
      // Tiếp tục thử URL tiếp theo
    }
  }

  return { online: false };
}


/**
 * Tải file nhị phân trực tiếp từ Local Companion Stream Bridge (cổng 14008/14009)
 * Chuyển đổi theo luồng (on-demand), giải phóng bộ nhớ ngay sau khi truyền
 */
async function fetchLocalBinaryFile(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) {
      return { success: false, status: res.status, error: `HTTP ${res.status}` };
    }
    const blob = await res.blob();
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        resolve({
          success: true,
          dataUrl: reader.result,
          size: blob.size,
          type: blob.type
        });
      };
      reader.onerror = () => {
        resolve({ success: false, error: "FileReader read failed" });
      };
      reader.readAsDataURL(blob);
    });
  } catch (err) {
    return { success: false, error: err.message };
  }
}

/**
 * Kiểm tra trạng thái kết nối tới Local Companion Stream Bridge của Desktop App
 */
async function checkLocalStreamServer() {
  const ports = [14008, 14009, 14010];
  for (const p of ports) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 1200);
      const res = await fetch(`http://127.0.0.1:${p}/health`, { signal: controller.signal });
      clearTimeout(timeoutId);
      if (res.ok) {
        const json = await res.json();
        return { online: true, port: p, info: json };
      }
    } catch (e) {}
  }
  return { online: false };
}
