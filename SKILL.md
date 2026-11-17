---
name: yandex-dzen-autopilot
description: End-to-end Yandex Dzen (Dzen Studio) content automation, competitor analysis, anti-slop writing, and draft publishing via MCP server. Use when the user asks to analyze a Yandex Dzen channel, scrape competitor headlines and views, build a title map or editorial style guide, write Dzen articles/posts without AI clichés, or save/publish drafts in Dzen Studio. Активируй для работы с Яндекс Дзен, Дзен-студией, парсинга каналов конкурентов, создания карты заголовков, редполитики ниши и автопубликации статей или постов.
---

# Yandex Dzen Autopilot (`yandex-dzen-autopilot`)

Autonomous pipeline for competitor channel research, editorial system extraction, anti-slop article drafting, and Playwright-powered publishing to Yandex Dzen Studio via the `dzen-mcp` MCP server.

## Core Rules (Mandatory)

1. **Never generate AI images or covers.** Dzen penalizes AI-generated illustrations.
   - Pass `image_path` / `image_paths` **only** when the user explicitly provides a path to an existing local file.
   - Otherwise, always call `create_dzen_article(..., image_path=None)` and `create_dzen_post(..., image_paths=None)`.
2. **Default to Drafts.** Always save articles with `publish=False` unless the user explicitly asks to publish live (`publish=True`).
3. **Strict Anti-Slop & Dzen Typography.** Never use long em-dashes (`—`). Use «guillemet» quotes, short lively paragraphs (1–2 sentences), varied sentence rhythm, and zero AI clichés.

---

## Autonomous 5-Step Workflow

### Step 1 — Verify Authentication (`login_dzen`)
- Before creating articles or posts, ensure an active Dzen Studio session exists in `./dzen_profile`.
- If `create_dzen_article` or `create_dzen_post` reports an unauthenticated session or Passport redirect, call `login_dzen()` so the user can sign in inside the opened Chromium window.
- Never run multiple tools that access `dzen_profile` concurrently; wait for any open browser window to close first.

### Step 2 — Competitor Channel Scraping (`dump_channel_articles`)
- When the user provides a competitor channel slug (e.g. `worldlord` or `id/<hex>`) and timeframe (`days`, default `60`), call `dump_channel_articles(slug, days)`.
- This runs in an isolated headless Chromium context without touching `dzen_profile`, parses the chronological `article` tab via `/api/v3/launcher/export`, and saves `<slug>_статьи_<days>дней.txt` (`Title = views`) into `./exports/`.

### Step 3 — Build Title Map (`prompts/02_Карта-заголовков.md`)
- Read `prompts/02_Карта-заголовков.md` and the exported file from `./exports/<slug>_статьи_<days>дней.txt`.
- Execute the two-pass analysis strictly following all 9 required sections (including the standalone Section 8 «Кит генерации»).
- Save the resulting map to `./knowledge/<slug>_map.md`.

### Step 4 — Build Niche Editorial System (`prompts/03_Сборщик-системы.md`)
- Using 1–3 full sample articles and `./knowledge/<slug>_map.md`, run the 3-pass methodology from `prompts/03_Сборщик-системы.md`.
- Generate and save three files inside `./knowledge/<niche>/`:
  - `ИНСТРУКЦИЯ.md`
  - `СТИЛЬ.md`
  - `СТРУКТУРА.md`

### Step 5 — Write & Save Anti-Slop Draft (`create_dzen_article`)
- Draft the article using the niche `ИНСТРУКЦИЯ.md`, `СТИЛЬ.md`, and `СТРУКТУРА.md` (if available) plus Dzen formatting rules:
  - **Dashes:** no em-dash `—`; limit en-dash `–` to 3–5 per article (dialogues/ranges); replace dashes with commas, periods, conjunctions, or colons.
  - **Quotes:** only «ёлочки».
  - **Rhythm:** short 1–2 sentence paragraphs; mix short, medium, and long sentences; start 20–30% of sentences with conjunctions.
  - **Anti-slop:** replace AI/bureaucratic markers («однако» → «но», «затем» → «потом», «является» → «это», «данный» → «этот», «осуществлять» → «делать»; remove «стоит отметить», «в современном мире», etc.).
  - **Markdown structure for Dzen Draft.js editor:**
    - `## ` for H2 subheadings
    - `> ` for blockquotes
    - `- ` for bulleted lists
    - `**...**` for bold emphasis and `*...*` for italics
- Call `create_dzen_article(title=..., content=..., image_path=None, publish=False)` and return the direct draft URL to the user for review.
