"""Site administration pages for users with admin access.

These sit on the public site (``/manage/``) so an admin does not have to use
Django's built-in admin. Every view is limited to admins: anonymous visitors are
sent to log in, and logged-in non-admins get a 403 page.
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User
from bar.models import BarStock, Ingredient
from menus.models import Menu
from recipes.models import Favourite


def admin_required(view):
    """Allow only logged-in users with admin access (admin role or superuser)."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.has_admin_access:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


@admin_required
def overview(request):
    """Site totals and the list of users with their activity."""
    users = User.objects.annotate(
        stock_total=Count("stock_items", distinct=True),
        menu_total=Count("menus", distinct=True),
        favourite_total=Count("favourites", distinct=True),
    ).order_by("email")
    context = {
        "users": users,
        "roles": User.Role.choices,
        "totals": {
            "users": User.objects.count(),
            "admins": User.objects.filter(role=User.Role.ADMIN).count(),
            "stock": BarStock.objects.count(),
            "menus": Menu.objects.count(),
            "favourites": Favourite.objects.count(),
        },
    }
    return render(request, "core/manage_overview.html", context)


@admin_required
@require_POST
def change_role(request, pk):
    """Set a user's role. Admins cannot change their own role."""
    user = get_object_or_404(User, pk=pk)
    role = request.POST.get("role")
    if user == request.user:
        messages.error(request, "You cannot change your own role.")
    elif role not in User.Role.values:
        messages.error(request, "Unknown role.")
    else:
        user.role = role
        user.save(update_fields=["role"])
        messages.success(request, f"{user.email} is now {user.get_role_display().lower()}.")
    return redirect("core:manage")


@admin_required
@require_POST
def toggle_active(request, pk):
    """Deactivate or reactivate an account. Admins cannot deactivate themselves."""
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
    else:
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        messages.success(request, f"{user.email} {'reactivated' if user.is_active else 'deactivated'}.")
    return redirect("core:manage")


@admin_required
def ingredients(request):
    """List the shared ingredient names and how many bars hold each."""
    items = Ingredient.objects.annotate(in_bars=Count("stock_items")).order_by("name")
    return render(request, "core/manage_ingredients.html", {"ingredients": items})


@admin_required
@require_POST
def delete_ingredient(request, pk):
    """Delete an ingredient name, but only if no bar is using it."""
    ingredient = get_object_or_404(Ingredient, pk=pk)
    if ingredient.stock_items.exists():
        messages.error(request, f"{ingredient.name} is in use and cannot be deleted.")
    else:
        ingredient.delete()
        messages.success(request, f"{ingredient.name} deleted.")
    return redirect("core:manage_ingredients")
