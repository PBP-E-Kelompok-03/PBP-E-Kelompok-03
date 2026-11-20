
document.addEventListener("DOMContentLoaded", function () {

    // Mengambil form, tombol kirim, dan tempat pesan
    const form = document.getElementById("review-form");
    if (!form) return;

    const message = document.getElementById("review-message");
    const button = form.querySelector('button[type="submit"]');

    // Menangani pengiriman ulasan menggunakan AJAX
    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        const formData = new FormData(form);
        button.disabled = true;
        message.textContent = "Mengirim ulasan...";

        try {
            // kirim data ke django
            const response = await fetch(form.action, {
                method: "POST",
                body: formData,
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            });
            const data = await response.json();
            if (response.ok && data.success) {
                message.textContent = data.message;
                message.style.color = "green";

                form.reset();
                button.textContent = "Ulasan Terkirim";

            } else {
                const errors = data.errors
                    ? Object.values(data.errors).flat().join(" ")
                    : data.error || "Gagal mengirim ulasan.";

                message.textContent = errors;
                message.style.color = "red";

                button.disabled = false;
            }

        } catch (error) {
            message.textContent = "Terjadi kesalahan saat mengirim ulasan.";
            message.style.color = "red";

            button.disabled = false;
        }
    });
});
