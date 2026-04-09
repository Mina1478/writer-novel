"""
Mô-đun Quản lý cấu hình - Hỗ trợ mã hóa thông tin nhạy cảm, quản lý phiên bản, xác thực


"""
import json
import os
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib
import logging
from locales.i18n import t
from core.database import get_db

logger = logging.getLogger(__name__)

# Giới hạn kích thước tệp tối đa (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024

# Các định dạng tệp cấu hình được hỗ trợ
SUPPORTED_CONFIG_FORMATS = [".json", ".yaml", ".yml"]

# Cấu hình nhà cung cấp API
API_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "default_model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "OpenAI API chính thức"
    },
    "openai_compatible": {
        "name": "OpenAI (Giao diện tương thích)",
        "default_model": "gpt-3.5-turbo",
        "base_url": "",
        "api_key_field": "api_key",
        "requires_custom_url": True,
        "description": "Dịch vụ bên thứ ba tương thích với định dạng OpenAI API"
    },
    "anthropic": {
        "name": "Anthropic",
        "default_model": "claude-3-5-sonnet-20241022",
        "base_url": "https://api.anthropic.com",
        "api_key_field": "x-api-key",
        "requires_custom_url": False,
        "description": "Mô hình Claude"
    },
    "google": {
        "name": "Google",
        "default_model": "gemini-1.5-pro",
        "base_url": "https://generativelanguage.googleapis.com",
        "api_key_field": "key",
        "requires_custom_url": False,
        "description": "Mô hình Gemini"
    },
    "alibaba": {
        "name": "Alibaba DashScope",
        "default_model": "qwen-turbo",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Dòng Qwen"
    },
    "deepseek": {
        "name": "DeepSeek",
        "default_model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "DeepSeek-V3"
    },
    "zhipu": {
        "name": "Zhipu AI",
        "default_model": "glm-4",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Dòng GLM"
    },
    "groq": {
        "name": "Groq",
        "default_model": "llama3-70b-8192",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Llama3, Mixtral"
    },
    "together": {
        "name": "Together AI",
        "default_model": "meta-llama/Llama-3-70b-chat-hf",
        "base_url": "https://api.together.xyz/v1",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Llama, Qwen"
    },
    "fireworks": {
        "name": "Fireworks AI",
        "default_model": "accounts/fireworks/models/llama-v3-70b-instruct",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Llama, Mixtral"
    },
    "mistral": {
        "name": "Mistral AI",
        "default_model": "mistral-large-latest",
        "base_url": "https://api.mistral.ai/v1",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Mistral Large, Pixtral"
    },
    "openrouter": {
        "name": "OpenRouter",
        "default_model": "anthropic/claude-3.5-sonnet",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Tổng hợp đa mô hình (GPT, Claude, v.v.)"
    },
    "deepinfra": {
        "name": "DeepInfra",
        "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "base_url": "https://api.deepinfra.com/v1",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Lưu trữ mô hình mã nguồn mở"
    },
    "anyscale": {
        "name": "Anyscale Endpoints",
        "default_model": "meta-llama/Llama-3-70b-chat-hf",
        "base_url": "https://api.endpoints.anyscale.com/v1",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Llama, Mistral"
    },
    "perplexity": {
        "name": "Perplexity AI",
        "default_model": "llama-3.1-sonar-small-128k-online",
        "base_url": "https://api.perplexity.ai",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Sonar, Llama"
    },
    "hyperbolic": {
        "name": "Hyperbolic",
        "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
        "base_url": "https://api.hyperbolic.xyz/v1",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Mô hình mã nguồn mở"
    },
    "siliconflow": {
        "name": "SiliconFlow",
        "default_model": "Qwen/Qwen2.5-72B-Instruct",
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Qwen, Llama"
    },
    "moonshot": {
        "name": "Moonshot AI (Kimi)",
        "default_model": "moonshot-v1-8k",
        "base_url": "https://api.moonshot.ai/v1",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Dòng Kimi"
    },
    "novita": {
        "name": "Novita AI",
        "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
        "base_url": "https://api.novita.ai/v1",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Lưu trữ mô hình mã nguồn mở"
    },
    "baichuan": {
        "name": "Baichuan AI",
        "default_model": "Baichuan4",
        "base_url": "https://api.baichuan-ai.com/v1",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Dòng Baichuan"
    },
    "cerebras": {
        "name": "Cerebras",
        "default_model": "llama3.1-70b",
        "base_url": "https://api.cerebras.ai/v1",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Dòng Llama"
    },
    "sambanova": {
        "name": "SambaNova",
        "default_model": "Meta-Llama-3.1-70B-Instruct",
        "base_url": "https://api.sambanova.ai/v1",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Dòng Llama"
    },
    "volcengine": {
        "name": "Volcengine (Doubao)",
        "default_model": "doubao-pro-4k",
        "base_url": "https://ark.volcengine.com/api/v3",
        "api_key_field": "api_key",
        "requires_custom_url": False,
        "description": "Dòng Doubao"
    }
}


