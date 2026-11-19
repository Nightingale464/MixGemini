"""CSS and JavaScript injection helpers for customizing Gemini chat font size."""

import json

STYLE_ELEMENT_ID = "mixgemini-custom-font-style"


def build_chat_font_css(font_size: int) -> str:
    """Return CSS rules that resize only Gemini conversation messages."""
    code_size = max(10, round(font_size * 0.9))
    return f"""
/* MixGemini: Conversation-only typography scaling */
html body user-query .query-text,
html body user-query .query-text-line,
html body .user-query-container .query-text,
html body .user-query-container .query-text-line,
html body model-response message-content,
html body model-response .model-response-text,
html body message-content .markdown,
html body message-content .markdown-main-panel,
html body .markdown-main-panel,
html body .markdown p,
html body .markdown li,
html body .markdown ol,
html body .markdown ul,
html body .markdown td,
html body .markdown th,
html body .markdown blockquote,
html body .markdown dl,
html body .markdown dt,
html body .markdown dd,
html body message-content p,
html body message-content li,
html body message-content td,
html body message-content th,
html body message-content blockquote {{
    font-size: {font_size}px !important;
    line-height: 1.62 !important;
}}

html body .markdown span:not(.mat-icon):not(.google-symbols):not([class*="icon"]),
html body message-content span:not(.mat-icon):not(.google-symbols):not([class*="icon"]),
html body user-query .query-text span:not(.mat-icon):not(.google-symbols) {{
    font-size: inherit !important;
    line-height: inherit !important;
}}

html body model-response h1, html body .markdown h1, html body message-content h1 {{
    font-size: {round(font_size * 1.38)}px !important;
    line-height: 1.38 !important;
}}

html body model-response h2, html body .markdown h2, html body message-content h2 {{
    font-size: {round(font_size * 1.24)}px !important;
    line-height: 1.42 !important;
}}

html body model-response h3, html body .markdown h3, html body message-content h3 {{
    font-size: {round(font_size * 1.12)}px !important;
    line-height: 1.48 !important;
}}

html body model-response h4, html body .markdown h4, html body message-content h4 {{
    font-size: {round(font_size * 1.04)}px !important;
    line-height: 1.5 !important;
}}

html body model-response pre,
html body model-response code,
html body .markdown pre,
html body .markdown code,
html body message-content pre,
html body message-content code,
html body code-block pre,
html body code-block code {{
    font-size: {code_size}px !important;
    line-height: 1.5 !important;
}}

html body .markdown h1 code,
html body .markdown h2 code,
html body .markdown h3 code,
html body .markdown h4 code {{
    font-size: 0.9em !important;
}}

/* Keep Gemini action buttons & icons at their native size */
html body model-response button,
html body model-response .mat-icon,
html body model-response .google-symbols,
html body user-query button,
html body user-query .mat-icon,
html body user-query .google-symbols {{
    font-size: revert !important;
}}
""".strip()


def build_injection_js(font_size: int, theme: str = "") -> str:
    """Return JS that applies and maintains custom chat font CSS on gemini.google.com."""
    css_json = json.dumps(build_chat_font_css(font_size))
    theme_init = ""
    if theme in ("dark", "light"):
        theme_init = f"    window.__mixGeminiTheme = {json.dumps(theme)};\n"
    return f"""
(function() {{
    if (!location.hostname.includes('gemini.google.com')) return;
{theme_init}    const cssText = {css_json};
    const styleId = '{STYLE_ELEMENT_ID}';

    function applyToRoot(root) {{
        if (!root) return;
        const activeCss = window.__mixGeminiCssText || cssText;
        if (root !== document) {{
            try {{
                if ('adoptedStyleSheets' in root && typeof CSSStyleSheet !== 'undefined') {{
                    if (!window.__mixGeminiSheet) {{
                        window.__mixGeminiSheet = new CSSStyleSheet();
                    }}
                    window.__mixGeminiSheet.replaceSync(activeCss);
                    if (!root.adoptedStyleSheets.includes(window.__mixGeminiSheet)) {{
                        root.adoptedStyleSheets = [...root.adoptedStyleSheets, window.__mixGeminiSheet];
                    }}
                    return;
                }}
            }} catch (_e) {{}}
        }}

        const target = root === document ? (document.documentElement || document.head) : root;
        if (!target) return;
        let styleEl = (root === document ? document : root).querySelector('#' + styleId);
        if (!styleEl) {{
            styleEl = document.createElement('style');
            styleEl.id = styleId;
        }}
        if (styleEl.textContent !== activeCss) {{
            styleEl.textContent = activeCss;
        }}
        if (styleEl.parentNode !== target) {{
            target.appendChild(styleEl);
        }}
    }}

    function hideDownloadAppButton() {{
        const needles = ['下载应用', '下載應用程式', '下載應用', 'Get app', 'Download app'];
        const candidates = document.querySelectorAll('button, a, [role="button"]');
        for (const el of candidates) {{
            const rect = el.getBoundingClientRect();
            if (rect.top > 90 || rect.width === 0 || rect.width > 240 || rect.height > 64) continue;
            const txt = ((el.innerText || el.textContent || '') + ' ' + (el.getAttribute('aria-label') || '')).trim();
            if (needles.some(k => txt.includes(k))) {{
                el.style.setProperty('display', 'none', 'important');
            }}
        }}
    }}

    function syncAll() {{
        applyToRoot(document);
        const hosts = document.querySelectorAll('user-query, model-response, message-content, code-block');
        for (const el of hosts) {{
            if (el.shadowRoot) {{
                applyToRoot(el.shadowRoot);
            }}
        }}
        if (window.__mixGeminiTheme && document.body) {{
            const isDark = window.__mixGeminiTheme === 'dark';
            document.documentElement.style.colorScheme = window.__mixGeminiTheme;
            document.body.classList.toggle('dark-theme', isDark);
            document.body.classList.toggle('light-theme', !isDark);
            const head = document.head || document.documentElement;
            const barColor = isDark ? '#131314' : '#f0f4f9';
            if (head) {{
                const existing = head.querySelector('meta[name="theme-color"]');
                if (!existing || existing.content !== barColor) {{
                    for (const m of head.querySelectorAll('meta[name="theme-color"]')) {{
                        m.remove();
                    }}
                    const meta = document.createElement('meta');
                    meta.name = 'theme-color';
                    meta.content = barColor;
                    head.appendChild(meta);
                }}
            }}
        }}
        hideDownloadAppButton();
    }}

    window.__mixGeminiCssText = cssText;
    window.__mixGeminiSync = syncAll;
    syncAll();
    setTimeout(syncAll, 600);
    setTimeout(syncAll, 1500);

    if (!window.__mixGeminiObserverInstalled) {{
        window.__mixGeminiObserverInstalled = true;
        let scheduled = false;
        const observer = new MutationObserver(() => {{
            if (scheduled) return;
            scheduled = true;
            requestAnimationFrame(() => {{
                scheduled = false;
                if (window.__mixGeminiCssText && window.__mixGeminiSync) {{
                    window.__mixGeminiSync();
                }}
            }});
        }});
        const rootNode = document.documentElement || document.body;
        if (rootNode) {{
            observer.observe(rootNode, {{ childList: true, subtree: true }});
        }}
    }}
}})();
""".strip()
