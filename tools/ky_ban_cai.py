"""
KÝ BỘ CÀI trước khi đăng GitHub Release.
  python tools\\ky_ban_cai.py CaiDat_XNK_eCoSys_SC_vX.Y.Z.exe
-> tạo <file>.exe.sig (base64 Ed25519 của "co-doc-ecosys-update:sha256:<sha256 hex>") và in SHA256.
Khóa bí mật: %USERPROFILE%\\.co_doc_keys\\cap_nhat_ed25519.pem — KHÔNG đưa lên GitHub, không đóng gói vào bộ cài.
Phải đăng CẢ file .exe và .exe.sig lên Release; thiếu .sig thì máy khách (từ v3.4.0) từ chối tự cập nhật.
"""
import os
import sys
import base64

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cryptography.hazmat.primitives import serialization  # noqa: E402
from github_updater import TIEN_TO_CHU_KY, sha256_file, kiem_tra_chu_ky  # noqa: E402

KHOA = os.path.join(os.path.expanduser("~"), ".co_doc_keys", "cap_nhat_ed25519.pem")


def ky(path_exe):
    k = serialization.load_pem_private_key(open(KHOA, "rb").read(), None)
    sha = sha256_file(path_exe)
    sig = base64.b64encode(k.sign(TIEN_TO_CHU_KY + sha.encode())).decode()
    with open(path_exe + ".sig", "w", encoding="ascii") as f:
        f.write(sig)
    assert kiem_tra_chu_ky(path_exe, sig), "Chữ ký vừa tạo không khớp khóa công khai trong github_updater.py!"
    return sha, path_exe + ".sig"


if __name__ == "__main__":
    sha, sig = ky(sys.argv[1])
    print("SHA256:", sha)
    print("Chữ ký:", sig)