@dataclass
class Backend:
    """Lớp dữ liệu cấu hình phụ trợ"""
    name: str
    type: str
    base_url: str
    api_key: str
    model: str
    enabled: bool = True
    timeout: int = 120
    retry_times: int = 3
    is_default: bool = False
    
    def validate(self) -> tuple[bool, str]:
        """Xác minh tính hợp lệ của cấu hình"""
        if not self.name or not self.name.strip():
            return False, t("config.backend_name_empty")
        # Accepted types: all keys from API_PROVIDERS + legacy types
        valid_types = set(API_PROVIDERS.keys()) | {"ollama", "openai", "claude", "other"}
        if self.type not in valid_types:
            return False, t("config.unsupported_type", type=self.type)
        if not self.base_url or not self.base_url.strip().startswith(("http://", "https://")):
            return False, t("config.base_url_invalid")
        # loại ollama cho phép api_key trống
        if self.type != "ollama" and (not self.api_key or not self.api_key.strip()):
            return False, t("config.api_key_empty")
        if not self.model or not self.model.strip():
            return False, t("config.model_empty")
        if self.timeout < 5 or self.timeout > 10000:
            return False, t("config.timeout_range")
        if self.retry_times < 1 or self.retry_times > 10:
            return False, t("config.retry_range")
        return True, "OK"


@dataclass
class GenerationConfig:
    """Cấu hình tham số tạo"""
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    max_tokens: int = 16384
    chapter_target_words: int = 4000
    writing_style: str = "Trôi chảy tự nhiên, tình tiết chặt chẽ, miêu tả nhân vật tinh tế"
    writing_tone: str = "Trung lập"
    character_development: str = "Chi tiết"
    plot_complexity: str = "Trung bình"
    
    def validate(self) -> tuple[bool, str]:
        """Xác minh tính hợp lệ của các tham số"""
        if not 0.1 <= self.temperature <= 2.0:
            return False, t("config.temp_range")
        if not 0.1 <= self.top_p <= 1.0:
            return False, t("config.top_p_range")
        if self.max_tokens < 100 or self.max_tokens > 100000:
            return False, t("config.max_tokens_range")
        if self.chapter_target_words < 500 or self.chapter_target_words > 65536:
            return False, t("config.chapter_words_range")
        return True, "OK"


