from django.test import TestCase

from carbon.forms import ActivityEntryForm, ActivityEntryFormSet
from carbon.models import ActivityCategory


class ActivityEntryFormTests(TestCase):
    """
    Tests for the user-facing activity entry form.
    """

    @classmethod
    def setUpTestData(cls):
        cls.electricity = ActivityCategory.objects.create(
            name="Electricity",
            description="Electricity consumption",
            unit="kWh",
            display_order=1,
            is_active=True,
        )

        cls.transportation = ActivityCategory.objects.create(
            name="Transportation",
            description="Transportation activity",
            unit="km",
            display_order=2,
            is_active=True,
        )

        cls.inactive_category = ActivityCategory.objects.create(
            name="Inactive Category",
            description="Disabled category",
            unit="unit",
            display_order=3,
            is_active=False,
        )

    def test_valid_activity_entry(self):
        form = ActivityEntryForm(
            data={
                "category": self.electricity.pk,
                "quantity": "100",
            }
        )

        self.assertTrue(form.is_valid())

    def test_zero_quantity_is_invalid(self):
        form = ActivityEntryForm(
            data={
                "category": self.electricity.pk,
                "quantity": "0",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)

    def test_inactive_category_is_not_available(self):
        form = ActivityEntryForm(
            data={
                "category": self.inactive_category.pk,
                "quantity": "100",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)


class ActivityEntryFormSetTests(TestCase):
    """
    Tests for multi-entry submission validation.
    """

    @classmethod
    def setUpTestData(cls):
        cls.electricity = ActivityCategory.objects.create(
            name="Electricity",
            description="Electricity consumption",
            unit="kWh",
            display_order=1,
            is_active=True,
        )

        cls.transportation = ActivityCategory.objects.create(
            name="Transportation",
            description="Transportation activity",
            unit="km",
            display_order=2,
            is_active=True,
        )

    def test_valid_multiple_entries(self):
        formset = ActivityEntryFormSet(
            data={
                "form-TOTAL_FORMS": "2",
                "form-INITIAL_FORMS": "0",
                "form-0-category": str(self.electricity.pk),
                "form-0-quantity": "100",
                "form-1-category": str(self.transportation.pk),
                "form-1-quantity": "50",
            }
        )

        self.assertTrue(formset.is_valid())

    def test_duplicate_categories_are_rejected(self):
        formset = ActivityEntryFormSet(
            data={
                "form-TOTAL_FORMS": "2",
                "form-INITIAL_FORMS": "0",
                "form-0-category": str(self.electricity.pk),
                "form-0-quantity": "100",
                "form-1-category": str(self.electricity.pk),
                "form-1-quantity": "50",
            }
        )

        self.assertFalse(formset.is_valid())
        self.assertTrue(formset.non_form_errors())