"""The Yoisho BD OS app: Sellbird's dashboard wrapped with Yoisho's pages.

Uses ``sellbird.dashboard.build_app`` (docs/extensions.md): Yoisho's routes
come first, every built-in route keeps working underneath, and Sellbird's
sign-in guard stays in place (the Access step later swaps it for team sign-in).

    /                     Yoisho BD OS (the founder's home)
    /static/engine.html   Sellbird's own screens, in Yoisho colours
    /static/yoisho/...    Yoisho BD OS page assets
    /static/app.css       Sellbird's styles plus the Yoisho theme
    /static/yoisho-logo   The logo from private/brand/, if present

Pages and assets are public paths in Sellbird's guard (they hold no data).
Every record comes through /api/yoisho/..., which needs the token.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

HERE = Path(__file__).resolve().parent
WEB = HERE / "web"
PROJECT = HERE.parent
PRIVATE_BRAND = PROJECT / "private" / "brand"
LOGO_NAMES = ("logo.svg", "logo.png", "logo.webp")
TYPES = {".css": "text/css", ".js": "text/javascript", ".svg": "image/svg+xml",
         ".png": "image/png", ".webp": "image/webp", ".html": "text/html"}
NO_CACHE = {"Cache-Control": "no-cache"}

pages = APIRouter()


def _sellbird_web() -> Path:
    import sellbird.dashboard as dash
    return dash.WEB_DIR


def _logo() -> Path | None:
    for name in LOGO_NAMES:
        path = PRIVATE_BRAND / name
        if path.is_file():
            return path
    return None


@pages.get("/")
async def home():
    return HTMLResponse((WEB / "index.html").read_text(encoding="utf-8"), headers=NO_CACHE)


@pages.get("/static/engine.html")
async def engine():
    html = (_sellbird_web() / "index.html").read_text(encoding="utf-8")
    html = html.replace("<title>Sellbird</title>", "<title>Yoisho BD OS: engine</title>", 1)
    html = html.replace("/static/sellbird-mark.svg", "/static/yoisho/mark.svg")
    back = ('<a class="yo-back" href="/">&larr; Yoisho BD OS</a>')
    html = html.replace('<header class="brandrow">', back + '<header class="brandrow">', 1)
    return HTMLResponse(html, headers=NO_CACHE)


@pages.get("/static/app.css")
async def themed_css():
    base = (_sellbird_web() / "app.css").read_text(encoding="utf-8")
    theme = (WEB / "theme.css").read_text(encoding="utf-8")
    return Response(base + "\n\n/* ── Yoisho theme ── */\n" + theme,
                    media_type="text/css", headers=NO_CACHE)


@pages.get("/static/yoisho-logo")
async def logo():
    path = _logo()
    if path is None:
        return PlainTextResponse("no logo", status_code=404)
    return Response(path.read_bytes(), media_type=TYPES.get(path.suffix, "image/png"),
                    headers={"Cache-Control": "public, max-age=3600"})


@pages.get("/static/yoisho/{name}")
async def asset(name: str):
    target = (WEB / name).resolve()
    if not target.is_file() or target.parent != WEB.resolve() or target.suffix not in TYPES:
        return PlainTextResponse("not found", status_code=404)
    return Response(target.read_bytes(), media_type=TYPES[target.suffix], headers=NO_CACHE)


def build():
    import sellbird.dashboard as dash
    return dash.build_app(routers=[pages])


def configure_dashboard(parser):
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--url", action="store_true", help="Print the private link and exit")

    def _main(args):
        import uvicorn

        import sellbird.dashboard as dash
        from sellbird import dashboard_instance

        bind = dash._check_loopback_bind(args.host)
        url = dash.dashboard_url(args.host, args.port)
        if args.url:
            print(url)
            return
        print("\n  Yoisho BD OS running. Open this link to unlock it:\n\n    " + url + "\n")
        print("  Keep the link private: anyone with it can use the dashboard.\n")
        dashboard_instance.write(dash.DB_PATH.parent, host=bind, port=args.port,
                                 instance=dash.INSTANCE_ID)
        uvicorn.run(build(), host=bind, port=args.port, log_level="warning",
                    proxy_headers=False, server_header=False, date_header=False)

    return _main
