"""Views for the public landing page and the logged-in dashboard."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def home(request):
    """Public landing page describing Bar Companion."""
    return render(request, "core/home.html")


@login_required
def dashboard(request):
    """Personal dashboard shown after login (features are added week by week)."""
    context = {
        "stock_count": request.user.stock_items.count(),
        "favourites": request.user.favourites.all()[:5],
        "menu_count": request.user.menus.count(),
        "favourite_count": request.user.favourites.count(),
    }
    return render(request, "core/dashboard.html", context)
