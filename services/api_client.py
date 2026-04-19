"""
Mô-đun Gọi API - Hỗ trợ thử lại, giới hạn tốc độ, bộ nhớ cache, cân bằng tải


"""
import time
import hashlib
import json
import os
import threading
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
import logging
from openai import OpenAI, RateLimitError, APIError, AuthenticationError, APIConnectionError
import pickle
import random
import re

from core.config import get_config, Backend
from locales.i18n import t
from core.database import get_db

logger = logging.getLogger(__name__)

MAX_CACHE_SIZE = 100

# Cấu hình backend theo tác vụ (đọc từ env var)
# BACKEND_FOR_CHAPTER  = tên backend dùng để viết chương (tác vụ nặng)
# BACKEND_FOR_SIMPLE   = tên backend dùng cho tác vụ nhẹ (gợi ý tên, tóm tắt...)
BACKEND_FOR_CHAPTER = os.getenv("BACKEND_FOR_CHAPTER", "")
BACKEND_FOR_SIMPLE  = os.getenv("BACKEND_FOR_SIMPLE", "")


@dataclass
class CacheEntry:
    """mục bộ nhớ đệm"""
    key: str
    value: str
    timestamp: datetime
    ttl: int = 3600


class ResponseCache:
    """trình quản lý bộ đệm phản hồi"""
    
    def __init__(self, max_size: int = MAX_CACHE_SIZE):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.lock = threading.Lock()
        self._dirty_count = 0
        self._disk_loaded = False
    
    def _generate_key(self, messages: List[Dict], model: str) -> str:
        content = json.dumps(messages, sort_keys=True, ensure_ascii=False) + model
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def get(self, messages: List[Dict], model: str) -> Optional[str]:
        key = self._generate_key(messages, model)
        
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                if datetime.now() - entry.timestamp < timedelta(seconds=entry.ttl):
                    logger.debug(f"Cache hit (RAM): {key}")
                    return entry.value
                else:
                    del self.cache[key]
        
        try:
            conn = get_db()
            row = conn.execute(
                "SELECT value, timestamp, ttl FROM response_cache WHERE key = ?", (key,)
            ).fetchone()
            if row:
                try:
                    ts = datetime.fromisoformat(row["timestamp"])
                except Exception:
                    ts = datetime.now()
                ttl = int(row["ttl"])
                if datetime.now() - ts < timedelta(seconds=ttl):
                    entry = CacheEntry(key=key, value=row["value"], timestamp=ts, ttl=ttl)
                    with self.lock:
                        self.cache[key] = entry
                    logger.debug(f"Cache hit (DB): {key}")
                    return row["value"]
        except Exception as e:
            logger.debug(f"DB cache lookup failed: {e}")
        
        return None
    
    def set(self, messages: List[Dict], model: str, value: str, ttl: int = 3600) -> None:
        key = self._generate_key(messages, model)
        
        with self.lock:
            if len(self.cache) >= self.max_size:
                oldest_key = min(self.cache.keys(),
                               key=lambda k: self.cache[k].timestamp)
                del self.cache[oldest_key]
            
            self.cache[key] = CacheEntry(
                key=key,
                value=value,
                timestamp=datetime.now(),
                ttl=ttl
            )
            self._dirty_count += 1
            logger.debug(f"Cache set: {key}")
        
        try:
            self._save_entry_to_disk(key, value, ttl)
        except Exception:
            logger.debug("Cache save to disk error (ignored)")
    
    def clear(self) -> None:
        with self.lock:
            self.cache.clear()
        logger.info("Cache cleared")
    
    def _save_entry_to_disk(self, key: str, value: str, ttl: int) -> None:
        try:
            conn = get_db()
            conn.execute(
                "INSERT OR REPLACE INTO response_cache (key, value, timestamp, ttl) VALUES (?, ?, ?, ?)",
                (key, value, datetime.now().isoformat(), ttl)
            )
            conn.commit()
        except Exception as e:
            logger.warning(f"Save cache entry to database failed: {e}")
    
    def _cleanup_expired_db(self) -> None:
        try:
            conn = get_db()
            conn.execute("DELETE FROM response_cache WHERE datetime(timestamp, '+' || ttl || ' seconds') < datetime('now')")
            conn.commit()
            logger.debug("Expired cache entries cleaned from DB")
        except Exception as e:
            logger.debug(f"Cache cleanup failed: {e}")


class RateLimiter:
    """Giới hạn tỷ lệ - Thuật toán nhóm mã thông báo"""
    
    def __init__(self, rate: float = 10, window: int = 60):
        self.rate = rate
        self.window = window
        self.tokens = rate
        self.last_update = time.time()
        self.lock = threading.Lock()
    
    def acquire(self, tokens: int = 1, blocking: bool = True) -> bool:
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate / self.window)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            if blocking:
                wait_time = (tokens - self.tokens) * self.window / self.rate
                time.sleep(wait_time)
                self.tokens = 0
                return True
            
            return False


