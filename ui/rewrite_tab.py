import gradio as gr
from locales.i18n import t
from services.novel_generator import get_preset_templates
from utils.file_parser import parse_novel_file
from core.state import app_state
import logging

logger = logging.getLogger(__name__)

def build_rewrite_tab():
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
            yield "⏳ Đang gọi AI xử lý... Vui lòng chờ.", gr.update(), gr.update(interactive=False)
            instructions = get_preset_templates().get(style, "")
            gen = app_state.get_generator()
            content, msg = gen.rewrite_paragraph(text, instructions)
            if content:
                yield f"✅ {msg}", content, gr.update(interactive=True)
            else:
                yield f"❌ {msg}", gr.update(), gr.update(interactive=True)

        rewrite_file_input.change(fn=on_file_upload, inputs=[rewrite_file_input], outputs=[rewrite_input])
        rewrite_btn.click(fn=on_rewrite, inputs=[rewrite_input, rewrite_style], outputs=[rewrite_status, rewrite_output, rewrite_btn])
