"""
Mô-đun Quản lý dự án - Hỗ trợ lưu, tải, xuất dự án

Bản quyền © 2026 Công ty TNHH Công nghệ An ninh mạng Huyễn Thành Tân Cương (Công nghệ Huyễn Thành)
Tác giả: Huyễn Thành
"""
import json
import os
import re
import tempfile
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path

from services.novel_generator import NovelProject, Chapter
from locales.i18n import t
from core.database import get_db

logger = logging.getLogger(__name__)


class ProjectManager:
    """quản lý dự án"""
    
    @staticmethod
    def _slugify(name: str) -> str:
        s = str(name or "").lower()
        s = re.sub(r'[^\w\s-]', '', s)
        s = re.sub(r'[\s_]+', '-', s)
        s = re.sub(r'-+', '-', s).strip('-')
        return s or "untitled"
    
    @staticmethod
    def create_project(
        title: str,
        genre: str,
        sub_genres: List[str],
        character_setting: str,
        world_setting: str,
        plot_idea: str
    ) -> Tuple[Optional[NovelProject], str]:
        """
        Tạo dự án mới
        
        Returns:
            (Đối tượng dự án, Thông tin trạng thái)
        """
        try:
            if not title or not title.strip():
                return None, "Title cannot be empty"
            
            project_id = ProjectManager._slugify(title)
            now = datetime.now().isoformat()
            
            project = NovelProject(
                title=title.strip(),
                genre=genre.strip() if genre else "",
                sub_genres=sub_genres if sub_genres else [],
                character_setting=character_setting.strip() if character_setting else "",
                world_setting=world_setting.strip() if world_setting else "",
                plot_idea=plot_idea.strip() if plot_idea else "",
                id=project_id,
                created_at=now,
                updated_at=now
            )
            
            logger.info(f"Project created: {project_id}")
            return project, t("project_manager.create_success", title=title)
        
        except Exception as e:
            logger.error(f"Project create failed: {e}")
            return None, t("project_manager.create_failed", error=str(e))
    
    @staticmethod
    def save_project(project: NovelProject) -> Tuple[bool, str]:
        """
        Lưu dự án vào SQLite
        
        Returns:
            (Cờ thành công (boolean), Thông tin trạng thái)
        """
        try:
            if not project or not project.title:
                return False, "Project data incomplete"

            # Sử dụng project.id hiện có hoặc tạo mới
            if getattr(project, 'id', None):
                project_id = project.id
            else:
                project_id = ProjectManager._slugify(project.title)
                project.id = project_id

            conn = get_db()
            now = datetime.now().isoformat()
            project.updated_at = now

            # Lưu project
            conn.execute("""
                INSERT OR REPLACE INTO projects 
                (id, title, genre, sub_genres, character_setting, world_setting, plot_idea, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id,
                project.title,
                project.genre,
                json.dumps(project.sub_genres if isinstance(project.sub_genres, list) else [], ensure_ascii=False),
                project.character_setting,
                project.world_setting,
                project.plot_idea,
                project.created_at,
                now
            ))

            # Xóa chapters cũ và insert lại
            conn.execute("DELETE FROM chapters WHERE project_id = ?", (project_id,))
            for ch in project.chapters:
                conn.execute("""
                    INSERT INTO chapters 
                    (project_id, num, title, desc, content, word_count, generated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    project_id,
                    ch.num,
                    ch.title,
                    ch.desc,
                    ch.content,
                    ch.word_count,
                    ch.generated_at
                ))

            conn.commit()
            logger.info(f"Project saved to database: {project_id}")
            return True, t("project_manager.save_success", title=project_id)

        except Exception as e:
            logger.error(f"Project save failed: {e}")
            return False, t("project_manager.save_failed", error=str(e))
    
    @staticmethod
    def load_project(project_id: str) -> Tuple[Optional[NovelProject], str]:
        """
        Tải dự án từ SQLite
        
        Returns:
            (Đối tượng dự án, Thông tin trạng thái)
        """
        try:
            conn = get_db()
            
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            
            if not row:
                return None, t("project_manager.load_not_found", id=project_id)
            
            # Lấy list json string
            try:
                sg_str = row["sub_genres"]
            except (IndexError, KeyError):
                sg_str = "[]"
            try:
                sg_list = json.loads(sg_str) if sg_str else []
            except:
                sg_list = []
                
            # Xây dựng lại dự án
            project = NovelProject(
                title=row["title"],
                genre=row["genre"],
                sub_genres=sg_list,
                character_setting=row["character_setting"],
                world_setting=row["world_setting"],
                plot_idea=row["plot_idea"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
            project.id = row["id"]
            
            # Tải chapters
            ch_rows = conn.execute(
                "SELECT * FROM chapters WHERE project_id = ? ORDER BY num", (project_id,)
            ).fetchall()
            
            for ch_row in ch_rows:
                chapter = Chapter(
                    num=ch_row["num"],
                    title=ch_row["title"],
                    desc=ch_row["desc"],
                    content=ch_row["content"],
                    word_count=ch_row["word_count"],
                    generated_at=ch_row["generated_at"]
                )
                project.chapters.append(chapter)
            
            logger.info(f"Project loaded from core.database: {project_id}")
            return project, t("project_manager.load_success")
        
        except Exception as e:
            logger.error(f"Project load failed: {e}")
            return None, t("project_manager.load_failed", error=str(e))
    
    @staticmethod
    def list_projects() -> List[Dict]:
        """
        Liệt kê tất cả dự án từ SQLite
        
        Returns:
            Danh sách thông tin dự án
        """
        try:
            conn = get_db()
            rows = conn.execute(
                "SELECT id, title, genre, created_at, updated_at FROM projects ORDER BY updated_at DESC"
            ).fetchall()
            
            projects = []
            for row in rows:
                # Đếm chapters
                ch_count = conn.execute(
                    "SELECT COUNT(*) as total, SUM(CASE WHEN content != '' THEN 1 ELSE 0 END) as completed FROM chapters WHERE project_id = ?",
                    (row["id"],)
                ).fetchone()
                
                projects.append({
                    "id": row["id"],
                    "title": row["title"],
                    "genre": row["genre"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "chapter_count": ch_count["total"] if ch_count else 0,
                    "completed_chapters": ch_count["completed"] if ch_count else 0
                })
            
            logger.info(f"Found {len(projects)} projects in database")
            return projects
        
        except Exception as e:
            logger.error(f"List projects failed: {e}")
            return []
    

    @staticmethod
    def get_project_by_title(project_title: str) -> Optional[Dict]:
        """
        Lấy thông tin dự án theo tiêu đề

        Returns:
            Từ điển dự án hoặc None
        """
        projects = ProjectManager.list_projects()
        for project in projects:
            if project.get("title") == project_title:
                return project
        return None

    @staticmethod
    def delete_project(project_id: str) -> Tuple[bool, str]:
        """
        Xóa dự án từ SQLite
        
        Returns:
            (Cờ thành công (boolean), Thông tin trạng thái)
        """
        try:
            conn = get_db()
            cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
            
            if cursor.rowcount == 0:
                return False, t("project_manager.delete_not_found", id=project_id)
            
            logger.info(f"Project deleted from core.database: {project_id}")
            return True, t("project_manager.delete_success")
        
        except Exception as e:
            logger.error(f"Project delete failed: {e}")
            return False, t("project_manager.delete_failed", error=str(e))
    
    @staticmethod
    def export_project(project: NovelProject, export_format: str = "json") -> Tuple[Optional[str], str]:
        """
        Xuất cấu hình dự án (để chia sẻ hoặc sao lưu)
        
        Args:
            project: Đối tượng dự án
            export_format: Định dạng xuất (json/zip)
        
        Returns:
            (Đường dẫn tệp, Thông tin trạng thái)
        """
        try:
            if not project:
                return None, ""
            
            export_dir = os.path.join("exports", "project_backups")
            os.makedirs(export_dir, exist_ok=True)
            
            if export_format == "json":
                data = {
                    "title": project.title,
                    "genre": project.genre,
                    "sub_genres": project.sub_genres,
                    "character_setting": project.character_setting,
                    "world_setting": project.world_setting,
                    "plot_idea": project.plot_idea,
                    "created_at": project.created_at,
                    "chapters": [ch.to_dict() for ch in project.chapters]
                }
                
                filename = f"{project.title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                filepath = os.path.join(export_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                
                logger.info(f"Project exported: {filename}")
                return filepath, t("project_manager.export_success", filepath=filename)
            
            else:
                return None, f"Unsupported format: {export_format}"
        
        except Exception as e:
            logger.error(f"Project export failed: {e}")
            return None, t("project_manager.export_failed", error=str(e))


def get_project_manager() -> ProjectManager:
    """Nhận phiên bản quản lý dự án"""
    return ProjectManager()

def list_project_titles():
    """Lấy danh sách tiêu đề dự án"""
    try:
        projects = ProjectManager.list_projects()
        return [p["title"] for p in projects]
    except Exception:
        return []
