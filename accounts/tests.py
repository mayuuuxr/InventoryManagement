from django.test import Client, TestCase, override_settings

from .models import User


@override_settings(ALLOWED_HOSTS=["testserver"])
class LoginLockoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="lock_u", password="1234", role=User.Role.STAFF)
        self.url = "/accounts/login/"

    def _wrong(self):
        return self.client.post(
            self.url, {"username": "lock_u", "password": "9999"})

    def test_wrong_pin_shows_attempts_left(self):
        r = self._wrong()
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "koshish")

    def test_five_wrong_then_lockout_redirects_to_login(self):
        for _ in range(4):
            r = self._wrong()
            self.assertEqual(r.status_code, 200)
        # 5th wrong try hits the limit: back to login page, not a 403.
        r = self._wrong()
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/?locked=1", r["Location"])

    def test_locked_login_page_shows_timer(self):
        for _ in range(5):
            self._wrong()
        r = self.client.get("/accounts/login/?locked=1")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Login locked for 1 hour")
        self.assertContains(r, 'id="lockout-timer"')
        self.assertTrue(r.context["locked_out"])
        self.assertGreater(r.context["lockout_until_ms"], 0)

    def test_correct_pin_still_works_when_not_locked(self):
        r = self.client.post(
            self.url, {"username": "lock_u", "password": "1234"})
        self.assertEqual(r.status_code, 302)

    def test_other_id_can_login_while_one_locked(self):
        # Staff locked on this browser/IP — admin ki sahi PIN ab bhi
        # andar jaati hai (lock sirf us ID par hai).
        User.objects.create_user(
            username="lock_admin", password="5678", role=User.Role.ADMIN)
        for _ in range(5):
            self._wrong()
        r = self.client.post(
            self.url, {"username": "lock_admin", "password": "5678"})
        self.assertEqual(r.status_code, 302)

    def test_lock_does_not_spread_to_other_devices(self):
        # Ek phone/IP par lock → doosre phone (alag IP) par wahi ID ab bhi
        # login kar sakta hai. Lock (IP, username) dono par lagta hai taaki
        # koi attacker kisi aur ki ID ko door se lock na kar sake.
        for _ in range(5):
            self._wrong()
        c2 = Client(REMOTE_ADDR="10.9.9.9")
        r = c2.post(
            self.url, {"username": "lock_u", "password": "1234"})
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("locked=1", r["Location"])

    def test_banner_names_locked_id_and_clears_after_login(self):
        User.objects.create_user(
            username="lock_admin2", password="5678", role=User.Role.ADMIN)
        for _ in range(5):
            self._wrong()
        r = self.client.get("/accounts/login/?locked=1")
        self.assertContains(r, "Login locked for 1 hour")
        self.assertNotContains(r, "lock_u")  # privacy: no usernames shown
        # Doosri ID se sahi login ke baad nishan clear — logout par
        # banner nahi.
        self.client.post(
            self.url, {"username": "lock_admin2", "password": "5678"})
        self.client.post("/accounts/logout/")
        r = self.client.get(self.url)
        self.assertFalse(r.context["locked_out"])
        self.assertNotContains(r, "Login locked for 1 hour")
