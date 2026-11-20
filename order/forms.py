from django import forms

MAX_PER_ORDER = 3


class OrderCreateForm(forms.Form):
    jumlah = forms.IntegerField(
        min_value=1,
        max_value=MAX_PER_ORDER,
        error_messages={
            "invalid": "Jumlah tidak valid.",
            "required": "Jumlah tidak valid.",
            "min_value": "Jumlah harus minimal 1.",
            "max_value": f"Maksimal {MAX_PER_ORDER} box per pesanan.",
        },
    )


class PickupCodeForm(forms.Form):
    kode_pickup = forms.CharField(error_messages={"required": "Kode pickup wajib diisi."})

    def clean_kode_pickup(self):
        return self.cleaned_data["kode_pickup"].upper()
