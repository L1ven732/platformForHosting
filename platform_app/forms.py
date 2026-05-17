"""Формы приложения."""

import logging

from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from .models import UserProfile

logger = logging.getLogger(__name__)


class SignUpForm(UserCreationForm):
    """Форма регистрации с дополнительным полем роли."""

    email = forms.EmailField(required=True)
    role = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Например: Python разработчик'
        }),
        label="Роль"
    )

    class Meta:
        """Meta"""

        model = User
        fields = ('username', 'email', 'role', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Придумайте имя пользователя'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Придумайте пароль'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Повторите пароль'
        })

        logger.debug("SignUpForm initialized with fields=%s",
                     list(self.fields.keys()))


class UserUpdateForm(forms.ModelForm):
    """UserUpdateForm"""

    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    email = forms.EmailField(required=False)

    class Meta:
        """Meta"""

        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'email'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control'
            })


class ProfileUpdateForm(forms.ModelForm):
    """ProfileUpdateForm"""

    cropped_image = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )

    class Meta:
        """Meta"""

        model = UserProfile

        fields = [
            'role',
            'avatar'
        ]

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.fields['role'].widget.attrs.update({
            'class': 'form-control'
        })

        self.fields['avatar'].widget.attrs.update({
            'class': 'form-control'
        })


class StyledPasswordChangeForm(PasswordChangeForm):
    """StyledPasswordChangeForm"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control'
            })
