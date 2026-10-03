"""Views for the menu builder.

Every view requires login and only touches the current user's own menus, so one
bartender can never see or change another's.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from recipes import services

from .forms import MenuForm, MenuItemForm
from .models import Menu, MenuItem


class OwnMenuMixin(LoginRequiredMixin):
    """Restrict the queryset to the logged-in user's menus."""

    model = Menu

    def get_queryset(self):
        return Menu.objects.filter(user=self.request.user)


class MenuListView(OwnMenuMixin, ListView):
    template_name = "menus/menu_list.html"
    context_object_name = "menus"


class MenuCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    form_class = MenuForm
    template_name = "menus/menu_form.html"
    success_message = "Menu created. Add drinks from any recipe page."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("menus:detail", args=[self.object.pk])


class MenuDetailView(OwnMenuMixin, DetailView):
    template_name = "menus/menu_detail.html"
    context_object_name = "menu"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        items = list(self.object.items.all())
        context["items"] = items
        context["average_margin"] = self.object.average_margin_percent()
        context["unpriced"] = sum(1 for item in items if item.price <= 0)
        return context


class MenuDeleteView(OwnMenuMixin, SuccessMessageMixin, DeleteView):
    template_name = "menus/menu_confirm_delete.html"
    success_url = reverse_lazy("menus:list")
    success_message = "Menu deleted."


class ItemUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """Set the cost and price of one item (only on the user's own menus)."""

    form_class = MenuItemForm
    template_name = "menus/item_form.html"
    success_message = "Prices updated."

    def get_queryset(self):
        return MenuItem.objects.filter(menu__user=self.request.user).select_related("menu")

    def get_success_url(self):
        return reverse("menus:detail", args=[self.object.menu_id])


@login_required
@require_POST
def add_item(request, drink_id):
    """Add a recipe to one of the user's menus (cost and price start at 0)."""
    menu = get_object_or_404(Menu, pk=request.POST.get("menu") or 0, user=request.user)
    if MenuItem.objects.filter(menu=menu, drink_id=drink_id).exists():
        messages.info(request, f"That drink is already on {menu.name}.")
        return redirect("menus:detail", pk=menu.pk)
    try:
        drink = services.get_cocktail(drink_id)
    except services.CocktailAPIError:
        drink = None
    if drink is None:
        raise Http404("Cocktail not found")
    MenuItem.objects.create(menu=menu, drink_id=drink["id"], name=drink["name"], thumb=drink["thumb"])
    messages.success(request, f"{drink['name']} added to {menu.name}. Set its cost and price below.")
    return redirect("menus:detail", pk=menu.pk)


@login_required
@require_POST
def remove_item(request, pk):
    """Remove one item from a menu."""
    item = get_object_or_404(MenuItem, pk=pk, menu__user=request.user)
    menu_id = item.menu_id
    item.delete()
    messages.success(request, "Removed from the menu.")
    return redirect("menus:detail", pk=menu_id)
