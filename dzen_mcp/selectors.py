"""CSS and XPath selectors for Yandex Dzen Studio (dzen.ru/profile/editor).

Each entry may be a single selector string or a list of fallback selectors
tried in order. Update these values if Dzen changes its frontend markup.
"""

from typing import Union

SelectorValue = Union[str, list[str]]

URLS = {
    "home": "https://dzen.ru",
    "editor": "https://dzen.ru/profile/editor/create",
    "editor_create": "https://dzen.ru/profile/editor/create",
    "passport_host": "passport.yandex",
    "vk_auth_host": "id.vk.com",
}

SELECTORS: dict[str, dict[str, SelectorValue]] = {
    "auth": {
        "login_required": [
            'a[href*="passport.yandex"]',
            'button:has-text("Войти")',
            'a:has-text("Войти")',
        ],
        "profile_menu_button": [
            'button[aria-label*="Профиль"]',
            'button[aria-label*="Аккаунт"]',
            '[data-testid="user-avatar"]',
            '[data-testid="header-avatar"]',
            'header button:has(img)',
        ],
        "studio_menu_link": [
            'a[href*="/profile/editor"]',
            '[role="menuitem"]:has-text("Студия")',
            'a:has-text("Студия")',
            'button:has-text("Студия")',
        ],
        "logged_in_marker": [
            'button[aria-label*="Создать"]',
            'button:has-text("Создать")',
            '[data-testid="create-publication-button"]',
            '[data-testid="studio-header"]',
            'a[href*="/profile/editor/"]',
        ],
    },
    "studio": {
        "create_button": [
            '[data-testid="add-publication-button"]',
            '[data-testid="create-publication-button"]',
            'button[aria-label*="Создать"]',
            'button:has-text("Создать")',
            'button:has-text("Добавить")',
        ],
        "create_article_option": [
            '[data-testid="popup-base"] :text("Написать статью")',
            '[data-testid="create-article"]',
            'button:has-text("Написать статью")',
            'div[role="menuitem"]:has-text("Написать статью")',
            'div[role="menuitem"]:has-text("Статья")',
            'a:has-text("Написать статью")',
            'span:has-text("Написать статью")',
        ],
        "create_post_option": [
            '[data-testid="popup-base"] :text("Написать пост")',
            '[data-testid="create-post"]',
            'span:has-text("Написать пост")',
            'button:has-text("Создать пост")',
            'div[role="menuitem"]:has-text("Создать пост")',
            'div[role="menuitem"]:has-text("Пост")',
            'button:has-text("Пост")',
            'span:has-text("Создать пост")',
        ],
        "dismiss_popup": [
            'button[aria-label="Закрыть"]',
            'button:has-text("Понятно")',
            'button:has-text("Пропустить")',
        ],
    },
    "article_editor": {
        "title_input": [
            '.public-DraftEditor-content[contenteditable="true"]',
            '[data-testid="article-title-input"]',
            'textarea[placeholder*="Заголовок"]',
            'input[placeholder*="Заголовок"]',
            '[contenteditable="true"][data-placeholder*="Заголовок"]',
            'h1[contenteditable="true"]',
            '.zen-editor-title [contenteditable="true"]',
        ],
        "body_input": [
            'xpath=(//div[contains(@class,"public-DraftEditor-content") and @contenteditable="true"])[2]',
            '[data-testid="article-body-input"]',
            '.ProseMirror[contenteditable="true"]',
            'div[role="textbox"][contenteditable="true"]',
            '[contenteditable="true"][data-placeholder*="Текст"]',
            '.zen-editor-body [contenteditable="true"]',
        ],
        "side_image_button": [
            'button[class*="sideButton"]',
            'button[class*="side-button"]',
        ],
        "add_image_button": [
            'button[class*="image-popup__fileButton"]',
            'button:has-text("Загрузите файл")',
            'button[aria-label*="Изображение"]',
            'button[aria-label*="изображен"]',
            'button[aria-label*="картинк"]',
            'button[data-testid*="image"]',
            'button[title*="Изображение"]',
        ],
        "image_upload_input": [
            'input[type="file"][class*="image-popup__fileInput"]',
            'input[type="file"][accept*="image"]',
            'input[type="file"]',
        ],
        "uploaded_image_preview": [
            '.public-DraftEditor-content img',
            '.zen-editor-block img',
            '.zen-editor-image img',
            'figure img',
            '[data-testid*="image"] img',
        ],
        "publish_button": [
            'button[data-testid="article-publish-btn"]',
            'button[data-testid="publish-button"]',
            'button:has-text("Опубликовать")',
        ],
        "publish_confirm_button": [
            '[role="dialog"] button:has-text("Опубликовать")',
            '[data-testid="confirm-publish-button"]',
            'div[class*="modal"] button:has-text("Опубликовать")',
        ],
        "draft_saved_indicator": [
            'span[class*="editor-header__status"]:has-text("Сохранено")',
            'text=/Сохранено/i',
            'text=/Черновик/i',
            '[data-testid="draft-status"]',
        ],
        "draft_saving_indicator": [
            'span[class*="editor-header__status"]:has-text("Сохранение")',
            'text=/Идёт сохранение/i',
            'text=/Сохранение/i',
        ],
    },
    "post_editor": {
        "text_input": [
            '.ql-editor[contenteditable="true"]',
            '[data-placeholder="Что нового?"][contenteditable="true"]',
            '[data-testid="post-text-input"]',
            '[role="dialog"] [contenteditable="true"]',
            '[role="dialog"] textarea',
            '.ProseMirror[contenteditable="true"]',
            'div[contenteditable="true"][data-placeholder*="пост"]',
        ],
        "add_image_button": [
            'button[class*="brief-desktop-editor-image-button"]',
            '[role="dialog"] button[aria-label*="Изображение"]',
            '[role="dialog"] button[aria-label*="Фото"]',
            '[role="dialog"] button[aria-label*="картинк"]',
            'button[data-testid*="attach-image"]',
        ],
        "image_upload_input": [
            'input[type="file"][class*="brief-desktop-editor-image-button"]',
            '[role="dialog"] input[type="file"][accept*="image"]',
            'input[type="file"][accept*="image"]',
            'input[type="file"]',
        ],
        "uploaded_image_preview": [
            '[class*="brief"] img',
            '[role="dialog"] img',
        ],
        "publish_button": [
            'button[class*="brief-desktop-editor-content__publishButton"]',
            '[role="dialog"] button:has-text("Опубликовать")',
            'button[data-testid="post-publish-button"]',
            'button:has-text("Опубликовать")',
        ],
        "save_draft_button": [
            '[role="dialog"] button:has-text("Сохранить")',
            '[role="dialog"] button:has-text("В черновики")',
            '[role="dialog"] button[aria-label="Закрыть"]',
        ],
    },
}
