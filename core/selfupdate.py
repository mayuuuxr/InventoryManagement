"""One-click in-app updater (nibba PC build).

Flow: owner clicks "Install update" on the Help page -> this module
backups the DB, downloads the release zip, extracts it to a staging dir
and writes apply_update.bat next to manage.py. The view then launches
that batch detached and returns at once; the batch waits a few seconds
(so the browser lands on the polling page), stops the server (Windows
locks running files), copies staged code over the app (protected names
skipped — same list update.bat enforces), runs migrate + collectstatic,
restarts waitress and records the result in Logs/update-last-run.txt.

Nothing here touches the running server: staging is pure file IO in
%TEMP% plus one generated script. The dangerous half (stop/copy/
restart) runs after this process is gone, inside the batch.
"""
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

from core.update import PROTECTED_NAMES, PROTECTED_SUFFIXES, check_for_updates

#: A staged zip must at least contain these (else it is not our release).
REQUIRED_MEMBERS = ("manage.py", "VERSION")

#: Minimum plausible release-zip size (v1.0.0 ships ~500KB of code).
MIN_ZIP_BYTES = 50_000

#: Tag format enforced on anything that reaches the staging step.
TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")

STATUS_FILE = Path("Logs") / "update-last-run.txt"
LOCK_FILE = Path("Logs") / "update-in-progress.txt"
PROGRESS_FILE = Path("Logs") / "update-progress.txt"

#: A lock older than this is treated as a crashed run, not a live one.
LOCK_STALE_SECONDS = 15 * 60


class UpdateError(Exception):
    """Anything that must abort the update before the app is touched."""


def _read_lock(base):
    try:
        return (Path(base) / LOCK_FILE).read_text(
            encoding="utf-8").strip().splitlines()
    except OSError:
        return []


def update_in_progress(base):
    """Tag currently installing, or None (stale locks don't count)."""
    import time
    lines = _read_lock(base)
    if len(lines) < 2:
        return None
    try:
        started = float(lines[1])
    except ValueError:
        return None
    if time.time() - started > LOCK_STALE_SECONDS:
        return None
    return lines[0] or None


def _write_lock(base, tag):
    import time
    lock = Path(base) / LOCK_FILE
    lock.parent.mkdir(exist_ok=True)
    lock.write_text(f"{tag}\n{time.time()}\n", encoding="utf-8")


def _clear_lock(base):
    try:
        (Path(base) / LOCK_FILE).unlink(missing_ok=True)
    except OSError:
        pass


def is_staged_protected(rel_path):
    """Same protection as update.bat/is_protected, for staged members."""
    parts = rel_path.replace("\\", "/").split("/")
    if any(p in PROTECTED_NAMES for p in parts):
        return True
    return any(parts[-1].endswith(s) for s in PROTECTED_SUFFIXES)


def resolve_update(repo="", token=""):
    """Fresh update check; returns (tag, zip_url) or None.

    The view calls this on POST (never trusts tag/zip from the form).
    """
    try:
        info = check_for_updates(repo, token)
    except Exception:
        return None
    if not info or info.get("reason") != "ok":
        return None
    if not info.get("update_available"):
        return None
    tag, zip_url = info.get("latest", ""), info.get("zip_url", "")
    if not TAG_RE.match(tag) or not zip_url.startswith("https://"):
        return None
    return tag, zip_url


def backup_database(base_dir):
    """Copy db.sqlite3 to Backup/pre-update_<stamp>.sqlite3, size-verified.

    Aborts (raises) unless the backup byte-matches the live DB — the
    update must never start without a proven restore point.
    """
    base = Path(base_dir)
    live = base / "db.sqlite3"
    if not live.is_file():
        raise UpdateError("No stock database found — refusing to update.")
    backup_dir = base / "Backup"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup = backup_dir / f"pre-update_{stamp}.sqlite3"
    shutil.copyfile(live, backup)
    if backup.stat().st_size != live.stat().st_size or backup.stat().st_size == 0:
        backup.unlink(missing_ok=True)
        raise UpdateError("Database backup failed verification — aborted.")
    for old in sorted(backup_dir.glob("pre-update_*.sqlite3"))[:-10]:
        old.unlink(missing_ok=True)
    return backup


def format_size(num_bytes):
    """Human size for the progress label: 0.5 MB, 1.2 GB, ..."""
    mb = num_bytes / (1024 * 1024)
    if mb < 1024:
        return f"{mb:.1f} MB"
    return f"{mb / 1024:.2f} GB"


