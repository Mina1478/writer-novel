"""
Mô-đun tạo tiểu thuyết - Hỗ trợ tạo dàn ý, tạo chương, viết lại...


"""
import re
import logging
import json
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from services.api_client import get_api_client
from core.config import get_config
from locales.i18n import t
from core.database import get_db

logger = logging.getLogger(__name__)

# Mẫu cài sẵn - lựa chọn kiểu phong phú (các phím được ánh xạ tới ngôn ngữ)
def _build_preset_templates():
    """Build preset templates from StyleManager"""
    from services.style_manager import StyleManager
    styles = StyleManager.load_styles()
    templates = {}
    for g in styles:
        templates[g["name"]] = g["description"]
    return templates

def get_preset_templates():
    """Get preset templates (rebuilt each call to respect Active Genres)"""
    return _build_preset_templates()


@dataclass
class Chapter:
    """Cấu trúc dữ liệu chương"""
    num: int
    title: str
    desc: str
    content: str = ""
    word_count: int = 0
    generated_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Chuyển đổi sang từ điển"""
        return {
            "num": self.num,
            "title": self.title,
            "desc": self.desc,
            "content": self.content,
            "word_count": self.word_count,
            "generated_at": self.generated_at
        }


@dataclass
class NovelProject:
    """Cấu trúc dữ liệu dự án mới"""
    title: str
    genre: str
    character_setting: str
    world_setting: str
    plot_idea: str
    sub_genres: List[str] = field(default_factory=list)
    id: Optional[str] = None
    chapters: List[Chapter] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def get_completed_count(self) -> int:
        """Lấy số chương đã hoàn thành"""
        return sum(1 for ch in self.chapters if ch.content.strip())
    
    def get_total_words(self) -> int:
        """Nhận tổng số từ"""
        return sum(ch.word_count for ch in self.chapters)


class OutlineParser:
    """Trình phân tích cú pháp phác thảo"""
    
    @staticmethod
    def parse(outline_text: str) -> Tuple[List[Chapter], str]:
        """
        Phân tích văn bản dàn ý
        
        Returns (Trả về):
            (Danh sách chương, Thông báo lỗi)
        """
        if not outline_text or not outline_text.strip():
            return [], t("generator.outline_empty")
        
        chapters = []
        lines = [line.strip() for line in outline_text.split('\n') if line.strip()]

        chapter_count = 0
        # Hỗ trợ nhiều định dạng phác thảo phổ biến và thử nhiều biểu thức chính quy
        patterns = [
            r'(?:第\s*|Chương\s*|Chapter\s*|Hồi\s*|Phần\s*)(\d+)(?:\s*章)?[：:\s]+([^\-—–]+)[-—–]\s*(.+)',
            r'^(\d+)[\).:\s]+([^\-—–]+)[-—–]\s*(.+)',
            r'(?:第\s*|Chương\s*|Chapter\s*|Hồi\s*|Phần\s*)(\d+)(?:\s*章)?[：:\s]+(.+)',
        ]

        for line in lines:
            matched = False
            for pat in patterns:
                match = re.match(pat, line)
                if not match:
                    continue

                # Các nhóm chụp mẫu khác nhau có thể có ý nghĩa khác nhau
                if len(match.groups()) >= 3:
                    num = int(match.group(1))
                    title = match.group(2).strip()
                    desc = match.group(3).strip()
                else:
                    # Chỉ có hai nhóm, hãy thử sử dụng nhóm thứ hai để chia thành tiêu đề và mô tả
                    num = int(match.group(1))
                    rest = match.group(2).strip()
                    if '-' in rest or '—' in rest or '–' in rest:
                        parts = re.split('[-—–]', rest, maxsplit=1)
                        title = parts[0].strip()
                        desc = parts[1].strip() if len(parts) > 1 else ''
                    else:
                        # Không thể tách, coi như tiêu đề, mô tả trống
                        title = rest
                        desc = ''

                if not title:
                    logger.warning(f"Skip invalid chapter (no title): {line}")
                    matched = True
                    break

                # Tiêu đề rõ ràng: nếu nó chứa tiền tố "Chương X:", hãy xóa nó
                if re.match(r'^\s*(?:第\s*\d+\s*章|Chương\s*\d+|Chapter\s*\d+|Hồi\s*\d+|Phần\s*\d+)[：:\-\s]*', title, re.IGNORECASE):
                    title = re.sub(r'^\s*(?:第\s*\d+\s*章|Chương\s*\d+|Chapter\s*\d+|Hồi\s*\d+|Phần\s*\d+)[：:\-\s]*', '', title, flags=re.IGNORECASE).strip()
                chapters.append(Chapter(num=num, title=title, desc=desc))
                chapter_count += 1
                matched = True
                break

            if not matched:
                # Khả năng chịu lỗi bổ sung: cố gắng phân tích cú pháp theo 'mô tả tiêu đề', được tính tự động
                if '-' in line or '—' in line:
                    parts = re.split('[-—–]', line, maxsplit=1)
                    title = parts[0].strip()
                    desc = parts[1].strip() if len(parts) > 1 else ''
                    chapter_count += 1
                    chapters.append(Chapter(num=chapter_count, title=title, desc=desc))
        
        if not chapters:
            return [], t("generator.outline_parse_failed")
        
        # Sắp xếp theo Số chương
        chapters.sort(key=lambda x: x.num)
        
        # Kiểm tra tính liên tục của Số chương
        for i, chapter in enumerate(chapters, 1):
            if chapter.num != i:
                logger.warning(f"Chapter number not sequential: expected {i}, got {chapter.num}")
                chapter.num = i
        
        logger.info(f"Parsed {len(chapters)} chapters")
        return chapters, t("generator.outline_parse_success", count=len(chapters))
    
    @staticmethod
    def format_for_display(chapters: List[Chapter]) -> str:
        """Định dạng danh sách chương dưới dạng có thể chỉnh sửa Văn bản dàn ý"""
        lines = []
        for ch in chapters:
            lines.append(f"Chapter {ch.num}: {ch.title} - {ch.desc}")
        return "\n".join(lines)


from services.genre_manager import GenreManager
from services.sub_genre_manager import SubGenreManager

class NovelGenerator:
    """máy phát điện mới"""
    
    def __init__(self):
        self.config = get_config()
        self.api_client = get_api_client()
    
    def generate_outline(
        self,
        title: str,
        genre: str,
        sub_genres: List[str],
        total_chapters: int,
        character_setting: str,
        world_setting: str,
        plot_idea: str,
        custom_outline_prompt: str = ""
    ) -> Tuple[str, str]:
        """
        Tạo dàn ý tiểu thuyết
        
        Returns (Trả về):
            (Văn bản dàn ý, Thông báo lỗi hoặc tin báo thành công)
        """
        if not title or not title.strip():
            return "", t("generator.title_empty")
        if not character_setting or not character_setting.strip():
            return "", t("generator.char_empty")
        if not world_setting or not world_setting.strip():
            return "", t("generator.world_empty")
        if not plot_idea or not plot_idea.strip():
            return "", t("generator.plot_empty")
        
        if total_chapters <= 0:
            total_chapters = 20
        
        style_desc = self._build_style_description()
        
        genre_desc = GenreManager.get_genre_description(genre)
        if genre_desc:
            style_desc += f"\n\nHướng dẫn viết riêng cho thể loại {genre}: {genre_desc}"
            
        if sub_genres:
            sub_genre_details = []
            for sg in sub_genres:
                desc = SubGenreManager.get_sub_genre_description(sg)
                if desc:
                    sub_genre_details.append(f"- {sg}: {desc}")
                else:
                    sub_genre_details.append(f"- {sg}")
            style_desc += f"\n\nCác chủ đề con (Tag) bổ sung:\n" + "\n".join(sub_genre_details) + "\n\nHãy kết hợp chặt chẽ các đặc điểm của những chủ đề này để làm phong phú cấu trúc cốt truyện."
        
        custom_prompt_str = f"Yêu cầu chuyên biệt của tác giả:\n{custom_outline_prompt}\n\n" if custom_outline_prompt.strip() else ""

        prompt = t("prompts.outline_user",
            genre=genre, title=title,
            character_setting=character_setting,
            world_setting=world_setting,
            plot_idea=plot_idea,
            style_desc=style_desc,
            custom_prompt=custom_prompt_str,
            total_chapters=total_chapters
        )
        
        messages = [
            {"role": "system", "content": t("prompts.outline_system")},
            {"role": "user", "content": prompt}
        ]
        
        logger.info(f"Start generating outline: {title}")
        success, content = self.api_client.generate_for_simple(messages, use_cache=True)
        
        if not success:
            logger.error(f"Outline generation failed: {content}")
            return "", content
        
        logger.info("Outline generation success")
        return content, t("generator.outline_gen_success")
    
    def suggest_title(self, genre: str, sub_genres: List[str] = None, custom_prompt: str = "") -> Tuple[str, str]:
        """
        Gợi ý Tiêu đề truyện bằng AI.
        """
        system_prompt = t("prompts.suggest_system")
        genre_desc = GenreManager.get_genre_description(genre)
        if genre_desc:
            system_prompt += f"\n\nLưu ý bám sát hướng dẫn viết thể loại {genre}: {genre_desc}"
        
        if sub_genres:
            sub_genre_details = []
            for sg in sub_genres:
                desc = SubGenreManager.get_sub_genre_description(sg)
                if desc:
                    sub_genre_details.append(f"- {sg}: {desc}")
                else:
                    sub_genre_details.append(f"- {sg}")
            system_prompt += f"\n\nCác chủ đề con (Tag) bổ sung:\n" + "\n".join(sub_genre_details) + "\n\nVui lòng xem xét các chủ đề này khi đề xuất."
        
        # Nếu người dùng có prompt tùy chỉnh, ưu tiên ghép chung, nếu không dùng mặc định
        if custom_prompt.strip():
            user_prompt = f"{t('prompts.suggest_title_user', genre=genre)}\n\nYêu cầu bổ sung của tác giả:\n{custom_prompt}"
        else:
            user_prompt = t("prompts.suggest_title_user", genre=genre)
            
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        logger.info(f"Start generating title suggestions for genre: {genre}")
        success, content = self.api_client.generate_for_simple(messages, use_cache=False)
        
        if not success:
            logger.error(f"Title suggestion generation failed: {content}")
            return "", content
        
        logger.info("Title suggestion generation success")
        return content, t("generator.suggest_success")

    def suggest_content(
        self,
        suggest_type: str,
        title: str,
        genre: str,
        sub_genres: List[str] = None,
        character_setting: str = "",
        world_setting: str = "",
        custom_prompt: str = "",
        num_main_chars: int = 2,
        num_sub_chars: int = 3
    ) -> Tuple[str, str]:
        """
        Gợi ý nội dung bằng AI (Nhân vật, Thế giới, Cốt truyện) với Prompt tùy chỉnh
        """
        if not title or not title.strip():
            return "", t("generator.title_empty")
            
        system_prompt = t("prompts.suggest_system")
        genre_desc = GenreManager.get_genre_description(genre)
        if genre_desc:
            system_prompt += f"\n\nLưu ý bám sát đặc trưng thể loại {genre}: {genre_desc}"
            
        if sub_genres:
            sub_genre_details = []
            for sg in sub_genres:
                desc = SubGenreManager.get_sub_genre_description(sg)
                if desc:
                    sub_genre_details.append(f"- {sg}: {desc}")
                else:
                    sub_genre_details.append(f"- {sg}")
            system_prompt += f"\n\nCác chủ đề con (Tag) bổ sung:\n" + "\n".join(sub_genre_details) + "\n\nVui lòng lồng ghép các yếu tố này vào gợi ý."
        
        base_prompt = ""
        if suggest_type == "char":
            base_prompt = t("prompts.suggest_char_user", title=title, genre=genre, num_main_chars=num_main_chars, num_sub_chars=num_sub_chars)
            logger_msg = "character settings"
        elif suggest_type == "world":
            base_prompt = t("prompts.suggest_world_user", title=title, genre=genre)
            logger_msg = "world settings"
        elif suggest_type == "plot":
            base_prompt = t("prompts.suggest_plot_user", 
                            title=title, 
                            genre=genre, 
                            character_setting=character_setting, 
                            world_setting=world_setting)
            logger_msg = "plot ideas"
        else:
            return "", "Unknown suggestion type"

        if custom_prompt.strip():
            user_prompt = f"{base_prompt}\n\nYêu cầu bổ sung của tác giả:\n{custom_prompt}"
        else:
            user_prompt = base_prompt
            
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        logger.info(f"Start generating {logger_msg} suggestions for: {title}")
        success, content = self.api_client.generate_for_simple(messages, use_cache=False)
        
        if not success:
            logger.error(f"Suggestion generation failed: {content}")
            return "", content
        
        logger.info(f"Suggestion generation success ({logger_msg})")
        return content, t("generator.suggest_success")
    
    def generate_chapter(
        self,
        chapter_num: int,
        chapter_title: str,
        chapter_desc: str,
        novel_title: str,
        character_setting: str,
        world_setting: str,
        plot_idea: str,
        genre: str = "",
        sub_genres: List[str] = None,
        previous_content: str = "",
        context_summary: str = "",
        custom_prompt: str = "",
        use_reflection: bool = False
    ) -> Tuple[str, str]:
        """
        Tạo một chương đơn lẻ

        Args (Tham số):
            chapter_num: Số chương
            chapter_title: Tiêu đề chương
            chapter_desc: Mô tả chương
            novel_title: Tiêu đề tiểu thuyết
            character_setting: Thiết lập nhân vật
            world_setting: Thiết lập thế giới quan
            plot_idea: Cốt truyện chính
            genre: Thể loại truyện
            previous_content: Nội dung phần trước (dùng cho tính liền mạch)
            context_summary: Tóm tắt ngữ cảnh (dùng để tăng cường Context)

        Returns (Trả về):
            (Nội dung chương, Thông báo lỗi hoặc tin báo thành công)
        """
        style_desc = self._build_style_description()
        
        if genre:
            genre_desc = GenreManager.get_genre_description(genre)
            if genre_desc:
                style_desc += f"\n\nHướng dẫn viết riêng cho thể loại {genre}: {genre_desc}"
                
        if sub_genres:
            sub_genre_details = []
            for sg in sub_genres:
                desc = SubGenreManager.get_sub_genre_description(sg)
                if desc:
                    sub_genre_details.append(f"- {sg}: {desc}")
                else:
                    sub_genre_details.append(f"- {sg}")
            style_desc += f"\n\nCác chủ đề con (Tag) bổ sung:\n" + "\n".join(sub_genre_details) + "\n\nHãy kết hợp chặt chẽ các đặc điểm và yếu tố của những chủ đề này vào nội dung chương truyện."
                
        target_words = self.config.generation.chapter_target_words

        # Lời khuyên để xây dựng sự gắn kết
        continuity_prompt = ""
        if previous_content:
            continuity_prompt = t("prompts.continuity_prompt", previous_content=previous_content[-3000:])

        context_prompt = ""
        if context_summary:
            context_prompt = t("prompts.context_prompt", context_summary=context_summary)

        

        prompt = t("prompts.chapter_user",
            novel_title=novel_title, chapter_num=chapter_num,
            chapter_title=chapter_title, chapter_desc=chapter_desc,
            character_setting=character_setting,
            world_setting=world_setting,
            plot_idea=plot_idea,
            style_desc=style_desc,
            target_words=target_words,
            continuity_prompt=continuity_prompt,
            context_prompt=context_prompt
        )

        if custom_prompt:
            prompt += f"\n\n[Yêu cầu bổ sung của tác giả]:\n{custom_prompt}"

        sys_prompt = t("prompts.chapter_system")
        
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt}
        ]

        logger.info(f"Start generating chapter: {chapter_num} - {chapter_title}")
        if context_summary:
            logger.info(f"Using context enhancement, context length: {len(context_summary)}")
        success, content = self.api_client.generate_for_chapter(messages, use_cache=False)

        if not success:
            logger.error(f"Chapter generation failed: {content}")
            return "", content

        if use_reflection:
            logger.info("Applying self-reflection to the generated chapter draft...")
            # Sử dụng content nháp làm nguyên liệu cho lượt tạo reflection mới
            reflection_sys = t("prompts.reflection_system")
            reflection_prompt = t("prompts.reflection_user", chapter_req=prompt, draft_content=content, target_words=target_words)
            reflection_messages = [
                {"role": "system", "content": reflection_sys},
                {"role": "user", "content": reflection_prompt}
            ]
            success, final_content = self.api_client.generate_for_chapter(reflection_messages, use_cache=False)
            if not success:
                logger.error(f"Reflection generation failed: {final_content}. Falling back to draft content.")
            else:
                logger.info("Reflection generation success.")
                content = final_content

        logger.info(f"Chapter generation success: {chapter_num}")
        logger.info(f"Chapter content length: {len(content)}")
        return content, t("generator.gen_success")
    
    def generate_chapter_stream(
        self,
        chapter_num: int,
        chapter_title: str,
        chapter_desc: str,
        novel_title: str,
        character_setting: str,
        world_setting: str,
        plot_idea: str,
        genre: str = "",
        sub_genres: List[str] = None,
        previous_content: str = "",
        context_summary: str = "",
        custom_prompt: str = "",
        use_reflection: bool = False
    ):
        """
        Tạo một chương đơn lẻ bằng streaming

        Yields:
            (Chỉ báo thành công, Chunk văn bản / Thông báo lỗi)
        """
        style_desc = self._build_style_description()
        
        if genre:
            genre_desc = GenreManager.get_genre_description(genre)
            if genre_desc:
                style_desc += f"\n\nHướng dẫn viết riêng cho thể loại {genre}: {genre_desc}"
                
        if sub_genres:
            sub_genre_details = []
            for sg in sub_genres:
                desc = SubGenreManager.get_sub_genre_description(sg)
                if desc:
                    sub_genre_details.append(f"- {sg}: {desc}")
                else:
                    sub_genre_details.append(f"- {sg}")
            style_desc += f"\n\nCác chủ đề con (Tag) bổ sung:\n" + "\n".join(sub_genre_details) + "\n\nHãy kết hợp chặt chẽ các đặc điểm và yếu tố của những chủ đề này vào nội dung chương truyện."
                
        target_words = self.config.generation.chapter_target_words

        continuity_prompt = ""
        if previous_content:
            continuity_prompt = t("prompts.continuity_prompt", previous_content=previous_content[-3000:])

        context_prompt = ""
        if context_summary:
            context_prompt = t("prompts.context_prompt", context_summary=context_summary)

        prompt = t("prompts.chapter_user",
            novel_title=novel_title, chapter_num=chapter_num,
            chapter_title=chapter_title, chapter_desc=chapter_desc,
            character_setting=character_setting,
            world_setting=world_setting,
            plot_idea=plot_idea,
            style_desc=style_desc,
            target_words=target_words,
            continuity_prompt=continuity_prompt,
            context_prompt=context_prompt
        )

        if custom_prompt:
            prompt += f"\n\n[Yêu cầu bổ sung của tác giả]:\n{custom_prompt}"

        messages = [
            {"role": "system", "content": t("prompts.chapter_system")},
            {"role": "user", "content": prompt}
        ]

        logger.info(f"Start generating chapter (stream): {chapter_num} - {chapter_title}")
        if context_summary:
            logger.info(f"Using context enhancement, context length: {len(context_summary)}")
            
        if not use_reflection:
            for success, chunk in self.api_client.generate_stream(messages=messages):
                yield success, chunk
        else:
            logger.info("Generating draft for reflection in streaming mode...")
            success, draft_content = self.api_client.generate(messages, use_cache=False)
            
            if not success:
                logger.error(f"Draft generation failed: {draft_content}")
                yield False, draft_content
                return
            
            logger.info("Draft generated. Applying self-reflection stream...")
            reflection_sys = t("prompts.reflection_system")
            reflection_prompt = t("prompts.reflection_user", chapter_req=prompt, draft_content=draft_content, target_words=target_words)
            reflection_messages = [
                {"role": "system", "content": reflection_sys},
                {"role": "user", "content": reflection_prompt}
            ]
            
            for success, chunk in self.api_client.generate_stream(messages=reflection_messages):
                yield success, chunk
            
    def rewrite_paragraph(
        self,
        text: str,
        style_template: str = "",
        use_reflection: bool = False
    ) -> Tuple[str, str]:
        """
        Viết lại đoạn văn (có cơ chế thử lại)

        Returns (Trả về):
            (Văn bản sau khi viết lại, Thông báo lỗi hoặc tin báo thành công)
        """
        if not text or not text.strip():
            return "", t("generator.text_empty")

        if len(text) > 20000:
            return "", t("generator.text_too_long_rewrite")

        templates = get_preset_templates()
        default_key = t("templates.name_default")
        style = style_template or templates.get(default_key, t("templates.default"))

        prompt = t("prompts.rewrite_user", style=style, text=text)

        messages = [
            {"role": "system", "content": t("prompts.rewrite_system")},
            {"role": "user", "content": prompt}
        ]

        logger.info(f"Start rewriting, original length: {len(text)}, style: {style[:50]}")

        # Cơ chế thử lại: thử lại khi nội dung quá ngắn
        max_retries = 3
        content = ""

        for attempt in range(max_retries):
            logger.debug(f"Rewrite attempt {attempt + 1}/{max_retries}")
            success, content = self.api_client.generate(messages, use_cache=False)

            if not success:
                logger.error(f"Rewrite failed (attempt {attempt + 1}/{max_retries}): {content}")
                if attempt < max_retries - 1:
                    continue
                return "", content

            # Xác minh nội dung nghiêm ngặt
            if not content or not content.strip():
                logger.error(f"Rewrite returned empty (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    continue
                return "", t("generator.api_empty_content")

            # Lọc thông báo trạng thái (danh sách mở rộng)
            status_messages = [
                t("generator.continue_success"), t("generator.rewrite_success"), t("generator.polish_success"), t("generator.gen_success"), "done", "success",
                "OK", "ok", "Success", "SUCCESS",
                
                
            ]
            content_stripped = content.strip()
            if content_stripped in status_messages:
                logger.error(f"API returned status msg instead of content: {content} (attempt {attempt + 1}/{max_retries})")
                logger.error(f"Content length: {len(content)}, content: {content}")
                if attempt < max_retries - 1:
                    continue
                return "", t("generator.api_status_msg")

            # Kiểm tra độ dài nội dung (nghiêm ngặt hơn)
            if len(content_stripped) < 50:
                logger.warning(f"Rewrite content too short: {len(content)} (attempt {attempt + 1}/{max_retries})")
                logger.warning(f"Content: {content}")
                if attempt < max_retries - 1:
                    continue
                return "", t("generator.rewrite_too_short", length=len(content))

            # Xác minh nội dung đã được thông qua
            logger.info(f"Rewrite done, content length: {len(content)}, attempts: {attempt + 1}")
            logger.debug(f"Content first 200: {content[:200]}")
            
            if use_reflection:
                logger.info("Applying self-reflection to rewritten paragraph draft...")
                reflection_sys = t("prompts.reflection_system")
                reflection_prompt = t("prompts.reflection_user", chapter_req=prompt, draft_content=content, target_words=len(content))
                reflection_messages = [
                    {"role": "system", "content": reflection_sys},
                    {"role": "user", "content": reflection_prompt}
                ]
                success, final_content = self.api_client.generate(reflection_messages, use_cache=False)
                if success:
                    content = final_content
            
            return content, t("generator.rewrite_success")

        # Tất cả các lần thử lại đều thất bại
        logger.error(f"Rewrite failed after {max_retries} attempts")
        return "", t("generator.rewrite_failed_retries", max=max_retries)
    
    def generate_summary(self, text: str, max_length: int = 200) -> Tuple[str, str]:
        """
        Tạo tóm tắt văn bản
        
        Returns (Trả về):
            (Tóm tắt, Thông báo lỗi hoặc tin báo thành công)
        """
        if not text or not text.strip():
            return "", t("generator.text_empty")
        
        prompt = t("prompts.summary_user", max_length=max_length, text=text)
        
        messages = [
            {"role": "system", "content": t("prompts.summary_system")},
            {"role": "user", "content": prompt}
        ]
        
        logger.info("Start generating summary")
        success, content = self.api_client.generate(messages, use_cache=True)
        
        if not success:
            return "", content
        
        logger.info("Summary generation success")
        return content.strip(), t("generator.summary_success")
    
    def polish_text(
        self,
        text: str,
        polish_type: str = "general",
        custom_requirements: str = "",
        use_reflection: bool = False
    ) -> Tuple[str, str]:
        """
        Văn bản tiếng Ba Lan (với cơ chế thử lại)

        Args (Tham số):
            text: Văn bản cần trau chuốt
            polish_type: Loại trau chuốt
            custom_requirements: Yêu cầu tùy chỉnh

        Returns (Trả về):
            (Văn bản sau khi trau chuốt, Thông báo lỗi hoặc tin báo thành công)
        """
        if not text or not text.strip():
            return "", t("generator.text_empty")

        if len(text) > 10000:
            return "", t("generator.text_too_long_polish")

        # Từ nhắc tương ứng với Loại trau dồi
        polish_prompts = {
            "general": t("prompts.polish_general"),
            "find_errors": t("prompts.polish_find_errors"),
            "suggest_improvements": t("prompts.polish_suggest"),
            "direct_modify": t("prompts.polish_direct"),
            "remove_ai_flavor": t("prompts.polish_remove_ai"),
            "enhance_details": t("prompts.polish_enhance"),
            "optimize_dialogue": t("prompts.polish_dialogue"),
            "improve_pacing": t("prompts.polish_pacing"),
        }

        prompt = polish_prompts.get(polish_type, polish_prompts["general"])

        if custom_requirements:
            prompt += t("prompts.polish_extra_req", custom_requirements=custom_requirements)

        prompt += t("prompts.polish_output_only", text=text)

        messages = [
            {"role": "system", "content": t("prompts.polish_system")},
            {"role": "user", "content": prompt}
        ]

        logger.info(f"Start polishing, type: {polish_type}, length: {len(text)}")

        # Cơ chế thử lại: thử lại khi nội dung quá ngắn
        max_retries = 3
        content = ""

        for attempt in range(max_retries):
            logger.debug(f"Polish attempt {attempt + 1}/{max_retries}")
            success, content = self.api_client.generate(messages, use_cache=False)

            if not success:
                logger.error(f"Polish failed (attempt {attempt + 1}/{max_retries}): {content}")
                if attempt < max_retries - 1:
                    continue
                return "", content

            # Xác minh nội dung nghiêm ngặt
            if not content or not content.strip():
                logger.error(f"Polish returned empty (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    continue
                return "", t("generator.api_empty_content")

            # Lọc thông báo trạng thái (danh sách mở rộng)
            status_messages = [
                t("generator.continue_success"), t("generator.rewrite_success"), t("generator.polish_success"), t("generator.gen_success"), "done", "success",
                "OK", "ok", "Success", "SUCCESS",
                
                
            ]
            content_stripped = content.strip()
            if content_stripped in status_messages:
                logger.error(f"API returned status msg: {content} (attempt {attempt + 1}/{max_retries})")
                logger.error(f"Content length: {len(content)}, content: {content}")
                if attempt < max_retries - 1:
                    continue
                return "", t("generator.api_status_msg")

            # Kiểm tra độ dài nội dung (nghiêm ngặt hơn)
            if len(content_stripped) < 50:
                logger.warning(f"Polish content too short: {len(content)} (attempt {attempt + 1}/{max_retries})")
                logger.warning(f"Content: {content}")
                if attempt < max_retries - 1:
                    continue
                return "", t("generator.polish_too_short", length=len(content))

            # Xác minh nội dung đã được thông qua
            logger.info(f"Polish done, content length: {len(content)}, attempts: {attempt + 1}")
            logger.debug(f"Content first 200: {content[:200]}")
            
            if use_reflection:
                logger.info("Applying self-reflection to polished paragraph draft...")
                reflection_sys = t("prompts.reflection_system")
                reflection_prompt = t("prompts.reflection_user", chapter_req=prompt, draft_content=content, target_words=len(content))
                reflection_messages = [
                    {"role": "system", "content": reflection_sys},
                    {"role": "user", "content": reflection_prompt}
                ]
                success, final_content = self.api_client.generate(reflection_messages, use_cache=False)
                if success:
                    content = final_content
            
            return content, t("generator.polish_success")

        # Tất cả các lần thử lại đều thất bại
        logger.error(f"Polish failed after {max_retries} attempts")
        return "", t("generator.polish_failed_retries", max=max_retries)

    def polish_and_suggest(
        self,
        text: str,
        custom_requirements: str = "",
        use_reflection: bool = False
    ) -> Tuple[str, str, str]:
        """
        Trau chuốt văn bản và đưa ra đề xuất

        Returns (Trả về):
            (Văn bản sau khi trau chuốt, Đề xuất sửa đổi, Thông báo lỗi hoặc tin báo thành công)
        """
        if not text or not text.strip():
            return "", "", t("generator.text_empty")

        if len(text) > 10000:
            return "", "", t("generator.text_too_long_polish")

        extra_req = t("prompts.polish_extra_req", custom_requirements=custom_requirements) if custom_requirements else ""
        prompt = t("prompts.polish_suggest_user", text=text, extra_req=extra_req)

        messages = [
            {"role": "system", "content": t("prompts.polish_suggest_system")},
            {"role": "user", "content": prompt}
        ]

        logger.info("Start polish and suggest")
        success, content = self.api_client.generate(messages, use_cache=False)

        if not success:
            logger.error(f"Polish failed: {content}")
            return "", "", content

        if use_reflection:
            logger.info("Applying self-reflection to polish and suggest paragraph draft...")
            reflection_sys = t("prompts.reflection_system")
            reflection_prompt = t("prompts.reflection_user", chapter_req=prompt, draft_content=content, target_words=len(content))
            reflection_messages = [
                {"role": "system", "content": reflection_sys},
                {"role": "user", "content": reflection_prompt}
            ]
            success, final_content = self.api_client.generate(reflection_messages, use_cache=False)
            if success:
                content = final_content

        # Thêm xác minh nội dung
        if len(content) < 10:
            logger.warning(f"Polish content too short: {len(content)}, content: {content}")
            logger.warning("API may have returned status instead of content")

        # Phân tích nội dung trả về
        import re
        errors = ""
        suggestions = ""
        polished = ""

        # Cố gắng phân tích đầu ra có cấu trúc
        found_errors_h = t("prompts.found_errors_header")
        suggestions_h = t("prompts.suggestions_header")
        polished_h = t("prompts.polished_text_header")

        if f"【{found_errors_h}】" in content:
            parts = content.split("【")
            for part in parts:
                if part.startswith(f"{found_errors_h}】"):
                    errors = part.replace(f"{found_errors_h}】", "").strip()
                elif part.startswith(f"{suggestions_h}】"):
                    suggestions = part.replace(f"{suggestions_h}】", "").strip()
                elif part.startswith(f"{polished_h}】"):
                    polished = part.replace(f"{polished_h}】", "").strip()
        else:
            # Nếu đầu ra không được định dạng, toàn bộ nội dung sẽ được coi là kết quả tinh tế
            polished = content.strip()
            suggestions = t("prompts.ai_no_format")

        logger.info(f"Polish done, polished length: {len(polished)}")
        return polished, suggestions, t("generator.polish_success")

    def continue_writing(
        self,
        existing_text: str,
        novel_title: str,
        character_setting: str,
        world_setting: str,
        plot_idea: str,
        genre: str = "",
        sub_genres: List[str] = None,
        target_words: int = 2500,
        continue_count: int = 1
    ) -> Tuple[str, str]:
        """
        Viết tiếp nội dung tiểu thuyết (có cơ chế thử lại)

        Args (Tham số):
            existing_text: Văn bản tiểu thuyết hiện có
            novel_title: Tiêu đề tiểu thuyết
            character_setting: Thiết lập nhân vật
            world_setting: Thiết lập thế giới quan
            plot_idea: Thiết lập cốt truyện
            genre: Thể loại truyện
            sub_genres: Các chủ đề con (Tag)
            target_words: Số chữ mục tiêu
            continue_count: Số chương cần viết tiếp

        Returns (Trả về):
            (Nội dung viết tiếp, Thông báo lỗi hoặc tin báo thành công)
        """
        if not existing_text or not existing_text.strip():
            return "", t("generator.existing_text_empty")

        style_desc = self._build_style_description()

        # Enrichment thể loại và chủ đề con
        if genre:
            genre_desc = GenreManager.get_genre_description(genre)
            if genre_desc:
                style_desc += f"\n\nHướng dẫn viết riêng cho thể loại {genre}: {genre_desc}"

        if sub_genres:
            sub_genre_details = []
            for sg in sub_genres:
                desc = SubGenreManager.get_sub_genre_description(sg)
                if desc:
                    sub_genre_details.append(f"- {sg}: {desc}")
                else:
                    sub_genre_details.append(f"- {sg}")
            style_desc += f"\n\nCác chủ đề con (Tag) bổ sung:\n" + "\n".join(sub_genre_details) + "\n\nHãy kết hợp chặt chẽ các đặc điểm và yếu tố của những chủ đề này vào nội dung viết tiếp."

        # Lấy phần cuối cùng của văn bản hiện có làm ngữ cảnh
        previous_content = existing_text[-1500:] if len(existing_text) > 1500 else existing_text

        prompt = t("prompts.continue_user",
            novel_title=novel_title,
            character_setting=character_setting,
            world_setting=world_setting,
            plot_idea=plot_idea,
            style_desc=style_desc,
            previous_content=previous_content,
            target_words=target_words
        )

        messages = [
            {"role": "system", "content": t("prompts.continue_system")},
            {"role": "user", "content": prompt}
        ]

        logger.info(f"Start continue writing: {novel_title}, existing: {len(existing_text)}, target: {target_words}")

        # Cơ chế thử lại
        max_retries = 3
        content = ""

        for attempt in range(max_retries):
            logger.debug(f"Continue attempt {attempt + 1}/{max_retries}")
            success, content = self.api_client.generate(messages, use_cache=False)

            if not success:
                logger.error(f"Continue failed (attempt {attempt + 1}/{max_retries}): {content}")
                if attempt < max_retries - 1:
                    continue
                return "", content

            if not content or not content.strip():
                logger.error(f"Continue returned empty (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    continue
                return "", t("generator.api_empty_content")

            status_messages = [
                t("generator.continue_success"), t("generator.rewrite_success"), t("generator.polish_success"), t("generator.gen_success"), "done", "success",
                "OK", "ok", "Success", "SUCCESS",
                
                
            ]
            content_stripped = content.strip()
            if content_stripped in status_messages:
                logger.error(f"API returned status msg: {content} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    continue
                return "", t("generator.api_status_msg")

            if len(content_stripped) < 100:
                logger.warning(f"Continue content too short: {len(content)} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    continue
                return "", t("generator.continue_too_short", length=len(content))

            logger.info(f"Continue success, chars: {len(content)}, attempts: {attempt + 1}")
            return content, t("generator.continue_success")

        logger.error(f"Continue failed after {max_retries} attempts")
        return "", t("generator.continue_failed_retries", max=max_retries)

    def continue_writing_stream(
        self,
        existing_text: str,
        novel_title: str,
        character_setting: str,
        world_setting: str,
        plot_idea: str,
        genre: str = "",
        sub_genres: List[str] = None,
        target_words: int = 2500,
        continue_count: int = 1
    ):
        """
        Tiếp tục tiểu thuyết dưới dạng stream
        Yields:
            (Success flag, Chunk or error message)
        """
        if not existing_text or not existing_text.strip():
            yield False, t("generator.existing_text_empty")
            return

        style_desc = self._build_style_description()

        # Enrichment thể loại và chủ đề con
        if genre:
            genre_desc = GenreManager.get_genre_description(genre)
            if genre_desc:
                style_desc += f"\n\nHướng dẫn viết riêng cho thể loại {genre}: {genre_desc}"

        if sub_genres:
            sub_genre_details = []
            for sg in sub_genres:
                desc = SubGenreManager.get_sub_genre_description(sg)
                if desc:
                    sub_genre_details.append(f"- {sg}: {desc}")
                else:
                    sub_genre_details.append(f"- {sg}")
            style_desc += f"\n\nCác chủ đề con (Tag) bổ sung:\n" + "\n".join(sub_genre_details) + "\n\nHãy kết hợp chặt chẽ các đặc điểm và yếu tố của những chủ đề này vào nội dung viết tiếp."

        previous_content = existing_text[-1500:] if len(existing_text) > 1500 else existing_text

        prompt = t("prompts.continue_user",
            novel_title=novel_title,
            character_setting=character_setting,
            world_setting=world_setting,
            plot_idea=plot_idea,
            style_desc=style_desc,
            previous_content=previous_content,
            target_words=target_words
        )

        messages = [
            {"role": "system", "content": t("prompts.continue_system")},
            {"role": "user", "content": prompt}
        ]

        logger.info(f"Start continue writing (stream): {novel_title}, existing: {len(existing_text)}")
        for success, chunk in self.api_client.generate_stream(messages=messages):
            yield success, chunk

    def _build_style_description(self) -> str:
        """Mô tả phong cách xây dựng"""
        from services.style_manager import StyleManager
        gen = self.config.generation
        style_name = gen.writing_style
        style_desc = StyleManager.get_style_description(style_name)
        
        full_style = style_name
        if style_desc:
            full_style += f" ({style_desc})"
            
        return t("prompts.style_description",
            writing_style=full_style,
            writing_tone=gen.writing_tone,
            character_development=gen.character_development,
            plot_complexity=gen.plot_complexity
        )


def get_generator() -> NovelGenerator:
    """Nhận phiên bản trình tạo mới"""
    global _GENERATOR
    try:
        _GENERATOR
    except NameError:
        _GENERATOR = NovelGenerator()
    return _GENERATOR


# ===================== Quản lý bộ đệm =======================

def save_generation_cache(project_id: str, cache_data: Dict) -> Tuple[bool, str]:
    """
    Lưu bộ nhớ cache khởi tạo vào SQLite

    Args (Tham số):
        project_id: ID dự án
        cache_data: Từ điển dữ liệu cache

    Returns (Trả về):
        (Có thành công không, Thông báo)
    """
    if not project_id or not project_id.strip():
        return False, t("generator.cache_id_empty")

    if not cache_data:
        return False, t("generator.cache_data_empty")

    try:
        conn = get_db()
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO generation_cache (project_id, data, updated_at) VALUES (?, ?, ?)",
            (project_id, json.dumps(cache_data, ensure_ascii=False), now)
        )
        conn.commit()
        logger.info(f"Cache saved to database: {project_id}")
        return True, t("generator.cache_save_success")
    except Exception as e:
        logger.error(f"Cache save failed: {e}")
        return False, t("generator.cache_save_failed", error=str(e))


def load_generation_cache(project_id: str) -> Tuple[Optional[Dict], str]:
    """
    Tải bộ nhớ cache khởi tạo từ SQLite

    Args (Tham số):
        project_id: ID dự án

    Returns (Trả về):
        (Dữ liệu cache, Thông báo)
    """
    if not project_id or not project_id.strip():
        return None, t("generator.cache_id_empty")

    try:
        conn = get_db()
        row = conn.execute(
            "SELECT data FROM generation_cache WHERE project_id = ?", (project_id,)
        ).fetchone()

        if not row:
            return None, t("generator.cache_not_found")

        cache_data = json.loads(row["data"])
        logger.info(f"Cache loaded from core.database: {project_id}")
        return cache_data, t("generator.cache_load_success")
    except Exception as e:
        logger.error(f"Cache load failed: {e}")
        return None, t("generator.cache_load_failed", error=str(e))


def clear_generation_cache(project_id: str) -> Tuple[bool, str]:
    """
    Xóa bộ nhớ cache khởi tạo

    Args (Tham số):
        project_id: ID dự án

    Returns (Trả về):
        (Có thành công không, Thông báo)
    """
    if not project_id or not project_id.strip():
        return False, t("generator.cache_id_empty")

    try:
        conn = get_db()
        cursor = conn.execute(
            "DELETE FROM generation_cache WHERE project_id = ?", (project_id,)
        )
        conn.commit()

        if cursor.rowcount == 0:
            return False, t("generator.cache_not_found")

        logger.info(f"Cache cleared: {project_id}")
        return True, t("generator.cache_clear_success")
    except Exception as e:
        logger.error(f"Cache clear failed: {e}")
        return False, t("generator.cache_clear_failed", error=str(e))


def list_generation_caches() -> List[Dict]:
    """
    Liệt kê tất cả bộ nhớ cache khởi tạo

    Returns (Trả về):
        Danh sách thông tin bộ đệm
    """
    caches = []
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT project_id, data, LENGTH(data) as size, updated_at FROM generation_cache"
        ).fetchall()

        for row in rows:
            try:
                cache_data = json.loads(row["data"])
                caches.append({
                    "project_id": row["project_id"],
                    "title": cache_data.get("title", t("generator.unknown_title")),
                    "current_chapter": cache_data.get("current_chapter", 0),
                    "total_chapters": cache_data.get("total_chapters", 0),
                    "status": cache_data.get("generation_status", "unknown"),
                    "timestamp": cache_data.get("timestamp", ""),
                    "size": row["size"]
                })
            except Exception as e:
                logger.error(f"Read cache failed {row['project_id']}: {e}")
    except Exception as e:
        logger.error(f"List generation caches failed: {e}")

    return caches


def get_cache_size() -> int:
    """
    Lấy tổng kích thước cache (byte)

    Returns (Trả về):
        Tổng kích thước bộ đệm
    """
    try:
        conn = get_db()
        row = conn.execute("SELECT COALESCE(SUM(LENGTH(data)), 0) as total FROM generation_cache").fetchone()
        return row["total"] if row else 0
    except Exception:
        return 0


# ===================== Quản lý tóm tắt chương ======================

def generate_chapter_summary(chapter_content: str, chapter_title: str) -> Tuple[str, str]:
    """
    Tạo tóm tắt chương

    Args (Tham số):
        chapter_content: Nội dung chương
        chapter_title: Tiêu đề chương

    Returns (Trả về):
        (Nội dung tóm tắt, Thông báo lỗi hoặc tin báo thành công)
    """
    if not chapter_content or not chapter_content.strip():
        return "", t("generator.summary_content_empty")

    try:
        api_client = get_api_client()
        messages = [
            {"role": "system", "content": t("prompts.chapter_summary_system")},
            {"role": "user", "content": t("prompts.chapter_summary_user", chapter_title=chapter_title, chapter_content=chapter_content[:3000])}
        ]
        success, summary = api_client.generate(messages, use_cache=False)
        if success and summary:
            return summary.strip(), t("generator.summary_gen_success")
        else:
            return "", summary or t("generator.summary_gen_failed")
    except Exception as e:
        logger.error(f"Generate chapter summary failed: {e}")
        return "", t("generator.summary_gen_error", error=str(e))


def save_chapter_summary(project_id: str, chapter_num: int, summary: str) -> Tuple[bool, str]:
    """
    Lưu tóm tắt chương vào SQLite

    Args (Tham số):
        project_id: ID dự án
        chapter_num: Số chương
        summary: Nội dung tóm tắt

    Returns (Trả về):
        (Có thành công không, Thông báo)
    """
    if not project_id or not project_id.strip():
        return False, t("generator.cache_id_empty")

    if not summary or not summary.strip():
        return False, t("generator.summary_empty")

    try:
        conn = get_db()
        now = datetime.now().isoformat()
        conn.execute("""
            INSERT OR REPLACE INTO chapter_summaries 
            (project_id, chapter_num, summary, generated_at)
            VALUES (?, ?, ?, ?)
        """, (project_id, chapter_num, summary, now))
        conn.commit()
        logger.info(f"Chapter summary saved to database: {project_id}/{chapter_num}")
        return True, t("generator.summary_save_success")
    except Exception as e:
        logger.error(f"Save chapter summary failed: {e}")
        return False, t("generator.summary_save_failed", error=str(e))


def load_chapter_summaries(project_id: str) -> Tuple[List[Dict], str]:
    """
    Tải tất cả tóm tắt chương từ SQLite

    Args (Tham số):
        project_id: ID dự án

    Returns (Trả về):
        (Danh sách tóm tắt, Thông báo)
    """
    if not project_id or not project_id.strip():
        return [], t("generator.cache_id_empty")

    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT chapter_num, summary, generated_at 
            FROM chapter_summaries 
            WHERE project_id = ? 
            ORDER BY chapter_num
        """, (project_id,)).fetchall()

        if not rows:
            return [], t("generator.summary_dir_not_found")

        summaries = [{"chapter_num": row["chapter_num"], "summary": row["summary"], "generated_at": row["generated_at"]} for row in rows]
        logger.info(f"Loaded {len(summaries)} chapter summaries from core.database")
        return summaries, t("generator.summary_load_done", count=len(summaries))
    except Exception as e:
        logger.error(f"Load chapter summaries failed: {e}")
        return [], t("generator.summary_load_failed", error=str(e))


