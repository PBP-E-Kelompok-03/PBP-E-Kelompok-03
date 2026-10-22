
from django import forms
from .models import Review


# Form untuk mengisi dan mengedit rating serta komentar pengguna
class ReviewForm(forms.ModelForm):

    class Meta:
        # Menggunakan model Review sebagai sumber data form
        model = Review

        # Pengguna hanya boleh mengisi rating dan komentar
        fields = ["rating", "comment"]

        # Menentukan label yang ditampilkan pada form
        labels = {
            "rating": "Rating",
            "comment": "Ulasan",
        }

        # Mengatur tampilan input form
        widgets = {
            "rating": forms.RadioSelect(
                choices=[
                    (1, "1 Bintang"),
                    (2, "2 Bintang"),
                    (3, "3 Bintang"),
                    (4, "4 Bintang"),
                    (5, "5 Bintang"),
                ]
            ),
            "comment": forms.Textarea(
                attrs={
                    "placeholder": "Ceritakan pengalamanmu...",
                    "rows": 4,
                }
            ),
        }

    # Memastikan komentar tidak kosong atau hanya berisi spasi
    def clean_comment(self):
        comment = self.cleaned_data["comment"].strip()

        if not comment:
            raise forms.ValidationError(
                "Komentar tidak boleh kosong."
            )

        return comment
