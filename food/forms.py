from django import forms
from .models import Restaurant, SurpriseBox


class RestaurantForm(forms.ModelForm):
    class Meta:
        model = Restaurant
        fields = ["nama", "alamat", "lat", "lng", "jam_buka", "jam_tutup"]
        widgets = {
            "nama": forms.TextInput(attrs={"placeholder": "Nama restoran"}),
            "alamat": forms.TextInput(attrs={"placeholder": "Alamat lengkap"}),
            "lat": forms.NumberInput(attrs={"placeholder": "Latitude, contoh: -6.337445", "step": "any"}),
            "lng": forms.NumberInput(attrs={"placeholder": "Longitude, contoh: 106.801589", "step": "any"}),
            "jam_buka": forms.TimeInput(attrs={"type": "time"}),
            "jam_tutup": forms.TimeInput(attrs={"type": "time"}),
        }


class SurpriseBoxForm(forms.ModelForm):
    class Meta:
        model = SurpriseBox
        fields = ["nama_paket", "harga_normal", "harga_diskon", "stok", "pickup_start", "pickup_end"]
        widgets = {
            "nama_paket": forms.TextInput(attrs={"placeholder": "Contoh: Paket Nasi Campur"}),
            "harga_normal": forms.NumberInput(attrs={"placeholder": "Harga normal (Rp)"}),
            "harga_diskon": forms.NumberInput(attrs={"placeholder": "Harga diskon (Rp)"}),
            "stok": forms.NumberInput(attrs={"placeholder": "Sisa stok", "min": "0"}),
            "pickup_start": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "pickup_end": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        normal = cleaned_data.get("harga_normal")
        diskon = cleaned_data.get("harga_diskon")
        if normal and diskon and diskon > normal:
            self.add_error("harga_diskon", "Harga diskon tidak boleh lebih besar dari harga normal.")
        return cleaned_data