def download_release(zip_url, dest, timeout=120):
    """Fetch the release zip; aborts on network errors or tiny files."""
    dest = Path(dest)
    req = urllib.request.Request(
        zip_url, headers={"Accept": "application/octet-stream"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            data = res.read()
    except Exception as exc:
        raise UpdateError(f"Could not download the update ({exc}).")
    if len(data) < MIN_ZIP_BYTES:
        raise UpdateError("Downloaded update looks broken (too small).")
    dest.write_bytes(data)
    return dest


def _safe_pair(name):
    """Map a zip member to a safe relative path, or None to skip it.

    Skips directory entries (Compress-Archive writes them explicitly;
    extracting one as a file would poison later mkdirs), anything that
    would escape the staging dir (absolute paths, ../ climbs), and
    anything protected (DB, .env, venv, ...).
    """
    if name.endswith(("/", "\\")):
        return None
    rel = name.replace("\\", "/").lstrip("/")
    if not rel or rel.startswith(("/", "../")) or "/../" in rel:
        return None
    if is_staged_protected(rel):
        return None
    return name, rel


def extract_staged(zip_path, stage_dir):
    """Extract approved members only; aborts unless it looks like our app."""
    stage = Path(stage_dir)
    if stage.exists():
        shutil.rmtree(stage, ignore_errors=True)
    try:
        stage.mkdir(parents=True)
    except FileExistsError:
        # Windows can linger a beat on deleted dirs (indexer/AV holds).
        import time
        time.sleep(2)
        stage.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        pairs = [p for p in (_safe_pair(n) for n in zf.namelist()) if p]
        if not set(REQUIRED_MEMBERS) <= {rel for _, rel in pairs}:
            raise UpdateError("Downloaded update is not a nibba release.")
        for name, rel in pairs:
            target = stage / rel
            if target.is_dir():
                continue  # belt-and-braces alongside the dir-entry skip
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src:
                target.write_bytes(src.read())
    return stage


APPLY_TEMPLATE = """@echo off
REM nibba one-click updater: applies staged {tag}, restarts the server.
REM Generated automatically - do not edit. Runs hidden. Deletes its lock,
REM its stage and itself when done (success or failure).
setlocal
cd /d "{appdir}"
echo %date% %time% {tag} applying >> "Logs\\update-last-run.txt"
REM Let the browser land on the updating page before the restart.
powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 8"
REM Stop the server (Windows locks running files). Kill by image name AND
REM by port owner, so a wedged lookup of either kind cannot stall us.
REM Refuse to touch code if the port will not free: a half-copy under a
REM live server is worse than no update. The old code keeps serving
REM untouched in that case. Every try is logged for diagnosis.
powershell -NoProfile -WindowStyle Hidden -Command "$c = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if ($c) {{ $n = '?'; try {{ $n = (Get-Process -Id $c.OwningProcess -ErrorAction Stop).ProcessName }} catch {{ }}; echo 'port owner: pid=' + $c.OwningProcess + ' name=' + $n >> 'Logs\\update-last-run.txt' }}"
set TRIES=0
:killagain
taskkill /F /IM waitress-serve.exe >nul 2>&1
powershell -NoProfile -WindowStyle Hidden -Command "$c = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if ($c) {{ try {{ Stop-Process -Id $c.OwningProcess -Force -ErrorAction Stop }} catch {{ }}; exit 1 }}"
if not errorlevel 1 goto killok
set /a TRIES=%TRIES%+1
if %TRIES% GEQ 30 goto stillrunning
powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2"
goto killagain
:killok
echo 30^|Copying new files > "Logs\\update-progress.txt"
if exist "runtime\\python.exe" (set PY=runtime\\python.exe) else (set PY=venv\\Scripts\\python.exe)
if exist "runtime\\Scripts\\waitress-serve.exe" (set WS=runtime\\Scripts\\waitress-serve.exe) else (set WS=venv\\Scripts\\waitress-serve.exe)
REM Copy staged code only (protected names excluded - same list as update.bat).
powershell -NoProfile -WindowStyle Hidden -Command "$prot = @('.env','Backup','Logs','Data','chrome-profile','venv','runtime','.git','staticfiles','__pycache__','tunnel.log','cloudflared.exe'); Get-ChildItem '{stage}' -Recurse -File | ForEach-Object {{ $rel = $_.FullName.Substring('{stage}'.Length + 1); $parts = $rel -split '[\\\\/]'; if (($parts | Where-Object {{ $prot -contains $_ }}).Count -gt 0) {{ return }}; if ($rel -like '*.sqlite3' -or $rel -like '*.pem') {{ return }}; $dest = Join-Path '.' $rel; New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null; Copy-Item $_.FullName $dest -Force }}"
if errorlevel 1 goto copyfail
echo 55^|Updating database > "Logs\\update-progress.txt"
"%PY%" manage.py migrate --noinput -v 0
if errorlevel 1 goto migratefail
echo 75^|Finishing up > "Logs\\update-progress.txt"
"%PY%" manage.py collectstatic --noinput -v 0
echo 90^|Restarting the app > "Logs\\update-progress.txt"
powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath '%WS%' -ArgumentList '--listen=127.0.0.1:8000','core.wsgi:application' -WorkingDirectory '%CD%' -WindowStyle Hidden"
echo %date% %time% {tag} OK >> "Logs\\update-last-run.txt"
echo 100^|Done > "Logs\\update-progress.txt"
rmdir /S /Q "{stage}"
del "Logs\\update-in-progress.txt"
del "%~f0"
exit /b 0
:copyfail
echo %date% %time% {tag} FAILED: file copy >> "Logs\\update-last-run.txt"
goto restartonly
:migratefail
echo %date% %time% {tag} FAILED: migrate >> "Logs\\update-last-run.txt"
:restartonly
powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath '%WS%' -ArgumentList '--listen=127.0.0.1:8000','core.wsgi:application' -WorkingDirectory '%CD%' -WindowStyle Hidden"
del "Logs\\update-in-progress.txt"
exit /b 1
:stillrunning
echo %date% %time% {tag} FAILED: server would not stop, nothing changed >> "Logs\\update-last-run.txt"
del "Logs\\update-in-progress.txt"
exit /b 1
"""


def write_apply_script(base_dir, stage_dir, tag):
    """Render apply_update.bat into the app dir. Returns the script path."""
    if not TAG_RE.match(tag):
        raise UpdateError("Bad update version — aborted.")
    script = Path(base_dir) / "apply_update.bat"
    script.write_text(APPLY_TEMPLATE.format(
        appdir=str(Path(base_dir).resolve()),
        stage=str(Path(stage_dir).resolve()),
        tag=tag,
    ), encoding="utf-8")
    return script


def perform_update(base_dir, tag, zip_url, tmp_root=None):
    """Backup + download + stage + write applier. Returns the script path.

    Raises UpdateError on any problem — the running app is never touched
    (all work happens in the temp staging dir + one generated script).
    Refuses when another update is in flight (single-flight lock), so a
    second click can never stage over a running applier. Launching is the
    view's job (launch_detached), so tests can stop here.
    """
    base = Path(base_dir)
    if not TAG_RE.match(tag):
        raise UpdateError("Bad update version — aborted.")
    live = update_in_progress(base)
    if live:
        raise UpdateError(
            f"Update {live} is already installing — "
            "wait a minute and check Help again.")
    staging_root = Path(tmp_root) if tmp_root else Path(tempfile.gettempdir())
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stage = staging_root / f"nibba_update_stage_{stamp}"
    staged_zip = staging_root / f"nibba_update_{stamp}.zip"
    backup_database(base)
    _write_lock(base, tag)
    try:
        write_progress(base, 5, "Backing up your entries")
        download_release(zip_url, staged_zip)
        write_progress(
            base, 12,
            f"Downloaded update ({format_size(staged_zip.stat().st_size)})")
        extract_staged(staged_zip, stage)
        return write_apply_script(base, stage, tag)
    except Exception:
        # Any failure (expected or raw OS error) releases the lock, so
        # the next click retries clean instead of seeing "already
        # installing" forever. The batch clears it on the happy path.
        _clear_lock(base)
        raise


def launch_detached(script):
    """Start the applier hidden and return at once (it outlives us).

    CREATE_NO_WINDOW: no black console window pops on the shop screen.
    """
    detached = getattr(subprocess, "DETACHED_PROCESS", 0)
    new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [str(script)], cwd=str(Path(script).parent),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=detached | new_group | no_window,
    )


def last_status(base_dir):
    """Last line of Logs/update-last-run.txt, or None if never updated."""
    try:
        lines = (Path(base_dir) / STATUS_FILE).read_text(
            encoding="utf-8").splitlines()
        return lines[-1].strip() or None
    except (OSError, IndexError):
        return None


def write_progress(base_dir, percent, label):
    """Current install step for the progress bar (percent|label)."""
    try:
        base = Path(base_dir)
        base.joinpath("Logs").mkdir(exist_ok=True)
        base.joinpath(PROGRESS_FILE).write_text(
            f"{int(percent)}|{label}\n", encoding="utf-8")
    except OSError:
        pass


def read_progress(base_dir):
    """(percent, label) or None when no update has reported progress."""
    try:
        text = (Path(base_dir) / PROGRESS_FILE).read_text(
            encoding="utf-8").strip()
        pct, _, label = text.partition("|")
        return max(0, min(100, int(pct))), label.strip()
    except (OSError, ValueError):
        return None
