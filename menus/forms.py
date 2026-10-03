"""Forms for creating menus and pricing their items."""
from django import forms

from .models import Menu, MenuItem


class MenuForm(forms.ModelForm):
    """Create a menu; the owner is supplied by the view, not the form."""

    class Meta:
        model = Menu
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Summer cocktails"})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if Menu.objects.filter(user=self.user, name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("You already have a menu with this name.")
        return name

    def save(self, commit=True):
        self.instance.user = self.user
        return super().save(commit=commit)


class MenuItemForm(forms.ModelForm):
    """Edit the cost and selling price of one menu item."""

    class Meta:
        model = MenuItem
        fields = ["cost", "price"]
        widgets = {
            "cost": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        }
