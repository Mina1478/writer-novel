import os
import json
import logging
from typing import Dict, List, Optional
from locales.i18n import t

logger = logging.getLogger(__name__)

SUBGENRES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sub_genres.json")

class SubGenreManager:
    """Quản lý các chủ đề con (hashtags) và mô tả hướng dẫn viết"""
    
    _cached_sub_genres = None
    _cached_mtime = 0
    
    @classmethod
    def get_default_sub_genres(cls) -> List[Dict[str, str]]:
        """Lấy danh sách chủ đề con mặc định nếu chưa có file"""
        # Mặc định sử dụng danh sách cũ từ file ngôn ngữ
        default_names = t("create.sub_genres")
        if isinstance(default_names, str):
            default_names = [
                "Xuyên không", "Xuyên sách", "Trọng sinh", "Hệ thống", "Bàn tay vàng", "Không gian tùy thân", "Linh tuyền", "Đọc tâm thuật", 
                "Vô địch lưu", "Cẩu đạo", "Nhiệt huyết", "Hài hước", "Sảng văn", "Ngọt sủng", "Ngược luyến", "Gương vỡ lại lành", 
                "Cưới trước yêu sau", "Oan gia ngõ hẹp", "Thanh mai trúc mã", "Hào môn thế gia", "Tổng tài", "Minh tinh", "Giới giải trí", 
                "Vườn trường", "Học bá", "Võng du", "E-sports", "Livestream", "Mỹ thực", "Nông trại", "Điền văn", "Nuôi con", "Làm giàu", 
                "Cung đấu", "Gia đấu", "Quyền mưu", "Nữ cường", "Nam cường", "Song khiết", "Phế Sài", "Thiên tài", "Mỹ cường thảm", "Trà xanh", 
                "Bạch liên hoa", "Hắc hóa", "Cứu rỗi", "Chữa lành", "Não tàn", "Bức hôn", "Thế thân", "Mang thai chạy trốn", "Manh bảo", 
                "Khoa cử", "Khoa học kỹ thuật", "Linh khí khôi phục", "Dị năng", "Dị dã", "Thần minh", "Tu ma", "Phật tu", "Đạo sĩ", "Yêu tu", 
                "Quỷ tu", "Sư đồ luyến", "Huynh đệ", "Tỷ muội", "Ngụy huynh muội", "Đại thúc luyến", "Tỷ đệ luyến", "Niên hạ", "Song hướng thầm mến", 
                "Tình hữu độc chung", "Một kiến chung tình", "Pháp sư", "Kiếm khách", "Kỵ sĩ", "Tinh tế", "Cơ giáp", "Trùng tộc", "Dị thú", 
                "Mạt thế khổng lồ", "Mạt thế luân hồi", "Hào môn ân oán", "Phá án", "Huyền nghi", "Phiêu lưu", "Mạo hiểm", "Sống sót", "Man hoang", 
                "Bộ lạc", "Trí tuệ nhân tạo", "Biến dị", "Độc y", "Sát thủ", "Ma pháp sơ nguyên", "Khế ước", "Hậu cung", "1v1", "NP"
            ]
            
        default_sub_genres = []
        for name in default_names:
            desc = ""
            default_sub_genres.append({
                "name": name,
                "description": desc
            })
            
        return default_sub_genres

    @classmethod
    def ensure_data_dir(cls):
        """Đảm bảo thư mục data tồn tại"""
        os.makedirs(os.path.dirname(SUBGENRES_FILE), exist_ok=True)

    @classmethod
    def load_sub_genres(cls) -> List[Dict[str, str]]:
        """Tải danh sách chủ đề con từ file (có cache theo mtime)"""
        cls.ensure_data_dir()
        if not os.path.exists(SUBGENRES_FILE):
            default_sub_genres = cls.get_default_sub_genres()
            cls.save_sub_genres(default_sub_genres)
            return default_sub_genres
            
        try:
            current_mtime = os.path.getmtime(SUBGENRES_FILE)
            if cls._cached_sub_genres is not None and cls._cached_mtime == current_mtime:
                return cls._cached_sub_genres
            
            with open(SUBGENRES_FILE, 'r', encoding='utf-8') as f:
                sub_genres = json.load(f)
            cls._cached_sub_genres = sub_genres
            cls._cached_mtime = current_mtime
            return sub_genres
        except Exception as e:
            logger.error(f"Error loading sub genres: {e}")
            return cls.get_default_sub_genres()

    @classmethod
    def save_sub_genres(cls, sub_genres: List[Dict[str, str]]) -> bool:
        """Lưu danh sách chủ đề con xuống file"""
        cls.ensure_data_dir()
        try:
            with open(SUBGENRES_FILE, 'w', encoding='utf-8') as f:
                json.dump(sub_genres, f, ensure_ascii=False, indent=4)
            # Invalidate cache
            cls._cached_sub_genres = sub_genres
            cls._cached_mtime = os.path.getmtime(SUBGENRES_FILE)
            return True
        except Exception as e:
            logger.error(f"Error saving sub genres: {e}")
            return False

    @classmethod
    def add_sub_genre(cls, name: str, description: str = "") -> bool:
        """Thêm một chủ đề con mới"""
        sub_genres = cls.load_sub_genres()
        # Kiểm tra trùng tên
        if any(g["name"] == name for g in sub_genres):
            return False
            
        sub_genres.append({"name": name, "description": description})
        return cls.save_sub_genres(sub_genres)

    @classmethod
    def update_sub_genre(cls, old_name: str, new_name: str, description: str) -> bool:
        """Cập nhật thông tin chủ đề con"""
        sub_genres = cls.load_sub_genres()
        for i, g in enumerate(sub_genres):
            if g["name"] == old_name:
                # Nếu đổi tên, kiểm tra trùng tên mới
                if old_name != new_name and any(x["name"] == new_name for x in sub_genres):
                    return False
                
                sub_genres[i] = {"name": new_name, "description": description}
                return cls.save_sub_genres(sub_genres)
        return False

    @classmethod
    def delete_sub_genre(cls, name: str) -> bool:
        """Xóa chủ đề con"""
        sub_genres = cls.load_sub_genres()
        initial_length = len(sub_genres)
        sub_genres = [g for g in sub_genres if g["name"] != name]
        
        if len(sub_genres) < initial_length:
            return cls.save_sub_genres(sub_genres)
        return False

    @classmethod
    def get_sub_genre_names(cls) -> List[str]:
        """Lấy danh sách tên các chủ đề con để hiển thị UI"""
        sub_genres = cls.load_sub_genres()
        return [g["name"] for g in sub_genres]
        
    @classmethod
    def get_sub_genre_description(cls, name: str) -> str:
        """Lấy mô tả hướng dẫn của một chủ đề con"""
        sub_genres = cls.load_sub_genres()
        for g in sub_genres:
            if g["name"] == name:
                return g["description"]
        return ""
