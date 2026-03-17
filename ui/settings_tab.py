import gradio as gr
from locales.i18n import t
from core.config import get_config, API_PROVIDERS
from core.config_api import ConfigAPIManager
from services.api_client import get_api_client, reinit_api_client
from services.novel_generator import get_cache_size, list_generation_caches, clear_generation_cache
from services.genre_manager import GenreManager
from services.sub_genre_manager import SubGenreManager
from core.state import app_state

def build_settings_tab():
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
                    yield "⏳ Đang kiểm tra kết nối API... Vui lòng chờ."
                    result = ConfigAPIManager.test_backend(name)
                    yield result["message"]

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

                        return f"### Thống kê bộ nhớ đệm\n- **API Cache**: {stats['total_entries']}/{stats['max_size']} ({stats['usage_rate']:.1f}%)\n- **Generation Cache**: {len(gen_caches)} files ({gen_size_val / 1024:.1f} KB)"
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
