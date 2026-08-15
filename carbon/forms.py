from django import forms

from .models import ActivityCategory

from django.forms import BaseFormSet, formset_factory

class ActivityEntryForm(forms.Form):
    """
    Form used to collect a single user activity entry.

    The user selects an active activity category and enters
    the quantity consumed/used.
    """

    category = forms.ModelChoiceField(
        queryset=ActivityCategory.objects.none(),
        empty_label="Select an activity",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    quantity = forms.DecimalField(
        min_value=0.0001,
        max_digits=12,
        decimal_places=4,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter quantity",
                "step": "0.0001",
                "min": "0.0001",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["category"].queryset = (
            ActivityCategory.objects.filter(is_active=True)
            .order_by("display_order", "name")
        )

class BaseActivityEntryFormSet(BaseFormSet):
    """
    Formset-level validation for a single carbon activity submission.
    """

    def clean(self):
        super().clean()

        if any(self.errors):
            return

        categories = set()

        for form in self.forms:
            category = form.cleaned_data.get("category")

            if category is None:
                continue

            if category in categories:
                raise forms.ValidationError(
                    "Each activity category can only be added once per submission."
                )

            categories.add(category)

ActivityEntryFormSet = formset_factory(
    ActivityEntryForm,
    formset=BaseActivityEntryFormSet,
    extra=1,
)
