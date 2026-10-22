
document.addEventListener("DOMContentLoaded", function () {

    // Mengambil form, tombol kirim, dan tempat pesan
    const form = document.getElementById("review-form");
    if (!form) return;

    const message = document.getElementById("review-message");
    const button = form.querySelector('button[type="submit"]');

    // Menangani pengiriman ulasan menggunakan AJAX
    form.addEventListener("submit", async function (event) {

        // Mencegah halaman reload ketika form dikirim
        event.preventDefault();

        // Mengambil rating, komentar, dan CSRF token dari form
        const formData = new FormData(form);

        // Menonaktifkan tombol selama proses pengiriman
        button.disabled = true;
        message.textContent = "Mengirim ulasan...";

        try {
            // Mengirim data review ke Django menggunakan Fetch API
            const response = await fetch(form.action, {
                method: "POST",
                body: formData,
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            });

            // Membaca respons JSON dari Django
            const data = await response.json();

            // Jika review berhasil disimpan
            if (response.ok && data.success) {
                message.textContent = data.message;
                message.style.color = "green";

                // Mengosongkan form setelah berhasil
                form.reset();
                button.textContent = "Ulasan Terkirim";

            } else {
                // Menampilkan pesan jika review gagal dikirim
                const errors = data.errors
                    ? Object.values(data.errors).flat().join(" ")
                    : data.error || "Gagal mengirim ulasan.";

                message.textContent = errors;
                message.style.color = "red";

                button.disabled = false;
            }

        } catch (error) {
            // Menangani kesalahan jaringan atau respons server
            message.textContent = "Terjadi kesalahan saat mengirim ulasan.";
            message.style.color = "red";

            button.disabled = false;
        }
    });
});
