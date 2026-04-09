import gradio as gr
from datetime import datetime
import json
import re
import traceback

from locales.i18n import t
from services.novel_generator import OutlineParser
from services.project_manager import ProjectManager
from services.genre_manager import GenreManager
from services.sub_genre_manager import SubGenreManager
from services.style_manager import StyleManager
from core.state import app_state
import logging

logger = logging.getLogger(__name__)

def build_create_tab():
    """Xây dựng giao diện Tab Sáng tác từ đầu"""
    with gr.Tab(t("tabs.create")):
        gr.Markdown(f"### 🪄 {t('create.header')}")

        with gr.Accordion("📌 1. Thông tin cơ bản", open=True):
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
                    
                    style_choices = StyleManager.get_style_names()
                    create_style_dropdown = gr.Dropdown(
                        choices=style_choices,
                        label="Phong cách viết",
                        value=style_choices[0] if style_choices else None,
                        interactive=True
                    )

                with gr.Column(scale=2):
                    title_input = gr.Textbox(
                        label=t("create.novel_title"),
                        placeholder=t("create.novel_title_default"),
                        interactive=True
                    )
                    with gr.Group():
                        suggested_titles_radio = gr.Radio(
                            label=t("create.suggested_titles_radio") if t("create.suggested_titles_radio") != "create.suggested_titles_radio" else "Gợi ý tên truyện",
                            choices=[],
                            visible=False,
                            interactive=True
                        )
                        with gr.Row():
                            suggest_title_prompt = gr.Textbox(
                                show_label=False,
                                placeholder=t("create.custom_prompt_placeholder"),
                                lines=1, interactive=True, scale=4
                            )
                            suggest_title_btn = gr.Button(t("create.suggest_title_btn"), variant="secondary", size="sm", scale=1)
                        suggest_title_status = gr.Textbox(show_label=False, interactive=False, visible=False)

        with gr.Accordion("🎭 2. Thiết lập chi tiết", open=False):
            with gr.Row():
                with gr.Column():
                    character_input = gr.Textbox(
                        label=t("create.char_setting"),
                        placeholder=t("create.char_setting_placeholder"),
                        lines=5, interactive=False
                    )
                    with gr.Group():
                        with gr.Row():
                            num_main_chars = gr.Number(label=t("create.num_main_chars"), value=2, minimum=1, maximum=10, step=1, scale=1)
                            num_sub_chars = gr.Number(label=t("create.num_sub_chars"), value=3, minimum=0, maximum=20, step=1, scale=1)
                        with gr.Row():
                            suggest_char_prompt = gr.Textbox(show_label=False, placeholder=t("create.custom_prompt_placeholder"), lines=1, interactive=False, scale=4)
                            suggest_char_btn = gr.Button(t("create.suggest_btn"), variant="secondary", size="sm", scale=1, interactive=False)
                        suggest_char_status = gr.Textbox(show_label=False, interactive=False, visible=False)

                with gr.Column():
                    world_input = gr.Textbox(
                        label=t("create.world_setting"),
                        placeholder=t("create.world_setting_placeholder"),
                        lines=5, interactive=False
                    )
                    with gr.Group():
                        with gr.Row():
                            suggest_world_prompt = gr.Textbox(show_label=False, placeholder=t("create.custom_prompt_placeholder"), lines=1, interactive=False, scale=4)
                            suggest_world_btn = gr.Button(t("create.suggest_btn"), variant="secondary", size="sm", scale=1, interactive=False)
                        suggest_world_status = gr.Textbox(show_label=False, interactive=False, visible=False)

                    plot_input = gr.Textbox(
                        label=t("create.plot_idea"),
                        placeholder=t("create.plot_idea_placeholder"),
                        lines=3, interactive=False
                    )
                    with gr.Group():
                        with gr.Row():
                            suggest_plot_prompt = gr.Textbox(show_label=False, placeholder=t("create.custom_prompt_placeholder"), lines=1, interactive=False, scale=4)
                            suggest_plot_btn = gr.Button(t("create.suggest_plot_btn"), variant="secondary", size="sm", scale=1, interactive=False)
                        suggest_plot_status = gr.Textbox(show_label=False, interactive=False, visible=False)

        with gr.Accordion("📝 3. Dàn ý truyện", open=False):
            custom_outline_prompt = gr.Textbox(
                label="Yêu cầu riêng/Chỉ dẫn bổ sung cho Dàn ý (Tùy chọn)",
                placeholder="VD: Không có nữ chính, kết cục mở, nvc là người tu ma nhưng tính cách hài hước...",
                lines=2, interactive=False
            )
            with gr.Row():
                total_chapters = gr.Number(
                    label=t("create.chapter_count"), value=20, minimum=1, maximum=200, step=1, scale=1, interactive=False
                )
                generate_outline_btn = gr.Button(t("create.gen_outline_btn"), variant="primary", size="lg", scale=3, interactive=False)

            outline_output = gr.Textbox(label=t("create.outline_display"), lines=15, interactive=True)
            outline_status = gr.Textbox(label=t("create.gen_status"), interactive=False)

        with gr.Accordion("🚀 4. Sáng tác tự động", open=False):
            with gr.Row():
                with gr.Column(scale=1):
                    memory_type = gr.Radio(label="Cách nhớ ngữ cảnh", choices=["Toàn văn", "Tóm tắt"], value="Toàn văn")
                with gr.Column(scale=1):
                    memory_chapters = gr.Number(label="Số chương ghi nhớ", value=3, minimum=1, maximum=20, step=1)
                with gr.Column(scale=1):
                    use_reflection_checkbox = gr.Checkbox(label="Bật chế độ Tự kiểm duyệt (Self-Reflection)", value=False, info="AI tự đọc lại và sửa lỗi nháp. Tốn gấp đôi thời gian & Token.")
            with gr.Row():
                auto_generate_btn = gr.Button(t("create.start_gen_btn"), variant="primary", size="lg", interactive=False)
                stop_btn = gr.Button(t("create.pause_gen_btn"), variant="stop", size="lg", interactive=False)

            with gr.Row():
                with gr.Column(scale=1):
                    generation_progress = gr.Textbox(label=t("create.gen_status"), lines=15, interactive=False)
                with gr.Column(scale=2):
                    chapter_selector = gr.Dropdown(label="Danh sách chương đã tạo", choices=[], interactive=True, allow_custom_value=True)
                    chapter_content_display = gr.Textbox(label="Nội dung chương", lines=15, interactive=False)

        def on_suggest_title(genre, sub_genres, custom_prompt):
            yield gr.Radio(visible=False), gr.update(value="⏳ Đang gọi AI xử lý... Vui lòng chờ.", visible=True), gr.update(interactive=False)
            try:
                gen = app_state.get_generator()
                content, msg = gen.suggest_title(genre, sub_genres, custom_prompt)
                if content:
                    try:
                        match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', content)
                        if match:
                            data = {"suggestions": json.loads(match.group(0))}
                        else:
                            clean_content = re.sub(r'```(?:json)?\s*', '', content)
                            clean_content = re.sub(r'```\s*', '', clean_content)
                            data = json.loads(clean_content)
                            
                        if "suggestions" in data:
                            choices = [f"{item.get('title', '')} - {item.get('description', '')}" for item in data["suggestions"]]
                            yield gr.Radio(choices=choices, visible=True), gr.update(visible=False), gr.update(interactive=True)
                            return
                    except Exception as e:
                        logger.error(f"Failed to parse title JSON: {e}")
                        yield gr.Radio(choices=[content, f"Parse error: {str(e)}"], visible=True), gr.update(visible=False), gr.update(interactive=True)
                        return
                yield gr.Radio(choices=[msg], visible=True), gr.update(visible=False), gr.update(interactive=True)
            except Exception as e:
                traceback.print_exc()
                yield gr.Radio(choices=[f"Lỗi: {str(e)}"], visible=True), gr.update(value=f"❌ Lỗi: {str(e)}", visible=True), gr.update(interactive=True)

        def on_title_select(selected):
            if selected and " - " in selected:
                return selected.split(" - ", 1)[0]
            return selected

        def on_suggest_char(title, genre, sub_genres, custom_prompt, num_main, num_sub):
            yield gr.update(), gr.update(value="⏳ Đang gọi AI xử lý... Vui lòng chờ.", visible=True), gr.update(interactive=False)
            try:
                gen = app_state.get_generator()
                nm = int(num_main) if num_main else 2
                ns = int(num_sub) if num_sub else 3
                content, msg = gen.suggest_content("char", title, genre, sub_genres, "", "", custom_prompt, nm, ns)
                yield gr.update(value=content if content else msg), gr.update(visible=False), gr.update(interactive=True)
            except Exception as e:
                traceback.print_exc()
                yield gr.update(), gr.update(value=f"❌ Lỗi: {str(e)}", visible=True), gr.update(interactive=True)
                
        def on_suggest_world(title, genre, sub_genres, custom_prompt):
            yield gr.update(), gr.update(value="⏳ Đang gọi AI xử lý... Vui lòng chờ.", visible=True), gr.update(interactive=False)
            try:
                gen = app_state.get_generator()
                content, msg = gen.suggest_content("world", title, genre, sub_genres, "", "", custom_prompt)
                yield gr.update(value=content if content else msg), gr.update(visible=False), gr.update(interactive=True)
            except Exception as e:
                traceback.print_exc()
                yield gr.update(), gr.update(value=f"❌ Lỗi: {str(e)}", visible=True), gr.update(interactive=True)
                
        def on_suggest_plot(title, genre, sub_genres, char_setting, world_setting, custom_prompt):
            yield gr.update(), gr.update(value="⏳ Đang gọi AI xử lý... Vui lòng chờ.", visible=True), gr.update(interactive=False)
            try:
                gen = app_state.get_generator()
                content, msg = gen.suggest_content("plot", title, genre, sub_genres, char_setting, world_setting, custom_prompt)
                yield gr.update(value=content if content else msg), gr.update(visible=False), gr.update(interactive=True)
            except Exception as e:
                traceback.print_exc()
                yield gr.update(), gr.update(value=f"❌ Lỗi: {str(e)}", visible=True), gr.update(interactive=True)

        def on_generate_outline(title, genre, sub_genres, num_chapters, char_setting, world_setting, plot_idea, custom_outline, progress=gr.Progress()):
            progress(0.1, desc="Đang gọi AI...")
            gen = app_state.get_generator()
            content, msg = gen.generate_outline(
                title, genre, sub_genres or [],
                int(num_chapters), char_setting, world_setting, plot_idea, custom_outline
            )
            return content, msg

        def on_auto_generate(title, genre, sub_genres, char_setting, world_setting, plot_idea, outline_text, mem_type, mem_chaps, use_reflection, selected_style, progress=gr.Progress()):
            """Tự động tạo toàn bộ tiểu thuyết"""
            gen = app_state.get_generator()
            
            # Cập nhật style vào config hiện tại
            if selected_style:
                gen.config.generation.writing_style = selected_style

            chapters, parse_msg = OutlineParser.parse(outline_text)
            if not chapters:
                yield f"❌ {parse_msg}", gr.update()
                return

            project, create_msg = ProjectManager.create_project(
                title, genre, sub_genres or [],
                char_setting, world_setting, plot_idea
            )
            if not project:
                yield f"❌ {create_msg}", gr.update()
                return

            project.chapters = chapters
            app_state.current_project = project
            app_state.is_generating = True
            app_state.stop_requested = False

            # Save immediately to ensure chapter titles are stored even if generation is stopped early
            ProjectManager.save_project(project)

            results = [f"📋 Đã phân tích {len(chapters)} chương", f"💾 {create_msg}"]
            yield "\n".join(results), gr.update(choices=[], value=None)

            generated_chapters = []

            for i, chapter in enumerate(chapters):
                if app_state.stop_requested:
                    results.append("\n⚠️ Đã dừng sinh!")
                    yield "\n".join(results), gr.update(choices=generated_chapters)
                    break

                results.append(f"\n✍️ Đang sinh Chương {chapter.num}: {chapter.title}...")
                progress((i + 1) / len(chapters))
                yield "\n".join(results), gr.update(choices=generated_chapters)

                mem_ch = int(mem_chaps) if mem_chaps else 3
                start_idx = max(0, i - mem_ch)
                past_chapters = chapters[start_idx:i]
                
                prev_content = ""
                context_summary = ""

                if mem_type == "Toàn văn":
                    prev_texts = [c.content for c in past_chapters if hasattr(c, 'content') and c.content]
                    prev_content = "\n\n".join(prev_texts)
                    prev_content = prev_content[-4000:]
                else:
                    summaries = []
                    for c in past_chapters:
                        if not hasattr(c, 'content') or not c.content:
                            continue
                        if not hasattr(c, 'summary') or not c.summary:
                            summ, _ = gen.generate_chapter_summary(c.content, c.title)
                            c.summary = summ
                        if c.summary:
                            summaries.append(f"Chương {c.num} - {c.title}: {c.summary}")
                    
                    if summaries:
                        context_summary = "\n".join(summaries)
                    
                    if i > 0 and chapters[i-1].content:
                        prev_content = chapters[i-1].content[-1500:]

                content, msg = gen.generate_chapter(
                    chapter_num=chapter.num, chapter_title=chapter.title,
                    chapter_desc=chapter.desc, novel_title=title,
                    character_setting=char_setting, world_setting=world_setting,
                    plot_idea=plot_idea, genre=genre, sub_genres=sub_genres,
                    previous_content=prev_content, context_summary=context_summary,
                    use_reflection=use_reflection
                )

                if content:
                    chapter.content = content
                    chapter.word_count = len(content)
                    chapter.generated_at = datetime.now().isoformat()
                    results.append(f"✅ Chương {chapter.num}: {len(content)} từ")
                    ProjectManager.save_project(project)
                    chapter_name = f"Chương {chapter.num}: {chapter.title}"
                    generated_chapters.append(chapter_name)
                    yield "\n".join(results), gr.update(choices=generated_chapters, value=chapter_name)
                else:
                    results.append(f"❌ Chương {chapter.num}: {msg}")
                    yield "\n".join(results), gr.update(choices=generated_chapters)

            app_state.is_generating = False
            total_words = sum(ch.word_count for ch in chapters if ch.content)
            results.append(f"\n🎉 Hoàn thành! Tổng: {total_words} từ")
            yield "\n".join(results), gr.update(choices=generated_chapters)

        def on_chapter_select(chapter_title):
            if not app_state.current_project or not chapter_title:
                return ""
            for ch in app_state.current_project.chapters:
                if f"Chương {ch.num}: {ch.title}" == chapter_title:
                    return ch.content or ""
            return ""

        def on_stop():
            app_state.stop_requested = True
            return "⏸️ Đang dừng..."

        # Bind events
        suggest_title_btn.click(
            fn=on_suggest_title,
            inputs=[genre_dropdown, sub_genre_dropdown, suggest_title_prompt],
            outputs=[suggested_titles_radio, suggest_title_status, suggest_title_btn]
        )
        suggested_titles_radio.change(
            fn=on_title_select,
            inputs=[suggested_titles_radio],
            outputs=[title_input]
        )
        suggest_char_btn.click(
            fn=on_suggest_char,
            inputs=[title_input, genre_dropdown, sub_genre_dropdown, suggest_char_prompt, num_main_chars, num_sub_chars],
            outputs=[character_input, suggest_char_status, suggest_char_btn]
        )
        suggest_world_btn.click(
            fn=on_suggest_world,
            inputs=[title_input, genre_dropdown, sub_genre_dropdown, suggest_world_prompt],
            outputs=[world_input, suggest_world_status, suggest_world_btn]
        )
        suggest_plot_btn.click(
            fn=on_suggest_plot,
            inputs=[title_input, genre_dropdown, sub_genre_dropdown, character_input, world_input, suggest_plot_prompt],
            outputs=[plot_input, suggest_plot_status, suggest_plot_btn]
        )
        generate_outline_btn.click(
            fn=on_generate_outline,
            inputs=[title_input, genre_dropdown, sub_genre_dropdown, total_chapters, character_input, world_input, plot_input, custom_outline_prompt],
            outputs=[outline_output, outline_status],
            show_progress="full"
        )
        auto_generate_btn.click(
            fn=on_auto_generate,
            inputs=[title_input, genre_dropdown, sub_genre_dropdown, character_input, world_input, plot_input, outline_output, memory_type, memory_chapters, use_reflection_checkbox, create_style_dropdown],
            outputs=[generation_progress, chapter_selector]
        )
        chapter_selector.change(
            fn=on_chapter_select,
            inputs=[chapter_selector],
            outputs=[chapter_content_display]
        )
        stop_btn.click(fn=on_stop, outputs=[generation_progress])
        
        # Flow Enforcement Events
        title_input.change(
            fn=lambda t: [
                gr.update(interactive=bool(t)), 
                gr.update(interactive=bool(t)), 
                gr.update(interactive=bool(t))
            ],
            inputs=[title_input],
            outputs=[character_input, suggest_char_prompt, suggest_char_btn]
        )
        
        character_input.change(
            fn=lambda c: [
                gr.update(interactive=bool(c)), 
                gr.update(interactive=bool(c)), 
                gr.update(interactive=bool(c))
            ],
            inputs=[character_input],
            outputs=[world_input, suggest_world_prompt, suggest_world_btn]
        )
        
        world_input.change(
            fn=lambda w: [
                gr.update(interactive=bool(w)), 
                gr.update(interactive=bool(w)), 
                gr.update(interactive=bool(w))
            ],
            inputs=[world_input],
            outputs=[plot_input, suggest_plot_prompt, suggest_plot_btn]
        )
        
        plot_input.change(
            fn=lambda p: [
                gr.update(interactive=bool(p)), 
                gr.update(interactive=bool(p)),
                gr.update(interactive=bool(p))
            ],
            inputs=[plot_input],
            outputs=[total_chapters, custom_outline_prompt, generate_outline_btn]
        )
        
        outline_output.change(
            fn=lambda o: [
                gr.update(interactive=bool(o)),
                gr.update(interactive=bool(o))
            ],
            inputs=[outline_output],
            outputs=[auto_generate_btn, stop_btn]
        )
