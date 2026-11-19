"""Minimal pure-stdlib Chrome DevTools Protocol (CDP) client for injecting Gemini chat CSS."""

import base64
import hashlib
import json
import os
import queue
import socket
import struct
import threading
import urllib.error
import urllib.request
from urllib.parse import urlparse

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_CDP_QUEUE: queue.Queue = queue.Queue()


def _cdp_worker() -> None:
    while True:
        fn, args = _CDP_QUEUE.get()
        try:
            fn(*args)
        except Exception:
            pass
        finally:
            _CDP_QUEUE.task_done()


_WORKER_THREAD = threading.Thread(target=_cdp_worker, daemon=True)
_WORKER_THREAD.start()


def dispatch_cdp(fn, *args) -> None:
    """Queue a CDP operation on the background worker thread without blocking UI."""
    _CDP_QUEUE.put((fn, args))


def find_free_port() -> int:
    """Return an available localhost TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def list_page_targets(port: int) -> list[dict]:
    """Return all CDP page targets on the given debugging port."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=0.35) as resp:
            items = json.loads(resp.read().decode("utf-8"))
            return [t for t in items if isinstance(t, dict) and t.get("type") == "page"]
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return []


def get_current_gemini_url(port: int) -> str:
    """Return the active gemini.google.com tab URL, or empty string if unavailable."""
    for t in list_page_targets(port):
        url = t.get("url", "")
        if "gemini.google.com" in url:
            return url
    return ""


def _ws_recv_frame(sock: socket.socket) -> str | None:
    header = _recv_exact(sock, 2)
    if not header:
        return None
    b1, b2 = header[0], header[1]
    opcode = b1 & 0x0F
    length = b2 & 0x7F
    if length == 126:
        ext = _recv_exact(sock, 2)
        if not ext:
            return None
        length = struct.unpack("!H", ext)[0]
    elif length == 127:
        ext = _recv_exact(sock, 8)
        if not ext:
            return None
        length = struct.unpack("!Q", ext)[0]
    if b2 & 0x80:
        _recv_exact(sock, 4)
    payload = _recv_exact(sock, length)
    if payload is None or opcode == 0x8:
        return None
    return payload.decode("utf-8", errors="replace")


def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def _ws_send_text(sock: socket.socket, text: str) -> None:
    data = text.encode("utf-8")
    mask = os.urandom(4)
    header = bytearray([0x81])
    length = len(data)
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack("!Q", length))
    header.extend(mask)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    sock.sendall(bytes(header) + masked)


def _send_cdp_commands(
    ws_url: str, cmds: list[dict], results: dict[int, dict] | None = None
) -> bool:
    """Connect to a CDP WebSocket target and execute a sequence of commands."""
    parsed = urlparse(ws_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    path = parsed.path or "/"

    try:
        with socket.create_connection((host, port), timeout=1.0) as sock:
            key = base64.b64encode(os.urandom(16)).decode("ascii")
            req = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                "Sec-WebSocket-Version: 13\r\n\r\n"
            )
            sock.sendall(req.encode("ascii"))

            buf = b""
            while b"\r\n\r\n" not in buf:
                chunk = sock.recv(4096)
                if not chunk:
                    return False
                buf += chunk

            expected_accept = base64.b64encode(
                hashlib.sha1((key + _WS_GUID).encode("ascii")).digest()
            ).decode("ascii")
            if expected_accept not in buf.decode("latin1", errors="ignore"):
                return False

            for cmd in cmds:
                _ws_send_text(sock, json.dumps(cmd))

            expected_ids = {cmd["id"] for cmd in cmds}
            seen = set()
            while len(seen) < len(expected_ids):
                msg = _ws_recv_frame(sock)
                if msg is None:
                    break
                try:
                    obj = json.loads(msg)
                    msg_id = obj.get("id")
                    if msg_id in expected_ids:
                        seen.add(msg_id)
                        if results is not None:
                            results[msg_id] = obj
                except json.JSONDecodeError:
                    pass
            return len(seen) == len(expected_ids)
    except OSError:
        return False


def eval_js_on_target(ws_url: str, js_code: str) -> bool:
    """Connect to a CDP WebSocket target and evaluate + register js_code."""
    return _send_cdp_commands(
        ws_url,
        [
            {
                "id": 1,
                "method": "Page.addScriptToEvaluateOnNewDocument",
                "params": {"source": js_code},
            },
            {
                "id": 2,
                "method": "Runtime.evaluate",
                "params": {"expression": js_code, "silent": True},
            },
        ],
    )