class ConfigManager:
    """Trình quản lý cấu hình - Chế độ đơn"""
    _instance: Optional["ConfigManager"] = None
    
    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.backends: List[Backend] = []
        self.generation: GenerationConfig = GenerationConfig()
        self.version: str = "4.0.0"
        self.last_modified: str = datetime.now().isoformat()
        self._load()
        self._initialized = True
    
    def _load(self) -> None:
        """Tải cấu hình từ SQLite"""
        try:
            conn = get_db()
            
            # Tải backends
            rows = conn.execute("SELECT * FROM backends ORDER BY id").fetchall()
            if rows:
                for row in rows:
                    try:
                        backend = Backend(
                            name=row["name"],
                            type=row["type"],
                            base_url=row["base_url"],
                            api_key=row["api_key"],
                            model=row["model"],
                            enabled=bool(row["enabled"]),
                            timeout=row["timeout"],
                            retry_times=row["retry_times"],
                            is_default=bool(row["is_default"])
                        )
                        valid, msg = backend.validate()
                        if valid:
                            self.backends.append(backend)
                        else:
                            logger.warning(f"Skip invalid backend {backend.name}: {msg}")
                    except Exception as e:
                        logger.warning(f"Load backend config failed: {e}")
            
            # Tải generation config
            gen_row = conn.execute("SELECT value FROM config WHERE key = 'generation'").fetchone()
            if gen_row:
                try:
                    gen_data = json.loads(gen_row["value"])
                    gen_data = {k: v for k, v in gen_data.items()
                               if k in GenerationConfig.__dataclass_fields__}
                    self.generation = GenerationConfig(**gen_data)
                except Exception as e:
                    logger.warning(f"Load generation config failed: {e}")
            
            # Tải version
            ver_row = conn.execute("SELECT value FROM config WHERE key = 'version'").fetchone()
            if ver_row:
                self.version = ver_row["value"]
            
            mod_row = conn.execute("SELECT value FROM config WHERE key = 'last_modified'").fetchone()
            if mod_row:
                self.last_modified = mod_row["value"]
            
            if rows or gen_row:
                logger.info("Config loaded from core.database")
            else:
                logger.info("No config in database, using defaults")
                self._init_default()
        except Exception as e:
            logger.error(f"Config load failed: {e}")
            self._init_default()
    
    def _init_default(self) -> None:
        """Khởi tạo cấu hình mặc định"""
        self.backends = [
            Backend(
                name=t("config.default_backend_name"),
                type="ollama",
                base_url="http://localhost:11434/v1",
                api_key="ollama",
                model="llama3.1:latest"
            )
        ]
        self.generation = GenerationConfig()
        self.save()
    
    def save(self) -> tuple[bool, str]:
        """Lưu cấu hình vào SQLite"""
        try:
            conn = get_db()
            now = datetime.now().isoformat()
            
            # Tạo bản sao lưu
            backup_data = {
                "version": self.version,
                "last_modified": self.last_modified,
                "backends": [asdict(b) for b in self.backends],
                "generation": asdict(self.generation),
            }
            conn.execute(
                "INSERT INTO config_backups (data, created_at) VALUES (?, ?)",
                (json.dumps(backup_data, ensure_ascii=False), now)
            )
            
            # Xóa backends cũ và insert lại
            conn.execute("DELETE FROM backends")
            for b in self.backends:
                conn.execute("""
                    INSERT INTO backends 
                    (name, type, base_url, api_key, model, enabled, timeout, retry_times, is_default, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    b.name, b.type, b.base_url, b.api_key, b.model,
                    1 if b.enabled else 0, b.timeout, b.retry_times,
                    1 if b.is_default else 0, now, now
                ))
            
            # Lưu generation config
            conn.execute(
                "INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
                ("generation", json.dumps(asdict(self.generation), ensure_ascii=False), now)
            )
            
            # Lưu version + last_modified
            self.last_modified = now
            conn.execute(
                "INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
                ("version", self.version, now)
            )
            conn.execute(
                "INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
                ("last_modified", now, now)
            )
            
            conn.commit()
            logger.info("Config saved to database")
            return True, t("config.config_save_success")
        except Exception as e:
            logger.error(f"Config save failed: {e}")
            return False, t("config.config_save_failed", error=str(e))
    
    def add_backend(self, backend: Backend) -> tuple[bool, str]:
        """Thêm backend"""
        valid, msg = backend.validate()
        if not valid:
            return False, msg
        
        # Kiểm tra sự trùng lặp
        if any(b.name == backend.name for b in self.backends):
            return False, t("config.backend_exists", name=backend.name)
        
        self.backends.append(backend)
        success, msg = self.save()
        return success, msg if not success else t("config.backend_add_success")
    
    def update_backend(self, name: str, **kwargs) -> tuple[bool, str]:
        """Cập nhật cấu hình phụ trợ"""
        for backend in self.backends:
            if backend.name == name:
                for key, value in kwargs.items():
                    if hasattr(backend, key):
                        setattr(backend, key, value)
                
                valid, msg = backend.validate()
                if not valid:
                    return False, msg
                
                success, msg = self.save()
                return success, msg if not success else t("config.backend_update_success")
        
        return False, t("config.backend_not_found", name=name)
    
    def delete_backend(self, name: str) -> tuple[bool, str]:
        """Xóa backend"""
        self.backends = [b for b in self.backends if b.name != name]
        success, msg = self.save()
        return success, msg if not success else t("config.backend_delete_success", name=name)
    
    def set_default_backend(self, name: str) -> tuple[bool, str]:
        """Đặt giao diện làm mặc định"""
        found = False
        for backend in self.backends:
            if backend.name == name:
                backend.is_default = True
                found = True
            else:
                backend.is_default = False
        
        if found:
            success, msg = self.save()
            return success, msg if not success else "Success"
        return False, t("config.backend_not_found", name=name)
    
    def get_enabled_backends(self) -> List[Backend]:
        """Nhận tất cả các phụ trợ được kích hoạt"""
        return [b for b in self.backends if b.enabled]
    
    def update_generation_config(self, **kwargs) -> tuple[bool, str]:
        """Cập nhật cấu hình bản dựng"""
        for key, value in kwargs.items():
            if hasattr(self.generation, key):
                setattr(self.generation, key, value)
        
        valid, msg = self.generation.validate()
        if not valid:
            return False, msg
        
        success, msg = self.save()
        return success, msg if not success else t("config.gen_params_update_success")
    
    def export_config(self, filepath: str) -> tuple[bool, str]:
        """Xuất cấu hình (không chứa thông tin nhạy cảm)"""
        try:
            data = {
                "version": self.version,
                "backends": [{"name": b.name, "type": b.type, "model": b.model} 
                            for b in self.backends],
                "generation": asdict(self.generation),
            }
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            return True, t("config.config_export_success", filepath=filepath)
        except Exception as e:
            return False, t("config.config_export_failed", error=str(e))
    
    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi cấu hình sang định dạng từ điển"""
        return {
            "backends": [asdict(b) for b in self.backends],
            "generation": asdict(self.generation),
            "system": {
                "logging": {
                    "level": "INFO",
                    "file": "logs/novel_generator.log",
                    "console_output": True
                },
                "concurrency": {
                    "max_workers": 4,
                    "request_timeout": 30
                },
                "cache": {
                    "enabled": True,
                    "type": "file",
                    "location": "cache",
                    "ttl": 3600
                }
            },
            "export": {
                "default_format": "markdown",
                "output_directory": "output",
                "supported_formats": ["markdown", "pdf", "docx", "txt", "epub"]
            },
            "ui": {
                "theme": "light",
                "language": "zh-CN",
                "editor": {
                    "font_size": 14,
                    "font_family": "Microsoft YaHei, sans-serif",
                    "tab_size": 2,
                    "word_wrap": True
                }
            },
            "project": {
                "auto_save": {
                    "enabled": True,
                    "interval": 300,
                    "backup_count": 5
                },
                "backup": {
                    "enabled": True,
                    "location": "backups",
                    "schedule": "daily",
                    "keep_days": 30
                },
                "templates": {
                    "enabled": True,
                    "location": "project_templates",
                    "default_template": "standard_novel"
                }
            },
            "plugins": {
                "enabled": True,
                "directory": "plugins",
                "auto_load": True,
                "enabled_plugins": [
                    "style_analyzer",
                    "grammar_checker",
                    "character_tracker",
                    "plot_generator"
                ]
            },
            "advanced": {
                "performance": {
                    "enable_profiling": False,
                    "memory_limit": "1GB",
                    "cpu_limit": 80
                },
                "debug": {
                    "show_errors": False,
                    "debug_mode": False,
                    "trace_requests": False
                },
                "monitoring": {
                    "enabled": False,
                    "metrics_port": 8080,
                    "health_check_interval": 30
                }
            }
        }
    
    @staticmethod
    def get_api_providers() -> Dict[str, Dict[str, Any]]:
        """Nhận tất cả cấu hình của nhà cung cấp API"""
        return API_PROVIDERS
    
    @staticmethod
    def get_api_provider_choices() -> List[str]:
        """Nhận danh sách lựa chọn nhà cung cấp API"""
        return [provider["name"] for provider in API_PROVIDERS.values()]
    
    @staticmethod
    def get_api_provider_info(provider_key: str) -> Optional[Dict[str, Any]]:
        """Nhận thông tin nhà cung cấp dựa trên khóa nhà cung cấp"""
        return API_PROVIDERS.get(provider_key)
    
    @staticmethod
    def get_api_provider_key_by_name(provider_name: str) -> Optional[str]:
        """Nhận khóa nhà cung cấp dựa trên tên nhà cung cấp"""
        for key, provider in API_PROVIDERS.items():
            if provider["name"] == provider_name:
                return key
        return None


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Tải cấu hình từ database hoặc file chỉ định
    
    Args:
        config_path: đường dẫn file cấu hình (hỗ trợ import từ file)
        
    Returns:
        Từ điển cấu hình
    """
    if config_path:
        # Import từ file chỉ định
        if not os.path.exists(config_path):
            raise FileNotFoundError(t("config.config_file_missing", path=config_path))
            
        file_ext = os.path.splitext(config_path)[1].lower()
        if file_ext == ".json":
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            raise ValueError(t("config.config_format_unsupported", ext=file_ext))
    else:
        return get_config().to_dict()

def get_config() -> ConfigManager:
    """Nhận phiên bản cấu hình toàn cầu"""
    return ConfigManager()

def get_config_manager() -> ConfigManager:
    """Nhận phiên bản trình quản lý cấu hình toàn cầu (bí danh)"""
    return get_config()