class APIClient:
    """Ứng dụng khách API - hỗ trợ thử lại, giới hạn tốc độ, lưu vào bộ đệm, cân bằng tải"""
    
    def __init__(self):
        self.config = get_config()
        self.cache = ResponseCache()
        self.clients: List[tuple[Backend, OpenAI]] = []
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.current_client_index = 0
        self.lock = threading.Lock()
        self._init_clients()
    
    def _init_clients(self) -> None:
        self.clients = []
        enabled_backends = self.config.get_enabled_backends()
        
        if not enabled_backends:
            logger.error("No enabled backends")
            return
        
        for backend in enabled_backends:
            try:
                client = OpenAI(
                    base_url=backend.base_url.rstrip("/"),
                    api_key=backend.api_key,
                    timeout=backend.timeout
                )
                self.clients.append((backend, client))
                
                limiter_key = f"{backend.name}_{backend.model}"
                if limiter_key not in self.rate_limiters:
                    self.rate_limiters[limiter_key] = RateLimiter(rate=10, window=60)
                
                logger.info(f"Backend init success: {backend.name}")
            except Exception as e:
                logger.error(f"Backend init failed {backend.name}: {e}")
        
        if not self.clients:
            logger.error("All backends init failed")
    
    def _strip_reasoning(self, text: str) -> str:
        if not text:
            return ""
        
        import re
        text = re.sub(r'<(thought|reasoning)>[\s\S]*?</\1>', '', text)
        patterns = [
            r'^Thinking Process:[\s\S]*?(\n\n|$)',
            r'^Thought:[\s\S]*?(\n\n|$)',
            r'^Suy nghĩ:[\s\S]*?(\n\n|$)',
            r'^Phân tích:[\s\S]*?(\n\n|$)'
        ]
        for pattern in patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        return text.strip()

    def _get_client_by_name(self, backend_name: str) -> Optional[tuple[Backend, OpenAI]]:
        """Lấy client theo tên backend cụ thể"""
        for client_tuple in self.clients:
            backend, client = client_tuple
            if backend.name == backend_name:
                return client_tuple
        logger.warning(f"Backend '{backend_name}' not found, falling back to default")
        return None

    def _get_next_client(self, retry_count: int = 0) -> Optional[tuple[Backend, OpenAI]]:
        """Nhận ứng dụng khách có sẵn tiếp theo (cân bằng tải)"""
        if not self.clients:
            return None
        with self.lock:
            if retry_count == 0:
                for client_tuple in self.clients:
                    backend, client = client_tuple
                    if getattr(backend, 'is_default', False):
                        return client_tuple
            
            idx = self.current_client_index
            client_tuple = self.clients[idx]
            self.current_client_index = (idx + 1) % len(self.clients)
            return client_tuple

    def _do_generate(
        self,
        messages: List[Dict[str, str]],
        client_info: tuple,
        use_cache: bool = True,
        max_retries: int = 3,
        backoff_factor: float = 1.5
    ) -> tuple[bool, str]:
        """Logic generate dùng chung cho cả generate() và generate_with_backend()"""
        enabled_backends = self.config.get_enabled_backends()
        if not enabled_backends:
            return False, t("api_client.no_backends")

        if not isinstance(messages, list) or len(messages) == 0:
            return False, t("api_client.invalid_messages")

        retry_count = 0
        base_wait = 1.0

        while retry_count < max_retries:
            if retry_count == 0:
                backend, client = client_info
            else:
                fallback = self._get_next_client(retry_count)
                if not fallback:
                    return False, t("api_client.no_api_client")
                backend, client = fallback

            model = getattr(backend, "model", None)
            limiter_key = f"{backend.name}_{model}"

            if limiter_key not in self.rate_limiters:
                self.rate_limiters[limiter_key] = RateLimiter(rate=10, window=60)

            if use_cache and model:
                cached = self.cache.get(messages, model)
                if cached:
                    return True, cached

            try:
                self.rate_limiters[limiter_key].acquire(blocking=True)
                logger.debug(f"API call: {backend.name} model={model}")

                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=getattr(self.config.generation, "temperature", 0.8),
                    top_p=getattr(self.config.generation, "top_p", 1.0),
                    max_tokens=getattr(self.config.generation, "max_tokens", 4096)
                )

                content = ""
                try:
                    if hasattr(response, 'choices') and len(response.choices) > 0:
                        choice = response.choices[0]
                        if hasattr(choice, 'message'):
                            content = getattr(choice.message, 'content', None) or ""
                            reasoning = getattr(choice.message, 'reasoning', None)
                            if not content and reasoning:
                                content = reasoning
                        elif hasattr(choice, 'text'):
                            content = choice.text

                    if not content or len(content.strip()) < 10:
                        if hasattr(response, 'content'):
                            content = response.content

                        if not content or len(content.strip()) < 10:
                            try:
                                response_dict = response.model_dump() if hasattr(response, 'model_dump') else {}
                                if 'choices' in response_dict and response_dict['choices']:
                                    msg = response_dict['choices'][0].get('message', {})
                                    content = msg.get('content', '') or msg.get('reasoning', '')
                            except Exception as e:
                                logger.debug(f"Dict conversion failed: {e}")

                        if not content or len(content.strip()) < 10:
                            response_str = str(response)
                            content_match = re.search(r"content=(?:'|\")((?:.|\n)*?)(?:'|\"),\s*refusal", response_str)
                            if content_match:
                                content = content_match.group(1).replace("\\n", "\n").replace("\\'", "'")

                    if content:
                        content = content.strip()
                        status_messages = [
                            t("generator.continue_success"), t("generator.rewrite_success"),
                            t("generator.polish_success"), t("generator.gen_success"),
                            "done", "success", "OK", "ok", "Success", "SUCCESS",
                        ]
                        if content in status_messages or len(content) < 10:
                            content = ""
                        else:
                            content = self._strip_reasoning(content)

                except Exception as e:
                    logger.exception(f"API response parse exception: {e}")
                    content = ""

                if use_cache and model and content and len(content) >= 10:
                    self.cache.set(messages, model, content)

                if not content or not content.strip() or len(content.strip()) < 10:
                    return False, t("api_client.invalid_content", length=len(content) if content else 0)

                logger.info(f"API call success: {backend.name}")
                return True, content

            except RateLimitError as e:
                retry_count += 1
                wait_time = base_wait * (backoff_factor ** retry_count) + random.random() * 0.5
                if retry_count >= max_retries:
                    return False, t("api_client.rate_limit_error", error=str(e))
                time.sleep(wait_time)

            except AuthenticationError as e:
                return False, t("api_client.auth_error", error=str(e))

            except APIConnectionError as e:
                retry_count += 1
                wait_time = base_wait * (backoff_factor ** retry_count) + random.random() * 0.5
                if retry_count >= max_retries:
                    return False, t("api_client.connection_error", error=str(e))
                time.sleep(wait_time)

            except APIError as e:
                retry_count += 1
                wait_time = base_wait * (backoff_factor ** retry_count) + random.random() * 0.5
                if retry_count >= max_retries:
                    return False, t("api_client.api_error", error=str(e))
                time.sleep(wait_time)

            except Exception as e:
                logger.exception(f"Unexpected error ({getattr(backend,'name', 'unknown')}): {e}")
                return False, t("api_client.error_prefix", error=str(e))

        return False, t("api_client.retry_failed", max=max_retries)

    def generate(
        self,
        messages: List[Dict[str, str]],
        use_cache: bool = True,
        max_retries: int = 3,
        backoff_factor: float = 1.5
    ) -> tuple[bool, str]:
        """Generate dùng backend mặc định (hoặc is_default)"""
        client_info = self._get_next_client(0)
        if not client_info:
            return False, t("api_client.no_api_client")
        return self._do_generate(messages, client_info, use_cache, max_retries, backoff_factor)

    def generate_for_chapter(
        self,
        messages: List[Dict[str, str]],
        use_cache: bool = False,
        max_retries: int = 3,
        backoff_factor: float = 1.5
    ) -> tuple[bool, str]:
        """Generate dùng backend cho tác vụ viết chương (nặng, chất lượng cao)"""
        client_info = None
        if BACKEND_FOR_CHAPTER:
            client_info = self._get_client_by_name(BACKEND_FOR_CHAPTER)
        if not client_info:
            client_info = self._get_next_client(0)
        if not client_info:
            return False, t("api_client.no_api_client")
        logger.info(f"generate_for_chapter using backend: {client_info[0].name}")
        return self._do_generate(messages, client_info, use_cache, max_retries, backoff_factor)

    def generate_for_simple(
        self,
        messages: List[Dict[str, str]],
        use_cache: bool = True,
        max_retries: int = 3,
        backoff_factor: float = 1.5
    ) -> tuple[bool, str]:
        """Generate dùng backend cho tác vụ nhẹ (gợi ý, tóm tắt, outline...)"""
        client_info = None
        if BACKEND_FOR_SIMPLE:
            client_info = self._get_client_by_name(BACKEND_FOR_SIMPLE)
        if not client_info:
            client_info = self._get_next_client(0)
        if not client_info:
            return False, t("api_client.no_api_client")
        logger.info(f"generate_for_simple using backend: {client_info[0].name}")
        return self._do_generate(messages, client_info, use_cache, max_retries, backoff_factor)

    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        backend_name: str = ""
    ):
        """Streaming — có thể chỉ định backend_name cụ thể"""
        enabled_backends = self.config.get_enabled_backends()
        if not enabled_backends:
            yield False, t("api_client.no_backends")
            return

        if not isinstance(messages, list) or len(messages) == 0:
            yield False, t("api_client.invalid_messages")
            return

        retry_count = 0
        base_wait = 1.0

        while retry_count < max_retries:
            if backend_name and retry_count == 0:
                client_info = self._get_client_by_name(backend_name)
            else:
                client_info = self._get_next_client(retry_count)

            if not client_info:
                yield False, t("api_client.no_api_client")
                return

            backend, client = client_info
            model = getattr(backend, "model", None)
            limiter_key = f"{backend.name}_{model}"

            if limiter_key not in self.rate_limiters:
                self.rate_limiters[limiter_key] = RateLimiter(rate=10, window=60)

            try:
                self.rate_limiters[limiter_key].acquire(blocking=True)
                logger.debug(f"API call (stream): {backend.name} model={model}")

                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=getattr(self.config.generation, "temperature", 0.8),
                    top_p=getattr(self.config.generation, "top_p", 1.0),
                    max_tokens=getattr(self.config.generation, "max_tokens", 4096),
                    stream=True
                )

                chunk_count = 0
                for chunk in response:
                    if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        content_chunk = getattr(delta, 'content', None)
                        if content_chunk:
                            chunk_count += 1
                            yield True, content_chunk
                
                logger.info(f"API call stream success: {backend.name}, received {chunk_count} chunks")
                return

            except RateLimitError as e:
                retry_count += 1
                wait_time = base_wait * (backoff_factor ** retry_count) + random.random() * 0.5
                if retry_count >= max_retries:
                    yield False, t("api_client.rate_limit_error", error=str(e))
                    return
                time.sleep(wait_time)
            except Exception as e:
                logger.exception(f"Unexpected error in stream ({getattr(backend,'name', 'unknown')}): {e}")
                yield False, t("api_client.error_prefix", error=str(e))
                return

        yield False, t("api_client.retry_failed", max=max_retries)

    def test_backends(self) -> Dict[str, bool]:
        results = {}
        test_messages = [
            {"role": "system", "content": t("api_client.test_prompt")},
            {"role": "user", "content": t("api_client.test_hello")}
        ]
        for backend in self.config.get_enabled_backends():
            try:
                client = OpenAI(
                    base_url=backend.base_url.rstrip("/"),
                    api_key=backend.api_key,
                    timeout=5
                )
                client.chat.completions.create(
                    model=backend.model,
                    messages=test_messages,
                    max_tokens=10
                )
                results[backend.name] = True
            except Exception as e:
                results[backend.name] = False
        return results
    
    def test_connection(self, base_url: str, api_key: str, model: str) -> bool:
        test_messages = [
            {"role": "system", "content": t("api_client.test_prompt")},
            {"role": "user", "content": t("api_client.test_hello")}
        ]
        try:
            client = OpenAI(base_url=base_url.rstrip("/"), api_key=api_key, timeout=10)
            client.chat.completions.create(model=model, messages=test_messages, max_tokens=10)
            return True
        except Exception as e:
            logger.error(f"Test connection failed: {e}")
            raise e
        
    def clear_cache(self) -> None:
        self.cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        return {
            "total_entries": len(self.cache.cache),
            "max_size": self.cache.max_size,
            "usage_rate": len(self.cache.cache) / self.cache.max_size * 100
        }

    def generate_image(self, prompt: str, size: str = "1024x1024", quality: str = "standard", n: int = 1) -> tuple[bool, str]:
        client_info = self._get_next_client(0)
        if not client_info:
            return False, t("api_client.no_api_client")
        backend, client = client_info
        try:
            response = client.images.generate(model="dall-e-3", prompt=prompt, size=size, quality=quality, n=n)
            return True, response.data[0].url
        except Exception as e:
            error_msg = str(e)
            if "<!DOCTYPE html>" in error_msg or "<html" in error_msg.lower():
                return False, t("api_client.image_gen_unsupported")
            return False, t("api_client.error_prefix", error=error_msg)


_api_client: Optional[APIClient] = None


def get_api_client() -> APIClient:
    global _api_client
    if _api_client is None:
        _api_client = APIClient()
    return _api_client


def reinit_api_client() -> None:
    global _api_client
    if _api_client is not None:
        _api_client._init_clients()
