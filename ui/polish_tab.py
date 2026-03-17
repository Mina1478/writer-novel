import gradio as gr
from locales.i18n import t
from utils.file_parser import parse_novel_file
from core.state import app_state
import logging

logger = logging.getLogger(__name__)

def build_polish_tab():
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

        def on_polish(text, custom_req):
            yield "⏳ Đang gọi AI xử lý... Vui lòng chờ.", gr.update(), gr.update(interactive=False)
            gen = app_state.get_generator()
            content, msg = gen.polish_text(text, custom_requirements=custom_req)
            if content:
                yield f"✅ {msg}", content, gr.update(interactive=True)
            else:
                yield f"❌ {msg}", gr.update(), gr.update(interactive=True)

        def on_polish_suggest(text, custom_req):
            yield "⏳ Đang gọi AI xử lý... Vui lòng chờ.", gr.update(), gr.update(interactive=False)
            gen = app_state.get_generator()
            content, msg = gen.polish_and_suggest(text, custom_requirements=custom_req)
            if content:
                yield f"✅ {msg}", content, gr.update(interactive=True)
            else:
                yield f"❌ {msg}", gr.update(), gr.update(interactive=True)

        polish_file_input.change(fn=on_polish_file_upload, inputs=[polish_file_input], outputs=[polish_input])
        polish_btn.click(fn=on_polish, inputs=[polish_input, polish_custom_req], outputs=[polish_status, polish_output, polish_btn])
        polish_suggest_btn.click(fn=on_polish_suggest, inputs=[polish_input, polish_custom_req], outputs=[polish_status, polish_output, polish_suggest_btn])
