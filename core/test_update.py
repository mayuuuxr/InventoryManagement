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
            stage = Path(tmp) / "nibba_update_stage"
            self.assertTrue((stage / "VERSION").is_file())
            self.assertTrue((stage / "templates" / "new.html").is_file())
            self.assertFalse((stage / ".env").exists())
            self.assertFalse((stage / "db.sqlite3").exists())
            self.assertFalse((stage / "Backup").exists())
            self.assertFalse((Path(tmp) / "escape.txt").exists())
            self.assertTrue(script.is_file())
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