def build_context_from_summaries(summaries: List[Dict], max_context_length: int = 1000) -> str:
    """
    Xây dựng bối cảnh từ tóm tắt

    Args (Tham số):
        summaries: Danh sách tóm tắt
        max_context_length: Độ dài bối cảnh tối đa (số ký tự)

    Returns (Trả về):
        Chuỗi bối cảnh
    """
    if not summaries:
        return ""

    sorted_summaries = sorted(summaries, key=lambda x: x.get('chapter_num', 0), reverse=True)

    context_parts = []
    current_length = 0

    for summary_data in sorted_summaries:
        chapter_num = summary_data.get('chapter_num', 0)
        summary = summary_data.get('summary', '')

        if not summary:
            continue

        part = t("prompts.chapter_context_line", chapter_num=chapter_num, summary=summary)
        if current_length + len(part) > max_context_length:
            break

        context_parts.append(part)
        current_length += len(part)

    context_parts.reverse()

    if context_parts:
        context = t("prompts.context_header") + "\n".join(context_parts)
        logger.info(f"Context built, {len(context_parts)} summaries, total length {len(context)}")
        return context
    else:
        logger.warning("No summaries available to build context")
        return ""


def clear_chapter_summaries(project_id: str) -> Tuple[bool, str]:
    """
    Xóa tóm tắt chương của dự án

    Args (Tham số):
        project_id: ID dự án

    Returns (Trả về):
        (Có thành công không, Thông báo)
    """
    if not project_id or not project_id.strip():
        return False, t("generator.cache_id_empty")

    try:
        conn = get_db()
        cursor = conn.execute(
            "DELETE FROM chapter_summaries WHERE project_id = ?", (project_id,)
        )
        conn.commit()

        if cursor.rowcount == 0:
            return False, t("generator.summary_dir_not_found")

        logger.info(f"Chapter summaries cleared: {project_id}")
        return True, t("generator.summary_clear_success")
    except Exception as e:
        logger.error(f"Clear chapter summaries failed: {e}")
        return False, t("generator.summary_clear_failed", error=str(e))


def list_summary_caches() -> List[Dict]:
    """
    Liệt kê tất cả cache tóm tắt

    Returns (Trả về):
        Danh sách thông tin bộ đệm
    """
    caches = []
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT project_id, COUNT(*) as chapter_count, 
                   SUM(LENGTH(summary)) as total_size
            FROM chapter_summaries 
            GROUP BY project_id
        """).fetchall()

        for row in rows:
            caches.append({
                "project_id": row["project_id"],
                "chapter_count": row["chapter_count"],
                "total_size": row["total_size"],
                "size_kb": round(row["total_size"] / 1024, 2)
            })
    except Exception as e:
        logger.error(f"List summary caches failed: {e}")

    return caches


def get_summary_cache_size() -> int:
    """
    Lấy tổng kích thước cache tóm tắt (byte)

    Returns (Trả về):
        Tổng kích thước bộ đệm
    """
    try:
        conn = get_db()
        row = conn.execute("SELECT COALESCE(SUM(LENGTH(summary)), 0) as total FROM chapter_summaries").fetchone()
        return row["total"] if row else 0
    except Exception:
        return 0
