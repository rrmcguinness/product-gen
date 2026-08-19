import argparse
import asyncio
import base64
import email.utils
import http.server
import json
import mimetypes
import os
import re
import socketserver
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path
from typing import Dict, Any

from mkdocs.config import load_config
from mkdocs.commands.build import build as mkdocs_build


def get_paths() -> tuple[Path, Path, Path]:
    root_dir = Path(__file__).resolve().parent.parent.parent
    docs_dir = root_dir / "docs"
    site_dir = root_dir / "site"
    return root_dir, docs_dir, site_dir


def build_docs_if_needed(root_dir: Path, site_dir: Path, force_rebuild: bool = True) -> None:
    config_path = root_dir / "mkdocs.yml"
    if force_rebuild or not site_dir.exists() or not (site_dir / "index.html").exists():
        print(f"Building MkDocs site using config: {config_path}")
        config = load_config(config_file=str(config_path))
        mkdocs_build(config, dirty=False)
        print("MkDocs build complete.")


def create_single_file_html(site_dir: Path, output_file: Path) -> Path:
    """
    Bundles the entire multi-page documentation site into a single self-contained
    HTML application with inlined CSS, JS, and client-side SPA router.
    Works 100% offline in Chrome, Safari, Edge, and Firefox without a web server.
    """
    print(f"Generating standalone single-file HTML bundle -> {output_file.name}...")
    index_html_path = site_dir / "index.html"
    if not index_html_path.exists():
        raise FileNotFoundError(f"Missing {index_html_path}. Build site first.")

    with open(index_html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Inline all local stylesheets
    def replace_css(match):
        tag = match.group(0)
        if 'rel="stylesheet"' not in tag and "rel='stylesheet'" not in tag:
            return tag
        href = match.group(1)
        if href.startswith(("http://", "https://", "//")):
            return tag
        clean_href = href.split("?")[0].split("#")[0].lstrip("./")
        css_path = site_dir / clean_href
        if css_path.exists():
            with open(css_path, "r", encoding="utf-8") as cf:
                css_data = cf.read()
            return f"<style>\n{css_data}\n</style>"
        return tag

    html = re.sub(
        r'<link\b[^>]*?\bhref=[\"\']([^\"\']+)[\"\'][^>]*?>',
        replace_css,
        html
    )

    # Inline all local javascript files
    def replace_js(match):
        tag = match.group(0)
        src = match.group(1)
        if src.startswith(("http://", "https://", "//")):
            return tag
        clean_src = src.split("?")[0].split("#")[0].lstrip("./")
        js_path = site_dir / clean_src
        if js_path.exists():
            with open(js_path, "r", encoding="utf-8") as jf:
                js_data = jf.read()
            return f"<script>\n{js_data}\n</script>"
        return tag

    html = re.sub(
        r'<script\b[^>]*?\bsrc=[\"\']([^\"\']+)[\"\'][^>]*?>\s*</script>',
        replace_js,
        html
    )

    # Extract all documentation pages
    pages_data: Dict[str, Dict[str, str]] = {}
    for html_file in site_dir.glob("**/*.html"):
        rel_path = html_file.relative_to(site_dir).as_posix()
        if rel_path == "404.html":
            continue
        with open(html_file, "r", encoding="utf-8") as pf:
            content = pf.read()

        match = re.search(r'(<article\s+class=\"md-content__inner[^>]*>.*?</article>)', content, re.DOTALL)
        article_html = match.group(1) if match else ""

        title_match = re.search(r'<title>(.*?)</title>', content)
        title = title_match.group(1) if title_match else ""

        key = rel_path
        if key.endswith("index.html"):
            key = key[:-10]
        key = key.strip("/")

        pages_data[key] = {
            "title": title,
            "html": article_html
        }

    # Embedded client-side SPA router
    router_script = f"""
<script>
window.__EMBEDDED_PAGES__ = {json.dumps(pages_data)};

function normalizeDocPath(href) {{
    if (!href) return '';
    let path = href.split('#')[0].split('?')[0];
    path = path.replace(/^\\.\\//, '').replace(/^\\.\\.\\//, '');
    path = path.replace(/index\\.html$/, '').replace(/^\\/+|\\/+$/g, '');
    return path;
}}

function navigateDocTo(key, hash) {{
    const normKey = normalizeDocPath(key);
    const page = window.__EMBEDDED_PAGES__[normKey] || window.__EMBEDDED_PAGES__[''];
    if (!page) return;

    const articleContainer = document.querySelector('article.md-content__inner') || document.querySelector('.md-content');
    if (articleContainer) {{
        const temp = document.createElement('div');
        temp.innerHTML = page.html;
        const newArticle = temp.querySelector('article.md-content__inner') || temp;

        articleContainer.innerHTML = newArticle.innerHTML;

        if (page.title) {{
            document.title = page.title;
        }}

        if (typeof window.__renderMermaid === 'function') {{
            window.__renderMermaid(articleContainer);
        }}

        document.querySelectorAll('.md-nav__link').forEach(link => {{
            const linkPath = normalizeDocPath(link.getAttribute('href'));
            if (linkPath === normKey) {{
                link.classList.add('md-nav__link--active');
                let parent = link.closest('.md-nav__item');
                while (parent) {{
                    parent.classList.add('md-nav__item--active');
                    const toggle = parent.querySelector('input.md-nav__toggle');
                    if (toggle) toggle.checked = true;
                    parent = parent.parentElement ? parent.parentElement.closest('.md-nav__item') : null;
                }}
            }} else {{
                link.classList.remove('md-nav__link--active');
            }}
        }});

        if (hash) {{
            const targetId = hash.replace(/^#/, '');
            const targetEl = document.getElementById(targetId);
            if (targetEl) {{
                targetEl.scrollIntoView({{ behavior: 'smooth' }});
                return;
            }}
        }}
        window.scrollTo({{ top: 0, behavior: 'instant' }});
    }}
}}

document.addEventListener('DOMContentLoaded', () => {{
    document.addEventListener('click', (e) => {{
        const link = e.target.closest('a');
        if (!link) return;

        const href = link.getAttribute('href');
        if (!href) return;

        if (href.startsWith('http://') || href.startsWith('https://') || href.startsWith('mailto:')) {{
            return;
        }}

        if (href.startsWith('#')) {{
            return;
        }}

        e.preventDefault();
        const parts = href.split('#');
        const pathPart = parts[0];
        const hashPart = parts[1] || '';

        const normKey = normalizeDocPath(pathPart);
        window.location.hash = hashPart ? normKey + '#' + hashPart : normKey;
        navigateDocTo(normKey, hashPart);
    }});

    function handleRouteHash() {{
        let rawHash = window.location.hash.replace(/^#/, '');
        if (rawHash) {{
            const parts = rawHash.split('#');
            const pathKey = parts[0];
            const anchor = parts[1] || '';
            navigateDocTo(pathKey, anchor);
        }}
    }}

    window.addEventListener('hashchange', handleRouteHash);
    handleRouteHash();
}});
</script>
"""
    last_body_idx = html.rfind("</body>")
    if last_body_idx != -1:
        html = html[:last_body_idx] + router_script + "\n</body>" + html[last_body_idx + 7:]
    else:
        html += router_script + "\n"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Created standalone single-file HTML: {output_file} ({output_file.stat().st_size:,} bytes, {len(pages_data)} pages)")
    return output_file


async def _capture_mhtml_via_chrome(site_dir: Path, output_file: Path) -> bool:
    import websockets

    port = 8791
    cdp_port = 9244

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(site_dir), **kwargs)
        def log_message(self, format, *args):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    chrome_candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium"
    ]
    chrome_bin = None
    for c in chrome_candidates:
        if Path(c).exists():
            chrome_bin = c
            break

    if not chrome_bin:
        httpd.shutdown()
        return False

    proc = subprocess.Popen([
        chrome_bin,
        "--headless=new",
        f"--remote-debugging-port={cdp_port}",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check"
    ], stderr=subprocess.DEVNULL)

    await asyncio.sleep(1.5)

    try:
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{cdp_port}/json/new?http://127.0.0.1:{port}/", method="PUT")
        resp = urllib.request.urlopen(req)
        tab = json.loads(resp.read())
        ws_url = tab["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=100*1024*1024) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
            await asyncio.sleep(2)

            await ws.send(json.dumps({"id": 2, "method": "Page.captureSnapshot", "params": {"format": "mhtml"}}))
            while True:
                msg = await ws.recv()
                d = json.loads(msg)
                if d.get("id") == 2:
                    mhtml_data = d["result"]["data"]
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(mhtml_data)
                    print(f"Created native Chrome MHTML Web Archive: {output_file} ({output_file.stat().st_size:,} bytes)")
                    return True
    except Exception as e:
        print(f"[Warning] Failed to capture MHTML via Chrome CDP: {e}")
        return False
    finally:
        proc.terminate()
        httpd.shutdown()


def create_mhtml_archive(site_dir: Path, output_file: Path) -> Path:
    """
    Creates a native Chrome MHTML Web Archive (.mhtml) file.
    """
    print(f"Generating Chrome MHTML Web Archive -> {output_file.name}...")
    try:
        success = asyncio.run(_capture_mhtml_via_chrome(site_dir, output_file))
        if success and output_file.exists():
            return output_file
    except Exception as e:
        print(f"CDP capture encountered error: {e}")

    # Fallback to multi-part MIME builder
    boundary = "----=_NextPart_ProductGen_Docs_Archive"
    base_url = "http://docs.product-gen.local/"
    parts = []

    for root, _, files in os.walk(site_dir):
        for f in files:
            file_path = Path(root) / f
            rel_path = file_path.relative_to(site_dir).as_posix()
            content_type, _ = mimetypes.guess_type(str(file_path))
            if not content_type:
                if f.endswith(".woff2"): content_type = "font/woff2"
                elif f.endswith(".woff"): content_type = "font/woff"
                elif f.endswith(".js"): content_type = "application/javascript"
                elif f.endswith(".css"): content_type = "text/css"
                elif f.endswith(".html"): content_type = "text/html; charset=\"utf-8\""
                else: content_type = "application/octet-stream"

            with open(file_path, "rb") as fp:
                data = fp.read()

            b64_data = base64.b64encode(data).decode("ascii")
            formatted_b64 = "\n".join([b64_data[i:i+76] for i in range(0, len(b64_data), 76)])
            url = base_url + rel_path

            part = f"""--{boundary}
Content-Type: {content_type}
Content-Transfer-Encoding: base64
Content-Location: {url}

{formatted_b64}"""
            parts.append(part)

            if f == "index.html":
                dir_rel = rel_path[:-10]
                dir_url = base_url + dir_rel
                part_alias = f"""--{boundary}
Content-Type: {content_type}
Content-Transfer-Encoding: base64
Content-Location: {dir_url}

{formatted_b64}"""
                parts.append(part_alias)

    header = f"""From: <Walmart Product Generation Pipeline Docs Packager>
Snapshot-Content-Location: {base_url}
Subject: Walmart Product Generation Pipeline Documentation
Date: {email.utils.formatdate(usegmt=True)}
MIME-Version: 1.0
Content-Type: multipart/related;
\ttype=\"text/html\";
\tboundary=\"{boundary}\"

"""
    mhtml_content = header + "\n\n".join(parts) + f"\n\n--{boundary}--\n"
    with open(output_file, "w", encoding="utf-8") as fp:
        fp.write(mhtml_content)

    print(f"Created fallback MHTML archive: {output_file} ({output_file.stat().st_size:,} bytes)")
    return output_file


def create_zip_archive(site_dir: Path, output_file: Path) -> Path:
    print(f"Generating portable ZIP archive -> {output_file.name}...")
    with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(site_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(site_dir)
                zipf.write(file_path, arcname)
    print(f"Created portable ZIP package: {output_file} ({output_file.stat().st_size:,} bytes)")
    return output_file


def package_all(output_dir: Path | None = None) -> Dict[str, Path]:
    root_dir, docs_dir, site_dir = get_paths()
    target_dir = output_dir or root_dir

    build_docs_if_needed(root_dir, site_dir)

    html_file = target_dir / "product_gen_docs.html"
    mhtml_file = target_dir / "product_gen_docs.mhtml"
    zip_file = target_dir / "product_gen_docs.zip"

    create_single_file_html(site_dir, html_file)
    create_mhtml_archive(site_dir, mhtml_file)
    create_zip_archive(site_dir, zip_file)

    print("\n=======================================================")
    print("Documentation packaging complete!")
    print(f"1. Standalone Single-File HTML : {html_file.resolve()}")
    print(f"2. Chrome MHTML Web Archive    : {mhtml_file.resolve()}")
    print(f"3. Portable Site ZIP Package   : {zip_file.resolve()}")
    print("=======================================================\n")

    return {
        "html": html_file,
        "mhtml": mhtml_file,
        "zip": zip_file
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Package documentation site into single-file webarchive bundles.")
    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Directory to place output archive files (default: project root)"
    )
    parser.add_argument(
        "--format",
        choices=["all", "html", "mhtml", "zip"],
        default="all",
        help="Archive format to generate (default: all)"
    )
    args = parser.parse_args()

    root_dir, docs_dir, site_dir = get_paths()
    target_dir = Path(args.output_dir) if args.output_dir else root_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    build_docs_if_needed(root_dir, site_dir)

    if args.format == "all":
        package_all(target_dir)
    elif args.format == "html":
        create_single_file_html(site_dir, target_dir / "product_gen_docs.html")
    elif args.format == "mhtml":
        create_mhtml_archive(site_dir, target_dir / "product_gen_docs.mhtml")
    elif args.format == "zip":
        create_zip_archive(site_dir, target_dir / "product_gen_docs.zip")


if __name__ == "__main__":
    main()
