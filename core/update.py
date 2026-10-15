"""Offline-first in-app updates via GitHub Releases (nibba PC build).

The app itself runs fully offline. Only the update CHECK needs internet
for ~2 seconds (GitHub Releases API). Applying an update is done by
update.bat (backup-first, code-only replace — the DB is never touched).

No third-party packages: stdlib urllib only, so the lean PC env stays lean.
"""
import json
import urllib.request
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
VERSION_FILE = BASE_DIR / "VERSION"

# Files/dirs an update must NEVER overwrite (client data + secrets +
# environment). update.bat and release.yml both enforce this same list.
PROTECTED_NAMES = {
    ".env", "Backup", "Logs", "Data", "chrome-profile", "venv", "runtime",
    ".git", "staticfiles", "__pycache__", "tunnel.log", "cloudflared.exe",
}
PROTECTED_SUFFIXES = (".sqlite3", ".pem")


def is_protected(rel_path):
    """True if a release-zip member must never overwrite local files."""
    parts = rel_path.replace("\\", "/").split("/")
    if any(p in PROTECTED_NAMES for p in parts):
        return True
    return any(parts[-1].endswith(s) for s in PROTECTED_SUFFIXES)


def read_local_version():
    try:
        return VERSION_FILE.read_text().strip()
    except OSError:
        return "0.0.0-dev"


def _parts(tag):
    return [int(p) if p.isdigit() else 0
            for p in tag.lstrip("v").split(".")]


def is_newer(latest, current):
    """True if release tag `latest` is newer than `current` (vX.Y.Z)."""
    a, b = _parts(latest), _parts(current)
    n = max(len(a), len(b))
    a += [0] * (n - len(a))
    b += [0] * (n - len(b))
    return a > b


def _api(url, token, timeout=15):
    req = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.load(res)


def get_latest_release(repo, token="", timeout=15):
    """Latest GitHub release for 'owner/name'. Returns dict or None."""
    if not repo or "/" not in repo:
        return None
    try:
        data = _api(f"https://api.github.com/repos/{repo}/releases/latest",
                    token, timeout)
    except Exception:
        return None
    tag = (data.get("tag_name") or "").strip()
    if not tag:
        return None
    assets = [a.get("browser_download_url", "")
              for a in data.get("assets", [])]
    zip_url = next((u for u in assets if u.endswith(".zip")), "")
    return {"tag": tag, "name": data.get("name") or tag,
            "notes": data.get("body") or "", "zip_url": zip_url}


@lru_cache(maxsize=1)
def check_for_updates(repo, token=""):
    """Compare local VERSION with the latest release. Never raises."""
    current = read_local_version()
    if not repo:
        return {"current": current, "latest": None,
                "update_available": False, "reason": "not-configured"}
    latest = get_latest_release(repo, token)
    if not latest:
        return {"current": current, "latest": None,
                "update_available": False, "reason": "unreachable"}
    return {"current": current, "latest": latest["tag"],
            "name": latest["name"], "notes": latest["notes"],
            "zip_url": latest["zip_url"],
            "update_available": is_newer(latest["tag"], current),
            "reason": "ok"}
