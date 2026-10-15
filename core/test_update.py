"""Unit tests for the GitHub-Releases updater (pure logic, no network)."""
import zipfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from core.update import is_newer, is_protected, read_local_version


class VersionCompareTests(SimpleTestCase):
    def test_newer_patch(self):
        self.assertTrue(is_newer("v1.0.1", "1.0.0"))

    def test_same_is_not_newer(self):
        self.assertFalse(is_newer("v1.0.0", "1.0.0"))

    def test_older_is_not_newer(self):
        self.assertFalse(is_newer("v0.9.9", "1.0.0"))

    def test_minor_major(self):
        self.assertTrue(is_newer("v1.2.0", "1.1.9"))
        self.assertTrue(is_newer("v2.0.0", "1.9.9"))

    def test_local_version_reads_file(self):
        v = read_local_version()
        self.assertRegex(v, r"^\d+\.\d+\.\d+$")


class ProtectedPathTests(SimpleTestCase):
    def test_db_and_env_protected(self):
        self.assertTrue(is_protected("db.sqlite3"))
        self.assertTrue(is_protected(".env"))
        self.assertTrue(is_protected("Backup/db_2026-01-01.sqlite3"))
        self.assertTrue(is_protected("venv/Scripts/python.exe"))
        self.assertTrue(is_protected("runtime/python.exe"))
        self.assertTrue(is_protected("Logs/nibba.log"))
        self.assertTrue(is_protected("chrome-profile/Default/Cookies"))
        self.assertTrue(is_protected("staticfiles/admin/css/base.css"))

    def test_code_allowed(self):
        self.assertFalse(is_protected("entries/views.py"))
        self.assertFalse(is_protected("templates/base.html"))
        self.assertFalse(is_protected("VERSION"))


