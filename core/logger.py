"""
Mô-đun theo dõi và nhật ký - Hệ thống nhật ký cấp sản xuất

Bản quyền Â© 2026 Công ty TNHH Công nghệ An ninh mạng Huyễn Thành Tân Cương (Công nghệ Huyễn Thành)
Tác giả: Huyễn Thành
"""
import logging
import logging.handlers
import os
from datetime import datetime
from typing import Optional

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Cấu hình tệp nhật ký
LOG_FILE = os.path.join(LOG_DIR, f"novel_tool_{datetime.now().strftime('%Y%m%d')}.log")
ERROR_LOG_FILE = os.path.join(LOG_DIR, f"errors_{datetime.now().strftime('%Y%m%d')}.log")


def setup_logger(
    name: str,
    log_level: int = logging.INFO,
    log_to_file: bool = True,
    force_reconfigure: bool = False
) -> logging.Logger:
    """
    Khởi tạo logger cấp sản xuất
    
    Args:
        name: Tên logger
        log_level: Cấp độ nhật ký
        log_to_file: Có xuất ra tệp hay không
        force_reconfigure: Có bắt buộc cấu hình lại không (xóa các handler cũ)
    
    Returns:
        Biến logger đã được cấu hình
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Nếu bắt buộc cấu hình lại, xóa bỏ handler hiện có
    if force_reconfigure:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
    # Tránh thêm handler lặp lại
    elif logger.handlers:
        return logger
    
    # Định dạng đầu ra bảng điều khiển
    console_formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Đầu ra tệp (nếu được bật)
    if log_to_file:
        file_formatter = logging.Formatter(
            '[%(asctime)s] [%(name)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Nhật ký chung
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Nhật ký lỗi - Luôn thêm vào, đảm bảo chắc chắn sẽ thu thập được nhật ký cấp độ ERROR
        error_handler = logging.handlers.RotatingFileHandler(
            ERROR_LOG_FILE,
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        logger.addHandler(error_handler)
    
    return logger


class PerformanceMonitor:
    """Công cụ theo dõi hiệu suất"""
    
    def __init__(self):
        self.logger = setup_logger("PerformanceMonitor")
        self.metrics = {}
    
    def record_metric(self, name: str, value: float, unit: str = "ms") -> None:
        """Ghi lại số liệu hiệu suất"""
        if name not in self.metrics:
            self.metrics[name] = []
        
        self.metrics[name].append(value)
        
        # Chỉ lưu 1000 bản ghi gần nhất
        if len(self.metrics[name]) > 1000:
            self.metrics[name] = self.metrics[name][-1000:]
    
    def get_average(self, name: str) -> Optional[float]:
        """Lấy giá trị trung bình"""
        if name not in self.metrics or not self.metrics[name]:
            return None
        return sum(self.metrics[name]) / len(self.metrics[name])
    
    def report(self) -> str:
        """Tạo báo cáo hiệu suất"""
        if not self.metrics:
            return "No performance data yet"
        
        report = "=== Performance Report ===\n"
        for name, values in self.metrics.items():
            if values:
                avg = sum(values) / len(values)
                max_val = max(values)
                min_val = min(values)
                report += f"{name}: avg={avg:.2f}ms, max={max_val:.2f}ms, min={min_val:.2f}ms, count={len(values)}\n"
        
        return report


# Phiên bản toàn cục
_logger = setup_logger("NovelTool")
_performance_monitor = PerformanceMonitor()


def get_logger(name: str = "NovelTool") -> logging.Logger:
    """Lấy biến instance của logger"""
    return logging.getLogger(name)


def get_performance_monitor() -> PerformanceMonitor:
    """Lấy trình theo dõi hiệu suất"""
    return _performance_monitor
