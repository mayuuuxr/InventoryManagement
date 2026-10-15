"""Unit tests for the GitHub-Releases updater (pure logic, no network)."""
from django.test import SimpleTestCase

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
