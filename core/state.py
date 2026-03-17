import threading
from typing import Optional
from services.novel_generator import NovelGenerator, get_generator, NovelProject

class AppState:
    """Trạng thái ứng dụng dùng chung giữa các tab"""
    def __init__(self):
        self.is_generating = False
        self.stop_requested = False
        self.lock = threading.Lock()
        self.current_project: Optional[NovelProject] = None
        self.generator: Optional[NovelGenerator] = None

    def get_generator(self) -> NovelGenerator:
        """Lấy hoặc tạo generator"""
        if self.generator is None:
            self.generator = get_generator()
        return self.generator

# Global app state singleton
app_state = AppState()
