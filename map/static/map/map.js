(() => {
    "use strict";

    const restaurants = JSON.parse(document.getElementById("restaurant-data").textContent);
    const radiusSelect = document.getElementById("radius-filter");
    const locateButton = document.getElementById("locate-user");
    const locationStatus = document.getElementById("location-status");
    const mapStatus = document.getElementById("map-status");
    const list = document.getElementById("restaurant-list");
    const count = document.getElementById("restaurant-count");

    // The server-rendered list remains usable if Leaflet cannot be loaded.
    if (!window.L) {
        mapStatus.textContent = "Peta gagal dimuat. Anda tetap dapat membuka detail restoran dari daftar.";
        return;
    }

    const map = L.map("restaurant-map").setView([-6.369, 106.832], 13);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).on("tileerror", () => {
        mapStatus.textContent = "Latar peta belum dapat dimuat. Marker dan daftar restoran tetap dapat digunakan.";
    }).addTo(map);
    const markers = L.layerGroup().addTo(map);
    let userLocation = null;
    let userMarker = null;
    let radiusCircle = null;

    function textElement(tag, text) {
        const element = document.createElement(tag);
        element.textContent = text;
        return element;
    }

    function restaurantInfo(restaurant, distance) {
        const content = document.createElement("div");
        content.append(textElement("strong", restaurant.nama));
        content.append(textElement("p", restaurant.alamat));
        content.append(textElement("p",
            "Jam buka: " + (restaurant.jam_buka || "Belum tersedia") +
            " – " + (restaurant.jam_tutup || "Belum tersedia")));
        if (distance !== null) {
            content.append(textElement("p", (distance / 1000).toFixed(2) + " km dari lokasi Anda"));
        }
        const link = textElement("a", "Lihat detail restoran");
        link.href = restaurant.detail_url;
        content.append(link);
        return content;
    }

    function renderRestaurants(fitView = false) {
        markers.clearLayers();
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
            // Leaflet distanceTo returns great-circle distance in metres.
            const distance = userLocation ? userLocation.distanceTo(position) : null;
            if (radius !== null && distance > radius) continue;
            const marker = L.marker(position, {title: restaurant.nama})
                .bindPopup(restaurantInfo(restaurant, distance))
                .addTo(markers);
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
                document.getElementById("restaurant-map").focus();
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
                radius, color: "#006c41", fillOpacity: 0.06, interactive: false,
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
        userLocation = null;
        if (userMarker) {
            map.removeLayer(userMarker);
            userMarker = null;
        }
        radiusSelect.value = "all";
        radiusSelect.disabled = true;
        locateButton.disabled = false;
        const reasons = {
            1: "Izin lokasi ditolak.",
            2: "Lokasi Anda tidak tersedia.",
            3: "Waktu pencarian lokasi habis.",
        };
        locationStatus.textContent = (reasons[error.code] || "Lokasi tidak dapat diakses.") +
            " Semua restoran tetap ditampilkan; Anda dapat menggeser peta dan membuka detail. Coba lagi melalui Gunakan lokasi saya.";
        renderRestaurants(true);
    }

    locateButton.addEventListener("click", () => {
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
    });
    radiusSelect.addEventListener("change", () => renderRestaurants(true));
    renderRestaurants(true);
    if (navigator.geolocation && window.isSecureContext) {
        locateButton.disabled = false;
    } else {
        locationStatus.textContent = "Lokasi tidak tersedia di browser atau koneksi ini. Semua restoran tetap dapat dijelajahi melalui peta dan daftar.";
    }
})();
