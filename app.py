"""
AI Novel Generator 4.5 - Ứng dụng chính
Tích hợp hệ thống sinh tiểu thuyết, quản lý dự án, xuất file

Bản quyền © 2026 Công ty TNHH Công nghệ An ninh mạng Huyễn Thành Tân Cương (Công nghệ Huyễn Thành)
Tác giả: Huyễn Thành
"""

import gradio as gr
import logging
import threading
import json
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import os

# Import các module hiện có
from api_client import APIClient, get_api_client, reinit_api_client
from config import get_config, ConfigManager, Backend, GenerationConfig, API_PROVIDERS
from novel_generator import (
    NovelGenerator, NovelProject, Chapter, OutlineParser,
    get_preset_templates, get_generator,
    save_generation_cache, load_generation_cache, clear_generation_cache,
    list_generation_caches, get_cache_size
)
from project_manager import ProjectManager
from config_api import ConfigAPIManager
from exporter import export_to_docx, export_to_txt, export_to_markdown, export_to_html
from genre_manager import GenreManager
from sub_genre_manager import SubGenreManager
from file_parser import parse_novel_file
from locales.i18n import t
from database import get_db
from logger import get_logger

# ==================== Cấu hình Logging ====================

logger = get_logger("app")
logger.info("=" * 60)
logger.info("AI Novel Generator 4.5 - Hệ thống log đã khởi tạo")
logger.info("=" * 60)

