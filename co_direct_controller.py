import asyncio
import json
import os
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import requests
import websockets

CDP_HTTP_URL = "http://127.0.0.1:9222"
ARTIFACT_DIR = r"C:\Users\Admin\.gemini\antigravity\brain\b8688659-3248-4314-9de4-914cbbe6833b"

class ChromeController:
    def __init__(self):
        self.ws = None
        self.msg_id = 0
        self.target_tab = None

    def wait_for_debug_port(self, timeout_sec=180):
        print(f"[CHO CONG 9222] Dang lang nghe cong Chrome Debug 9222 (toi da {timeout_sec}s)...", flush=True)
        start = time.time()
        while time.time() - start < timeout_sec:
            try:
                res = requests.get(f"{CDP_HTTP_URL}/json/version", timeout=1)
                if res.status_code == 200:
                    print("[OK] Da ket noi thanh cong toi cong Chrome 9222!", flush=True)
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False

    def find_co_tab(self):
        try:
            res = requests.get(f"{CDP_HTTP_URL}/json/list", timeout=3)
            tabs = res.json()
            for tab in tabs:
                url = tab.get("url", "")
                if "co.moit.gov.vn" in url or "KhaiBaoCO" in url:
                    self.target_tab = tab
                    return tab
            for tab in tabs:
                if tab.get("type") == "page":
                    self.target_tab = tab
                    return tab
            return None
        except Exception as e:
            print(f"[Error] Khong lay duoc danh sach tab: {e}", flush=True)
            return None

    async def connect(self):
        tab = self.find_co_tab()
        if not tab:
            print("[Error] Khong tim thay tab eCoSys phu hop.", flush=True)
            return False
        
        ws_url = tab.get("webSocketDebuggerUrl")
        if not ws_url:
            print("[Error] Tab khong co webSocketDebuggerUrl.", flush=True)
            return False

        print(f"[MUC TIEU] Dang ket noi toi tab: {tab.get('title')} ({tab.get('url')})", flush=True)
        self.ws = await websockets.connect(ws_url, max_size=100 * 1024 * 1024)
        return True

    async def send_command(self, method, params=None):
        self.msg_id += 1
        msg = {
            "id": self.msg_id,
            "method": method,
            "params": params or {}
        }
        await self.ws.send(json.dumps(msg))
        
        while True:
            resp_raw = await self.ws.recv()
            resp = json.loads(resp_raw)
            if resp.get("id") == self.msg_id:
                return resp.get("result", {})

    async def eval_js(self, script):
        res = await self.send_command("Runtime.evaluate", {
            "expression": script,
            "returnByValue": True,
            "awaitPromise": True
        })
        val = res.get("result", {}).get("value")
        return val

    async def capture_screenshot(self, filename):
        os.makedirs(ARTIFACT_DIR, exist_ok=True)
        save_path = os.path.join(ARTIFACT_DIR, filename)
        res = await self.send_command("Page.captureScreenshot", {"format": "png"})
        b64_data = res.get("data")
        if b64_data:
            import base64
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(b64_data))
            print(f"[SCREENSHOT] Da chup anh man hinh luu tai: {save_path}", flush=True)
            return save_path
        return None

    async def close(self):
        if self.ws:
            await self.ws.close()

async def run_direct_fix():
    print("==================================================", flush=True)
    print("   AI TRUC TIEP DIEU KHIEN & SUA LOI TREN MAN HINH", flush=True)
    print("==================================================", flush=True)
    
    ctrl = ChromeController()
    if not ctrl.wait_for_debug_port(180):
        print("[TIMEOUT] Het thoi gian cho cong 9222. Hay bam dup file BAT_CHROME_DEBUG_9222.bat tren Desktop.", flush=True)
        return False

    if not await ctrl.connect():
        return False

    print("\n[Buoc 1] Dang chup anh man hinh hien trang...", flush=True)
    await ctrl.capture_screenshot("evidence_17_cdp_before_fix.png")

    print("\n[Buoc 2] Dang quet sach cac chu thua (Ma, By, CA...) trong cac o chon...", flush=True)
    cleanup_script = """
    (() => {
        let results = [];
        const searchInputs = document.querySelectorAll('.ant-select-selection-search-input, input.ant-select-selection-search-input');
        searchInputs.forEach(inp => {
            const val = inp.value;
            if (val) {
                results.push(val);
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                if (setter) setter.call(inp, '');
                inp.value = '';
                inp.dispatchEvent(new Event('input', { bubbles: true }));
                inp.dispatchEvent(new Event('change', { bubbles: true }));
                inp.style.width = '0px';
                inp.style.opacity = '0';
            }
        });
        document.querySelectorAll('.ant-select-selection-search').forEach(s => s.style.width = '0px');
        return results;
    })()
    """
    cleaned = await ctrl.eval_js(cleanup_script)
    print(f"[OK] Da don sach cac ky tu du thua: {cleaned}", flush=True)

    print("\n[Buoc 3] Kiem tra phien ban Extension dang chay...", flush=True)
    ext_ver = await ctrl.eval_js("document.querySelector('#ecosys-header-badge, .ecosys-badge')?.textContent || 'unknown'")
    print(f"[INFO] Phien ban extension tren trang: {ext_ver}", flush=True)

    print("\n[Buoc 4] Dang chup anh man hinh ket qua sau khi xu ly...", flush=True)
    await ctrl.capture_screenshot("evidence_18_cdp_after_fix.png")

    await ctrl.close()
    print("\n[HOAN TAT] Da thao tac truc tiep thanh cong tren trinh duyet!", flush=True)
    return True

if __name__ == "__main__":
    asyncio.run(run_direct_fix())
