from __future__ import annotations
import base64, hashlib, json, os, platform, secrets, uuid
from datetime import datetime, timezone
from pathlib import Path
from runtime_paths import INSTALL_PATH, LICENSE_PATH, resource_path


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def _machine_material() -> str:
    parts = [platform.node(), platform.machine(), str(uuid.getnode())]
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as k:
                parts.append(str(winreg.QueryValueEx(k, "MachineGuid")[0]))
        except Exception: pass
    return "|".join(parts)

def get_device_code() -> str:
    if INSTALL_PATH.exists():
        try:
            data = json.loads(INSTALL_PATH.read_text(encoding="utf-8"))
            if data.get("device_code"): return data["device_code"]
        except Exception: pass
    salt = secrets.token_hex(8)
    digest = hashlib.sha256((_machine_material()+"|"+salt).encode()).hexdigest().upper()[:12]
    code = "AOW-" + "-".join(digest[i:i+4] for i in range(0,12,4))
    INSTALL_PATH.write_text(json.dumps({"device_code":code,"salt":salt}, indent=2), encoding="utf-8")
    return code

def verify_token(token: str, device_code: str) -> tuple[bool, str, dict]:
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        p64, s64 = token.strip().split(".", 1)
        payload_raw = _b64d(p64)
        signature = _b64d(s64)
        public_key = serialization.load_pem_public_key(resource_path("license/public_key.pem").read_bytes())
        public_key.verify(signature, payload_raw, padding.PKCS1v15(), hashes.SHA256())
        payload = json.loads(payload_raw.decode("utf-8"))
        if payload.get("device") != device_code:
            return False, "Ключ создан для другого устройства.", payload
        exp = payload.get("exp")
        if exp:
            until = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > until:
                return False, "Срок действия ключа истёк.", payload
        return True, "Лицензия активна.", payload
    except Exception:
        return False, "Неверный код активации.", {}

def save_token(token: str):
    LICENSE_PATH.write_text(json.dumps({"token":token.strip()}, ensure_ascii=False, indent=2), encoding="utf-8")

def load_token() -> str:
    try: return json.loads(LICENSE_PATH.read_text(encoding="utf-8")).get("token", "")
    except Exception: return ""

def current_license() -> tuple[bool,str,dict]:
    return verify_token(load_token(), get_device_code())
