(function () {
  const csrf = document.currentScript.dataset.csrf;

  // kirim post ajax dengan csrf token, selalu balikin {ok, data} tanpa melempar error
  async function post(url, params) {
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "X-CSRFToken": csrf, "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams(params || {}).toString(),
      });
      const data = await response.json().catch(() => ({}));
      if (response.status === 429) data.error = "Terlalu banyak percobaan. Coba lagi nanti.";
      return { ok: response.ok, data };
    } catch (e) {
      return { ok: false, data: { error: "Koneksi bermasalah. Coba lagi." } };
    }
  }

  window.orderAjax = { post };
})();
