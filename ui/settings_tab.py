import gradio as gr
from locales.i18n import t
from core.config import get_config, API_PROVIDERS
from core.config_api import ConfigAPIManager
from services.api_client import get_api_client, reinit_api_client
from services.novel_generator import get_cache_size, list_generation_caches, clear_generation_cache
from services.genre_manager import GenreManager
from services.sub_genre_manager import SubGenreManager
from services.style_manager import StyleManager
from core.state import app_state

def build_settings_tab():
    from core.auth import has_password, verify_password, set_password
    with gr.Tab(t("tabs.settings")):
        gr.Markdown(f"### {t('settings.header')}")

        is_locked = has_password()
        
        with gr.Column(visible=is_locked) as login_col:
            gr.Markdown("#### 🔒 Bảng điều khiển bảo mật")
            gr.Markdown("Cài đặt hệ thống đang được bảo vệ bằng mật khẩu.")
            with gr.Row():
                login_pwd = gr.Textbox(label="Vui lòng nhập mật khẩu", type="password", scale=4)
                login_btn = gr.Button("Xác nhận", variant="primary", scale=1)
            login_msg = gr.Markdown("")

        with gr.Tabs(visible=not is_locked) as settings_tabs:
            def on_login(pwd):
                if verify_password(pwd):
                    return gr.update(visible=False), gr.update(visible=True), ""
                else:
                    return gr.update(), gr.update(), "❌ Mật khẩu không chính xác!"
                    
            login_btn.click(fn=on_login, inputs=[login_pwd], outputs=[login_col, settings_tabs, login_msg])
            login_pwd.submit(fn=on_login, inputs=[login_pwd], outputs=[login_col, settings_tabs, login_msg])
            
            # Sub-tab: Quản lý giao diện API
            with gr.Tab(t("settings.tab_backends")):
                gr.Markdown(f"### {t('settings.backends_header')}")

                def get_backends_display():
                    try:
                        result = ConfigAPIManager.list_backends()
                        if result["success"] and result["data"]:
                            lines = [f"#### 📋 {len(result['data'])} backend(s)\n"]
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

                with gr.Row():
                    # Cột trái: Quản lý danh sách
                    with gr.Column(scale=1):
                        with gr.Group():
                            backends_display = gr.Markdown("...")
                            api_refresh_btn = gr.Button(t("settings.refresh_list"), size="sm")
                            
                        with gr.Group():
                            gr.Markdown(f"#### {t('settings.test_manage_header')}")
                            with gr.Row():
                                test_name_input = gr.Textbox(label=t("settings.test_backend_name"), placeholder=t("settings.test_backend_placeholder"), scale=2)
                                api_test_btn = gr.Button(t("settings.test_btn"), variant="secondary", scale=1)
                            test_result = gr.Textbox(label=t("settings.test_result"), interactive=False)

                            gr.Markdown("---")
                            with gr.Row():
                                delete_name_input = gr.Textbox(label=t("settings.delete_backend_name"), placeholder=t("settings.delete_backend_placeholder"), scale=2)
                                api_delete_btn = gr.Button(t("settings.delete_btn"), variant="stop", scale=1)

                    # Cột phải: Form thay đổi
                    with gr.Column(scale=2):
                        with gr.Group():
                            gr.Markdown(f"#### Thay đổi cấu hình ({t('settings.add_backend_header')})")
                            
                            provider_names = [API_PROVIDERS[k]["name"] for k in API_PROVIDERS]
                            
                            with gr.Row():
                                manage_backend_select = gr.Dropdown(
                                    choices=[b['name'] for b in ConfigAPIManager.list_backends().get("data", [])],
                                    label="Chọn cấu hình để chỉnh sửa (bỏ trống để thêm mới)",
                                    interactive=True,
                                    scale=4
                                )
                                manage_backend_btn = gr.Button("Chọn", variant="secondary", scale=1)

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
                                api_key_input = gr.Textbox(label=t("settings.api_key"), placeholder=t("settings.api_key_placeholder"), type="text")

                            with gr.Row():
                                api_model_input = gr.Textbox(label=t("settings.model_name"), placeholder=t("settings.model_name_placeholder"))
                                api_timeout_input = gr.Slider(minimum=5, maximum=600, value=120, step=5, label=t("settings.timeout"))

                            with gr.Row():
                                api_save_btn = gr.Button(t("settings.add_btn"), variant="primary")
                                api_update_btn = gr.Button("Cập nhật thay đổi", variant="secondary")

                            api_status = gr.Textbox(label=t("settings.operation_result"), interactive=False)

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
                    if not name.strip():
                        return "❌ Vui lòng nhập tên giao diện", get_backends_display(), gr.update()
                        
                    result = ConfigAPIManager.add_backend(name, btype, url, key, model, int(timeout))
                    reinit_api_client()
                    app_state.generator = None
                    new_choices = [b['name'] for b in ConfigAPIManager.list_backends().get("data", [])]
                    return result["message"], get_backends_display(), gr.update(choices=new_choices)
                    
                def on_api_update(old_name, new_name, btype, url, key, model, timeout):
                    if not old_name:
                        return "❌ Vui lòng chọn một cấu hình để chỉnh sửa trước", get_backends_display(), gr.update()
                    if not new_name.strip():
                        return "❌ Vui lòng nhập tên giao diện", get_backends_display(), gr.update()
                        
                    # Handle updating the existing backend with new details
                    # If name was changed, it requires updating that as well but the update_backend method modifies existing object's properties in place based on its previous name
                    result = ConfigAPIManager.update_backend(
                        old_name, 
                        name=new_name.strip(), 
                        type=btype, 
                        base_url=url, 
                        api_key=key, 
                        model=model, 
                        timeout=int(timeout)
                    )
                    
                    reinit_api_client()
                    app_state.generator = None
                    new_choices = [b['name'] for b in ConfigAPIManager.list_backends().get("data", [])]
                    # if name changed, update the dropdown selected value to the new name, otherwise clear it
                    new_val = new_name.strip() if result["success"] else old_name
                    
                    return result["message"], get_backends_display(), gr.update(choices=new_choices, value=new_val)
                    
                def on_backend_select(selected_name):
                    print(f"DEBUG: on_backend_select triggered with: {selected_name}")
                    if not selected_name:
                        return gr.update(value=""), gr.update(value="openai"), gr.update(value=""), gr.update(value=""), gr.update(value=""), gr.update(value=120)
                        
                    backends = ConfigAPIManager.list_backends().get("data", [])
                    for b in backends:
                        if b["name"] == selected_name:
                            return (
                                gr.update(value=b.get("name", "")), 
                                gr.update(value=b.get("type", "openai")), 
                                gr.update(value=b.get("base_url", "")), 
                                gr.update(value=b.get("api_key", "")), 
                                gr.update(value=b.get("model", "")), 
                                gr.update(value=b.get("timeout", 120))
                            )
                    return gr.update(value=""), gr.update(value="openai"), gr.update(value=""), gr.update(value=""), gr.update(value=""), gr.update(value=120)

                def on_api_delete(name):
                    result = ConfigAPIManager.delete_backend(name)
                    reinit_api_client()
                    app_state.generator = None
                    new_choices = [b['name'] for b in ConfigAPIManager.list_backends().get("data", [])]
                    return result["message"], get_backends_display(), gr.update(choices=new_choices)

                api_provider_dropdown.change(
                    fn=on_provider_select,
                    inputs=[api_provider_dropdown],
                    outputs=[api_url_input, api_model_input, api_name_input]
                )
                
                manage_backend_btn.click(
                    fn=on_backend_select,
                    inputs=[manage_backend_select],
                    outputs=[api_name_input, api_type_dropdown, api_url_input, api_key_input, api_model_input, api_timeout_input]
                )
                
                api_save_btn.click(
                    fn=on_api_save,
                    inputs=[api_name_input, api_type_dropdown, api_url_input, api_key_input, api_model_input, api_timeout_input],
                    outputs=[api_status, backends_display, manage_backend_select]
                )
                
                api_update_btn.click(
                    fn=on_api_update,
                    inputs=[manage_backend_select, api_name_input, api_type_dropdown, api_url_input, api_key_input, api_model_input, api_timeout_input],
                    outputs=[api_status, backends_display, manage_backend_select]
                )
                
                api_test_btn.click(fn=on_api_test, inputs=[test_name_input], outputs=[test_result])
                api_delete_btn.click(fn=on_api_delete, inputs=[delete_name_input], outputs=[api_status, backends_display, manage_backend_select])
                
                def force_refresh_backends():
                    choices = [b['name'] for b in ConfigAPIManager.list_backends().get("data", [])]
                    return get_backends_display(), gr.update(choices=choices)
                    
                api_refresh_btn.click(fn=force_refresh_backends, outputs=[backends_display, manage_backend_select])

            # Sub-tab: Tham số sinh
            with gr.Tab(t("settings.tab_params")):
                with gr.Group():
                    gr.Markdown(f"#### {t('settings.params_header')}")

                    config = get_config()
                    gen_config = config.generation

                    with gr.Row():
                        param_temperature = gr.Slider(minimum=0.1, maximum=2.0, value=gen_config.temperature, step=0.1, label=t("settings.temperature_label"), info=t("settings.temperature_info"))
                        param_top_p = gr.Slider(minimum=0.1, maximum=1.0, value=gen_config.top_p, step=0.05, label="Top P", info=t("settings.top_p_info"))

                    with gr.Row():
                        param_max_tokens = gr.Slider(minimum=100, maximum=100000, value=gen_config.max_tokens, step=100, label="Max Tokens", info=t("settings.max_tokens_info"))
                        param_chapter_words = gr.Slider(minimum=500, maximum=65536, value=gen_config.chapter_target_words, step=500, label=t("settings.chapter_target_words"))

                    with gr.Row():
                        param_writing_style = gr.Dropdown(choices=StyleManager.get_style_names(), value=gen_config.writing_style, label=t("settings.writing_style"), allow_custom_value=True)
                        param_writing_tone = gr.Dropdown(choices=t("settings.tones"), value=gen_config.writing_tone, label=t("settings.tone_label"), allow_custom_value=True)

                    with gr.Row():
                        param_char_dev = gr.Dropdown(choices=t("settings.char_dev_options"), value=gen_config.character_development, label=t("settings.char_dev_label"), allow_custom_value=True)
                        param_plot_complexity = gr.Dropdown(choices=t("settings.plot_complexity_options"), value=gen_config.plot_complexity, label=t("settings.plot_complexity_label"), allow_custom_value=True)

                    save_params_btn = gr.Button(t("settings.save_params_btn"), variant="primary")
                    params_status = gr.Textbox(label=t("settings.save_status"), interactive=False)

                def on_save_params(temp, top_p, max_tokens, chapter_words, style, tone, chardev, plotcomp):
                    cfg = get_config()
                    success, msg = cfg.update_generation_config(
                        temperature=temp, top_p=top_p,
                        max_tokens=int(max_tokens),
                        chapter_target_words=int(chapter_words),
                        writing_style=style,
                        writing_tone=tone,
                        character_development=chardev,
                        plot_complexity=plotcomp
                    )
                    if success:
                        app_state.generator = None
                        return f"✅ {msg}"
                    return f"❌ {msg}"

                save_params_btn.click(
                    fn=on_save_params,
                    inputs=[param_temperature, param_top_p, param_max_tokens, param_chapter_words, param_writing_style, param_writing_tone, param_char_dev, param_plot_complexity],
                    outputs=[params_status]
                )

            # Sub-tab: Bộ nhớ đệm
            with gr.Tab(t("settings.tab_cache")):
                with gr.Group():
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
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown(f"#### {t('settings.genre_desc')}")
                        genre_select = gr.Dropdown(
                            choices=GenreManager.get_genre_names(),
                            label=t("settings.genre_select"),
                            interactive=True
                        )

                    with gr.Column(scale=2):
                        with gr.Group():
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
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown(f"#### {t('settings.sub_genre_desc')}")
                        sub_genre_select = gr.Dropdown(
                            choices=SubGenreManager.get_sub_genre_names(),
                            label=t("settings.sub_genre_select"),
                            interactive=True
                        )

                    with gr.Column(scale=2):
                        with gr.Group():
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

            # Sub-tab: Quản lý phong cách viết
            with gr.Tab("Quản lý phong cách viết"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("#### Quản lý danh sách các phong cách viết để AI hiểu và áp dụng")
                        style_select = gr.Dropdown(
                            choices=StyleManager.get_style_names(),
                            label="Chọn phong cách",
                            interactive=True
                        )

                    with gr.Column(scale=2):
                        with gr.Group():
                            style_name_input = gr.Textbox(label="Tên phong cách", placeholder="Ví dụ: Mượt mà tự nhiên...")
                            style_desc_input = gr.Textbox(label="Mô tả phong cách", placeholder="Hướng dẫn chi tiết cách viết...", lines=3)

                            with gr.Row():
                                style_add_btn = gr.Button("Thêm phong cách", variant="primary")
                                style_update_btn = gr.Button("Cập nhật", variant="secondary")
                                style_delete_btn = gr.Button("Xóa", variant="stop")

                            style_op_status = gr.Textbox(label="Trạng thái thao tác", interactive=False)

                def on_style_select(name):
                    if name:
                        desc = StyleManager.get_style_description(name)
                        return name, desc or ""
                    return "", ""

                def on_style_add(name, desc):
                    if not name.strip():
                        return "❌ Tên phong cách không được trống", gr.update()
                    success = StyleManager.add_style(name.strip(), desc.strip())
                    if success:
                        new_choices = StyleManager.get_style_names()
                        return "✅ Đã thêm phong cách mới", gr.update(choices=new_choices)
                    return "❌ Tên phong cách đã tồn tại hoặc lỗi", gr.update()

                def on_style_update(old_name, new_name, desc):
                    if not old_name:
                        return "❌ Vui lòng chọn phong cách", gr.update()
                    success = StyleManager.update_style(old_name, new_name.strip(), desc.strip())
                    if success:
                        new_choices = StyleManager.get_style_names()
                        return "✅ Đã cập nhật phong cách", gr.update(choices=new_choices)
                    return "❌ Cập nhật thất bại", gr.update()

                def on_style_delete(name):
                    if not name:
                        return "❌ Vui lòng chọn phong cách", gr.update()
                    success = StyleManager.delete_style(name)
                    if success:
                        new_choices = StyleManager.get_style_names()
                        return "✅ Đã xóa phong cách", gr.update(choices=new_choices)
                    return "❌ Xóa thất bại", gr.update()

                style_select.change(fn=on_style_select, inputs=[style_select], outputs=[style_name_input, style_desc_input])
                style_add_btn.click(fn=on_style_add, inputs=[style_name_input, style_desc_input], outputs=[style_op_status, style_select])
                style_update_btn.click(fn=on_style_update, inputs=[style_select, style_name_input, style_desc_input], outputs=[style_op_status, style_select])
                style_delete_btn.click(fn=on_style_delete, inputs=[style_select], outputs=[style_op_status, style_select])

            # Sub-tab: Bảo mật
            with gr.Tab("Bảo mật"):
                gr.Markdown("#### Quản lý Mật khẩu cho phần Cài đặt hệ thống")
                gr.Markdown("Nếu để trống mật khẩu mới, hệ thống sẽ gỡ bỏ bảo vệ mật khẩu.")
                
                with gr.Row():
                    with gr.Column(scale=1):
                        security_old_pwd = gr.Textbox(label="Mật khẩu cũ (để trống nếu chưa cài)", type="password")
                        security_new_pwd = gr.Textbox(label="Mật khẩu mới", type="password")
                        security_confirm_pwd = gr.Textbox(label="Xác nhận mật khẩu mới", type="password")
                
                        security_save_btn = gr.Button("Lưu mật khẩu", variant="primary")
                        security_status = gr.Textbox(label="Trạng thái", interactive=False)
                
                def on_security_save(old_pwd, new_pwd, confirm_pwd):
                    if new_pwd != confirm_pwd:
                        return "❌ Mật khẩu xác nhận không khớp!"
                    success, msg = set_password(old_pwd, new_pwd)
                    return ("✅ " if success else "❌ ") + msg
                    
                security_save_btn.click(fn=on_security_save, inputs=[security_old_pwd, security_new_pwd, security_confirm_pwd], outputs=[security_status])

