(() => {
    "use strict";

    let restaurants = JSON.parse(document.getElementById("restaurant-data").textContent);
    const radiusSelect = document.getElementById("radius-filter");
    const locateButton = document.getElementById("locate-user");
    const refreshButton = document.getElementById("refresh-restaurants");
    const locationStatus = document.getElementById("location-status");
    const mapStatus = document.getElementById("map-status");
    const dataStatus = document.getElementById("data-status");
    const list = document.getElementById("restaurant-list");
    const count = document.getElementById("restaurant-count");
    const mapElement = document.getElementById("restaurant-map");
    const placeholderUrl = mapElement.dataset.placeholderUrl;

    function handleImageError(img, figure) {
        img.addEventListener("error", () => {
            img.src = placeholderUrl;
            img.alt = "Foto restoran belum tersedia";
            if (!figure.querySelector("figcaption")) {
                figure.append(textElement("figcaption", "Foto belum tersedia"));
            }
        }, {once: true});
    }
    // Also handle missing images when Leaflet is unavailable.
    list.querySelectorAll(".restaurant-photo img").forEach(img => handleImageError(img, img.parentElement));
    if (!window.L) {
        mapStatus.textContent = "Peta gagal dimuat. Anda tetap dapat membuka detail restoran dari daftar.";
        return;
    }

    const map = L.map("restaurant-map").setView([-6.369, 106.832], 13);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        // Keep browser-generated origin identification on cross-origin OSM tiles.
        referrerPolicy: "strict-origin-when-cross-origin",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).on("tileerror", () => {
        mapStatus.textContent = "Latar peta belum dapat dimuat. Marker dan daftar restoran tetap dapat digunakan.";
    }).addTo(map);
    const markers = L.layerGroup().addTo(map);
    const icons = Object.fromEntries([
        ["available", "✓"], ["unavailable", "◷"], ["sold_out", "−"],
    ].map(([status, symbol]) => [status, L.divIcon({
        className: "restaurant-marker restaurant-marker--" + status,
        html: '<span aria-hidden="true">' + symbol + "</span>",
        iconSize: [32, 32], iconAnchor: [16, 16], popupAnchor: [0, -18],
    })]));
    const rupiah = new Intl.NumberFormat("id-ID", {
        style: "currency", currency: "IDR", maximumFractionDigits: 0,
    });
    let markerEntries = [];
    let userLocation = null;
    let userMarker = null;
    let radiusCircle = null;
    let locating = false;
    let refreshing = false;

    function textElement(tag, text) {
        const element = document.createElement(tag);
        element.textContent = text;
        return element;
    }

    function restaurantInfo(restaurant, distance) {
        const content = document.createElement("div");
        content.className = "restaurant-info";
        const figure = document.createElement("figure");
        figure.className = "restaurant-photo";
        const img = document.createElement("img");
        img.alt = restaurant.has_image ? "Foto " + restaurant.nama : "Foto restoran belum tersedia";
        img.loading = "lazy";
        img.referrerPolicy = "no-referrer";
        img.width = 320;
        img.height = 180;
        handleImageError(img, figure);
        img.src = restaurant.image_url || placeholderUrl;
        figure.append(img);
        if (!restaurant.has_image) figure.append(textElement("figcaption", "Foto belum tersedia"));
        content.append(figure, textElement("h3", restaurant.nama));
        const status = textElement("p", restaurant.stock_label);
        status.className = "restaurant-stock restaurant-stock--" + restaurant.stock_status;
        content.append(status);
        if (restaurant.is_available && restaurant.min_discount_price !== null) {
            const price = textElement("p", "Mulai " + rupiah.format(Number(restaurant.min_discount_price)));
            price.className = "restaurant-price";
            content.append(price);
        }
        content.append(textElement("p", restaurant.alamat));
        content.append(textElement("p",
            "Jam buka: " + (restaurant.jam_buka || "Belum tersedia") +
            " – " + (restaurant.jam_tutup || "Belum tersedia")));
        if (distance !== null) {
            content.append(textElement("p", (distance / 1000).toFixed(2) + " km dari lokasi Anda"));
        }
        const link = textElement("a", "Lihat detail restoran");
        link.href = restaurant.detail_url;
        link.className = "btn btn--primary restaurant-detail-link";
        content.append(link);
        const directions = textElement("a", "Arahkan ke Lokasi");
        directions.href = restaurant.directions_url;
        directions.className = "btn btn--outline restaurant-directions-link";
        directions.target = "_blank";
        directions.rel = "noopener noreferrer";
        directions.title = "Buka petunjuk arah di Google Maps (tab baru)";
        directions.setAttribute("aria-label",
            "Arahkan ke Lokasi " + restaurant.nama + " di Google Maps (tab baru)");
        content.append(directions);
        if (restaurant.photo_edit_url) {
            const editLink = textElement("a", "Ubah foto restoran");
            editLink.href = restaurant.photo_edit_url;
            editLink.className = "restaurant-photo-link";
            content.append(editLink);
        }
        return content;
    }

    function renderRestaurants(fitView = false) {
        const openId = markerEntries.find(entry => entry.marker.isPopupOpen())?.id;
        markers.clearLayers();
        markerEntries = [];
        list.replaceChildren();
        if (radiusCircle) {
            map.removeLayer(radiusCircle);
            radiusCircle = null;
        }
        const radius = userLocation && radiusSelect.value !== "all"
            ? Number(radiusSelect.value) * 1000 : null;
        const visiblePositions = [];
        let visibleCount = 0;
        for (const restaurant of restaurants) {
            const position = L.latLng(restaurant.lat, restaurant.lng);
            const distance = userLocation ? userLocation.distanceTo(position) : null;
            if (radius !== null && distance > radius) continue;
            const marker = L.marker(position, {
                title: restaurant.nama + " — " + restaurant.stock_label,
                alt: restaurant.nama + " — " + restaurant.stock_label,
                icon: icons[restaurant.stock_status] || icons.sold_out,
            }).bindPopup(restaurantInfo(restaurant, distance), {maxWidth: 280, minWidth: 220}).addTo(markers);
            markerEntries.push({id: restaurant.id, marker});
            if (restaurant.id === openId) marker.openPopup();
            visiblePositions.push(position);
            visibleCount += 1;

            const item = document.createElement("li");
            item.append(restaurantInfo(restaurant, distance));
            const showOnMap = textElement("button", "Lihat di peta");
            showOnMap.type = "button";
            showOnMap.className = "btn btn--secondary";
            showOnMap.addEventListener("click", () => {
                map.setView(position, 16);
                marker.openPopup();
                mapElement.focus();
            });
            item.append(showOnMap);
            list.append(item);
        }
        count.textContent = visibleCount + " restoran ditampilkan" +
            (radius !== null ? " dalam radius " + radiusSelect.value + " km." : ".");
        if (!visibleCount) {
            list.append(textElement("li", radius !== null
                ? "Tidak ada restoran dalam radius ini. Pilih radius lebih besar atau Semua restoran."
                : "Belum ada restoran dengan koordinat yang valid."));
        }
        if (radius !== null) {
            radiusCircle = L.circle(userLocation, {
                radius, color: "#38761d", fillOpacity: 0.06, interactive: false,
            }).addTo(map);
        }
        if (fitView) {
            if (radiusCircle) {
                map.fitBounds(radiusCircle.getBounds(), {padding: [24, 24]});
            } else {
                if (userLocation) visiblePositions.push(userLocation);
                if (visiblePositions.length) {
                    map.fitBounds(L.latLngBounds(visiblePositions), {padding: [24, 24], maxZoom: 15});
                }
            }
        }
    }

    function locationFailed(error) {
        locating = false;
        userLocation = null;
        if (userMarker) {
            map.removeLayer(userMarker);
            userMarker = null;
        }
        radiusSelect.value = "all";
        radiusSelect.disabled = true;
        locateButton.disabled = false;
        const reasons = {
            1: "Izin lokasi ditolak. Anda dapat mengizinkan lokasi melalui pengaturan situs di browser.",
            2: "Lokasi Anda tidak tersedia.",
            3: "Waktu pencarian lokasi habis.",
        };
        locationStatus.textContent = (reasons[error.code] || "Lokasi tidak dapat diakses.") +
            " Semua restoran tetap ditampilkan. Coba lagi melalui Gunakan lokasi saya.";
        renderRestaurants(true);
    }

    function requestLocation() {
        if (locating) return;
        locating = true;
        locateButton.disabled = true;
        locationStatus.textContent = "Sedang mencari lokasi Anda. Peta tetap dapat digunakan.";
        try {
            navigator.geolocation.getCurrentPosition((position) => {
                const {latitude, longitude} = position.coords;
                if (!Number.isFinite(latitude) || !Number.isFinite(longitude) ||
                    Math.abs(latitude) > 90 || Math.abs(longitude) > 180) {
                    locationFailed({code: 2});
                    return;
                }
                locating = false;
                userLocation = L.latLng(latitude, longitude);
                if (userMarker) map.removeLayer(userMarker);
                userMarker = L.circleMarker(userLocation, {
                    radius: 8, color: "#ffffff", weight: 3, fillColor: "#2563eb", fillOpacity: 1,
                }).bindPopup(textElement("span", "Lokasi Anda")).addTo(map);
                radiusSelect.disabled = false;
                locateButton.disabled = false;
                locationStatus.textContent = "Lokasi ditemukan. Pilih radius 1, 3, atau 5 km untuk menyaring restoran.";
                renderRestaurants(true);
            }, locationFailed, {enableHighAccuracy: true, timeout: 10000, maximumAge: 60000});
        } catch {
            locationFailed({code: 2});
        }
    }

    async function refreshRestaurants() {
        if (refreshing || document.hidden) return;
        refreshing = true;
        refreshButton.disabled = true;
        const controller = new AbortController();
        const timeout = window.setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetch(mapElement.dataset.restaurantsUrl, {
                cache: "no-store", credentials: "same-origin", signal: controller.signal,
            });
            if (!response.ok) throw new Error("Restaurant data unavailable");
            const data = await response.json();
            if (!Array.isArray(data.restaurants)) throw new Error("Invalid restaurant data");
            restaurants = data.restaurants;
            renderRestaurants();
            dataStatus.textContent = "Stok dan harga telah diperbarui.";
        } catch {
            dataStatus.textContent = "Stok belum dapat diperbarui. Data sebelumnya tetap ditampilkan; coba Perbarui stok.";
        } finally {
            window.clearTimeout(timeout);
            refreshing = false;
            refreshButton.disabled = false;
        }
    }

    locateButton.addEventListener("click", requestLocation);
    radiusSelect.addEventListener("change", () => renderRestaurants(true));
    refreshButton.addEventListener("click", refreshRestaurants);
    refreshButton.disabled = false;
    window.setInterval(refreshRestaurants, 30000);
    window.addEventListener("focus", refreshRestaurants);
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) refreshRestaurants();
    });
    renderRestaurants(true);
    if (navigator.geolocation && window.isSecureContext) {
        requestLocation();
    } else {
        locationStatus.textContent = "Lokasi tidak tersedia di browser atau koneksi ini. Semua restoran tetap dapat dijelajahi melalui peta dan daftar.";
    }
})();
