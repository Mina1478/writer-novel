import os
import json
import logging
from threading import Lock

logger = logging.getLogger(__name__)

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
SECURITY_FILE = os.path.join(CONFIG_DIR, "security.json")

# Ensure config directory exists
os.makedirs(CONFIG_DIR, exist_ok=True)

_auth_lock = Lock()

def _load_security_data() -> dict:
    with _auth_lock:
        if not os.path.exists(SECURITY_FILE):
            return {}
        try:
            with open(SECURITY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read security.json: {e}")
            return {}

def _save_security_data(data: dict) -> bool:
    with _auth_lock:
        try:
            with open(SECURITY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logger.error(f"Failed to write security.json: {e}")
            return False

def has_password() -> bool:
    """Kiểm tra xem hệ thống đã thiết lập mật khẩu chưa."""
    data = _load_security_data()
    pwd = data.get("settings_password", "")
    return bool(pwd.strip())

def verify_password(pwd: str) -> bool:
    """Xác thực mật khẩu. Trả về True nếu đúng hoặc nếu hệ thống chưa yêu cầu mật khẩu."""
    if not has_password():
        return True
    
    data = _load_security_data()
    return data.get("settings_password", "") == pwd

def set_password(old_pwd: str, new_pwd: str) -> tuple[bool, str]:
    """Cập nhật mật khẩu mới."""
    data = _load_security_data()
    current_pwd = data.get("settings_password", "")
    
    # Nếu đang có pass, phải nhập đúng pass cũ
    if current_pwd and old_pwd != current_pwd:
        return False, "Mật khẩu cũ không chính xác."
        
    data["settings_password"] = new_pwd
    if _save_security_data(data):
        if not new_pwd:
            return True, "Đã gỡ bỏ mật khẩu bảo vệ."
        return True, "Cập nhật mật khẩu thành công."
    return False, "Lỗi khi lưu mật khẩu, vui lòng xem log."
