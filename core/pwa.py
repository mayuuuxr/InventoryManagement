"""PWA endpoints: manifest, service worker, icons.

Served as plain Django views (not staticfiles) so they work identically in
local dev and on production without any STATIC_ROOT/whitenoise setup:

- /manifest.webmanifest — install metadata, icon URLs reversed here.
- /sw.js — MUST live at the site root: a worker served from /static/
  could only control /static/*. Long browser cache here would brick
  updates, so Cache-Control is explicitly no-cache.
- /pwa/*.png — app icons. Immutable filenames → cached hard (30 days).
"""
from pathlib import Path

from django.http import FileResponse, HttpResponse, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET

PWA_DIR = Path(__file__).resolve().parent / "pwa_files"


@require_GET
def manifest_view(request):
    """Install metadata. start_url lands staff on the site list; scope "/"
    keeps the installed app on our pages (a same-origin hop outside scope
    would kick the user back to the browser — none of ours do)."""
    return JsonResponse({
        "name": "nibba",
        "short_name": "nibba",
        "description": "Shop stock: purchase, sale, live balance.",
        "start_url": "/dashboard/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#E8F6FF",
        "theme_color": "#0B3D91",
        "icons": [
            {"src": reverse("pwa_icon", args=["icon-192.png"]),
             "sizes": "192x192", "type": "image/png"},
            {"src": reverse("pwa_icon", args=["icon-512.png"]),
             "sizes": "512x512", "type": "image/png"},
            {"src": reverse("pwa_icon", args=["icon-maskable-512.png"]),
             "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    })


@require_GET
def service_worker_view(request):
    """Serve sw.js from the site root with no-cache (see module docstring).
    No auth required: the worker itself holds no data; every fetch it makes
    still carries the user's own session cookies to the real views."""
    resp = HttpResponse(
        (PWA_DIR / "sw.js").read_text(encoding="utf-8"),
        content_type="application/javascript",
    )
    resp["Cache-Control"] = "no-cache"
    return resp


@require_GET
def icon_view(request, filename):
    """Serve one of the committed PWA icons. Unknown names 404 via the
    allowlist below — this is not a generic file server."""
    allowed = {
        "icon-192.png": "image/png",
        "icon-512.png": "image/png",
        "icon-maskable-512.png": "image/png",
        "apple-touch-icon.png": "image/png",
    }
    if filename not in allowed:
        from django.http import Http404
        raise Http404("Unknown icon.")
    resp = FileResponse(
        open(PWA_DIR / filename, "rb"), content_type=allowed[filename])
    resp["Cache-Control"] = "public, max-age=2592000"
    return resp