# Cấu hình biến môi trường
WEB_HOST = os.getenv("NOVEL_TOOL_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("NOVEL_TOOL_PORT", os.getenv("PORT", "7860")))
WEB_SHARE = os.getenv("NOVEL_TOOL_SHARE", "false").lower() in ("1", "true", "yes")


# ==================== Quản lý trạng thái ứng dụng ====================

class AppState:
    """Quản lý trạng thái ứng dụng"""

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


# Trạng thái ứng dụng toàn cục
app_state = AppState()


# ==================== Hàm tiện ích ====================

def list_project_titles():
    """Lấy danh sách tiêu đề dự án"""
    try:
        projects = ProjectManager.list_projects()
        return [p["title"] for p in projects]
    except Exception:
        return []


# ==================== Giao diện chính ====================

def create_main_ui():
    """Tạo giao diện chính"""

    # Tải CSS tùy chỉnh
    custom_css = ""
    css_path = Path("custom.css")
    if css_path.exists():
        with open(css_path, 'r', encoding='utf-8') as f:
            custom_css = f.read()

    with gr.Blocks(title=t("app.title")) as app:
        # Header
        gr.Markdown(f"""
        <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-bottom: 20px;">
            <h1 style="color: white; margin: 0; font-size: 2.5em;">🚀 {t("app.title")}</h1>
            <h3 style="color: #f0f0f0; margin: 10px 0 0 0;">{t("app.subtitle")}</h3>
        </div>
        """)

        with gr.Tabs():
            # ==================== Tab 1: Sáng tác từ đầu ====================
            with gr.Tab(t("tabs.create")):
                gr.Markdown(f"### {t('create.header')}")

                with gr.Row():
                    with gr.Column(scale=1):
                        genre_choices = GenreManager.get_genre_names()
                        genre_dropdown = gr.Dropdown(
                            choices=genre_choices,
                            value=genre_choices[0] if genre_choices else None,
                            label=t("create.genre_label"),
                            interactive=True
                        )
                        sub_genre_choices = SubGenreManager.get_sub_genre_names()
                        sub_genre_dropdown = gr.Dropdown(
                            choices=sub_genre_choices,
                            label=t("create.sub_genres_label"),
                            multiselect=True,
                            interactive=True
                        )

                    with gr.Column(scale=2):
                        title_input = gr.Textbox(
                            label=t("create.novel_title"),
                            placeholder=t("create.novel_title_default"),
                            interactive=True
                        )
                        suggested_titles_radio = gr.Radio(
                            label=t("create.suggested_titles_radio") if t("create.suggested_titles_radio") != "create.suggested_titles_radio" else "Gợi ý tên truyện",
                            choices=[],
                            visible=False,
                            interactive=True
                        )
                        with gr.Row():
                            suggest_title_btn = gr.Button(t("create.suggest_title_btn"), variant="secondary", size="sm")
                            suggest_title_prompt = gr.Textbox(
                                label=t("create.custom_prompt_label"),
                                placeholder=t("create.custom_prompt_placeholder"),
                                lines=1, interactive=True, scale=3
                            )

                # Thiết lập nhân vật
                with gr.Row():
                    with gr.Column():
                        character_input = gr.Textbox(
                            label=t("create.char_setting"),
                            placeholder=t("create.char_setting_placeholder"),
                            lines=5, interactive=True
                        )
                        with gr.Row():
                            suggest_char_btn = gr.Button(t("create.suggest_btn"), variant="secondary", size="sm")
                            num_main_chars = gr.Number(label=t("create.num_main_chars"), value=2, minimum=1, maximum=10, step=1, scale=1)
                            num_sub_chars = gr.Number(label=t("create.num_sub_chars"), value=3, minimum=0, maximum=20, step=1, scale=1)
                            suggest_char_prompt = gr.Textbox(label=t("create.custom_prompt_label"), placeholder=t("create.custom_prompt_placeholder"), lines=1, interactive=True, scale=2)

                    with gr.Column():
                        world_input = gr.Textbox(
                            label=t("create.world_setting"),
                            placeholder=t("create.world_setting_placeholder"),
                            lines=5, interactive=True
                        )
                        with gr.Row():
                            suggest_world_btn = gr.Button(t("create.suggest_btn"), variant="secondary", size="sm")
                            suggest_world_prompt = gr.Textbox(label=t("create.custom_prompt_label"), placeholder=t("create.custom_prompt_placeholder"), lines=1, interactive=True, scale=3)

                # Ý tưởng cốt truyện
                plot_input = gr.Textbox(
                    label=t("create.plot_idea"),
                    placeholder=t("create.plot_idea_placeholder"),
                    lines=3, interactive=True
                )
                with gr.Row():
                    suggest_plot_btn = gr.Button(t("create.suggest_plot_btn"), variant="secondary", size="sm")
                    suggest_plot_prompt = gr.Textbox(label=t("create.custom_prompt_label"), placeholder=t("create.custom_prompt_placeholder"), lines=1, interactive=True, scale=3)

                # Số chương và tạo dàn ý
                with gr.Row():
                    total_chapters = gr.Number(
                        label=t("create.chapter_count"), value=20, minimum=1, maximum=200, step=1
                    )
                    generate_outline_btn = gr.Button(t("create.gen_outline_btn"), variant="primary", size="lg")

                outline_output = gr.Textbox(label=t("create.outline_display"), lines=15, interactive=True)
                outline_status = gr.Textbox(label=t("create.gen_status"), interactive=False)

                # Tạo toàn bộ tiểu thuyết
                gr.Markdown("---")
                with gr.Row():
                    auto_generate_btn = gr.Button(t("create.start_gen_btn"), variant="primary", size="lg")
                    stop_btn = gr.Button(t("create.pause_gen_btn"), variant="stop", size="lg")

                generation_progress = gr.Textbox(label=t("create.gen_status"), lines=10, interactive=False)

                # --- Sự kiện Tab Sáng tác ---
                def on_suggest_title(genre, sub_genres, custom_prompt):
                    gen = app_state.get_generator()
                    content, msg = gen.suggest_title(genre, sub_genres, custom_prompt)
                    if content:
                        import json
                        import re
                        try:
                            # Tìm array JSON [...] trực tiếp để tránh rác text bao quanh
                            match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', content)
                            if match:
                                data = {"suggestions": json.loads(match.group(0))}
                            else:
                                clean_content = re.sub(r'```(?:json)?\s*', '', content)
                                clean_content = re.sub(r'```\s*', '', clean_content)
                                data = json.loads(clean_content)
                                
                            if "suggestions" in data:
                                choices = [f"{item.get('title', '')} - {item.get('description', '')}" for item in data["suggestions"]]
                                return gr.update(choices=choices, visible=True)
                        except Exception as e:
                            logger.error(f"Failed to parse title JSON: {e}")
                            return gr.update(choices=[content], visible=True)
                    return gr.update(choices=[msg], visible=True)

                def on_title_select(selected):
                    if selected and " - " in selected:
                        return selected.split(" - ", 1)[0]
                    return selected

                def on_suggest_content(suggest_type, title, genre, sub_genres, char_setting, world_setting, custom_prompt, num_main=2, num_sub=3):
                    gen = app_state.get_generator()
                    content, msg = gen.suggest_content(
                        suggest_type, title, genre, sub_genres,
                        char_setting, world_setting, custom_prompt,
                        int(num_main), int(num_sub)
                    )
                    return content if content else msg

                def on_generate_outline(title, genre, sub_genres, num_chapters, char_setting, world_setting, plot_idea):
                    gen = app_state.get_generator()
                    content, msg = gen.generate_outline(
                        title, genre, sub_genres or [],
                        int(num_chapters), char_setting, world_setting, plot_idea
                    )
                    return content, msg

                def on_auto_generate(title, genre, sub_genres, char_setting, world_setting, plot_idea, outline_text, progress=gr.Progress()):
                    """Tự động tạo toàn bộ tiểu thuyết"""
                    gen = app_state.get_generator()

                    chapters, parse_msg = OutlineParser.parse(outline_text)
                    if not chapters:
                        return f"❌ {parse_msg}"

                    project, create_msg = ProjectManager.create_project(
                        title, genre, sub_genres or [],
                        char_setting, world_setting, plot_idea
                    )
                    if not project:
                        return f"❌ {create_msg}"

                    project.chapters = chapters
                    app_state.current_project = project
                    app_state.is_generating = True
                    app_state.stop_requested = False

                    results = [f"📋 Đã phân tích {len(chapters)} chương", f"💾 {create_msg}"]

                    for i, chapter in enumerate(chapters):
                        if app_state.stop_requested:
                            results.append("\n⚠️ Đã dừng sinh!")
                            break

                        results.append(f"\n✍️ Đang sinh Chương {chapter.num}: {chapter.title}...")
                        progress((i + 1) / len(chapters))

                        prev_content = ""
                        if i > 0 and chapters[i-1].content:
                            prev_content = chapters[i-1].content[-2000:]

                        content, msg = gen.generate_chapter(
                            chapter_num=chapter.num, chapter_title=chapter.title,
                            chapter_desc=chapter.desc, novel_title=title,
                            character_setting=char_setting, world_setting=world_setting,
                            plot_idea=plot_idea, genre=genre, sub_genres=sub_genres,
                            previous_content=prev_content
                        )

                        if content:
                            chapter.content = content
                            chapter.word_count = len(content)
                            chapter.generated_at = datetime.now().isoformat()
                            results.append(f"✅ Chương {chapter.num}: {len(content)} từ")
                            ProjectManager.save_project(project)
                        else:
                            results.append(f"❌ Chương {chapter.num}: {msg}")

                    app_state.is_generating = False
                    total_words = sum(ch.word_count for ch in chapters if ch.content)
                    results.append(f"\n🎉 Hoàn thành! Tổng: {total_words} từ")
                    return "\n".join(results)

                def on_stop():
                    app_state.stop_requested = True
                    return "⏸️ Đang dừng..."

                # Bind events
                suggest_title_btn.click(
                    fn=on_suggest_title,
                    inputs=[genre_dropdown, sub_genre_dropdown, suggest_title_prompt],
                    outputs=[suggested_titles_radio]
                )
                suggested_titles_radio.change(
                    fn=on_title_select,
                    inputs=[suggested_titles_radio],
                    outputs=[title_input]
                )
                suggest_char_btn.click(
                    fn=lambda ti, g, sg, cp, nm, ns: on_suggest_content("char", ti, g, sg, "", "", cp, nm, ns),
                    inputs=[title_input, genre_dropdown, sub_genre_dropdown, suggest_char_prompt, num_main_chars, num_sub_chars],
                    outputs=[character_input]
                )
                suggest_world_btn.click(
                    fn=lambda ti, g, sg, cp: on_suggest_content("world", ti, g, sg, "", "", cp),
                    inputs=[title_input, genre_dropdown, sub_genre_dropdown, suggest_world_prompt],
                    outputs=[world_input]
                )
                suggest_plot_btn.click(
                    fn=lambda ti, g, sg, cs, ws, cp: on_suggest_content("plot", ti, g, sg, cs, ws, cp),
                    inputs=[title_input, genre_dropdown, sub_genre_dropdown, character_input, world_input, suggest_plot_prompt],
                    outputs=[plot_input]
                )
                generate_outline_btn.click(
                    fn=on_generate_outline,
                    inputs=[title_input, genre_dropdown, sub_genre_dropdown, total_chapters, character_input, world_input, plot_input],
                    outputs=[outline_output, outline_status]
                )
                auto_generate_btn.click(
                    fn=on_auto_generate,
                    inputs=[title_input, genre_dropdown, sub_genre_dropdown, character_input, world_input, plot_input, outline_output],
                    outputs=[generation_progress]
                )
                stop_btn.click(fn=on_stop, outputs=[generation_progress])

            # ==================== Tab 2: Viết tiếp dự án ====================
            with gr.Tab(t("tabs.continue_tab")):
                gr.Markdown(f"### {t('continue_tab.header')}")

                project_choices = list_project_titles()
                continue_project_selector = gr.Dropdown(
                    choices=project_choices,
                    label=t("continue_tab.select_project"),
                    interactive=True
                )
                refresh_continue_btn = gr.Button(t("continue_tab.load_btn"), size="sm")
                continue_project_info = gr.Markdown(t("continue_tab.no_project_loaded"))

                gr.Markdown("---")
                with gr.Row():
                    continue_chapter_num = gr.Number(label="Chương số", value=1, minimum=1)
                    continue_chapter_title = gr.Textbox(label="Tiêu đề chương", placeholder="Nhập tiêu đề chương...", scale=2)

                continue_chapter_desc = gr.Textbox(
                    label=t("continue_tab.outline_label"),
                    lines=5, placeholder="Nhập mô tả nội dung chương..."
                )

                with gr.Row():
                    continue_target_words = gr.Number(label=t("rewrite.target_words"), value=3000, minimum=100, maximum=50000, step=100)
                    continue_custom_prompt = gr.Textbox(label=t("create.custom_prompt_label"), placeholder=t("create.custom_prompt_placeholder"), scale=2)

                continue_generate_btn = gr.Button(t("continue_tab.continue_gen_btn"), variant="primary", size="lg")
                continue_status = gr.Textbox(label=t("continue_tab.gen_status"), interactive=False)
                continue_output = gr.Textbox(label=t("continue_tab.novel_label"), lines=20, interactive=True)

                # Sự kiện
                def on_refresh_continue():
                    titles = list_project_titles()
                    return gr.update(choices=titles, value=None)

                def on_continue_project_select(project_title):
                    if not project_title:
                        return t("continue_tab.no_project_loaded"), 1
                    try:
                        project_data = ProjectManager.get_project_by_title(project_title)
                        if not project_data:
                            return f"❌ {t('continue_tab.project_not_found')}", 1

                        project_id = project_data.get("id")
                        project, msg = ProjectManager.load_project(project_id)
                        if project:
                            app_state.current_project = project
                            completed = project.get_completed_count()
                            next_ch = completed + 1
                            info = t("continue_tab.info_template").format(
                                title=project.title,
                                genre=project.genre,
                                completed=completed,
                                total=len(project.chapters),
                                words=project.get_total_words()
                            ) if isinstance(t("continue_tab.info_template"), str) and '{' in t("continue_tab.info_template") else f"""### 📖 {project.title}
**Thể loại**: {project.genre}
**Hoàn thành**: {completed}/{len(project.chapters)} chương
**Tổng số từ**: {project.get_total_words()}
💡 Chương tiếp theo: {next_ch}"""
                            return info, next_ch
                        return f"❌ {msg}", 1
                    except Exception as e:
                        return f"❌ {str(e)}", 1

                def on_continue_generate(project_title, ch_num, ch_title, ch_desc, target_words, custom_prompt):
                    if not app_state.current_project:
                        return f"❌ {t('continue_tab.no_project_selected')}", ""

                    gen = app_state.get_generator()
                    project = app_state.current_project

                    prev_content = ""
                    for ch in project.chapters:
                        if ch.num == int(ch_num) - 1 and ch.content:
                            prev_content = ch.content[-2000:]

                    content, msg = gen.generate_chapter(
                        chapter_num=int(ch_num), chapter_title=ch_title,
                        chapter_desc=ch_desc, novel_title=project.title,
                        character_setting=project.character_setting,
                        world_setting=project.world_setting,
                        plot_idea=project.plot_idea, genre=project.genre,
                        sub_genres=project.sub_genres,
                        previous_content=prev_content, custom_prompt=custom_prompt
                    )

                    if content:
                        new_ch = Chapter(
                            num=int(ch_num), title=ch_title, desc=ch_desc,
                            content=content, word_count=len(content),
                            generated_at=datetime.now().isoformat()
                        )
                        found = False
                        for i, ch in enumerate(project.chapters):
                            if ch.num == int(ch_num):
                                project.chapters[i] = new_ch
                                found = True
                                break
                        if not found:
                            project.chapters.append(new_ch)
                            project.chapters.sort(key=lambda x: x.num)

                        ProjectManager.save_project(project)
                        return f"✅ Chương {int(ch_num)} đã sinh ({len(content)} từ)", content
                    else:
                        return f"❌ {msg}", ""

                refresh_continue_btn.click(fn=on_refresh_continue, outputs=[continue_project_selector])
                continue_project_selector.change(
                    fn=on_continue_project_select,
                    inputs=[continue_project_selector],
                    outputs=[continue_project_info, continue_chapter_num]
                )
                continue_generate_btn.click(
                    fn=on_continue_generate,
                    inputs=[continue_project_selector, continue_chapter_num, continue_chapter_title,
                            continue_chapter_desc, continue_target_words, continue_custom_prompt],
                    outputs=[continue_status, continue_output]
                )

            # ==================== Tab 3: Viết lại ====================
            with gr.Tab(t("tabs.rewrite")):
                gr.Markdown(f"### {t('rewrite.header')}")

                rewrite_file_input = gr.File(label=t("rewrite.upload_file"), file_types=[".txt", ".docx", ".md", ".pdf"])
                rewrite_input = gr.Textbox(
                    label=t("polish.original_text"),
                    lines=10, placeholder="Dán nội dung cần viết lại..."
                )

                preset_choices = list(get_preset_templates().keys())
                rewrite_style = gr.Dropdown(
                    choices=preset_choices,
                    label=t("rewrite.preset_style"),
                    value=preset_choices[0] if preset_choices else None,
                    interactive=True
                )

                rewrite_btn = gr.Button(t("rewrite.start_rewrite"), variant="primary")
                rewrite_status = gr.Textbox(label=t("rewrite.parse_status"), interactive=False)
                rewrite_output = gr.Textbox(label=t("rewrite.full_rewritten"), lines=15, interactive=True)

                def on_file_upload(file):
                    if file is None:
                        return ""
                    try:
                        content = parse_novel_file(file.name)
                        return content
                    except Exception as e:
                        return f"❌ {str(e)}"

                def on_rewrite(text, style):
                    instructions = get_preset_templates().get(style, "")
                    gen = app_state.get_generator()
                    content, msg = gen.rewrite_paragraph(text, instructions)
                    if content:
                        return f"✅ {msg}", content
                    return f"❌ {msg}", ""

                rewrite_file_input.change(fn=on_file_upload, inputs=[rewrite_file_input], outputs=[rewrite_input])
                rewrite_btn.click(fn=on_rewrite, inputs=[rewrite_input, rewrite_style], outputs=[rewrite_status, rewrite_output])

            # ==================== Tab 4: Đánh bóng ====================
            with gr.Tab(t("tabs.polish")):
                gr.Markdown(f"### {t('polish.header')}")

                polish_file_input = gr.File(label=t("polish.upload_file"), file_types=[".txt", ".docx", ".md", ".pdf"])
                polish_input = gr.Textbox(
                    label=t("polish.original_text"),
                    lines=10, placeholder="Dán nội dung cần đánh bóng..."
                )

                polish_custom_req = gr.Textbox(
                    label=t("polish.custom_req"),
                    placeholder=t("polish.custom_req_placeholder"),
                    lines=2
                )

                with gr.Row():
                    polish_btn = gr.Button(t("polish.start_polish"), variant="primary")
                    polish_suggest_btn = gr.Button(t("polish.polish_suggest_btn"), variant="secondary")

                polish_status = gr.Textbox(label=t("polish.polish_status"), interactive=False)
                polish_output = gr.Textbox(label=t("polish.polished_text"), lines=15, interactive=True)

                def on_polish_file_upload(file):
                    if file is None:
                        return ""
                    try:
                        content = parse_novel_file(file.name)
                        return content
                    except Exception as e:
                        return f"❌ {str(e)}"

                def on_polish(text):
                    gen = app_state.get_generator()
                    content, msg = gen.polish_text(text)
                    if content:
                        return f"✅ {msg}", content
                    return f"❌ {msg}", ""

                def on_polish_suggest(text):
                    gen = app_state.get_generator()
                    content, msg = gen.polish_and_suggest(text)
                    if content:
                        return f"✅ {msg}", content
                    return f"❌ {msg}", ""

                polish_file_input.change(fn=on_polish_file_upload, inputs=[polish_file_input], outputs=[polish_input])
                polish_btn.click(fn=on_polish, inputs=[polish_input], outputs=[polish_status, polish_output])
                polish_suggest_btn.click(fn=on_polish_suggest, inputs=[polish_input], outputs=[polish_status, polish_output])

            # ==================== Tab 5: Xuất file ====================
            with gr.Tab(t("tabs.export")):
                gr.Markdown(f"### {t('export.header')}")

                export_project_choices = list_project_titles()
                export_project_selector = gr.Dropdown(
                    choices=export_project_choices,
                    label=t("projects.select_project"),
                    interactive=True
                )
                refresh_export_btn = gr.Button(t("projects.refresh_btn"), size="sm")

                export_format = gr.Radio(
                    choices=[
                        t("create.export_format_word"),
                        t("create.export_format_txt"), 
                        t("create.export_format_md"),
                        t("create.export_format_html")
                    ],
                    value=t("create.export_format_txt"),
                    label=t("projects.export_format"),
                    interactive=True
                )
                export_btn = gr.Button(t("projects.export_btn"), variant="primary", size="lg")
                export_status = gr.Textbox(label=t("projects.export_status"), interactive=False)
                export_download = gr.File(label=t("projects.download_file"), interactive=False)

                def on_refresh_export():
                    titles = list_project_titles()
                    return gr.update(choices=titles, value=None)

                def on_export(project_title, format_type):
                    if not project_title:
                        return f"❌ {t('projects.select_project_first')}", None

                    try:
                        project_data = ProjectManager.get_project_by_title(project_title)
                        if not project_data:
                            return f"❌ {t('projects.project_not_found')}", None

                        project_id = project_data.get("id")
                        project, msg = ProjectManager.load_project(project_id)
                        if not project:
                            return f"❌ {msg}", None

                        full_text = f"# {project.title}\n\n"
                        for ch in project.chapters:
                            if ch.content:
                                full_text += f"## Chương {ch.num}: {ch.title}\n\n"
                                full_text += ch.content + "\n\n"

                        if len(full_text.strip()) < 50:
                            return f"❌ {t('ui.no_content_export')}", None

                        # Map format
                        format_map = {
                            t("create.export_format_word"): "docx",
                            t("create.export_format_txt"): "txt",
                            t("create.export_format_md"): "md",
                            t("create.export_format_html"): "html"
                        }
                        fmt = format_map.get(format_type, "txt")

                        if fmt == "docx":
                            filepath, exp_msg = export_to_docx(full_text, project.title)
                        elif fmt == "txt":
                            filepath, exp_msg = export_to_txt(full_text, project.title)
                        elif fmt == "md":
                            filepath, exp_msg = export_to_markdown(full_text, project.title)
                        elif fmt == "html":
                            filepath, exp_msg = export_to_html(full_text, project.title)
                        else:
                            return f"❌ {t('ui.unsupported_format', format=fmt)}", None

                        if filepath:
                            return f"✅ {exp_msg}", filepath
                        return f"❌ {exp_msg}", None

                    except Exception as e:
                        logger.error(f"Export failed: {e}", exc_info=True)
                        return f"❌ {t('ui.export_failed', error=str(e))}", None

                refresh_export_btn.click(fn=on_refresh_export, outputs=[export_project_selector])
                export_btn.click(fn=on_export, inputs=[export_project_selector, export_format], outputs=[export_status, export_download])

            # ==================== Tab 6: Quản lý dự án ====================
            with gr.Tab(t("tabs.projects")):
                gr.Markdown(f"### {t('projects.header')}")

                projects_table = gr.Dataframe(
                    headers=["ID", t("ui.col_project_name"), t("ui.col_type"), t("ui.col_created_at"), t("ui.col_chapters")],
                    interactive=False
                )
                with gr.Row():
                    refresh_projects_btn = gr.Button(t("projects.refresh_btn"))
                    delete_project_btn = gr.Button(t("projects.delete_btn"), variant="stop")

                gr.Markdown(f"#### {t('projects.delete_header')}")
                delete_project_selector = gr.Dropdown(
                    choices=list_project_titles(),
                    label=t("projects.delete_select_project"),
                    interactive=True
                )
                project_manage_status = gr.Textbox(label=t("projects.status_label"), interactive=False)

                def on_refresh_projects():
                    try:
                        projects = ProjectManager.list_projects()
                        table_data = []
                        for p in projects:
                            table_data.append([
                                p.get("id", ""),
                                p.get("title", ""),
                                p.get("genre", ""),
                                p.get("created_at", "")[:10] if p.get("created_at") else "",
                                f"{p.get('completed_chapters', 0)}/{p.get('chapter_count', 0)}"
                            ])
                        titles = [p.get("title", "") for p in projects]
                        return table_data, gr.update(choices=titles, value=None)
                    except Exception as e:
                        logger.error(f"Refresh projects failed: {e}")
                        return [], gr.update()

                def on_delete_project(project_title):
                    if not project_title or not project_title.strip():
                        return f"❌ {t('projects.select_project_first')}", gr.update(), gr.update()

                    try:
                        project_data = ProjectManager.get_project_by_title(project_title)
                        if not project_data:
                            return f"❌ {t('projects.project_not_found')}", gr.update(), gr.update()

                        project_id = project_data.get("id")
                        success, msg = ProjectManager.delete_project(project_id)
                        if success:
                            new_table, new_dropdown = on_refresh_projects()
                            return f"✅ {t('projects.delete_success')}", new_table, new_dropdown
                        return f"❌ {t('projects.delete_failed')}: {msg}", gr.update(), gr.update()
                    except Exception as e:
                        return f"❌ {str(e)}", gr.update(), gr.update()

                refresh_projects_btn.click(fn=on_refresh_projects, outputs=[projects_table, delete_project_selector])
                delete_project_btn.click(
                    fn=on_delete_project,
                    inputs=[delete_project_selector],
                    outputs=[project_manage_status, projects_table, delete_project_selector]
                )

            # ==================== Tab 7: Cài đặt hệ thống ====================
            with gr.Tab(t("tabs.settings")):
                gr.Markdown(f"### {t('settings.header')}")

                with gr.Tabs():
                    # Sub-tab: Quản lý giao diện API
                    with gr.Tab(t("settings.tab_backends")):
                        gr.Markdown(f"#### {t('settings.backends_header')}")

                        backends_display = gr.Markdown("...")

                        def get_backends_display():
                            try:
                                result = ConfigAPIManager.list_backends()
                                if result["success"] and result["data"]:
                                    lines = [f"### 📋 {len(result['data'])} backend(s)\n"]
                                    for b in result["data"]:
                                        enabled = "✅" if b.get("enabled") else "❌"
                                        default = " ⭐" if b.get("is_default") else ""
                                        lines.append(f"{enabled} **{b['name']}**{default}")
                                        lines.append(f"  - Model: `{b.get('model', '')}`")
                                        lines.append(f"  - URL: `{b.get('base_url', '')[:50]}...`")
                                        lines.append(f"  - Timeout: {b.get('timeout', 30)}s")
                                        lines.append("")
                                    return "\n".join(lines)
                                return t("app.no_backends_warning")
                            except Exception as e:
                                return f"❌ {str(e)}"

                        gr.Markdown("---")
                        gr.Markdown(f"#### {t('settings.add_backend_header')}")

                        provider_names = [API_PROVIDERS[k]["name"] for k in API_PROVIDERS]

                        with gr.Row():
                            api_provider_dropdown = gr.Dropdown(
                                choices=provider_names,
                                label=t("settings.provider_label"),
                                info=t("settings.provider_info"),
                                interactive=True
                            )

                        with gr.Row():
                            api_name_input = gr.Textbox(label=t("settings.backend_name"), placeholder=t("settings.backend_name_placeholder"))
                            api_type_dropdown = gr.Dropdown(
                                choices=ConfigAPIManager.get_backend_types(),
                                value="openai", label=t("settings.backend_type"), interactive=True
                            )

                        with gr.Row():
                            api_url_input = gr.Textbox(label=t("settings.base_url"), placeholder=t("settings.base_url_placeholder"))
                            api_key_input = gr.Textbox(label=t("settings.api_key"), placeholder=t("settings.api_key_placeholder"), type="password")

                        with gr.Row():
                            api_model_input = gr.Textbox(label=t("settings.model_name"), placeholder=t("settings.model_name_placeholder"))
                            api_timeout_input = gr.Slider(minimum=5, maximum=600, value=120, step=5, label=t("settings.timeout"))

                        with gr.Row():
                            api_save_btn = gr.Button(t("settings.add_btn"), variant="primary")
                            api_refresh_btn = gr.Button(t("settings.refresh_list"), size="sm")

                        api_status = gr.Textbox(label=t("settings.operation_result"), interactive=False)

                        gr.Markdown("---")
                        gr.Markdown(f"#### {t('settings.test_manage_header')}")

                        with gr.Row():
                            test_name_input = gr.Textbox(label=t("settings.test_backend_name"), placeholder=t("settings.test_backend_placeholder"))
                            api_test_btn = gr.Button(t("settings.test_btn"), variant="secondary")

                        with gr.Row():
                            delete_name_input = gr.Textbox(label=t("settings.delete_backend_name"), placeholder=t("settings.delete_backend_placeholder"))
                            api_delete_btn = gr.Button(t("settings.delete_btn"), variant="stop")

                        test_result = gr.Textbox(label=t("settings.test_result"), interactive=False)

                        def on_provider_select(provider_name):
                            for key, info in API_PROVIDERS.items():
                                if info["name"] == provider_name:
                                    return info.get("base_url", ""), info.get("default_model", ""), provider_name
                            return "", "", provider_name

                        def on_api_test(name):
                            result = ConfigAPIManager.test_backend(name)
                            return result["message"]

                        def on_api_save(name, btype, url, key, model, timeout):
                            result = ConfigAPIManager.add_backend(name, btype, url, key, model, int(timeout))
                            reinit_api_client()
                            app_state.generator = None
                            return result["message"], get_backends_display()

                        def on_api_delete(name):
                            result = ConfigAPIManager.delete_backend(name)
                            reinit_api_client()
                            app_state.generator = None
                            return result["message"], get_backends_display()

                        api_provider_dropdown.change(
                            fn=on_provider_select,
                            inputs=[api_provider_dropdown],
                            outputs=[api_url_input, api_model_input, api_name_input]
                        )
                        api_save_btn.click(
                            fn=on_api_save,
                            inputs=[api_name_input, api_type_dropdown, api_url_input, api_key_input, api_model_input, api_timeout_input],
                            outputs=[api_status, backends_display]
                        )
                        api_test_btn.click(fn=on_api_test, inputs=[test_name_input], outputs=[test_result])
                        api_delete_btn.click(fn=on_api_delete, inputs=[delete_name_input], outputs=[api_status, backends_display])
                        api_refresh_btn.click(fn=lambda: get_backends_display(), outputs=[backends_display])

                    # Sub-tab: Tham số sinh
                    with gr.Tab(t("settings.tab_params")):
                        gr.Markdown(f"#### {t('settings.params_header')}")

                        config = get_config()
                        gen_config = config.generation

                        param_temperature = gr.Slider(minimum=0.1, maximum=2.0, value=gen_config.temperature, step=0.1, label=t("settings.temperature_label"), info=t("settings.temperature_info"))
                        param_top_p = gr.Slider(minimum=0.1, maximum=1.0, value=gen_config.top_p, step=0.05, label="Top P", info=t("settings.top_p_info"))
                        param_max_tokens = gr.Slider(minimum=100, maximum=100000, value=gen_config.max_tokens, step=100, label="Max Tokens", info=t("settings.max_tokens_info"))
                        param_chapter_words = gr.Slider(minimum=500, maximum=65536, value=gen_config.chapter_target_words, step=500, label=t("settings.chapter_target_words"))

                        save_params_btn = gr.Button(t("settings.save_params_btn"), variant="primary")
                        params_status = gr.Textbox(label=t("settings.save_status"), interactive=False)

                        def on_save_params(temp, top_p, max_tokens, chapter_words):
                            cfg = get_config()
                            success, msg = cfg.update_generation_config(
                                temperature=temp, top_p=top_p,
                                max_tokens=int(max_tokens),
                                chapter_target_words=int(chapter_words)
                            )
                            if success:
                                app_state.generator = None
                                return f"✅ {msg}"
                            return f"❌ {msg}"

                        save_params_btn.click(
                            fn=on_save_params,
                            inputs=[param_temperature, param_top_p, param_max_tokens, param_chapter_words],
                            outputs=[params_status]
                        )

                    # Sub-tab: Bộ nhớ đệm
                    with gr.Tab(t("settings.tab_cache")):
                        gr.Markdown(f"#### {t('settings.cache_header')}")

                        cache_info_display = gr.Markdown(t("ui.no_cache"))

                        def get_cache_info():
                            try:
                                api_client = get_api_client()
                                stats = api_client.get_cache_stats()
                                gen_caches = list_generation_caches()
                                gen_size_val = get_cache_size()

                                return f"""### Thống kê bộ nhớ đệm
- **API Cache**: {stats['total_entries']}/{stats['max_size']} ({stats['usage_rate']:.1f}%)
- **Generation Cache**: {len(gen_caches)} files ({gen_size_val / 1024:.1f} KB)"""
                            except Exception as e:
                                return f"❌ {str(e)}"

                        with gr.Row():
                            refresh_cache_btn = gr.Button(t("settings.refresh_cache"), size="sm")
                            clear_all_cache_btn = gr.Button(t("settings.clear_all"), variant="stop")

                        cache_op_status = gr.Textbox(label=t("settings.cache_op_status"), interactive=False)

                        def on_clear_all_cache():
                            try:
                                api_client = get_api_client()
                                api_client.clear_cache()
                                clear_generation_cache()
                                return "✅ Đã xóa tất cả bộ nhớ đệm", get_cache_info()
                            except Exception as e:
                                return f"❌ {str(e)}", get_cache_info()

                        refresh_cache_btn.click(fn=get_cache_info, outputs=[cache_info_display])
                        clear_all_cache_btn.click(fn=on_clear_all_cache, outputs=[cache_op_status, cache_info_display])

                    # Sub-tab: Quản lý thể loại
                    with gr.Tab(t("settings.tab_genre")):
                        gr.Markdown(f"#### {t('settings.genre_desc')}")

                        genre_select = gr.Dropdown(
                            choices=GenreManager.get_genre_names(),
                            label=t("settings.genre_select"),
                            interactive=True
                        )
                        genre_name_input = gr.Textbox(label=t("settings.genre_name"), placeholder=t("settings.genre_name_placeholder"))
                        genre_desc_input = gr.Textbox(label=t("settings.genre_description"), placeholder=t("settings.genre_description_placeholder"), lines=3)

                        with gr.Row():
                            genre_add_btn = gr.Button(t("settings.genre_add_btn"), variant="primary")
                            genre_update_btn = gr.Button(t("settings.genre_update_btn"), variant="secondary")
                            genre_delete_btn = gr.Button(t("settings.genre_delete_btn"), variant="stop")

                        genre_op_status = gr.Textbox(label=t("settings.genre_op_status"), interactive=False)

                        def on_genre_select(name):
                            if name:
                                desc = GenreManager.get_genre_description(name)
                                return name, desc or ""
                            return "", ""

                        def on_genre_add(name, desc):
                            if not name.strip():
                                return t("settings.genre_err_name_empty"), gr.update()
                            success = GenreManager.add_genre(name.strip(), desc.strip())
                            if success:
                                return t("settings.genre_add_success"), gr.update(choices=GenreManager.get_genre_names())
                            return t("settings.genre_err_exists"), gr.update()

                        def on_genre_update(old_name, new_name, desc):
                            if not old_name:
                                return t("settings.genre_err_none_selected"), gr.update()
                            success = GenreManager.update_genre(old_name, new_name.strip(), desc.strip())
                            if success:
                                return t("settings.genre_update_success"), gr.update(choices=GenreManager.get_genre_names())
                            return t("settings.genre_err_update"), gr.update()

                        def on_genre_delete(name):
                            if not name:
                                return t("settings.genre_err_none_selected"), gr.update()
                            success = GenreManager.delete_genre(name)
                            if success:
                                return t("settings.genre_delete_success"), gr.update(choices=GenreManager.get_genre_names())
                            return t("settings.genre_err_delete"), gr.update()

                        genre_select.change(fn=on_genre_select, inputs=[genre_select], outputs=[genre_name_input, genre_desc_input])
                        genre_add_btn.click(fn=on_genre_add, inputs=[genre_name_input, genre_desc_input], outputs=[genre_op_status, genre_select])
                        genre_update_btn.click(fn=on_genre_update, inputs=[genre_select, genre_name_input, genre_desc_input], outputs=[genre_op_status, genre_select])
                        genre_delete_btn.click(fn=on_genre_delete, inputs=[genre_select], outputs=[genre_op_status, genre_select])

                    # Sub-tab: Quản lý chủ đề con
                    with gr.Tab(t("settings.tab_sub_genre")):
                        gr.Markdown(f"#### {t('settings.sub_genre_desc')}")

                        sub_genre_select = gr.Dropdown(
                            choices=SubGenreManager.get_sub_genre_names(),
                            label=t("settings.sub_genre_select"),
                            interactive=True
                        )
                        sub_genre_name_input = gr.Textbox(label=t("settings.sub_genre_name"), placeholder=t("settings.sub_genre_name_placeholder"))
                        sub_genre_desc_input = gr.Textbox(label=t("settings.sub_genre_description"), placeholder=t("settings.sub_genre_description_placeholder"), lines=3)

                        with gr.Row():
                            sub_genre_add_btn = gr.Button(t("settings.sub_genre_add_btn"), variant="primary")
                            sub_genre_update_btn = gr.Button(t("settings.sub_genre_update_btn"), variant="secondary")
                            sub_genre_delete_btn = gr.Button(t("settings.sub_genre_delete_btn"), variant="stop")

                        sub_genre_op_status = gr.Textbox(label=t("settings.sub_genre_op_status"), interactive=False)

                        def on_sub_genre_select(name):
                            if name:
                                desc = SubGenreManager.get_sub_genre_description(name)
                                return name, desc or ""
                            return "", ""

                        def on_sub_genre_add(name, desc):
                            if not name.strip():
                                return t("settings.sub_genre_err_name_empty"), gr.update()
                            success = SubGenreManager.add_sub_genre(name.strip(), desc.strip())
                            if success:
                                return t("settings.sub_genre_add_success"), gr.update(choices=SubGenreManager.get_sub_genre_names())
                            return t("settings.sub_genre_err_exists"), gr.update()

                        def on_sub_genre_update(old_name, new_name, desc):
                            if not old_name:
                                return t("settings.sub_genre_err_none_selected"), gr.update()
                            success = SubGenreManager.update_sub_genre(old_name, new_name.strip(), desc.strip())
                            if success:
                                return t("settings.sub_genre_update_success"), gr.update(choices=SubGenreManager.get_sub_genre_names())
                            return t("settings.sub_genre_err_update"), gr.update()

                        def on_sub_genre_delete(name):
                            if not name:
                                return t("settings.sub_genre_err_none_selected"), gr.update()
                            success = SubGenreManager.delete_sub_genre(name)
                            if success:
                                return t("settings.sub_genre_delete_success"), gr.update(choices=SubGenreManager.get_sub_genre_names())
                            return t("settings.sub_genre_err_delete"), gr.update()

                        sub_genre_select.change(fn=on_sub_genre_select, inputs=[sub_genre_select], outputs=[sub_genre_name_input, sub_genre_desc_input])
                        sub_genre_add_btn.click(fn=on_sub_genre_add, inputs=[sub_genre_name_input, sub_genre_desc_input], outputs=[sub_genre_op_status, sub_genre_select])
                        sub_genre_update_btn.click(fn=on_sub_genre_update, inputs=[sub_genre_select, sub_genre_name_input, sub_genre_desc_input], outputs=[sub_genre_op_status, sub_genre_select])
                        sub_genre_delete_btn.click(fn=on_sub_genre_delete, inputs=[sub_genre_select], outputs=[sub_genre_op_status, sub_genre_select])

        # Footer
        gr.Markdown("""
        <div style="text-align: center; padding: 15px; margin-top: 30px; border-top: 1px solid #e0e0e0; color: #666;">
            <p style="margin: 5px 0;">AI Novel Generator v4.5.0</p>
            <p style="margin: 5px 0; font-size: 0.9em;">Bản quyền © 2026 Công ty TNHH Công nghệ An ninh mạng Huyễn Thành Tân Cương</p>
            <p style="margin: 5px 0; font-size: 0.8em; color: #999;">Made with ❤️ by Huyễn Thành</p>
        </div>
        """)

    return app


# ==================== Khởi động ứng dụng ====================

def main():
    """Khởi động ứng dụng"""
    logger.info(t("app.startup_log"))

    # Tạo UI
    app = create_main_ui()

    # Tải CSS
    custom_css = ""
    css_path = Path("custom.css")
    if css_path.exists():
        with open(css_path, 'r', encoding='utf-8') as f:
            custom_css = f.read()

    # Khởi động
    logger.info(t("app.gradio_start", port=WEB_PORT))
    app.launch(
        server_name=WEB_HOST,
        server_port=WEB_PORT,
        share=WEB_SHARE,
        show_error=True
    )


if __name__ == "__main__":
    main()