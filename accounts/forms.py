from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import CustomUser

from carbon.models import BenchmarkScope, CarbonBenchmark, UserLocation

class CustomUserCreationForm(UserCreationForm):
    """
    Form used to register a new user.
    """

    class Meta:
        model = CustomUser

        fields = (
            "email",
            "full_name",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["email"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "Enter your email",
        })

        self.fields["full_name"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "Enter your full name",
        })

        self.fields["password1"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "Create a password",
        })

        self.fields["password2"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "Confirm your password",
        })

class CustomAuthenticationForm(AuthenticationForm):
    """
    Form used to authenticate an existing user.
    """

    username = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your email",
            }
        )
    )

    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your password",
            }
        )
    )

class UserLocationForm(forms.ModelForm):
    """
    Form used to configure the user's benchmarking location.

    State and district choices are derived from the active
    historical benchmark dataset.
    """

    state = forms.ChoiceField(
        label="State",
        required=True,
        choices=(),
        widget=forms.Select(
            attrs={
                "class": "form-select",
                "id": "id_state",
            }
        ),
    )

    district = forms.ChoiceField(
        label="District",
        required=True,
        choices=(),
        widget=forms.Select(
            attrs={
                "class": "form-select",
                "id": "id_district",
            }
        ),
    )

    class Meta:
        model = UserLocation
        fields = (
            "state",
            "district",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        benchmarks = (
            CarbonBenchmark.objects.filter(
                scope=BenchmarkScope.DISTRICT,
                is_active=True,
            )
            .values_list("state", "district")
            .order_by("state", "district")
        )

        state_names = []
        district_pairs = []

        seen_states = set()
        seen_districts = set()
        districts_by_state = {}

        for state, district in benchmarks:
            normalized_state = self._normalize(state)
            normalized_district = self._normalize(district)

            if normalized_state not in seen_states:
                state_names.append(state)
                seen_states.add(normalized_state)

            district_key = (normalized_state, normalized_district)

            if district_key not in seen_districts:
                district_pairs.append((state, district))
                seen_districts.add(district_key)

                districts_by_state.setdefault(normalized_state, []).append(
                    {
                        "value": district,
                        "label": district,
                    }
                )

        self.fields["state"].choices = [
            ("", "Select your state")
        ] + [
            (state, state)
            for state in state_names
        ]

        self.fields["district"].choices = [
            ("", "Select your district")
        ] + [
            (
                district,
                district,
            )
            for state, district in district_pairs
        ]

        self.districts_by_state = districts_by_state

        # Match an already saved location against the benchmark
        # dataset without requiring exact capitalization.
        if self.instance and self.instance.pk:
            saved_state = self._normalize(self.instance.state)
            saved_district = self._normalize(self.instance.district)

            for state, district in district_pairs:
                if self._normalize(state) == saved_state:
                    self.initial["state"] = state

                    if self._normalize(district) == saved_district:
                        self.initial["district"] = district

                    break

    @staticmethod
    def _normalize(value):
        return " ".join(value.strip().split()).casefold()

    def clean(self):
        cleaned_data = super().clean()

        state = cleaned_data.get("state")
        district = cleaned_data.get("district")

        if not state or not district:
            return cleaned_data

        state_normalized = self._normalize(state)
        district_normalized = self._normalize(district)

        exists = CarbonBenchmark.objects.filter(
            scope=BenchmarkScope.DISTRICT,
            is_active=True,
        ).exists()

        if not exists:
            raise forms.ValidationError(
                "No active district benchmarks are currently available."
            )

        valid_pair = False

        benchmarks = CarbonBenchmark.objects.filter(
            scope=BenchmarkScope.DISTRICT,
            is_active=True,
        ).values_list("state", "district")

        for benchmark_state, benchmark_district in benchmarks:
            if (
                self._normalize(benchmark_state) == state_normalized
                and self._normalize(benchmark_district)
                == district_normalized
            ):
                cleaned_data["state"] = benchmark_state
                cleaned_data["district"] = benchmark_district
                valid_pair = True
                break

        if not valid_pair:
            raise forms.ValidationError(
                "Please select a valid state and district "
                "from the available benchmark locations."
            )

        return cleaned_data