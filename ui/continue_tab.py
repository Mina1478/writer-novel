import gradio as gr
from datetime import datetime
from locales.i18n import t
from services.project_manager import ProjectManager, list_project_titles
from services.novel_generator import Chapter
from core.state import app_state
import logging

logger = logging.getLogger(__name__)

def build_continue_tab():
    with gr.Tab(t("tabs.continue_tab")):
        gr.Markdown(f"### {t('continue_tab.header')}")

        with gr.Accordion("📂 1. Quản lý dự án", open=True):
            with gr.Row():
                with gr.Column(scale=4):
                    project_choices = list_project_titles()
                    continue_project_selector = gr.Dropdown(
                        choices=project_choices,
                        label=t("continue_tab.select_project"),
                        interactive=True
                    )
                with gr.Column(scale=1, min_width=100):
                    refresh_continue_btn = gr.Button(t("continue_tab.load_btn"), size="lg")

        with gr.Accordion("⚙️ 2. Thông tin & Cài đặt", open=False):
            with gr.Row():
                with gr.Column(scale=1):
                    continue_project_info = gr.Markdown(t("continue_tab.no_project_loaded"))
                with gr.Column(scale=2):
                    continue_outline_display = gr.Textbox(
                        label=t("continue_tab.outline_label"),
                        interactive=False, lines=6, max_lines=12,
                        value="Chưa tải dự án..."
                    )

            with gr.Row():
                with gr.Column(scale=1):
                    memory_type = gr.Radio(label="Cách nhớ ngữ cảnh", choices=["Toàn văn", "Tóm tắt"], value="Toàn văn")
                with gr.Column(scale=1):
                    memory_chapters = gr.Number(label="Số chương ghi nhớ", value=3, minimum=1, maximum=20, step=1)

            with gr.Row():
                continue_target_words = gr.Number(label=t("rewrite.target_words"), value=3000, minimum=100, maximum=50000, step=100)
                continue_custom_prompt = gr.Textbox(label=t("create.custom_prompt_label"), placeholder=t("create.custom_prompt_placeholder"), scale=2)

        with gr.Accordion("🚀 3. Sáng tác tiếp", open=False):
            with gr.Row():
                continue_chapter_num = gr.Number(label="Chương số", value=1, minimum=1, scale=1)
                continue_chapter_title = gr.Textbox(label="Tiêu đề chương", placeholder="Nhập tiêu đề chương...", scale=2)
            continue_chapter_desc = gr.Textbox(
                label="Nội dung/Dàn ý chương này",
                lines=3, placeholder="Nhập mô tả nội dung chương..."
            )
            with gr.Row():
                continue_generate_btn = gr.Button(t("continue_tab.continue_gen_btn"), variant="primary", size="lg", scale=1)
                continue_auto_btn = gr.Button("Tự động viết nốt các chương còn lại", variant="primary", size="lg", scale=2)
                continue_stop_btn = gr.Button("Dừng tự động", variant="stop", size="lg", scale=1)
            
            with gr.Row():
                with gr.Column(scale=1):
                    continue_status = gr.Textbox(label=t("continue_tab.gen_status"), interactive=False, lines=15)
                with gr.Column(scale=2):
                    continue_chapter_selector = gr.Dropdown(label="Danh sách chương đã tạo", choices=[], interactive=True)
                    continue_content_display = gr.Textbox(label="Nội dung chương", lines=15, interactive=False)

        def on_refresh_continue(current_title):
            titles = list_project_titles()
            if current_title in titles:
                info, next_ch, outline_text, chapter_choices = on_continue_project_select(current_title)
                return gr.update(choices=titles, value=current_title), info, next_ch, outline_text, gr.update(choices=chapter_choices, value=chapter_choices[-1] if chapter_choices else None)
            else:
                return gr.update(choices=titles, value=None), t("continue_tab.no_project_loaded"), 1, "Chưa tải dự án...", gr.update(choices=[], value=None)

        def on_continue_project_select(project_title):
            if not project_title:
                return t("continue_tab.no_project_loaded"), 1, "Chưa tải dự án...", []
            try:
                project_data = ProjectManager.get_project_by_title(project_title)
                if not project_data:
                    return f"❌ {t('continue_tab.project_not_found')}", 1, "Chưa tải dự án..."

                project_id = project_data.get("id")
                project, msg = ProjectManager.load_project(project_id)
                if project:
                    app_state.current_project = project
                    completed = project.get_completed_count()
                    total_chapters = len(project.chapters)
                    next_ch = completed + 1
                    percent = f"{(completed / total_chapters * 100):.1f}" if total_chapters > 0 else "0.0"
                    
                    # Handle None values safely
                    char_str = project.character_setting or ""
                    world_str = project.world_setting or ""
                    plot_str = project.plot_idea or ""

                    char_fmt = char_str[:100] + "..." if len(char_str) > 100 else char_str
                    world_fmt = world_str[:100] + "..." if len(world_str) > 100 else world_str
                    plot_fmt = plot_str[:100] + "..." if len(plot_str) > 100 else plot_str

                    # Logic fallback
                    info_template = t("continue_tab.info_template")
                    if isinstance(info_template, str) and '{' in info_template:
                        info = info_template.format(
                            title=project.title,
                            genre=project.genre,
                            completed=completed,
                            total=total_chapters,
                            words=project.get_total_words(),
                            percent=percent,
                            char=char_fmt,
                            world=world_fmt,
                            plot=plot_fmt
                        )
                    else:
                        info = f"### 📖 {project.title}\n**Thể loại**: {project.genre}\n**Tiến độ**: {percent}% ({completed}/{total_chapters} chương)\n**Tổng số từ**: {project.get_total_words()}\n💡 Chương tiếp theo: {next_ch}"
                    
                    # Format the outline list
                    outline_lines = []
                    for ch in project.chapters:
                        status = "✅" if getattr(ch, 'content', None) else "⬜"
                        outline_lines.append(f"{status} Chương {ch.num}: {ch.title} - {ch.desc}")
                    outline_text = "\n".join(outline_lines)
                    if not outline_text:
                        outline_text = "Dự án này chưa có dàn ý chi tiết."

                    # Generate chapter choices
                    chapter_choices = [f"Chương {ch.num}: {ch.title}" for ch in project.chapters if getattr(ch, 'content', None)]

                    return info, next_ch, outline_text, chapter_choices
                return f"❌ {msg}", 1, "Chưa tải dự án...", []
            except Exception as e:
                return f"❌ {str(e)}", 1, "Lỗi khi tải dàn ý", []

        def on_continue_chapter_select(chapter_title):
            if not chapter_title or not app_state.current_project:
                return ""
            for ch in app_state.current_project.chapters:
                if f"Chương {ch.num}: {ch.title}" == chapter_title:
                    return ch.content or ""
            return ""

        def on_continue_generate(project_title, ch_num, ch_title, ch_desc, target_words, custom_prompt, mem_type, mem_chaps):
            yield "⏳ Đang chuẩn bị dữ liệu...", "", gr.update(interactive=False), gr.update(), gr.update()
            if not app_state.current_project:
                yield f"❌ {t('continue_tab.no_project_selected')}", "", gr.update(interactive=True), gr.update(), gr.update()
                return

            gen = app_state.get_generator()
            project = app_state.current_project
            
            # Check if the requested chapter exists in the outline
            if not any(int(ch.num) == int(ch_num) for ch in project.chapters):
                yield f"❌ Lỗi: Chương {int(ch_num)} không có trong dàn ý. Tab này chỉ hỗ trợ hoàn thành nốt nội dung dàn ý đã có, không viết thêm chương mới.", "", gr.update(interactive=True), gr.update(), gr.update()
                return

            # Get completed past chapters mapped linearly
            all_past_chapters = [ch for ch in project.chapters if ch.num < int(ch_num) and getattr(ch, 'content', None)]
            mem_ch = int(mem_chaps) if mem_chaps else 3
            past_chapters = all_past_chapters[-mem_ch:] if len(all_past_chapters) > mem_ch else all_past_chapters

            prev_content = ""
            context_summary = ""

            if mem_type == "Toàn văn":
                prev_texts = [c.content for c in past_chapters]
                prev_content = "\n\n".join(prev_texts)
                prev_content = prev_content[-4000:]
            else:
                summaries = []
                for c in past_chapters:
                    if not hasattr(c, 'summary') or not c.summary:
                        yield f"⏳ Đang tạo tóm tắt ngữ cảnh cho chương {c.num}...", ""
                        summ, _ = gen.generate_chapter_summary(c.content, c.title)
                        c.summary = summ
                    if c.summary:
                        summaries.append(f"Chương {c.num} - {c.title}: {c.summary}")
                
                if summaries:
                    context_summary = "\n".join(summaries)
                
                if all_past_chapters:
                    prev_content = all_past_chapters[-1].content[-1500:]

            yield f"⏳ Đang sinh Chương {int(ch_num)}...", "", gr.update(interactive=False), gr.update(), gr.update()

            content, msg = gen.generate_chapter(
                chapter_num=int(ch_num), chapter_title=ch_title,
                chapter_desc=ch_desc, novel_title=project.title,
                character_setting=project.character_setting,
                world_setting=project.world_setting,
                plot_idea=project.plot_idea, genre=project.genre,
                sub_genres=project.sub_genres,
                previous_content=prev_content, context_summary=context_summary, custom_prompt=custom_prompt
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
                
                # Format the outline list
                outline_lines = []
                for ch in project.chapters:
                    status = "✅" if getattr(ch, 'content', None) else "⬜"
                    outline_lines.append(f"{status} Chương {ch.num}: {ch.title} - {ch.desc}")
                outline_text = "\n".join(outline_lines)
                
                # Update choices
                chapter_choices = [f"Chương {ch.num}: {ch.title}" for ch in project.chapters if getattr(ch, 'content', None)]
                selected_choice = f"Chương {int(ch_num)}: {ch_title}"
                
                yield f"✅ Chương {int(ch_num)} đã sinh ({len(content)} từ)", content, gr.update(interactive=True), gr.update(value=outline_text), gr.update(choices=chapter_choices, value=selected_choice)
            else:
                yield f"❌ {msg}", "", gr.update(interactive=True), gr.update(), gr.update()

        def on_continue_auto_generate(project_title, target_words, custom_prompt, mem_type, mem_chaps, progress=gr.Progress()):
            yield "⏳ Đang chuẩn bị dữ liệu...", "", gr.update(interactive=False), gr.update(interactive=False), gr.update(), gr.update()
            if not app_state.current_project:
                yield f"❌ {t('continue_tab.no_project_selected')}", "", gr.update(interactive=True), gr.update(interactive=True), gr.update(), gr.update()
                return

            gen = app_state.get_generator()
            project = app_state.current_project
            app_state.is_generating = True
            app_state.stop_requested = False

            blank_chapters = [ch for ch in project.chapters if not getattr(ch, 'content', None)]
            if not blank_chapters:
                yield "✅ Đã viết xong tất cả các chương trong dàn ý!", "", gr.update(interactive=True), gr.update(interactive=True), gr.update(), gr.update()
                return

            results = [f"📋 Phát hiện {len(blank_chapters)} chương chưa viết. Bắt đầu tự động tạo..."]
            yield "\n".join(results), "", gr.update(interactive=False), gr.update(interactive=False), gr.update(), gr.update()

            last_content = ""

            for i, ch in enumerate(blank_chapters):
                if app_state.stop_requested:
                    results.append("\n⚠️ Đã dừng sinh tự động!")
                    yield "\n".join(results), last_content, gr.update(interactive=True), gr.update(interactive=True), gr.update(), gr.update()
                    break

                results.append(f"\n✍️ Đang sinh Chương {ch.num}: {ch.title}...")
                progress((i + 1) / len(blank_chapters))
                yield "\n".join(results), last_content, gr.update(interactive=False), gr.update(interactive=False), gr.update(), gr.update()

                all_past_chapters = [past for past in project.chapters if past.num < ch.num and getattr(past, 'content', None)]
                mem_ch = int(mem_chaps) if mem_chaps else 3
                past_chapters = all_past_chapters[-mem_ch:] if len(all_past_chapters) > mem_ch else all_past_chapters

                prev_content = ""
                context_summary = ""

                if mem_type == "Toàn văn":
                    prev_texts = [c.content for c in past_chapters]
                    prev_content = "\n\n".join(prev_texts)
                    prev_content = prev_content[-4000:]
                else:
                    summaries = []
                    for c in past_chapters:
                        if not hasattr(c, 'summary') or not c.summary:
                            summ, _ = gen.generate_chapter_summary(c.content, c.title)
                            c.summary = summ
                        if c.summary:
                            summaries.append(f"Chương {c.num} - {c.title}: {c.summary}")
                    
                    if summaries:
                        context_summary = "\n".join(summaries)
                    
                    if all_past_chapters:
                        prev_content = all_past_chapters[-1].content[-1500:]

                content, msg = gen.generate_chapter(
                    chapter_num=int(ch.num), chapter_title=ch.title,
                    chapter_desc=ch.desc, novel_title=project.title,
                    character_setting=project.character_setting,
                    world_setting=project.world_setting,
                    plot_idea=project.plot_idea, genre=project.genre,
                    sub_genres=project.sub_genres,
                    previous_content=prev_content, context_summary=context_summary, custom_prompt=custom_prompt
                )

                if content:
                    ch.content = content
                    ch.word_count = len(content)
                    ch.generated_at = datetime.now().isoformat()
                    ProjectManager.save_project(project)
                    last_content = content
                    
                    # Format the outline list
                    outline_lines = []
                    for pr_ch in project.chapters:
                        status = "✅" if getattr(pr_ch, 'content', None) else "⬜"
                        outline_lines.append(f"{status} Chương {pr_ch.num}: {pr_ch.title} - {pr_ch.desc}")
                    outline_text = "\n".join(outline_lines)
                    
                    # Update choices
                    chapter_choices = [f"Chương {ch.num}: {ch.title}" for ch in project.chapters if getattr(ch, 'content', None)]
                    selected_choice = f"Chương {ch.num}: {ch.title}"
                    
                    results.append(f"✅ Chương {ch.num} hoàn tất ({len(content)} từ)")
                    yield "\n".join(results), content, gr.update(interactive=False), gr.update(interactive=False), gr.update(value=outline_text), gr.update(choices=chapter_choices, value=selected_choice)
                else:
                    results.append(f"❌ Lỗi ở chương {ch.num}: {msg}")
                    app_state.stop_requested = True
                    yield "\n".join(results), last_content, gr.update(interactive=True), gr.update(interactive=True), gr.update(), gr.update()
                    break

            app_state.is_generating = False
            results.append("\n🎉 Hoàn thành chuỗi viết tự động!")
            yield "\n".join(results), last_content, gr.update(interactive=True), gr.update(interactive=True), gr.update(), gr.update()

        def on_continue_stop():
            app_state.stop_requested = True
            return "⏸️ Đang dừng..."

        refresh_continue_btn.click(
            fn=on_refresh_continue, 
            inputs=[continue_project_selector], 
            outputs=[continue_project_selector, continue_project_info, continue_chapter_num, continue_outline_display, continue_chapter_selector]
        )
        continue_project_selector.change(
            fn=on_continue_project_select,
            inputs=[continue_project_selector],
            outputs=[continue_project_info, continue_chapter_num, continue_outline_display, continue_chapter_selector]
        )
        continue_chapter_selector.change(
            fn=on_continue_chapter_select,
            inputs=[continue_chapter_selector],
            outputs=[continue_content_display]
        )
        continue_generate_btn.click(
            fn=on_continue_generate,
            inputs=[continue_project_selector, continue_chapter_num, continue_chapter_title,
                    continue_chapter_desc, continue_target_words, continue_custom_prompt, memory_type, memory_chapters],
            outputs=[continue_status, continue_content_display, continue_generate_btn, continue_outline_display, continue_chapter_selector]
        )
        continue_auto_btn.click(
            fn=on_continue_auto_generate,
            inputs=[continue_project_selector, continue_target_words, continue_custom_prompt, memory_type, memory_chapters],
            outputs=[continue_status, continue_content_display, continue_auto_btn, continue_generate_btn, continue_outline_display, continue_chapter_selector],
            show_progress="full"
        )
        continue_stop_btn.click(
            fn=on_continue_stop,
            outputs=[continue_status]
        )
