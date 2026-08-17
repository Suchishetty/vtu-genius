from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import StudentProfile


class RegistrationForm(UserCreationForm):
    """
    Custom registration form that creates both User and StudentProfile.
    Extends Django's UserCreationForm with additional fields for student information.
    When saved, creates a User account and links a StudentProfile to it.
    """
    
    full_name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your full name',
            'autocomplete': 'name',
        }),
        label='Full Name'
    )
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address',
            'autocomplete': 'email',
        }),
        label='Email Address'
    )
    
    branch = forms.ChoiceField(
        choices=StudentProfile.BRANCH_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control',
        }),
        label='Branch'
    )
    
    semester = forms.ChoiceField(
        choices=StudentProfile.SEMESTER_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control',
        }),
        label='Current Semester'
    )
    
    password1 = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter a strong password',
            'autocomplete': 'new-password',
        }),
        label='Password',
        help_text='Password must contain at least 8 characters and cannot be entirely numeric.'
    )
    
    password2 = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password',
            'autocomplete': 'new-password',
        }),
        label='Confirm Password',
        help_text='Enter the same password for verification.'
    )
    
    class Meta:
        model = User
        fields = ('full_name', 'email', 'branch', 'semester', 'password1', 'password2')
    
    def clean_email(self):
        """
        Validate that email is unique across both User and StudentProfile models.
        Prevents duplicate email registrations.
        """
        email = self.cleaned_data.get('email')
        
        # Check if email exists in User model
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                'An account with this email already exists. Please use a different email.'
            )
        
        # Check if email exists in StudentProfile
        if StudentProfile.objects.filter(email=email).exists():
            raise forms.ValidationError(
                'An account with this email already exists. Please use a different email.'
            )
        
        return email
    
    def clean_password2(self):
        """
        Validate that both passwords match.
        Django's UserCreationForm validates password strength; we ensure they match.
        """
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(
                'Passwords do not match. Please enter the same password in both fields.'
            )
        
        return password2
    
    def save(self, commit=True):
        """
        Save method that creates both User and StudentProfile instances.
        
        Process:
        1. Create Django User with email as username
        2. Create StudentProfile linked to the User
        3. Return the User instance
        
        This ensures data consistency between User and StudentProfile.
        """
        # Extract cleaned form data
        email = self.cleaned_data['email']
        full_name = self.cleaned_data['full_name']
        branch = self.cleaned_data['branch']
        semester = self.cleaned_data['semester']
        password = self.cleaned_data['password1']
        
        # Create Django User instance with email as username
        user = User.objects.create_user(
            username=email,  # Username = Email (simplifies login)
            email=email,
            password=password
        )
        
        # Create StudentProfile linked to the User
        profile = StudentProfile.objects.create(
            user=user,          # OneToOne link to User
            full_name=full_name,
            email=email,
            branch=branch,
            semester=semester
        )
        
        return user
