from django import forms

from .models import RestaurantMapProfile


class RestaurantPhotoForm(forms.ModelForm):
    class Meta:
        model = RestaurantMapProfile
        fields = ("image_url",)
        widgets = {
            "image_url": forms.URLInput(attrs={"placeholder": "https://contoh.com/foto-restoran.jpg"}),
        }
