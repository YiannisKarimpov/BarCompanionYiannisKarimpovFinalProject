"""Views for registration, login and logout."""
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import EmailLoginForm, RegisterForm


class BarLoginView(LoginView):
    """Log a user in with email and password."""

    authentication_form = EmailLoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


def register(request):
    """Create a new account, log the user in and send them to the dashboard."""
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to Bar Companion, {user.first_name}.")
            return redirect("core:dashboard")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})
