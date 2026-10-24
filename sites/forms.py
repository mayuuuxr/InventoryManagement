from django import forms

from .models import Site


class SiteForm(forms.ModelForm):
    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError("Shop name is required.")
        dup = Site.objects.filter(name__iexact=name)
        if self.instance.pk:
            dup = dup.exclude(pk=self.instance.pk)
        if dup.exists():
            raise forms.ValidationError(
                "A shop with this name already exists.")
        return name

    class Meta:
        model = Site
        fields = ("name", "location")
        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "e.g. Main Shop",
                "autofocus": True,
            }),
            "location": forms.TextInput(attrs={
                "placeholder": "e.g. Market Road",
            }),
        }
