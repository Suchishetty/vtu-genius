from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import StudentProfile


User = get_user_model()


class AuthenticationModuleTests(TestCase):
    def register_payload(self, email="student@vtu.edu"):
        return {
            "full_name": "VTU Student",
            "email": email,
            "branch": StudentProfile.BRANCH_CSE,
            "semester": StudentProfile.SEMESTER_5,
            "password": "StrongPass1",
            "confirm_password": "StrongPass1",
        }

    def create_user_with_profile(self, email="student@vtu.edu", password="StrongPass1"):
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
        )
        StudentProfile.objects.create(
            user=user,
            full_name="VTU Student",
            email=email,
            branch=StudentProfile.BRANCH_CSE,
            semester=StudentProfile.SEMESTER_5,
        )
        return user

    def test_registration_creates_user_and_profile(self):
        response = self.client.post(reverse("accounts:register"), data=self.register_payload())

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertTrue(User.objects.filter(email="student@vtu.edu").exists())
        self.assertTrue(StudentProfile.objects.filter(email="student@vtu.edu").exists())

    def test_registration_rejects_duplicate_email(self):
        self.create_user_with_profile()

        response = self.client.post(reverse("accounts:register"), data=self.register_payload())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This email is already registered.")

    def test_registration_rejects_weak_password(self):
        payload = self.register_payload()
        payload["password"] = "weakpass"
        payload["confirm_password"] = "weakpass"

        response = self.client.post(reverse("accounts:register"), data=payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Password must contain at least one uppercase letter.")

    def test_login_with_email_redirects_to_dashboard(self):
        self.create_user_with_profile()

        response = self.client.post(
            reverse("accounts:login"),
            data={"email": "student@vtu.edu", "password": "StrongPass1", "remember_me": True},
        )

        self.assertRedirects(response, reverse("dashboard:dashboard_home"))

    def test_invalid_login_shows_error(self):
        self.create_user_with_profile()

        response = self.client.post(
            reverse("accounts:login"),
            data={"email": "student@vtu.edu", "password": "WrongPass1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password.")

    def test_logout_redirects_home(self):
        user = self.create_user_with_profile()
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:logout"))

        self.assertRedirects(response, reverse("accounts:home"))

    def test_profile_requires_login(self):
        response = self.client.get(reverse("accounts:profile"))

        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('accounts:profile')}")

    def test_profile_displays_student_data(self):
        user = self.create_user_with_profile()
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "VTU Student")
        self.assertContains(response, "student@vtu.edu")
        self.assertContains(response, StudentProfile.BRANCH_CSE)
        self.assertContains(response, StudentProfile.SEMESTER_5)

    def test_change_password_requires_login(self):
        response = self.client.get(reverse("accounts:change_password"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('accounts:change_password')}",
        )

    def test_change_password_updates_password(self):
        user = self.create_user_with_profile()
        self.client.force_login(user)

        response = self.client.post(
            reverse("accounts:change_password"),
            data={
                "old_password": "StrongPass1",
                "new_password1": "NewStrongPass1",
                "new_password2": "NewStrongPass1",
            },
        )

        user.refresh_from_db()
        self.assertRedirects(response, reverse("accounts:profile"))
        self.assertTrue(user.check_password("NewStrongPass1"))

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard:dashboard_home"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('dashboard:dashboard_home')}",
        )

    def test_dashboard_shows_profile_summary_for_logged_in_user(self):
        user = self.create_user_with_profile()
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard:dashboard_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome, VTU Student.")
        self.assertContains(response, StudentProfile.BRANCH_CSE)
        self.assertContains(response, StudentProfile.SEMESTER_5)
