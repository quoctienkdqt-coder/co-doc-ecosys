"""
KỊCH BẢN ĐÓNG GÓI TỰ ĐỘNG v3.1:
1. Build Core App: dist/XNK_eCoSys_SC/
2. Nén Zip tối đa: installer/app_bundle.zip & dist/XNK_eCoSys_SC_v3.1_Portable.zip
3. Build Setup Wizard: dist/CaiDat_XNK_eCoSys_SC_v3.1.exe
Tác giả & Phát triển: Ngô Quốc Tiến - Zalo: 0905387808
"""

import os
import sys
import zipfile
import subprocess
import shutil
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def zip_directory(source_dir, output_zip):
    log(f"Đang nén {source_dir} -> {output_zip} (Mức nén tối đa)...")
    total_files = sum(len(files) for _, _, files in os.walk(source_dir))
    count = 0
    with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, source_dir)
                zf.write(abs_path, rel_path)
                count += 1
                if count % 100 == 0 or count == total_files:
                    pct = int(count / total_files * 100)
                    print(f"\r   -> Tiến độ nén: {pct}% ({count}/{total_files} tệp)", end="", flush=True)
    print()
    size_mb = os.path.getsize(output_zip) / (1024 * 1024)
    log(f"✅ Đã nén xong! Dung lượng: {size_mb:.2f} MB")

def main():
    start_time = time.time()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    log("==================================================================")
    log(" BẮT ĐẦU ĐÓNG GÓI HỆ THỐNG XNK & THỦY SẢN TOÀN DIỆN v3.1")
    log(" Tác giả: Ngô Quốc Tiến • Hotline/Zalo: 0905387808")
    log("==================================================================")

    # 1. Build Core App
    log("BƯỚC 1/3: Đang biên dịch ứng dụng chính (XNK_eCoSys_SC.exe)...")
    try:
        subprocess.run(["taskkill", "/f", "/im", "XNK_eCoSys_SC.exe"], capture_output=True)
    except Exception:
        pass
    time.sleep(1)

    cmd_build_app = [
        sys.executable, "-m", "PyInstaller",
        "build_unified_app.spec",
        "--noconfirm",
        "--clean"
    ]
    ret1 = subprocess.run(cmd_build_app)
    if ret1.returncode != 0:
        log("❌ LỖI KHI BUILD ỨNG DỤNG CHÍNH!")
        sys.exit(1)

    app_dir = os.path.join(base_dir, "dist", "XNK_eCoSys_SC")
    main_exe = os.path.join(app_dir, "XNK_eCoSys_SC.exe")
    if not os.path.exists(main_exe):
        log(f"❌ Không tìm thấy file {main_exe} sau khi build!")
        sys.exit(1)

    log("✅ Bước 1 hoàn thành! Đã tạo thư mục ứng dụng độc lập.")

    # 2. Zip Bundle
    log("BƯỚC 2/3: Đang đóng gói tệp nén dung lượng nhẹ...")
    os.makedirs("installer", exist_ok=True)
    app_bundle_zip = os.path.join("installer", "app_bundle.zip")
    portable_zip = os.path.join("dist", "XNK_eCoSys_SC_v3.1_Portable.zip")

    zip_directory(app_dir, app_bundle_zip)
    shutil.copy2(app_bundle_zip, portable_zip)
    log(f"✅ Đã tạo gói Portable chạy ngay: {portable_zip}")

    # 3. Build Setup Wizard
    log("BƯỚC 3/3: Đang biên dịch Trình cài đặt tự động (CaiDat_XNK_eCoSys_SC_v3.1.exe)...")
    cmd_build_installer = [
        sys.executable, "-m", "PyInstaller",
        "installer.spec",
        "--noconfirm",
        "--clean"
    ]
    ret2 = subprocess.run(cmd_build_installer)
    if ret2.returncode != 0:
        log("❌ LỖI KHI BUILD TRÌNH CÀI ĐẶT SETUP!")
        sys.exit(1)

    setup_exe = os.path.join(base_dir, "dist", "CaiDat_XNK_eCoSys_SC_v3.1.exe")
    if not os.path.exists(setup_exe):
        log(f"❌ Không tìm thấy file cài đặt: {setup_exe}")
        sys.exit(1)

    # Copy installer to root directory for easy access
    root_setup = os.path.join(base_dir, "CaiDat_XNK_eCoSys_SC_v3.1.exe")
    shutil.copy2(setup_exe, root_setup)

    setup_size = os.path.getsize(root_setup) / (1024 * 1024)
    portable_size = os.path.getsize(portable_zip) / (1024 * 1024)
    total_sec = time.time() - start_time

    log("==================================================================")
    log(f"🎉 HOÀN TẤT ĐÓNG GÓI 100% trong {total_sec:.1f} giây!")
    log(f"📦 1. File Cài Đặt (Setup Wizard):")
    log(f"      -> {root_setup} ({setup_size:.2f} MB)")
    log(f"📦 2. File Nén Di Động (Portable Zip - Giải nén dùng ngay):")
    log(f"      -> {portable_zip} ({portable_size:.2f} MB)")
    log("==================================================================")

if __name__ == "__main__":
    main()
