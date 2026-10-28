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
    // Port 14005 chưa mở (người dùng chưa bật MOITSignPlugin.exe) -> Ghi log nhẹ, không gọi console.error để tránh Chrome báo lỗi tiện ích
    console.warn("[eCoSys AutoFill] MOITSignPlugin offline on", targetUrl);
    return {
      status: 0,
      responseText: "",
      error: err.message
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
