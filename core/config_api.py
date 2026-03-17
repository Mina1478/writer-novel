"""
Mô-đun Quản lý cấu hình Web API
Hỗ trợ thêm, sửa, xóa, kiểm tra giao diện API qua Web UI

Bản quyền © 2026 Công ty TNHH Công nghệ An ninh mạng Huyễn Thành Tân Cương (Công nghệ Huyễn Thành)
Tác giả: Huyễn Thành
"""
import json
from typing import Dict, List, Tuple, Any
from dataclasses import asdict
from core.config import Backend, get_config
from services.api_client import get_api_client, reinit_api_client
from core.logger import get_logger
from locales.i18n import t

logger = get_logger("ConfigAPI")


class ConfigAPIManager:
    """API quản lý cấu hình"""
    
    @staticmethod
    def list_backends() -> Dict[str, Any]:
        """Nhận danh sách tất cả các phụ trợ"""
        try:
            config = get_config()
            backends_data = []
            for backend in config.backends:
                backend_dict = asdict(backend)
                backends_data.append(backend_dict)
            return {
                "success": True,
                "data": backends_data,
                "message": t("app.backends_loaded", count=len(backends_data))
            }
        except Exception as e:
            logger.error(f"List backends failed: {e}")
            return {
                "success": False,
                "data": [],
                "message": f"❌ {str(e)}"
            }
    
    @staticmethod
    def add_backend(name: str, type: str, base_url: str, api_key: str, 
                    model: str, timeout: int = 30, retry_times: int = 3,
                    enabled: bool = True) -> Dict[str, Any]:
        """Thêm cấu hình phụ trợ mới"""
        try:
            config = get_config()
            
            # Kiểm tra xem tên có trùng lặp không
            for backend in config.backends:
                if backend.name == name:
                    return {
                        "success": False,
                        "message": t("config_api.name_exists", name=name)
                    }
            
            # Tạo phụ trợ mới
            new_backend = Backend(
                name=name,
                type=type,
                base_url=base_url,
                api_key=api_key,
                model=model,
                timeout=timeout,
                retry_times=retry_times,
                enabled=enabled
            )
            
            # Xác minh cấu hình phụ trợ
            valid, msg = new_backend.validate()
            if not valid:
                return {
                    "success": False,
                    "message": f"❌ {msg}"
                }
            
            # Thêm phụ trợ
            config.backends.append(new_backend)
            success, save_msg = config.save()
            
            if success:
                logger.info(f"Backend added: {name}")
                return {
                    "success": True,
                    "message": t("config_api.add_success", name=name),
                    "backend": asdict(new_backend)
                }
            else:
                return {
                    "success": False,
                    "message": t("config_api.add_failed", error=save_msg)
                }
                
        except Exception as e:
            logger.error(f"Add backend failed: {e}")
            return {
                "success": False,
                "message": t("config_api.add_failed", error=str(e))
            }
    
    @staticmethod
    def update_backend(name: str, **kwargs) -> Dict[str, Any]:
        """Cập nhật cấu hình backend"""
        try:
            config = get_config()
            success, msg = config.update_backend(name, **kwargs)
            
            if success:
                logger.info(f"Backend updated: {name}")
                return {
                    "success": True,
                    "message": msg
                }
            else:
                return {
                    "success": False,
                    "message": msg
                }
                
        except Exception as e:
            logger.error(f"Update backend failed: {e}")
            return {
                "success": False,
                "message": t("config_api.update_failed", error=str(e))
            }
    
    @staticmethod
    def delete_backend(name: str) -> Dict[str, Any]:
        """Xóa cấu hình phụ trợ"""
        try:
            config = get_config()
            success, msg = config.delete_backend(name)
            
            if success:
                logger.info(f"Backend deleted: {name}")
                return {
                    "success": True,
                    "message": msg
                }
            else:
                return {
                    "success": False,
                    "message": msg
                }
                
        except Exception as e:
            logger.error(f"Delete backend failed: {e}")
            return {
                "success": False,
                "message": t("config_api.delete_failed", error=str(e))
            }
    
    @staticmethod
    def toggle_backend(name: str, enabled: bool) -> Dict[str, Any]:
        """Bật/tắt phụ trợ"""
        try:
            config = get_config()
            success, msg = config.update_backend(name, enabled=enabled)
            
            if success:
                status = t("config_api.toggle_enabled") if enabled else t("config_api.toggle_disabled")
                logger.info(f"Backend {name}: {status}")
                return {
                    "success": True,
                    "message": t("config_api.toggle_success", name=name, status=status)
                }
            else:
                return {
                    "success": False,
                    "message": msg
                }
                
        except Exception as e:
            logger.error(f"Toggle backend failed: {e}")
            return {
                "success": False,
                "message": t("config_api.toggle_failed", error=str(e))
            }
    
    @staticmethod
    def set_default_backend(name: str) -> Dict[str, Any]:
        """Đặt giao diện làm mặc định"""
        try:
            config = get_config()
            success, msg = config.set_default_backend(name)
            
            if success:
                logger.info(f"Backend set to default: {name}")
                return {
                    "success": True,
                    "message": t("config_api.default_success", name=name)
                }
            else:
                return {
                    "success": False,
                    "message": msg
                }
                
        except Exception as e:
            logger.error(f"Set default backend failed: {e}")
            return {
                "success": False,
                "message": t("config_api.default_failed", error=str(e))
            }
    
    @staticmethod
    def test_backend(name: str) -> Dict[str, Any]:
        """Kiểm tra kết nối backend"""
        try:
            config = get_config()
            backend = None
            
            # Tìm phần phụ trợ được chỉ định
            for b in config.backends:
                if b.name == name:
                    backend = b
                    break
            
            if not backend:
                return {
                    "success": False,
                    "message": t("config_api.test_not_found", name=name)
                }
            
            # kết nối thử nghiệm
            if not backend.enabled:
                return {
                    "success": False,
                    "message": f"❌ {name} disabled"
                }
            
            # Kiểm tra bằng ứng dụng khách API
            try:
                api_client = get_api_client()
                # Hãy thử lấy thông tin model để kiểm tra kết nối
                test_response = api_client.test_connection(backend.base_url, backend.api_key, backend.model)
                
                if test_response:
                    logger.info(f"Backend test passed: {name}")
                    return {
                        "success": True,
                        "message": t("config_api.test_success", name=name),
                        "backend": name,
                        "model": backend.model
                    }
                else:
                    return {
                        "success": False,
                        "message": t("config_api.test_failed", name=name, error="No response")
                    }
            except Exception as test_error:
                logger.error(f"Backend test error: {test_error}")
                return {
                    "success": False,
                    "message": t("config_api.test_failed", name=name, error=str(test_error))
                }
                
        except Exception as e:
            logger.error(f"Test backend failed: {e}")
            return {
                "success": False,
                "message": t("config_api.test_failed", name="", error=str(e))
            }
    
    @staticmethod
    def get_backend_types() -> List[str]:
        """Nhận danh sách các loại phụ trợ được hỗ trợ"""
        return ["ollama", "openai", "claude", "other"]
    
    @staticmethod
    def export_config(filepath: str) -> Dict[str, Any]:
        """Xuất file cấu hình"""
        try:
            config = get_config()
            success, msg = config.export_config(filepath)
            
            if success:
                return {
                    "success": True,
                    "message": msg
                }
            else:
                return {
                    "success": False,
                    "message": msg
                }
                
        except Exception as e:
            logger.error(f"Export config failed: {e}")
            return {
                "success": False,
                "message": t("config_api.export_failed", error=str(e))
            }


# Phiên bản trình quản lý API toàn cầu
config_api = ConfigAPIManager()