def _fixture_zip(path, version="9.9.9"):
    """A fake release zip: good files plus evil/protected members."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manage.py", "# fake")
        zf.writestr("VERSION", version)
        zf.writestr("templates/new.html", "<p>new</p>")
        # Pad past the downloader's broken-file floor (uncompressed store).
        zf.writestr("static/pad.bin", "x" * 60000)
        zf.writestr(".env", "SECRET=x")
        zf.writestr("db.sqlite3", "fakedb")
        zf.writestr("Backup/db_old.sqlite3", "fakedb")
        zf.writestr("../escape.txt", "evil")
        zf.writestr("/abs.txt", "evil")
        # Explicit directory entries (Compress-Archive writes these):
        # must be skipped, never extracted as files.
        zf.writestr("accounts/", "")
        zf.writestr("accounts/templates/", "")
        zf.writestr("accounts/templates/accounts/base.html", "<p>x</p>")
    return path


class OneClickStageTests(SimpleTestCase):
    def test_backup_missing_db_aborts(self):
        from core.selfupdate import UpdateError, backup_database
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(UpdateError):
                backup_database(Path(tmp))

    def test_backup_verified_and_pruned(self):
        from core.selfupdate import backup_database
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "db.sqlite3").write_bytes(b"x" * 100)
            for i in range(12):
                (base / "Backup").mkdir(exist_ok=True)
                (base / "Backup" / f"pre-update_2026-01-01_0000{i:02d}.sqlite3"
                 ).write_bytes(b"old")
            made = backup_database(base)
            self.assertEqual(made.stat().st_size, 100)
            kept = list((base / "Backup").glob("pre-update_*.sqlite3"))
            self.assertEqual(len(kept), 10)
            self.assertIn(made, kept)

    def test_perform_update_stages_safely(self):
        from core.selfupdate import perform_update
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "app"
            base.mkdir()
            (base / "db.sqlite3").write_bytes(b"data" * 30000)
            (base / "VERSION").write_text("1.0.0")
            zf = _fixture_zip(Path(tmp) / "rel.zip")
            script = perform_update(
                base, "v9.9.9", zf.as_uri(), tmp_root=Path(tmp))
            stages = list(Path(tmp).glob("nibba_update_stage_*"))
            self.assertEqual(len(stages), 1)
            stage = stages[0]
            self.assertTrue((stage / "VERSION").is_file())
            self.assertTrue((stage / "templates" / "new.html").is_file())
            self.assertFalse((stage / ".env").exists())
            self.assertFalse((stage / "db.sqlite3").exists())
            self.assertFalse((stage / "Backup").exists())
            self.assertFalse((Path(tmp) / "escape.txt").exists())
            nested = stage / "accounts" / "templates" / "accounts" / "base.html"
            self.assertTrue(nested.is_file())
            self.assertTrue((stage / "accounts" / "templates").is_dir())
            self.assertTrue(script.is_file())
            from core.selfupdate import read_progress
            pct, label = read_progress(base)
            self.assertEqual(pct, 12)
            self.assertIn("MB", label)
            from core.selfupdate import format_size
            self.assertEqual(format_size(524288), "0.5 MB")
            self.assertEqual(format_size(2 * 1024 * 1024 * 1024), "2.00 GB")
            text = script.read_text(encoding="utf-8")
            self.assertIn("v9.9.9", text)
            self.assertIn("Stop-Process", text)

    def test_bad_tag_and_bad_zip_abort(self):
        from core.selfupdate import UpdateError, perform_update
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "app"
            base.mkdir()
            (base / "db.sqlite3").write_bytes(b"data" * 30000)
            zf = _fixture_zip(Path(tmp) / "rel.zip")
            with self.assertRaises(UpdateError):
                perform_update(base, "not-a-version", zf.as_uri(),
                               tmp_root=Path(tmp))
            empty = Path(tmp) / "empty.zip"
            with zipfile.ZipFile(empty, "w") as z:
                z.writestr("README.md", "nope")
            with self.assertRaises(UpdateError):
                perform_update(base, "v9.9.9", empty.as_uri(),
                               tmp_root=Path(tmp))

    def test_second_run_blocked_while_in_flight(self):
        from core.selfupdate import UpdateError, perform_update
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "app"
            base.mkdir()
            (base / "db.sqlite3").write_bytes(b"data" * 30000)
            zf = _fixture_zip(Path(tmp) / "rel.zip")
            perform_update(base, "v9.9.9", zf.as_uri(), tmp_root=Path(tmp))
            with self.assertRaises(UpdateError) as cm:
                perform_update(base, "v9.9.9", zf.as_uri(),
                               tmp_root=Path(tmp))
            self.assertIn("already installing", str(cm.exception))

    def test_stale_lock_does_not_block(self):
        from core.selfupdate import _write_lock, update_in_progress
        import tempfile
        import time
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_lock(base, "v9.9.9")
            self.assertEqual(update_in_progress(base), "v9.9.9")
            lock = base / "Logs" / "update-in-progress.txt"
            old = time.time() - 20 * 60
            lock.write_text(f"v9.9.9\n{old}\n", encoding="utf-8")
            self.assertIsNone(update_in_progress(base))

    def test_applier_batch_markers(self):
        from core.selfupdate import write_apply_script
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            script = write_apply_script(base, Path(tmp) / "stage", "v9.9.9")
            text = script.read_text(encoding="utf-8")
            self.assertIn("update-in-progress", text)
            self.assertIn("Start-Sleep -Seconds 8", text)
            self.assertIn("FAILED: server would not stop", text)
            self.assertIn("taskkill /F /IM waitress-serve.exe", text)
            self.assertIn("killagain", text)
            self.assertIn("port owner", text)
            self.assertIn("update-progress", text)
            self.assertNotIn("timeout /t", text)

    def test_changelog_line_stripped(self):
        from unittest import mock
        from core.update import get_latest_release
        body = "Better balance math.\n\n**Full Changelog**: https://x/y"
        fake = {"tag_name": "v1.2.0", "name": "v1.2.0", "body": body,
                "assets": [{"browser_download_url": "https://x/nibba.zip"}]}
        with mock.patch("core.update._api", return_value=fake):
            info = get_latest_release("o/r")
        self.assertEqual(info["notes"], "Better balance math.")
        self.assertNotIn("Changelog", info["notes"])

    def test_last_status_roundtrip(self):
        from core.selfupdate import last_status
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self.assertIsNone(last_status(base))
            (base / "Logs").mkdir()
            (base / "Logs" / "update-last-run.txt").write_text(
                "2026-10-15 v9.9.9 OK\n", encoding="utf-8")
            self.assertIn("OK", last_status(base))


@override_settings(ALLOWED_HOSTS=["testserver"])
class ApplyUpdateViewTests(TestCase):
    def setUp(self):
        from accounts.models import User
        self.admin = User.objects.create_user(
            username="u_admin", password="1111", role=User.Role.ADMIN)
        self.staff = User.objects.create_user(
            username="u_staff", password="2222", role=User.Role.STAFF)

    def test_staff_blocked(self):
        self.client.force_login(self.staff)
        r = self.client.post("/update/apply/")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.get("/update/status/").status_code, 403)

    def test_status_feed_reports_lock_and_last_line(self):
        import tempfile
        self.client.force_login(self.admin)
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(BASE_DIR=tmp):
                r = self.client.get("/update/status/")
                self.assertEqual(r.status_code, 200)
                self.assertEqual(
                    r.json(), {"in_flight": None, "last": "",
                               "progress": None})
            from core.selfupdate import _write_lock, write_progress
            _write_lock(tmp, "v9.9.9")
            logs = Path(tmp) / "Logs"
            logs.mkdir(exist_ok=True)
            (logs / "update-last-run.txt").write_text(
                "someday v9.9.9 OK\n", encoding="utf-8")
            write_progress(tmp, 55, "Updating database")
            with override_settings(BASE_DIR=tmp):
                r = self.client.get("/update/status/")
                self.assertEqual(
                    r.json(), {"in_flight": "v9.9.9",
                               "last": "someday v9.9.9 OK",
                               "progress": {"pct": 55,
                                            "label": "Updating database"}})

    def test_progress_roundtrip_and_bounds(self):
        from core.selfupdate import read_progress, write_progress
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(read_progress(tmp))
            write_progress(tmp, 30, "Copying new files")
            self.assertEqual(read_progress(tmp), (30, "Copying new files"))
            write_progress(tmp, 999, "x")
            self.assertEqual(read_progress(tmp)[0], 100)

    def test_no_update_redirects(self):
        self.client.force_login(self.admin)
        r = self.client.post("/update/apply/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/help/", r["Location"])

    def test_owner_stages_and_sees_polling_page(self):
        import tempfile
        self.client.force_login(self.admin)
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            app.mkdir()
            (app / "db.sqlite3").write_bytes(b"d" * 100000)
            zf = _fixture_zip(Path(tmp) / "rel.zip")
            with mock.patch("core.selfupdate.resolve_update",
                            return_value=("v9.9.9", zf.as_uri())), \
                 mock.patch("core.selfupdate.tempfile.gettempdir",
                            return_value=tmp), \
                 mock.patch("core.selfupdate.launch_detached") as launched, \
                 override_settings(BASE_DIR=str(app)):
                r = self.client.post("/update/apply/")
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "Installing nibba v9.9.9")
            self.assertContains(r, "update-state")
            launched.assert_called_once()
            self.assertTrue((app / "apply_update.bat").is_file())
