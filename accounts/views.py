from django.shortcuts import render, redirect
from django.views.generic import CreateView
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.views import PasswordChangeView as DjangoPasswordChangeView
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .forms import RegistrationForm


def home(request):
    """
    Home view that renders the landing page.
    """
    return render(request, "landing_page.html")


class RegistrationView(UserPassesTestMixin, CreateView):
    """
    Registration view for creating new student accounts.
    
    Features:
    - Uses RegistrationForm which creates both User and StudentProfile
    - Prevents authenticated users from accessing registration
    - Shows success message after registration
    - Redirects to login page for new users
    - Displays validation errors inline in form
    
    Inherits from:
    - UserPassesTestMixin: Controls access based on test_func()
    - CreateView: Handles form display and model creation
    """
    
    form_class = RegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('accounts:login')
    
    def test_func(self):
        """
        Access control function.
        
        Returns:
        - True: User is anonymous (allow registration)
        - False: User is authenticated (deny registration)
        """
        return not self.request.user.is_authenticated
    
    def handle_no_permission(self):
        """
        Called when test_func() returns False (user is authenticated).
        Redirects authenticated users to home page.
        
        Flow:
        1. Authenticated user tries to visit /register/
        2. test_func() returns False
        3. handle_no_permission() is called
        4. Redirects to home with info message
        """
        messages.info(
            self.request,
            'You are already registered. Redirecting to home.'
        )
        return redirect('accounts:home')
    
    def form_valid(self, form):
        """
        Called when form submission is valid and ready to save.
        
        Process:
        1. Call parent's form_valid() to save User and StudentProfile
        2. Show success message
        3. Redirect to login page
        
        The RegistrationForm.save() method handles:
        - Creating Django User with email as username
        - Creating StudentProfile linked to User
        - Hashing password securely
        """
        response = super().form_valid(form)
        messages.success(
            self.request,
            'Registration completed successfully. Please login.'
        )
        return response


class LoginView(DjangoLoginView):
    """
    Login view for authenticating student users.
    
    Features:
    - Uses Django's built-in LoginView from django.contrib.auth.views
    - Uses AuthenticationForm for credentials validation
    - Prevents already-authenticated users from accessing login page
    - Shows success message after login
    - Shows error message if authentication fails
    - Redirects to dashboard:dashboard after successful login
    
    Inherits from:
    - DjangoLoginView: Built-in Django authentication view
    """
    
    form_class = AuthenticationForm
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True  # Prevent logged-in users from accessing this view
    
    def get_success_url(self):
        """
        Returns the redirect URL after successful login.
        
        Returns:
        - dashboard:dashboard (dashboard home page for authenticated user)
        """
        return reverse_lazy('dashboard:dashboard')
    
    def form_valid(self, form):
        """
        Called when login form is valid and authentication succeeds.
        
        Process:
        1. Call parent's form_valid() to authenticate user and set session
        2. Show success message to user
        3. Redirect to dashboard (via get_success_url)
        
        The form.cleaned_data contains:
        - username: Email address or username entered by user
        - password: User's password (validated against database)
        
        Parent's form_valid() calls:
        - auth.authenticate(username=..., password=...) to verify credentials
        - auth.login(request, user) to create session
        - redirect() to success_url
        """
        response = super().form_valid(form)
        messages.success(
            self.request,
            'Login successful. Welcome back.'
        )
        return response
    
    def form_invalid(self, form):
        """
        Called when login form is invalid (authentication fails).
        
        Process:
        1. Show error message explaining authentication failed
        2. Re-render login form with error details
        
        Common failure reasons:
        - Email/username doesn't exist in User table
        - Password is incorrect for the user
        - Account is inactive/disabled
        - User account was deleted
        
        Django's AuthenticationForm automatically validates:
        - Username field is required
        - Password field is required
        - Username and password match an existing active user
        """
        messages.error(
            self.request,
            'Invalid username or password.'
        )
        return super().form_invalid(form)


class PasswordChangeView(LoginRequiredMixin, DjangoPasswordChangeView):
    """
    Password change view for authenticated users.

    Features:
    - Restricts access to logged-in users only
    - Uses Django's built-in password validation and hashing
    - Shows a success message after password update
    - Redirects to the student profile page after success
    """

    template_name = 'accounts/change_password.html'
    success_url = reverse_lazy('dashboard:profile')
    login_url = reverse_lazy('accounts:login')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            'Your password has been changed successfully.'
        )
        return response
