import re

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.password_validation import password_validators_help_text_html
from django.core.exceptions import ValidationError

from .models import StudentProfile


User = get_user_model()


class BootstrapFormMixin:
    field_classes = {
        forms.CheckboxInput: "form-check-input",
        forms.Select: "form-select",
    }
    default_class = "form-control"

    def apply_bootstrap_classes(self):
        for field in self.fields.values():
            widget = field.widget
            css_class = self.default_class

            for widget_type, widget_class in self.field_classes.items():
                if isinstance(widget, widget_type):
                    css_class = widget_class
                    break

            existing_classes = widget.attrs.get("class", "").strip()
            widget.attrs["class"] = f"{existing_classes} {css_class}".strip()


class RegistrationForm(BootstrapFormMixin, forms.Form):
    full_name = forms.CharField(
        max_length=255,
        label="Full Name",
        widget=forms.TextInput(attrs={"placeholder": "Enter your full name"}),
        error_messages={"required": "Please enter your full name."},
    )
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={"placeholder": "Enter your email address"}),
        error_messages={
            "required": "Please enter your email address.",
            "invalid": "Enter a valid email address.",
        },
    )
    branch = forms.ChoiceField(
        label="Branch",
        choices=[("", "Select your branch")] + StudentProfile.BRANCH_CHOICES,
        widget=forms.Select(),
        error_messages={"required": "Please select your branch."},
    )
    semester = forms.ChoiceField(
        label="Semester",
        choices=[("", "Select your semester")] + StudentProfile.SEMESTER_CHOICES,
        widget=forms.Select(),
        error_messages={"required": "Please select your semester."},
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Create a strong password"}),
        error_messages={"required": "Please enter a password."},
        help_text="Use at least 8 characters with uppercase, lowercase, and a number.",
    )
    confirm_password = forms.CharField(
        label="Confirm Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Re-enter your password"}),
        error_messages={"required": "Please confirm your password."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap_classes()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists() or StudentProfile.objects.filter(email__iexact=email).exists():
            raise ValidationError("This email is already registered.")

        return email

    def clean_password(self):
        password = self.cleaned_data["password"]

        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        if not re.search(r"[A-Z]", password):
            raise ValidationError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", password):
            raise ValidationError("Password must contain at least one lowercase letter.")
        if not re.search(r"\d", password):
            raise ValidationError("Password must contain at least one number.")

        validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Confirm Password must match Password.")

        return cleaned_data

    def save(self):
        full_name = self.cleaned_data["full_name"].strip()
        email = self.cleaned_data["email"]
        branch = self.cleaned_data["branch"]
        semester = self.cleaned_data["semester"]
        password = self.cleaned_data["password"]

        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=full_name,
            password=password,
        )

        StudentProfile.objects.create(
            user=user,
            full_name=full_name,
            email=email,
            branch=branch,
            semester=semester,
        )

        return user


class LoginForm(BootstrapFormMixin, forms.Form):
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={"placeholder": "Enter your email address"}),
        error_messages={
            "required": "Please enter your email address.",
            "invalid": "Enter a valid email address.",
        },
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Enter your password"}),
        error_messages={"required": "Please enter your password."},
    )
    remember_me = forms.BooleanField(
        label="Remember Me",
        required=False,
    )

    error_messages = {
        "invalid_login": "Invalid email or password.",
        "inactive": "This account is inactive.",
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)
        self.apply_bootstrap_classes()

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if not email or not password:
            return cleaned_data

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise ValidationError(self.error_messages["invalid_login"])

        self.user_cache = authenticate(
            self.request,
            username=user.username,
            password=password,
        )

        if self.user_cache is None:
            raise ValidationError(self.error_messages["invalid_login"])

        if not self.user_cache.is_active:
            raise ValidationError(self.error_messages["inactive"])

        return cleaned_data

    def get_user(self):
        return self.user_cache


class ChangePasswordForm(BootstrapFormMixin, DjangoPasswordChangeForm):
    old_password = forms.CharField(
        label="Current Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Enter your current password"}),
    )
    new_password1 = forms.CharField(
        label="New Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Enter your new password"}),
        help_text=password_validators_help_text_html(),
    )
    new_password2 = forms.CharField(
        label="Confirm New Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Re-enter your new password"}),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.apply_bootstrap_classes()
