# dzen-mcp

Локальный MCP-сервер на Python (`FastMCP` / `MCPServer` + `Playwright` async API) для автоматизации публикаций и аналитики каналов в **Яндекс Дзен** (`Дзен-студия`).

## Возможности (MCP-инструменты)

1. **`login_dzen(timeout_seconds: int = 150)`**
   Открывает видимое окно Chromium (`headless=False`), переходит на `https://dzen.ru`, отслеживает авторизацию (Яндекс ID / VK ID) и проверяет доступ к Дзен-студии. Сохраняет cookies и профиль браузера в `./dzen_profile` для последующих фоновых запусков.

2. **`create_dzen_article(title: str, content: str, image_path: str | None = None, publish: bool = False, headless: bool = True)`**
   Создаёт статью в Дзен-студии.
   - Поддерживает Markdown-вёрстку для редактора Дзена (Draft.js):
     - `## Заголовок` → подзаголовок `H2`
     - `> Цитата` → блок-цитата (`blockquote`)
     - `- Пункт` / `* Пункт` → маркированный список (`ul/li`)
     - `**жирный**` и `*курсив*` → переключение через `Ctrl+B` / `Ctrl+I`
   - Быстро вставляет длинные фрагменты текста через `keyboard.insert_text`, дожидается статуса автосохранения «Сохранено» и сохраняет черновик (`publish=False`) либо публикует статью (`publish=True`).
   - При передаче локального пути `image_path` загружает изображение через боковое меню `+` редактора и ждёт появления `<img>`.

3. **`create_dzen_post(text: str, image_paths: list[str] | None = None, publish: bool = False, headless: bool = True)`**
   Создаёт короткий «Пост» в Дзен-студии, при необходимости прикрепляет локальные изображения `image_paths` и сохраняет черновик или публикует.

4. **`dump_channel_articles(slug: str, days: int = 60, output_dir: str | None = None)`**
   Выгружает список статей и просмотров **любого публичного канала Дзена** (поддерживает как `worldlord`, так и `id/<hex>`).
   - Работает в **отдельном изолированном браузере** без `dzen_profile` (не блокирует основную сессию студии и не использует ваш аккаунт).
   - Читает хронологическую вкладку `article` из `/api/v3/launcher/export` с фильтрацией по дате из `publication_object_id`.
   - Сохраняет файл `<slug>_статьи_<days>дней.txt` в папку `./exports/` (формат `Заголовок = просмотры`) и возвращает сводку с топ-5 самых популярных заголовков.

## Структура проекта

- `server.py` — MCP-сервер и реализация всех 4 инструментов.
- `dzen_mcp/selectors.py` — вынесенные CSS/XPath-селекторы Дзен-студии (удобно обновлять при изменении вёрстки).
- `prompts/` — промпты аналитики заголовков (`02_Карта-заголовков.md`) и сборки редполитики (`03_Сборщик-системы.md`).
- `GEMINI.md` — регламент работы ИИ-агента с контентом и пайплайн подготовки статей.
- `pyproject.toml` — метаданные и зависимости (`mcp[cli]`, `playwright`).

## Установка

Требуется Python **3.10+**.

### Вариант 1: через `uv`

```bash
git clone https://github.com/Strenchnow/MCP-dzen.git
cd MCP-dzen

uv venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS / Linux:
# source .venv/bin/activate

uv pip install "mcp[cli]" playwright
uv run playwright install chromium
```

### Вариант 2: через стандартный `.venv`

```bash
git clone https://github.com/Strenchnow/MCP-dzen.git
cd MCP-dzen

python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
# source .venv/bin/activate

pip install --upgrade pip
pip install "mcp[cli]" playwright
playwright install chromium
```

## Подключение к MCP-клиенту (`mcp_config.json`)

Добавьте блок в проектный `.agents/mcp_config.json` или глобальный `~/.gemini/config/mcp_config.json` (укажите абсолютный путь к Python из `.venv` и к `server.py`):

**Windows:**
```json
{
  "mcpServers": {
    "dzen-mcp": {
      "command": "D:\\dzen-mcp\\.venv\\Scripts\\python.exe",
      "args": [
        "D:\\dzen-mcp\\server.py"
      ]
    }
  }
}
```

**macOS / Linux:**
```json
{
  "mcpServers": {
    "dzen-mcp": {
      "command": "/path/to/MCP-dzen/.venv/bin/python",
      "args": [
        "/path/to/MCP-dzen/server.py"
      ]
    }
  }
}
```

## Первый запуск

1. Перезапустите / обновите (`Refresh`) MCP-сервер в настройках клиента.
2. Вызовите инструмент `login_dzen` и войдите в свой аккаунт Яндекса в открывшемся окне Chromium.
3. После сохранения профиля можно вызывать `create_dzen_article`, `create_dzen_post` и `dump_channel_articles` в режиме `headless=True`.

## Безопасность

Папка `dzen_profile/` хранит cookies и активную сессию вашего аккаунта Дзен. Она добавлена в `.gitignore` — **никогда не публикуйте её в репозиторий**.
