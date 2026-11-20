from django import forms
from .models import Restaurant, SurpriseBox


class RestaurantForm(forms.ModelForm):
    image_url = forms.CharField(
        required=False,
        label="Foto Restoran",
        help_text="Unggah file foto langsung dari komputermu, atau tempelkan URL gambar.",
        widget=forms.TextInput(
            attrs={
                "id": "id_image_url",
                "placeholder": "https://... (atau pilih file foto langsung di atas)",
            }
        ),
    )

    class Meta:
        model = Restaurant
        fields = ["nama", "alamat", "lat", "lng", "jam_buka", "jam_tutup", "image_url"]
        labels = {
            "nama": "Nama Restoran",
            "alamat": "Alamat Lengkap",
            "lat": "Latitude (Koordinat)",
            "lng": "Longitude (Koordinat)",
            "jam_buka": "Jam Buka",
            "jam_tutup": "Jam Tutup",
            "image_url": "Foto Restoran",
        }
        help_texts = {
            "lat": "Opsional. Contoh: -6.337445",
            "lng": "Opsional. Contoh: 106.801589",
        }
        widgets = {
            "nama": forms.TextInput(attrs={"placeholder": "Nama restoran"}),
            "alamat": forms.TextInput(attrs={"placeholder": "Alamat lengkap"}),
            "lat": forms.NumberInput(attrs={"placeholder": "Latitude, contoh: -6.337445", "step": "any"}),
            "lng": forms.NumberInput(attrs={"placeholder": "Longitude, contoh: 106.801589", "step": "any"}),
            "jam_buka": forms.TimeInput(attrs={"type": "time"}),
            "jam_tutup": forms.TimeInput(attrs={"type": "time"}),
        }

    def clean_image_url(self):
        url = self.cleaned_data.get("image_url")
        if not url:
            return ""
        url = url.strip()

        # Handle Base64 Data URI from direct file upload
        if url.startswith("data:image/"):
            if len(url) > 2_500_000:
                raise forms.ValidationError("Ukuran foto terlalu besar. Silakan pilih foto dengan resolusi lebih kecil (maksimal 2MB).")
            return url

        # Handle external URL
        if not (url.startswith("http://") or url.startswith("https://")):
            url = f"https://{url}"
        elif url.startswith("http://"):
            url = f"https://{url[7:]}"

        if "pinterest.com/pin/" in url or "pin.it/" in url:
            raise forms.ValidationError(
                "Tautan ini mengarah ke halaman web Pinterest (bukan link gambar langsung). "
                "Silakan buka gambarnya, klik kanan pada foto, lalu pilih 'Salin Alamat Gambar' "
                "(format tautan langsung berawalan https://i.pinimg.com/...)."
            )
        return url


class SurpriseBoxForm(forms.ModelForm):
    image_url = forms.CharField(
        required=False,
        label="Foto Produk Makanan",
        help_text="Unggah file foto langsung dari komputermu, atau tempelkan URL gambar.",
        widget=forms.TextInput(
            attrs={
                "id": "id_image_url",
                "placeholder": "https://... (atau pilih file foto langsung di atas)",
            }
        ),
    )

    class Meta:
        model = SurpriseBox
        fields = ["nama_paket", "harga_normal", "harga_diskon", "stok", "image_url"]
        labels = {
            "nama_paket": "Nama Paket Surprise Box",
            "harga_normal": "Harga Normal (Rp)",
            "harga_diskon": "Harga Diskon (Rp)",
            "stok": "Jumlah Stok Box",
            "image_url": "Foto Produk Makanan",
        }
        help_texts = {
            "stok": "Jumlah paket makanan yang tersedia untuk dijual hari ini.",
        }
        widgets = {
            "nama_paket": forms.TextInput(attrs={"placeholder": "Contoh: Paket Nasi Campur"}),
            "harga_normal": forms.NumberInput(attrs={"placeholder": "Harga normal (Rp)"}),
            "harga_diskon": forms.NumberInput(attrs={"placeholder": "Harga diskon (Rp)"}),
            "stok": forms.NumberInput(attrs={"placeholder": "Sisa stok", "min": "0"}),
        }

    def clean_image_url(self):
        url = self.cleaned_data.get("image_url")
        if not url:
            return ""
        url = url.strip()

        # Handle Base64 Data URI from direct file upload
        if url.startswith("data:image/"):
            if len(url) > 2_500_000:
                raise forms.ValidationError("Ukuran foto terlalu besar. Silakan pilih foto dengan resolusi lebih kecil (maksimal 2MB).")
            return url

        # Handle external URL
        if not (url.startswith("http://") or url.startswith("https://")):
            url = f"https://{url}"
        elif url.startswith("http://"):
            url = f"https://{url[7:]}"

        if "pinterest.com/pin/" in url or "pin.it/" in url:
            raise forms.ValidationError(
                "Tautan ini mengarah ke halaman web Pinterest (bukan link gambar langsung). "
                "Silakan buka gambarnya, klik kanan pada foto, lalu pilih 'Salin Alamat Gambar' "
                "(format tautan langsung berawalan https://i.pinimg.com/...)."
            )
        return url

    def clean(self):
        cleaned_data = super().clean()
        normal = cleaned_data.get("harga_normal")
        diskon = cleaned_data.get("harga_diskon")
        if normal and diskon and diskon > normal:
            self.add_error("harga_diskon", "Harga diskon tidak boleh lebih besar dari harga normal.")
        return cleaned_data
