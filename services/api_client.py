"""
Mô-đun Gọi API - Hỗ trợ thử lại, giới hạn tốc độ, bộ nhớ cache, cân bằng tải

Bản quyền © 2026 Công ty TNHH Công nghệ An ninh mạng Huyễn Thành Tân Cương (Công nghệ Huyễn Thành)
Tác giả: Huyễn Thành
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

from core.config import get_config, Backend
from locales.i18n import t
from core.database import get_db

logger = logging.getLogger(__name__)

# Số mục được lưu trong bộ nhớ đệm tối đa
MAX_CACHE_SIZE = 100


@dataclass
class CacheEntry:
    """mục bộ nhớ đệm"""
    key: str
    value: str
    timestamp: datetime
    ttl: int = 3600  # Mặc định hết hạn sau 1 giờ


class ResponseCache:
    """trình quản lý bộ đệm phản hồi"""
    
    def __init__(self, max_size: int = MAX_CACHE_SIZE):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.lock = threading.Lock()
        self._dirty_count = 0  # Đếm số lần set chưa flush
        self._disk_loaded = False  # Lazy load flag
    
    def _generate_key(self, messages: List[Dict], model: str) -> str:
        """Tạo khóa bộ đệm"""
        content = json.dumps(messages, sort_keys=True, ensure_ascii=False) + model
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def get(self, messages: List[Dict], model: str) -> Optional[str]:
        """Nhận bộ đệm (lazy load từ DB nếu chưa có trong RAM)"""
        key = self._generate_key(messages, model)
        
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                # Kiểm tra xem đã hết hạn chưa
                if datetime.now() - entry.timestamp < timedelta(seconds=entry.ttl):
                    logger.debug(f"Cache hit (RAM): {key}")
                    return entry.value
                else:
                    del self.cache[key]
        
        # Lazy load: thử tìm trong DB nếu không có trong RAM
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
                    # Cache hit từ DB → đưa vào RAM
                    entry = CacheEntry(key=key, value=row["value"], timestamp=ts, ttl=ttl)
                    with self.lock:
                        self.cache[key] = entry
                    logger.debug(f"Cache hit (DB): {key}")
                    return row["value"]
        except Exception as e:
            logger.debug(f"DB cache lookup failed: {e}")
        
        return None
    
    def set(self, messages: List[Dict], model: str, value: str, ttl: int = 3600) -> None:
        """Thiết lập bộ nhớ cache"""
        key = self._generate_key(messages, model)
        
        with self.lock:
            # Khi bộ đệm đầy, hãy xóa mục cũ nhất
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
        
        # Lưu vào DB ngay lập tức (chỉ entry mới, không flush toàn bộ)
        try:
            self._save_entry_to_disk(key, value, ttl)
        except Exception:
            logger.debug("Cache save to disk error (ignored)")
    
    def clear(self) -> None:
        """Xóa bộ nhớ đệm"""
        with self.lock:
            self.cache.clear()
        logger.info("Cache cleared")
    
    def _save_entry_to_disk(self, key: str, value: str, ttl: int) -> None:
        """Lưu một entry vào SQLite (thay vì flush toàn bộ cache)"""
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
        """Xóa các entry hết hạn trong DB (gọi định kỳ)"""
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
        """
        Args:
            rate: số lượng yêu cầu trên mỗi giây của cửa sổ
            cửa sổ: cửa sổ thời gian (giây)
        """
        self.rate = rate
        self.window = window
        self.tokens = rate
        self.last_update = time.time()
        self.lock = threading.Lock()
    
    def acquire(self, tokens: int = 1, blocking: bool = True) -> bool:
        """Nhận mã thông báo"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            
            # Mã thông báo bổ sung
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
        """Khởi tạo tất cả client"""
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
                
                # Tạo bộ giới hạn tốc độ cho mỗi chương trình phụ trợ
                limiter_key = f"{backend.name}_{backend.model}"
                if limiter_key not in self.rate_limiters:
                    # Giả sử tối đa 10 yêu cầu/phút đồng thời cho mỗi chương trình phụ trợ
                    self.rate_limiters[limiter_key] = RateLimiter(rate=10, window=60)
                
                logger.info(f"Backend init success: {backend.name}")
            except Exception as e:
                logger.error(f"Backend init failed {backend.name}: {e}")
        
        if not self.clients:
            logger.error("All backends init failed")
    
    def _strip_reasoning(self, text: str) -> str:
        """Loại bỏ phần suy nghĩ (reasoning/thinking) khỏi nội dung"""
        if not text:
            return ""
        
        import re
        
        # 1. Loại bỏ các thẻ <thought>...</thought> hoặc <reasoning>...</reasoning>
        text = re.sub(r'<(thought|reasoning)>[\s\S]*?</\1>', '', text)
        
        # 2. Loại bỏ các đoạn văn bắt đầu bằng "Thinking Process:", "Thought:", v.v.
        # Thường các đoạn này nằm ở đầu và phân tách bởi xuống dòng kép
        patterns = [
            r'^Thinking Process:[\s\S]*?(\n\n|$)',
            r'^Thought:[\s\S]*?(\n\n|$)',
            r'^Suy nghĩ:[\s\S]*?(\n\n|$)',
            r'^Phân tích:[\s\S]*?(\n\n|$)'
        ]
        for pattern in patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
            
        return text.strip()

    def _get_next_client(self, retry_count: int = 0) -> Optional[tuple[Backend, OpenAI]]:
        """Nhận ứng dụng khách có sẵn tiếp theo (cân bằng tải)"""
        if not self.clients:
            return None
        with self.lock:
            # Nếu là lần thử đầu tiên, ưu tiên tìm backend mặc định
            if retry_count == 0:
                for client_tuple in self.clients:
                    backend, client = client_tuple
                    if getattr(backend, 'is_default', False):
                        return client_tuple
            
            idx = self.current_client_index
            client_tuple = self.clients[idx]
            # Con trỏ tiến lên và cuộc gọi tiếp theo trả về cuộc gọi tiếp theo
            self.current_client_index = (idx + 1) % len(self.clients)
            return client_tuple
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        use_cache: bool = True,
        max_retries: int = 3,
        backoff_factor: float = 1.5
    ) -> tuple[bool, str]:
        """
        Tạo văn bản (kèm bộ nhớ cache, thử lại, giới hạn tốc độ)
        
        Args:
            messages: Danh sách thông báo (messages)
            use_cache: Có sử dụng bộ nhớ cache không
            max_retries: Số lần thử lại tối đa
            backoff_factor: Hệ số lùi lại (backoff factor)
        
        Returns:
            (Cờ thành công, Nội dung khởi tạo/Thông báo lỗi)
        """
        enabled_backends = self.config.get_enabled_backends()
        if not enabled_backends:
            return False, t("api_client.no_backends")

        # Xác minh thông số
        if not isinstance(messages, list) or len(messages) == 0:
            return False, t("api_client.invalid_messages")

        # Thử lại logic (thăm dò các chương trình phụ trợ khác nhau)
        retry_count = 0
        base_wait = 1.0
        
        import random

        while retry_count < max_retries:
            client_info = self._get_next_client(retry_count)
            if not client_info:
                return False, t("api_client.no_api_client")

            backend, client = client_info
            model = getattr(backend, "model", None)
            limiter_key = f"{backend.name}_{model}"

            # Đảm bảo có giới hạn tỷ lệ
            if limiter_key not in self.rate_limiters:
                self.rate_limiters[limiter_key] = RateLimiter(rate=10, window=60)

            # Cố gắng sử dụng bộ nhớ đệm (tùy theo mô hình phụ trợ đã chọn)
            if use_cache and model:
                cached = self.cache.get(messages, model)
                if cached:
                    return True, cached

            try:
                # Yêu cầu mã thông báo (chặn cho đến khi có sẵn)
                self.rate_limiters[limiter_key].acquire(blocking=True)

                logger.debug(f"API call: {backend.name} model={model}")

                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=getattr(self.config.generation, "temperature", 0.8),
                    top_p=getattr(self.config.generation, "top_p", 1.0),
                    max_tokens=getattr(self.config.generation, "max_tokens", 4096)
                )

                # Logic phân tích phản hồi nâng cao - hỗ trợ nhiều định dạng, lọc thông báo trạng thái
                logger.debug(f"API response type: {type(response)}")
                logger.debug(f"API response object: {response}")

                content = ""
                try:
                    # Hãy thử định dạng OpenAI tiêu chuẩn
                    if hasattr(response, 'choices') and len(response.choices) > 0:
                        choice = response.choices[0]
                        logger.debug(f"Choice type: {type(choice)}")
                        logger.debug(f"Choice attrs: {dir(choice)}")

                        if hasattr(choice, 'message'):
                            # Ưu tiên content, nếu không có thử lấy từ reasoning (ví dụ DeepSeek R1)
                            content = getattr(choice.message, 'content', None) or ""
                            reasoning = getattr(choice.message, 'reasoning', None)
                            
                            if not content and reasoning:
                                logger.info(f"[{backend.name}] Content is empty but reasoning is found, using reasoning as content")
                                content = reasoning
                            
                            if not (not content or len(content.strip()) < 10):
                                logger.debug(f"Got content from message, len: {len(content)}")
                        elif hasattr(choice, 'text'):
                            content = choice.text
                            logger.debug(f"Got content from choice.text, len: {len(content) if content else 0}")
                        else:
                            logger.warning(f"Cannot get content from choice, type: {type(choice)}")
                    else:
                        logger.warning(f"Response has no choices, type: {type(response)}")

                    # Nếu phân tích cú pháp tiêu chuẩn không thành công, hãy thử các định dạng có thể khác
                    if not content or len(content.strip()) < 10:
                        logger.warning("Standard parse failed, trying alternatives")

                        # Hãy thử truy cập trực tiếp vào thuộc tính nội dung của phản hồi
                        if hasattr(response, 'content'):
                            content = response.content
                            logger.debug(f"Got content from response.content, len: {len(content) if content else 0}")

                        # Cố gắng trích xuất từ ​​​​biểu diễn chính tả của phản hồi
                        if not content or len(content.strip()) < 10:
                            try:
                                response_dict = response.model_dump() if hasattr(response, 'model_dump') else response.dict() if hasattr(response, 'dict') else {}
                                if 'choices' in response_dict and response_dict['choices']:
                                    msg = response_dict['choices'][0].get('message', {})
                                    content = msg.get('content', '') or msg.get('reasoning', '')
                                    logger.debug(f"Extracted from dict, len: {len(content) if content else 0}")
                            except Exception as e:
                                logger.debug(f"Dict conversion failed: {e}")

                        # Dự phòng cuối cùng: chuyển đổi thành chuỗi và dùng regex (Xử lý trường hợp đối tượng thô quá lớn)
                        if not content or len(content.strip()) < 10:
                            logger.warning("All primary parse methods failed, using regex fallback on str(response)")
                            response_str = str(response)
                            
                            # Thử tìm content='...'
                            import re
                            content_match = re.search(r"content=(?:'|\")((?:.|\n)*?)(?:'|\"),\s*refusal", response_str)
                            if content_match:
                                content = content_match.group(1).replace("\\n", "\n").replace("\\'", "'")
                                logger.info(f"Regex extracted content, len: {len(content)}")
                            
                            # Nếu vẫn không có, thử tìm reasoning='...'
                            if not content or len(content.strip()) < 10:
                                reasoning_match = re.search(r"reasoning=(?:'|\")((?:.|\n)*?)(?:'|\"),\s*role", response_str)
                                if reasoning_match:
                                    content = reasoning_match.group(1).replace("\\n", "\n").replace("\\'", "'")
                                    logger.info(f"Regex extracted reasoning, len: {len(content)}")

                            if not content or len(content.strip()) < 10:
                                # Lọc các thông báo trạng thái phổ biến
                                status_messages = [t("generator.continue_success"), t("generator.rewrite_success"), t("generator.polish_success"), t("generator.gen_success"), "done", "success"]
                                if response_str.strip() in status_messages or len(response_str.strip()) < 10:
                                    content = None
                                else:
                                    content = response_str

                        if not content or len(content.strip()) < 10:
                            logger.error("Failed to extract content even with fallback methods")

                    # Xác thực cuối cùng - lọc nghiêm ngặt các thông báo trạng thái
                    if content:
                        content = content.strip()
                        
                        # Xác định trạng thái cần lọc Danh sách thông báo (tin nhắn)
                        status_messages = [
                            t("generator.continue_success"), t("generator.rewrite_success"), t("generator.polish_success"), t("generator.gen_success"), "done", "success",
                            "OK", "ok", "Success", "SUCCESS",
                            
                        ]
                        
                        # Kiểm tra xem nội dung có phải là thông báo trạng thái không
                        if content in status_messages:
                            logger.error(f"Status msg detected, rejecting: {content}")
                            content = ""
                        # Kiểm tra độ dài nội dung
                        elif len(content) < 10:
                            logger.warning(f"Content too short ({len(content)} chars), may be status msg")
                            logger.warning(f"Content: {content}")
                            content = ""
                        else:
                            # Loại bỏ reasoning trước khi trả về
                            content = self._strip_reasoning(content)
                            logger.info(f"Got content successfully, final len: {len(content)}")
                            logger.debug(f"Content first 200: {content[:200]}")
                    else:
                        logger.error("Failed to get any content")

                except Exception as e:
                    logger.exception(f"API response parse exception: {e}")
                    # Đồng thời cố gắng lấy nội dung trong những trường hợp bất thường
                    try:
                        response_str = str(response)
                        # Lọc thông báo trạng thái
                        status_messages = [t("generator.continue_success"), t("generator.rewrite_success"), t("generator.polish_success"), t("generator.gen_success"), "done", "success"]
                        if response_str.strip() not in status_messages and len(response_str.strip()) >= 10:
                            content = response_str
                            logger.warning(f"Exception fallback str(response), len: {len(content)}")
                        else:
                            logger.error(f"Exception fallback: API returned status msg: {response_str}")
                            content = ""
                    except Exception as e2:
                        logger.exception(f"Exception fallback also failed: {e2}")
                        content = ""

                # Kết quả được lưu vào bộ nhớ đệm - chỉ lưu nội dung hợp lệ vào bộ nhớ đệm
                if use_cache and model and content and len(content) >= 10:
                    self.cache.set(messages, model, content)
                elif use_cache and model and (not content or len(content) < 10):
                    logger.warning("Invalid content, not caching")

                # Xác minh cuối cùng: Đảm bảo nội dung không trống và hợp lệ
                if not content or not content.strip() or len(content.strip()) < 10:
                    logger.error(f"Invalid/short content, rejecting: len={len(content) if content else 0}")
                    return False, t("api_client.invalid_content", length=len(content) if content else 0)

                logger.info(f"API call success: {backend.name}")
                return True, content

            except RateLimitError as e:
                retry_count += 1
                jitter = random.random() * 0.5
                wait_time = base_wait * (backoff_factor ** retry_count) + jitter
                logger.warning(f"API rate limit ({backend.name}), waiting {wait_time:.2f}s... (retry {retry_count})")
                if retry_count >= max_retries:
                    return False, t("api_client.rate_limit_error", error=str(e))
                time.sleep(wait_time)

            except AuthenticationError as e:
                logger.error(f"API authentication error ({backend.name}): {e}")
                return False, t("api_client.auth_error", error=str(e))

            except APIConnectionError as e:
                retry_count += 1
                jitter = random.random() * 0.5
                wait_time = base_wait * (backoff_factor ** retry_count) + jitter
                logger.warning(f"API connection error ({backend.name}), waiting {wait_time:.2f}s... (retry {retry_count})")
                if retry_count >= max_retries:
                    return False, t("api_client.connection_error", error=str(e))
                time.sleep(wait_time)

            except APIError as e:
                retry_count += 1
                jitter = random.random() * 0.5
                wait_time = base_wait * (backoff_factor ** retry_count) + jitter
                logger.warning(f"API error ({backend.name}): {e}, waiting {wait_time:.2f}s... (retry {retry_count})")
                if retry_count >= max_retries:
                    return False, t("api_client.api_error", error=str(e))
                time.sleep(wait_time)

            except Exception as e:
                # Lỗi không xác định được trả về trực tiếp nhưng có ngữ cảnh
                logger.exception(f"Unexpected error ({getattr(backend,'name', 'unknown')}): {e}")
                return False, t("api_client.error_prefix", error=str(e))

        return False, t("api_client.retry_failed", max=max_retries)
    
    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        max_retries: int = 3,
        backoff_factor: float = 1.5
    ):
        """
        Tạo văn bản theo luồng (Streaming)
        
        Args:
            messages: Danh sách thông báo (messages)
            max_retries: Số lần thử lại tối đa
            backoff_factor: Hệ số lùi lại (backoff factor)
        
        Yields:
            (Cờ thành công, Nội dung chunk/Thông báo lỗi)
        """
        enabled_backends = self.config.get_enabled_backends()
        if not enabled_backends:
            yield False, t("api_client.no_backends")
            return

        if not isinstance(messages, list) or len(messages) == 0:
            yield False, t("api_client.invalid_messages")
            return

        retry_count = 0
        base_wait = 1.0
        import random

        while retry_count < max_retries:
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
                        # Thử lấy từ content hoặc reasoning/reasoning_content (hỗ trợ DeepSeek R1 và các mô hình tương tự)
                        content_chunk = getattr(delta, 'content', None)
                        reasoning_chunk = getattr(delta, 'reasoning', None) or getattr(delta, 'reasoning_content', None)
                        
                        if content_chunk:
                            chunk_count += 1
                            yield True, content_chunk
                
                logger.info(f"API call stream success: {backend.name}, received {chunk_count} chunks")
                return

            except RateLimitError as e:
                retry_count += 1
                wait_time = base_wait * (backoff_factor ** retry_count) + random.random() * 0.5
                logger.warning(f"API rate limit (stream), waiting {wait_time:.2f}s...")
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
        """Kiểm tra tính khả dụng của tất cả các phụ trợ"""
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
                
                response = client.chat.completions.create(
                    model=backend.model,
                    messages=test_messages,
                    max_tokens=10
                )
                
                results[backend.name] = True
                logger.info(f"Backend test success: {backend.name}")
            except Exception as e:
                results[backend.name] = False
                logger.error(f"Backend test failed {backend.name}: {e}")
        return results
    
    def test_connection(self, base_url: str, api_key: str, model: str) -> bool:
        """Kiểm tra kết nối cho một phụ trợ duy nhất"""
        test_messages = [
            {"role": "system", "content": t("api_client.test_prompt")},
            {"role": "user", "content": t("api_client.test_hello")}
        ]
        
        try:
            client = OpenAI(
                base_url=base_url.rstrip("/"),
                api_key=api_key,
                timeout=10
            )
            
            response = client.chat.completions.create(
                model=model,
                messages=test_messages,
                max_tokens=10
            )
            return True
        except Exception as e:
            logger.error(f"Test connection failed: {e}")
            raise e
        
    def clear_cache(self) -> None:
        """Xóa bộ nhớ đệm"""
        self.cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Nhận số liệu thống kê bộ đệm"""
        return {
            "total_entries": len(self.cache.cache),
            "max_size": self.cache.max_size,
            "usage_rate": len(self.cache.cache) / self.cache.max_size * 100
        }

    def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        n: int = 1
    ) -> tuple[bool, str]:
        """
        Tạo hình ảnh (DALL-E) qua API OpenAI
        
        Args:
            prompt: Nội dung mô tả hình ảnh
            size: Kích thước hình ảnh (1024x1024, v.v.)
            quality: Chất lượng (standard/hd)
            n: Số lượng hình ảnh
            
        Returns:
            (Cờ thành công, URL hình ảnh hoặc thông báo lỗi)
        """
        client_info = self._get_next_client(0)
        if not client_info:
            return False, t("api_client.no_api_client")

        backend, client = client_info
        
        try:
            logger.info(f"Generating image with prompt: {prompt[:100]}... using {backend.name}")
            # Thử gọi API tạo hình ảnh (chỉ OpenAI chính thức mới hỗ trợ tốt nhất)
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality=quality,
                n=n,
            )
            image_url = response.data[0].url
            return True, image_url
        except Exception as e:
            error_msg = str(e)
            if "<!DOCTYPE html>" in error_msg or "<html" in error_msg.lower():
                user_msg = t("api_client.image_gen_unsupported")
                logger.error(f"Image generation not supported by backend {backend.name}")
                return False, user_msg
            logger.error(f"Image generation failed: {error_msg}")
            return False, t("api_client.error_prefix", error=error_msg)


# Phiên bản ứng dụng khách API toàn cầu
_api_client: Optional[APIClient] = None


def get_api_client() -> APIClient:
    """Nhận phiên bản máy khách API toàn cầu"""
    global _api_client
    if _api_client is None:
        _api_client = APIClient()
    return _api_client


def reinit_api_client() -> None:
    """Re-Khởi tạo API client (được gọi sau khi thay đổi cấu hình)"""
    global _api_client
    if _api_client is not None:
        _api_client._init_clients()
