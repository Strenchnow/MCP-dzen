"""Local MCP server for automating Yandex Dzen publications via Playwright."""

from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:  # mcp < 2.0
    from mcp.server.fastmcp import FastMCP
from playwright.async_api import (
    BrowserContext,
    Locator,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from dzen_mcp.selectors import SELECTORS, URLS

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR / "dzen_profile"
EXPORTS_DIR = BASE_DIR / "exports"

REALISTIC_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru', 'en-US', 'en'] });
"""

mcp = FastMCP("dzen-mcp")
_CONTEXT_LOCK = asyncio.Lock()
_LOCK_FILENAMES = ("SingletonLock", "SingletonSocket", "SingletonCookie", "lockfile")


def _cleanup_stale_profile_locks() -> None:
    """Remove stale Chromium singleton lock files or raise if a live browser holds the profile."""
    for name in _LOCK_FILENAMES:
        lock_path = PROFILE_DIR / name
        if not lock_path.exists() and not lock_path.is_symlink():
            continue
        try:
            lock_path.unlink()
        except PermissionError as exc:
            raise RuntimeError(
                f"Browser profile '{PROFILE_DIR}' is currently locked by another running browser window. "
                "Close that browser window and try again."
            ) from exc
        except OSError:
            pass


@asynccontextmanager
async def _open_dzen_context(headless: bool) -> AsyncIterator[tuple[BrowserContext, Page]]:
    """Launch a persistent Chromium context with anti-detection settings."""
    if _CONTEXT_LOCK.locked():
        raise RuntimeError(
            "Another dzen-mcp browser session is already active. "
            "Wait for it to finish or close the open browser window."
        )

    async with _CONTEXT_LOCK:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        _cleanup_stale_profile_locks()
        pw: Playwright = await async_playwright().start()
        context: BrowserContext | None = None
        try:
            try:
                context = await pw.chromium.launch_persistent_context(
                    user_data_dir=str(PROFILE_DIR),
                    headless=headless,
                    user_agent=REALISTIC_USER_AGENT,
                    locale="ru-RU",
                    viewport={"width": 1366, "height": 900},
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                    ignore_default_args=["--enable-automation"],
                )
            except Exception as exc:
                msg = str(exc)
                if any(
                    token in msg
                    for token in (
                        "ProcessSingleton",
                        "SingletonLock",
                        "already in use",
                        "TargetClosedError",
                        "Target page, context or browser has been closed",
                    )
                ):
                    raise RuntimeError(
                        f"Failed to open browser profile '{PROFILE_DIR}': it is locked by another "
                        "Chromium process. Close any open dzen-mcp browser window and try again."
                    ) from exc
                raise

            await context.add_init_script(STEALTH_INIT_SCRIPT)
            page = context.pages[0] if context.pages else await context.new_page()
            yield context, page
        finally:
            if context is not None:
                try:
                    await context.close()
                except Exception:
                    pass
            await pw.stop()


async def _find_first_locator(
    page: Page,
    selectors: list[str] | str,
    timeout_ms: int = 8000,
    state: str = "visible",
) -> Locator | None:
    """Return the first locator from candidate selectors that reaches the desired state."""
    candidates = [selectors] if isinstance(selectors, str) else selectors
    per_selector_timeout = max(1200, timeout_ms // max(1, len(candidates)))
    for selector in candidates:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state=state, timeout=per_selector_timeout)
            return locator
        except PlaywrightTimeoutError:
            continue
    return None


async def _require_locator(
    page: Page,
    group: str,
    key: str,
    timeout_ms: int = 10000,
    state: str = "visible",
) -> Locator:
    """Find a required element from SELECTORS[group][key] or raise a descriptive error."""
    locator = await _find_first_locator(page, SELECTORS[group][key], timeout_ms=timeout_ms, state=state)
    if locator is None:
        raise RuntimeError(
            f"Could not find element '{group}.{key}' on {page.url}. "
            "Dzen layout may have changed — update selectors.py."
        )
    return locator


async def _dismiss_popups(page: Page) -> None:
    """Close optional onboarding/promo popups if they appear."""
    popup_btn = await _find_first_locator(page, SELECTORS["studio"]["dismiss_popup"], timeout_ms=1500)
    if popup_btn is not None:
        try:
            await popup_btn.click(timeout=2000)
        except Exception:
            pass


async def _ensure_authenticated(page: Page) -> None:
    """Verify the persistent profile has an active Dzen session."""
    await page.goto(URLS["editor"], wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(2000)

    if URLS["passport_host"] in page.url:
        raise RuntimeError(
            "Not logged in to Yandex Dzen (redirected to Passport). "
            "Run the `login_dzen` tool first to sign in."
        )

    login_btn = await _find_first_locator(page, SELECTORS["auth"]["login_required"], timeout_ms=2000)
    logged_in = await _find_first_locator(page, SELECTORS["auth"]["logged_in_marker"], timeout_ms=5000)
    if logged_in is None and login_btn is not None:
        raise RuntimeError(
            "Dzen session is not authenticated. Run the `login_dzen` tool first."
        )


async def _click_and_follow_new_page(context: BrowserContext, page: Page, locator: Locator) -> Page:
    """Click a trigger that may open the editor in the same tab or a new tab."""
    existing_pages = set(context.pages)
    await locator.click()
    await page.wait_for_timeout(1500)
    new_pages = [p for p in context.pages if p not in existing_pages]
    if new_pages:
        target = new_pages[-1]
        await target.wait_for_load_state("domcontentloaded")
        return target
    return page


async def _count_preview_images(page: Page, group: str) -> int:
    """Count currently rendered preview images in the editor."""
    selectors = SELECTORS[group].get("uploaded_image_preview", [])
    if isinstance(selectors, str):
        selectors = [selectors]
    total = 0
    for sel in selectors:
        try:
            total = max(total, await page.locator(sel).count())
        except Exception:
            continue
    return total


async def _upload_images(
    page: Page,
    image_paths: list[Path],
    group: str,
) -> None:
    """Upload one or more local image files into the Dzen editor and wait for <img>."""
    for img_path in image_paths:
        before_count = await _count_preview_images(page, group)
        file_input = await _find_first_locator(
            page,
            SELECTORS[group]["image_upload_input"],
            timeout_ms=2500,
            state="attached",
        )
        if file_input is None and "side_image_button" in SELECTORS[group]:
            side_btn = await _find_first_locator(
                page,
                SELECTORS[group]["side_image_button"],
                timeout_ms=3000,
            )
            if side_btn is not None:
                await side_btn.click()
                file_input = await _find_first_locator(
                    page,
                    SELECTORS[group]["image_upload_input"],
                    timeout_ms=3000,
                    state="attached",
                )
        if file_input is not None:
            await file_input.set_input_files(str(img_path))
        else:
            add_btn = await _require_locator(page, group, "add_image_button", timeout_ms=5000)
            async with page.expect_file_chooser(timeout=5000) as fc_info:
                await add_btn.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(str(img_path))

        # Wait up to 15s for the uploaded <img> to appear in the editor
        for _ in range(30):
            if await _count_preview_images(page, group) > before_count:
                break
            await page.wait_for_timeout(500)
        await page.wait_for_timeout(1000)


_INLINE_MD_RE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*)")


def _parse_inline_formatting(text: str) -> list[tuple[str, bool, bool]]:
    """Split text into (segment, is_bold, is_italic) tuples for **bold** and *italic*."""
    parts: list[tuple[str, bool, bool]] = []
    pos = 0
    for match in _INLINE_MD_RE.finditer(text):
        if match.start() > pos:
            parts.append((text[pos:match.start()], False, False))
        token = match.group(0)
        if token.startswith("**") and token.endswith("**"):
            parts.append((token[2:-2], True, False))
        else:
            parts.append((token[1:-1], False, True))
        pos = match.end()
    if pos < len(text):
        parts.append((text[pos:], False, False))
    return parts or [(text, False, False)]


async def _type_formatted_text(page: Page, text: str) -> None:
    """Insert inline-formatted text quickly using insert_text and Ctrl+B / Ctrl+I toggles."""
    for segment, is_bold, is_italic in _parse_inline_formatting(text):
        if not segment:
            continue
        if is_bold:
            await page.keyboard.press("Control+b")
        if is_italic:
            await page.keyboard.press("Control+i")
        await page.keyboard.insert_text(segment)
        if is_italic:
            await page.keyboard.press("Control+i")
        if is_bold:
            await page.keyboard.press("Control+b")


async def _type_markdown_content(page: Page, content: str) -> None:
    """Type Markdown-structured content into Dzen's Draft.js article editor."""
    lines = content.splitlines()
    in_list = False
    in_quote = False
    wrote_any = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if in_list:
                await page.keyboard.press("Enter")
                in_list = False
            if in_quote:
                await page.keyboard.press("Enter")
                in_quote = False
            continue

        is_list_item = bool(re.match(r"^[-*]\s+", line))
        is_quote_line = line.startswith("> ")

        if in_list and not is_list_item:
            await page.keyboard.press("Enter")
            in_list = False
        if in_quote and not is_quote_line:
            await page.keyboard.press("Enter")
            in_quote = False

        if wrote_any and not in_list and not in_quote:
            await page.keyboard.press("Enter")

        if line.startswith("## ") or line.startswith("### ") or line.startswith("# "):
            heading_text = re.sub(r"^#{1,3}\s+", "", line)
            plain_heading = re.sub(r"\*\*([^*]+)\*\*", r"\1", heading_text)
            await page.keyboard.type("##", delay=4)
            await page.keyboard.insert_text(plain_heading)
        elif is_quote_line:
            quote_text = line[2:].strip()
            if not in_quote:
                await page.keyboard.type("> ", delay=4)
                in_quote = True
            else:
                await page.keyboard.press("Enter")
            await _type_formatted_text(page, quote_text)
        elif is_list_item:
            item_text = re.sub(r"^[-*]\s+", "", line)
            if not in_list:
                await page.keyboard.type("- ", delay=4)
                in_list = True
            else:
                await page.keyboard.press("Enter")
            await _type_formatted_text(page, item_text)
        else:
            await _type_formatted_text(page, line)

        wrote_any = True

    if in_list or in_quote:
        await page.keyboard.press("Enter")


async def _wait_for_draft_saved(page: Page, timeout_ms: int = 15000) -> None:
    """Wait until Dzen's autosave finishes ('Сохранено') or settle for 5s."""
    await page.wait_for_timeout(1000)
    saving_selectors = SELECTORS["article_editor"]["draft_saving_indicator"]
    saved_selectors = SELECTORS["article_editor"]["draft_saved_indicator"]

    loop = asyncio.get_running_loop()
    deadline = loop.time() + (timeout_ms / 1000.0)
    while loop.time() < deadline:
        saving = await _find_first_locator(page, saving_selectors, timeout_ms=400)
        if saving is None:
            saved = await _find_first_locator(page, saved_selectors, timeout_ms=600)
            if saved is not None:
                await page.wait_for_timeout(1000)
                return
        await page.wait_for_timeout(400)

    await page.wait_for_timeout(5000)


def _validate_files(paths: list[str] | None) -> list[Path]:
    """Validate that all provided file paths exist and are regular files."""
    if not paths:
        return []
    resolved: list[Path] = []
    for raw in paths:
        p = Path(raw).expanduser().resolve()
        if not p.is_file():
            raise FileNotFoundError(f"Image file not found: {raw}")
        resolved.append(p)
    return resolved


async def _is_studio_not_found(page: Page, status: int | None) -> bool:
    """Return True if the current page is a 404 error page."""
    if status == 404:
        return True
    not_found = await _find_first_locator(page, 'text="Такой страницы не существует"', timeout_ms=1200)
    return not_found is not None


async def _verify_studio_access(context: BrowserContext, page: Page) -> str | None:
    """Navigate to Dzen Studio after login and return its working URL, or None if 404."""
    response = await page.goto(URLS["editor"], wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(1500)
    status = response.status if response is not None else None
    if URLS["passport_host"] not in page.url and not await _is_studio_not_found(page, status):
        return page.url

    await page.goto(URLS["home"], wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(1000)
    menu_btn = await _find_first_locator(page, SELECTORS["auth"]["profile_menu_button"], timeout_ms=3000)
    if menu_btn is not None:
        await menu_btn.click()
        studio_link = await _find_first_locator(page, SELECTORS["auth"]["studio_menu_link"], timeout_ms=3000)
        if studio_link is not None:
            studio_page = await _click_and_follow_new_page(context, page, studio_link)
            await studio_page.wait_for_timeout(1500)
            if URLS["passport_host"] not in studio_page.url and not await _is_studio_not_found(studio_page, None):
                return studio_page.url

    response = await page.goto(URLS["editor_create"], wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(1500)
    status = response.status if response is not None else None
    if URLS["passport_host"] not in page.url and not await _is_studio_not_found(page, status):
        return page.url

    return None


@mcp.tool()
async def login_dzen(timeout_seconds: int = 150) -> str:
    """Open Dzen home page in a visible browser window so the user can log in, then verify Studio access.

    Saves cookies and session data to ./dzen_profile for subsequent headless calls.
    """
    async with _open_dzen_context(headless=False) as (context, page):
        await page.goto(URLS["home"], wait_until="domcontentloaded", timeout=30000)

        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(10, timeout_seconds)
        auth_hosts = (URLS["passport_host"], URLS["vk_auth_host"])
        saw_login_flow = any(host in page.url for host in auth_hosts)
        saw_login_button = False

        while loop.time() < deadline:
            if page.is_closed() or not context.pages:
                return f"Browser window closed. Profile saved to {PROFILE_DIR}."

            current_url = page.url
            if any(host in current_url for host in auth_hosts):
                saw_login_flow = True

            if not any(host in current_url for host in auth_hosts) and "dzen.ru" in current_url:
                login_btn = await _find_first_locator(
                    page,
                    SELECTORS["auth"]["login_required"],
                    timeout_ms=1200,
                )
                if login_btn is not None:
                    saw_login_button = True
                else:
                    profile_btn = await _find_first_locator(
                        page,
                        SELECTORS["auth"]["profile_menu_button"],
                        timeout_ms=1500,
                    )
                    studio_marker = await _find_first_locator(
                        page,
                        SELECTORS["auth"]["logged_in_marker"],
                        timeout_ms=1200,
                    )
                    if (profile_btn is not None or studio_marker is not None) and (
                        saw_login_flow or saw_login_button or studio_marker is not None
                    ):
                        await page.wait_for_timeout(1500)
                        studio_url = await _verify_studio_access(context, page)
                        if studio_url:
                            return (
                                f"Successfully logged in to Yandex Dzen. "
                                f"Studio verified at {studio_url}. Profile saved to {PROFILE_DIR}."
                            )
                        return (
                            f"Logged in to Yandex Dzen and saved profile to {PROFILE_DIR}, "
                            f"but Dzen Studio returned 404 (last URL: {page.url})."
                        )

            await asyncio.sleep(1.0)

        return (
            f"Login wait timed out after {timeout_seconds}s. "
            f"Any completed session state was saved to {PROFILE_DIR}."
        )


@mcp.tool()
async def create_dzen_article(
    title: str,
    content: str,
    image_path: str | None = None,
    publish: bool = False,
    headless: bool = True,
) -> str:
    """Create an article in Yandex Dzen Studio, optionally upload an image, and save draft or publish."""
    if not title.strip():
        raise ValueError("Article title cannot be empty.")
    if not content.strip():
        raise ValueError("Article content cannot be empty.")

    images = _validate_files([image_path] if image_path else None)

    async with _open_dzen_context(headless=headless) as (context, page):
        await _ensure_authenticated(page)
        await _dismiss_popups(page)

        create_btn = await _require_locator(page, "studio", "create_button", timeout_ms=10000)
        await create_btn.click()

        article_opt = await _require_locator(page, "studio", "create_article_option", timeout_ms=8000)
        editor_page = await _click_and_follow_new_page(context, page, article_opt)
        await _dismiss_popups(editor_page)

        title_el = await _require_locator(editor_page, "article_editor", "title_input", timeout_ms=15000)
        await title_el.click()
        if await title_el.get_attribute("contenteditable") == "true":
            await editor_page.keyboard.insert_text(title.strip())
        else:
            await title_el.fill(title.strip())

        body_el = await _require_locator(editor_page, "article_editor", "body_input", timeout_ms=10000)
        await body_el.click()

        await _type_markdown_content(editor_page, content)

        if images:
            await editor_page.keyboard.press("Enter")
            await editor_page.wait_for_timeout(500)
            await _upload_images(editor_page, images, group="article_editor")

        if publish:
            publish_btn = await _require_locator(editor_page, "article_editor", "publish_button", timeout_ms=10000)
            await publish_btn.click()
            confirm_btn = await _find_first_locator(
                editor_page,
                SELECTORS["article_editor"]["publish_confirm_button"],
                timeout_ms=4000,
            )
            if confirm_btn is not None:
                await confirm_btn.click()
            await editor_page.wait_for_timeout(3000)
            return f"Article published: {editor_page.url}"

        await _wait_for_draft_saved(editor_page)
        return f"Article saved as draft: {editor_page.url}"


@mcp.tool()
async def create_dzen_post(
    text: str,
    image_paths: list[str] | None = None,
    publish: bool = False,
    headless: bool = True,
) -> str:
    """Create a short post in Yandex Dzen Studio, optionally attach images, and save draft or publish."""
    if not text.strip():
        raise ValueError("Post text cannot be empty.")

    images = _validate_files(image_paths)

    async with _open_dzen_context(headless=headless) as (context, page):
        await _ensure_authenticated(page)
        await _dismiss_popups(page)

        create_btn = await _require_locator(page, "studio", "create_button", timeout_ms=10000)
        await create_btn.click()

        post_opt = await _require_locator(page, "studio", "create_post_option", timeout_ms=8000)
        editor_page = await _click_and_follow_new_page(context, page, post_opt)
        await _dismiss_popups(editor_page)

        text_el = await _require_locator(editor_page, "post_editor", "text_input", timeout_ms=12000)
        await text_el.click()
        await editor_page.keyboard.type(text.strip(), delay=5)

        if images:
            await _upload_images(editor_page, images, group="post_editor")

        if publish:
            publish_btn = await _require_locator(editor_page, "post_editor", "publish_button", timeout_ms=10000)
            await publish_btn.click()
            await editor_page.wait_for_timeout(3000)
            return f"Post published: {editor_page.url}"

        save_btn = await _find_first_locator(
            editor_page,
            SELECTORS["post_editor"]["save_draft_button"],
            timeout_ms=3000,
        )
        if save_btn is not None:
            await save_btn.click()
        await editor_page.wait_for_timeout(2000)
        return f"Post saved as draft: {editor_page.url}"


_DUMP_CHANNEL_JS = """async ({ slug, days }) => {
  const CUTOFF = Date.now() - days * 24 * 60 * 60 * 1000;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const oidDate = oid => parseInt(oid.substring(0, 8), 16) * 1000;

  function collect(node, acc, depth) {
    if (depth > 8 || !node || typeof node !== 'object') return;
    if (Array.isArray(node)) { for (const x of node) collect(x, acc, depth + 1); return; }
    if (node.type === 'card' && node.publication_object_id && node.title && typeof node.views === 'number') acc.push(node);
    for (const k of Object.keys(node)) { const v = node[k]; if (v && typeof v === 'object') collect(v, acc, depth + 1); }
  }

  async function getJSON(url) {
    const r = await fetch(url, { credentials: 'include', headers: { accept: 'application/json' } });
    const t = await r.text();
    if (t[0] !== '{') throw new Error('non-JSON (captcha/redirect), status ' + r.status);
    return JSON.parse(t);
  }

  try {
    const exp = await getJSON(
      'https://dzen.ru/api/v3/launcher/export?country_code=ru&lang=ru&clid=300&referrer_place=more&channel_name=' +
      encodeURIComponent(slug)
    );
    const artTab = (exp.tabs || []).find(t => t.id === 'article');
    if (!artTab || !artTab.url) return { slug, error: 'no article tab (у канала нет статей?)' };

    const byOid = new Map();
    let link = artTab.url, page = 0, stop = false;
    while (link && page < 30 && !stop) {
      const j = await getJSON(link);
      const cards = []; collect(j.items, cards, 0);
      let maxD = -Infinity, added = 0;
      for (const c of cards) {
        const t = oidDate(c.publication_object_id);
        if (t > maxD) maxD = t;
        if (!byOid.has(c.publication_object_id)) {
          byOid.set(c.publication_object_id, { title: String(c.title).trim(), views: c.views, t });
          added++;
        }
      }
      if ((isFinite(maxD) && maxD < CUTOFF) || added === 0) stop = true;
      link = j.more && (j.more.link || j.more);
      page++;
      await sleep(300);
    }

    const recent = [...byOid.values()].filter(x => x.t >= CUTOFF).sort((a, b) => b.t - a.t);
    const iso = ms => new Date(ms).toISOString().slice(0, 10);
    return {
      slug,
      count: recent.length,
      newest: recent[0] ? iso(recent[0].t) : null,
      oldest: recent.length ? iso(recent[recent.length - 1].t) : null,
      items: recent,
      fileText: recent.length ? recent.map(x => `${x.title} = ${x.views}`).join('\\n') + '\\n' : ''
    };
  } catch (e) {
    return { slug, error: String(e) };
  }
}"""


def _normalize_channel_slug(slug: str) -> str:
    """Normalize a channel slug or dzen.ru URL while preserving 'id/<hex>' channels."""
    clean = slug.strip()
    for prefix in ("https://dzen.ru/", "http://dzen.ru/", "https://www.dzen.ru/", "http://www.dzen.ru/"):
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
            break
    clean = clean.split("?", 1)[0].strip("/")
    if not clean:
        raise ValueError("Channel slug cannot be empty.")
    return clean


@mcp.tool()
async def dump_channel_articles(
    slug: str,
    days: int = 60,
    output_dir: str | None = None,
) -> str:
    """Dump public articles and view counts for a Dzen channel over the last N days.

    Uses a clean isolated Chromium instance without dzen_profile so the studio session
    is neither locked nor exposed. Saves '<slug>_статьи_<days>дней.txt'.
    """
    if days <= 0:
        raise ValueError("days must be a positive integer.")

    clean_slug = _normalize_channel_slug(slug)
    target_dir = Path(output_dir).expanduser().resolve() if output_dir else EXPORTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_slug = clean_slug.replace("/", "_")
    out_file = target_dir / f"{safe_slug}_статьи_{days}дней.txt"

    pw: Playwright = await async_playwright().start()
    browser = None
    context = None
    try:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            user_agent=REALISTIC_USER_AGENT,
            locale="ru-RU",
            viewport={"width": 1366, "height": 900},
        )
        await context.add_init_script(STEALTH_INIT_SCRIPT)
        page = await context.new_page()

        channel_url = f"https://dzen.ru/{clean_slug}"
        await page.goto(channel_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1500)

        result = await page.evaluate(_DUMP_CHANNEL_JS, {"slug": clean_slug, "days": days})
    finally:
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass
        await pw.stop()

    if not isinstance(result, dict):
        raise RuntimeError(f"Unexpected response from Dzen export script for '{clean_slug}'.")
    if result.get("error"):
        raise RuntimeError(f"Failed to dump channel '{clean_slug}': {result['error']}")

    file_text = result.get("fileText", "")
    out_file.write_text(file_text, encoding="utf-8")

    items = result.get("items") or []
    count = int(result.get("count", len(items)))
    oldest = result.get("oldest") or "—"
    newest = result.get("newest") or "—"
    top5 = sorted(items, key=lambda x: x.get("views", 0), reverse=True)[:5]

    lines = [
        f"Канал: {clean_slug}",
        f"Найдено статей за {days} дней: {count}",
        f"Диапазон дат: {oldest} — {newest}",
        f"Файл: {out_file}",
    ]
    if top5:
        lines.append("Топ-5 самых популярных заголовков:")
        for idx, item in enumerate(top5, start=1):
            lines.append(f"{idx}. {item['title']} = {item['views']}")
    else:
        lines.append("За указанный период статей не найдено.")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
