# AI Novel Generator Pro v4.0

## 📖 Documentation / Tài liệu / 文档

| Language | Link |
|----------|------|
| 🇨🇳 中文 (Chinese) | [locales/CN/使用说明.md](locales/CN/使用说明.md) |
| 🇻🇳 Tiếng Việt (Vietnamese) | [locales/VI/使用说明.md](locales/VI/使用说明.md) |

## 🌐 i18n (Internationalization)

The application supports multiple languages. Language files are stored in the `locales/` directory:

```
locales/
├── i18n.py               # i18n helper module
├── __init__.py            # Package init
├── CN/
│   ├── messages.json      # UI strings in Chinese (default)
│   └── 使用说明.md         # Documentation in Chinese
└── VI/
    ├── messages.json      # UI strings in Vietnamese
    └── 使用说明.md         # Documentation in Vietnamese
```

### Switching Language

Set the `APP_LANGUAGE` environment variable before starting the app:

```bash
# Chinese (default)
python app.py

# Vietnamese
set APP_LANGUAGE=VI
python app.py
```

### Adding a New Language

1. Create a new directory under `locales/` (e.g. `locales/EN/`)
2. Copy `locales/CN/messages.json` as a template
3. Translate all values in the JSON file
4. Set `APP_LANGUAGE=EN` and start the app