def set_color_scheme_on_gemini(port: int, theme: str) -> int:
    """Sync Gemini web theme class ('dark' or 'light') via CDP without ephemeral Emulation overrides."""
    scheme = "dark" if theme == "dark" else "light"
    bar_color = "#131314" if scheme == "dark" else "#f0f4f9"
    js_theme = f"""
(function() {{
    if (!location.hostname.includes('gemini.google.com')) return;
    window.__mixGeminiTheme = '{scheme}';
    document.documentElement.style.colorScheme = '{scheme}';
    if (document.body) {{
        document.body.classList.toggle('dark-theme', {'true' if scheme == 'dark' else 'false'});
        document.body.classList.toggle('light-theme', {'true' if scheme == 'light' else 'false'});
    }}
    const head = document.head || document.documentElement;
    if (head) {{
        for (const m of head.querySelectorAll('meta[name="theme-color"]')) {{
            m.remove();
        }}
        const meta = document.createElement('meta');
        meta.name = 'theme-color';
        meta.content = '{bar_color}';
        head.appendChild(meta);
    }}
}})();
""".strip()
    count = 0
    for target in list_page_targets(port):
        url = target.get("url", "")
        ws_url = target.get("webSocketDebuggerUrl", "")
        if "gemini.google.com" in url and ws_url:
            if _send_cdp_commands(
                ws_url,
                [
                    {
                        "id": 1,
                        "method": "Runtime.evaluate",
                        "params": {"expression": js_theme, "silent": True},
                    },
                ],
            ):
                count += 1
    return count


def set_language_on_gemini(port: int, lang: str) -> int:
    """Sync Gemini web UI language via ?hl= query param when changed."""
    hl_map = {"zh-CN": "zh-CN", "zh-TW": "zh-TW", "en": "en"}
    hl = hl_map.get(lang, "zh-CN")
    js_lang = f"""
(function() {{
    if (!location.hostname.includes('gemini.google.com')) return;
    const u = new URL(location.href);
    if (u.searchParams.get('hl') !== '{hl}') {{
        u.searchParams.set('hl', '{hl}');
        location.replace(u.toString());
    }}
}})();
""".strip()
    count = 0
    for target in list_page_targets(port):
        url = target.get("url", "")
        ws_url = target.get("webSocketDebuggerUrl", "")
        if "gemini.google.com" in url and ws_url:
            if _send_cdp_commands(
                ws_url,
                [
                    {
                        "id": 1,
                        "method": "Runtime.evaluate",
                        "params": {"expression": js_lang, "silent": True},
                    }
                ],
            ):
                count += 1
    return count


def inject_js_into_gemini(port: int, js_code: str) -> int:
    """Inject js_code into all open gemini.google.com targets. Returns count injected."""
    count = 0
    for target in list_page_targets(port):
        url = target.get("url", "")
        ws_url = target.get("webSocketDebuggerUrl", "")
        if "gemini.google.com" in url and ws_url:
            if eval_js_on_target(ws_url, js_code):
                count += 1
    return count


def _target_needs_sync(ws_url: str, theme: str) -> bool:
    """Return True if the page lacks our observer, font style, or current theme."""
    expr = (
        "(() => !window.__mixGeminiObserverInstalled"
        f" || window.__mixGeminiTheme !== {json.dumps(theme)}"
        " || !document.getElementById('mixgemini-custom-font-style'))()"
    )
    results: dict[int, dict] = {}
    ok = _send_cdp_commands(
        ws_url,
        [
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "silent": True},
            }
        ],
        results=results,
    )
    if not ok:
        return False
    val = results.get(1, {}).get("result", {}).get("result", {}).get("value")
    return bool(val)


def sync_gemini_if_navigated(port: int, js_code: str, theme: str) -> None:
    """Background check: verify & re-inject CSS & theme on open Gemini tabs (handles F5 reloads)."""
    needs_theme = False
    for target in list_page_targets(port):
        url = target.get("url", "")
        ws_url = target.get("webSocketDebuggerUrl", "")
        if "gemini.google.com" in url and ws_url:
            if _target_needs_sync(ws_url, theme):
                eval_js_on_target(ws_url, js_code)
                needs_theme = True
    if needs_theme:
        set_color_scheme_on_gemini(port, theme)


def close_browser_via_cdp(port: int) -> bool:
    """Gracefully close the Chrome/Edge browser instance via CDP Browser.close."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=0.4) as resp:
            info = json.loads(resp.read().decode("utf-8"))
            ws_url = info.get("webSocketDebuggerUrl", "")
            if ws_url:
                return _send_cdp_commands(ws_url, [{"id": 1, "method": "Browser.close"}])
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        pass
    for target in list_page_targets(port):
        ws_url = target.get("webSocketDebuggerUrl", "")
        if ws_url:
            return _send_cdp_commands(ws_url, [{"id": 1, "method": "Browser.close"}])
    return False
