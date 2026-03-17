import gradio as gr
from locales.i18n import t
from services.project_manager import ProjectManager, list_project_titles
from utils.exporter import export_to_docx, export_to_txt, export_to_markdown, export_to_html
import logging

logger = logging.getLogger(__name__)

def build_export_tab():
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
