"""Form for adding and editing a stock line."""
from django import forms

from .models import BarStock, Ingredient


class BarStockForm(forms.ModelForm):
    """Add or edit a stock line, entering the ingredient by name.

    The ingredient is typed as text. If an ingredient with that name already
    exists (ignoring capitalisation) it is reused, otherwise it is created.
    The owner is passed in by the view and set on save, never taken from the
    submitted data.
    """

    ingredient_name = forms.CharField(max_length=100, label="Ingredient")

    class Meta:
        model = BarStock
        fields = ["quantity", "unit"]

    field_order = ["ingredient_name", "quantity", "unit"]

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if self.instance.pk:
            self.fields["ingredient_name"].initial = self.instance.ingredient.name
        for name, field in self.fields.items():
            css = "form-select" if name == "unit" else "form-control"
            field.widget.attrs.setdefault("class", css)

    def clean_ingredient_name(self):
        """Collapse repeated spaces so "  dry   vermouth " becomes "dry vermouth"."""
        name = " ".join(self.cleaned_data["ingredient_name"].split())
        if not name:
            raise forms.ValidationError("Enter an ingredient name.")
        return name

    def clean(self):
        """Reject a second stock line for an ingredient the user already holds."""
        cleaned = super().clean()
        name = cleaned.get("ingredient_name")
        if name:
            duplicates = BarStock.objects.filter(user=self.user, ingredient__name__iexact=name)
            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                self.add_error("ingredient_name", "This ingredient is already in your bar. Edit it instead.")
        return cleaned

    def save(self, commit=True):
        """Attach the (existing or new) ingredient and the owner, then save."""
        name = self.cleaned_data["ingredient_name"]
        ingredient = Ingredient.objects.filter(name__iexact=name).first()
        if ingredient is None:
            ingredient = Ingredient.objects.create(name=name)
        self.instance.ingredient = ingredient
        self.instance.user = self.user
        return super().save(commit=commit)
