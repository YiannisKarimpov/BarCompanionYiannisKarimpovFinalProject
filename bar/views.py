"""Views for the "My bar" stock pages.

Every view requires login and only ever touches the current user's own stock
lines, so one bartender can never see or change another's.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import BarStockForm
from .models import BarStock


class OwnStockMixin(LoginRequiredMixin):
    """Restrict the queryset to the logged-in user's stock lines."""

    model = BarStock
    success_url = reverse_lazy("bar:list")

    def get_queryset(self):
        return BarStock.objects.filter(user=self.request.user).select_related("ingredient")


class StockListView(OwnStockMixin, ListView):
    """List the user's stock."""

    template_name = "bar/stock_list.html"
    context_object_name = "items"


class StockFormMixin(OwnStockMixin, SuccessMessageMixin):
    """Shared behaviour for the add and edit forms."""

    form_class = BarStockForm
    template_name = "bar/stock_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class StockCreateView(StockFormMixin, CreateView):
    """Add an ingredient to the user's bar."""

    success_message = "Added to your bar."


class StockUpdateView(StockFormMixin, UpdateView):
    """Edit the quantity or unit of an existing stock line."""

    success_message = "Stock updated."


class StockDeleteView(OwnStockMixin, SuccessMessageMixin, DeleteView):
    """Confirm and remove a stock line."""

    template_name = "bar/stock_confirm_delete.html"
    success_message = "Removed from your bar."
