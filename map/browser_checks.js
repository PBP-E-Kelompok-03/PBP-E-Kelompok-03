(async () => {
    const results = [];
    const assert = (condition, message) => {
        if (!condition) throw new Error(message);
        results.push(message);
    };
    const waitFor = async (fn) => {
        for (let i = 0; i < 150; i++) {
            if (fn()) return;
            await new Promise(resolve => setTimeout(resolve, 20));
        }
        throw new Error("Timed out waiting for browser state");
    };
    const coordinates = [[0, 0], [0, .005], [0, .005], [0, .02]];
    function directionsMatch(link, lat, lng) {
        if (!link) return false;
        const url = new URL(link.href);
        const destination = (url.searchParams.get("destination") || "").split(",").map(Number);
        return url.origin === "https://www.google.com" && url.pathname === "/maps/dir/"
            && url.searchParams.get("api") === "1"
            && url.searchParams.get("dir_action") === "navigate"
            && !url.searchParams.has("origin")
            && destination.length === 2 && destination[0] === lat && destination[1] === lng
            && link.target === "_blank" && link.relList.contains("noopener")
            && link.relList.contains("noreferrer") && link.textContent === "Arahkan ke Lokasi";
    }
    const cardDirectionsMatch = doc => {
        const links = [...doc.querySelectorAll("#restaurant-list .restaurant-directions-link")];
        return links.length === coordinates.length
            && links.every((link, index) => directionsMatch(link, ...coordinates[index]));
    };
    async function frame(mode, width = 390) {
        const iframe = document.createElement("iframe");
        iframe.width = width;
        iframe.height = 844;
        iframe.style.border = "0";
        const loaded = new Promise(resolve => iframe.onload = resolve);
        iframe.src = "/map/?case=" + mode;
        document.body.append(iframe);
        await loaded;
        return {iframe, win: iframe.contentWindow, doc: iframe.contentDocument};
    }
    try {
        const {iframe, win, doc} = await frame("normal");
        const tileRequests = await (await win.fetch("/__tile_requests/")).json();
        assert(tileRequests.some(request => request.path.startsWith("/__tile/")), "Cross-origin tile requests observed");
        assert(tileRequests.every(request => request.referer === win.location.origin + "/"),
            "Cross-origin tile Referer contains only the application origin; observed " + JSON.stringify([...new Set(tileRequests.map(request => request.referer))]));
        assert(tileRequests.every(request => request.user_agent && !request.cache_control && !request.pragma),
            "Tile requests use browser User-Agent and do not force no-cache");
        const pageResponse = await win.fetch("/map/");
        assert(pageResponse.headers.get("Referrer-Policy") === "strict-origin-when-cross-origin", "Django map response exposes the intended referrer policy");
        assert(win.tileConfiguration.url === "https://tile.openstreetmap.org/{z}/{x}/{y}.png", "Production tile URL remains official OSM HTTPS endpoint");
        assert(win.tileConfiguration.options.referrerPolicy === "strict-origin-when-cross-origin", "Leaflet sets explicit tile referrer policy");
        assert([...doc.querySelectorAll(".leaflet-tile")].every(tile => tile.referrerPolicy === "strict-origin-when-cross-origin"), "Tile image elements receive the referrer policy");
        assert([...doc.querySelectorAll(".leaflet-tile")].some(tile => tile.complete && tile.naturalWidth > 0), "Cross-origin tiles actually load in Chrome");
        assert(doc.querySelector(".leaflet-control-attribution").textContent.includes("OpenStreetMap contributors"), "OSM contributor attribution remains visible");
        await new Promise((resolve, reject) => {
            const probe = new win.Image();
            probe.onload = resolve;
            probe.onerror = reject;
            probe.src = win.tileTestOrigin + "/__policy_probe.png";
        });
        const probes = await (await win.fetch("/__tile_requests/")).json();
        assert(probes.some(request => request.path === "/__policy_probe.png" && request.referer === win.location.origin + "/"),
            "Document header independently sends an origin Referer without element override");

        const markers = () => doc.querySelectorAll(".restaurant-marker");
        const listItems = () => doc.querySelectorAll("#restaurant-list > li");
        assert(win.geoRequests.length === 1, "Geolocation requested automatically exactly once");
        assert(markers().length === 4 && listItems().length === 4, "All database restaurants rendered");
        assert(cardDirectionsMatch(doc), "Each card navigates to its database coordinates before geolocation succeeds");
        assert(doc.querySelectorAll(".restaurant-marker--available").length === 2, "Available stock uses green markers");
        assert(doc.querySelectorAll(".restaurant-marker--sold_out").length === 1, "Zero stock uses sold-out marker");
        assert(doc.querySelectorAll(".restaurant-marker--unavailable").length === 1, "Expired pickup uses unavailable marker");
        assert(!doc.querySelector(".leaflet-overlay-pane path"), "No fake user marker before geolocation succeeds");
        doc.querySelector("#locate-user").click();
        assert(win.geoRequests.length === 1, "Duplicate geolocation request prevented while pending");
        win.geoRequests[0].success({coords: {latitude: 0, longitude: 0}});
        assert(!doc.querySelector("#radius-filter").disabled, "Location success enables radius filter");
        assert(!!doc.querySelector(".leaflet-overlay-pane path.leaflet-interactive"), "User marker displayed with real Leaflet");
        const radius = doc.querySelector("#radius-filter");
        radius.value = "1";
        radius.dispatchEvent(new win.Event("change"));
        assert(markers().length === 3 && listItems().length === 3, "1km radius filters markers and cards consistently");
        radius.value = "3";
        radius.dispatchEvent(new win.Event("change"));
        assert(markers().length === 4, "3km radius includes distant restaurant");
        radius.value = "all";
        radius.dispatchEvent(new win.Event("change"));
        markers()[3].click();
        await waitFor(() => doc.querySelector(".leaflet-popup-content")?.textContent.includes("D Distant"));
        assert(directionsMatch(doc.querySelector(".leaflet-popup-content .restaurant-directions-link"), 0, .02),
            "Clicking another restaurant marker navigates to that restaurant, not the user position");
        listItems()[0].querySelector("button").click();
        await waitFor(() => doc.querySelector(".leaflet-popup-content")?.textContent.includes("A Available"));
        let popup = doc.querySelector(".leaflet-popup-content");
        assert(popup.textContent.includes("A Available"), "Marker popup names the selected restaurant");
        assert(popup.textContent.includes("12.000"), "Popup displays minimum available discounted price");
        assert(!!popup.querySelector("img"), "Popup contains restaurant thumbnail");
        assert(directionsMatch(popup.querySelector(".restaurant-directions-link"), 0, 0),
            "Selected restaurant popup has a safe external directions link");
        assert(popup.querySelector(".restaurant-detail-link").getAttribute("href") === "/food/restaurant/1/", "CTA points to matching restaurant");
        const detailResponse = await win.fetch("/food/restaurant/1/");
        const detailHtml = await detailResponse.text();
        assert(detailResponse.status === 200 && detailHtml.includes("A Available"), "CTA destination serves the matching restaurant");
        const detailDoc = new win.DOMParser().parseFromString(detailHtml, "text/html");
        [...detailDoc.querySelectorAll("script:not([src])")].forEach(script => new Function(script.textContent));
        assert(true, "Rendered restaurant detail scripts parse under Indonesian locale");
        const photo = popup.querySelector("img");
        photo.dispatchEvent(new win.Event("error"));
        assert(photo.getAttribute("src").endsWith("/map/restaurant-placeholder.svg"), "Broken photo falls back to local image");
        assert(popup.querySelector("figcaption").textContent === "Foto belum tersedia", "Missing photo clearly labeled");
        assert(doc.documentElement.scrollWidth <= 390, "Mobile layout has no horizontal page overflow");
        await win.fetch("/__sold_out/");
        doc.querySelector("#refresh-restaurants").click();
        await waitFor(() => doc.querySelectorAll(".restaurant-marker--sold_out").length === 2);
        assert(doc.querySelectorAll(".restaurant-marker--sold_out").length === 2, "Refresh changes marker after actual database stock update");
        await waitFor(() => doc.querySelector(".leaflet-popup-content")?.textContent.includes("Stok habis"));
        popup = doc.querySelector(".leaflet-popup-content");
        assert(popup && popup.textContent.includes("A Available") && popup.textContent.includes("Stok habis"), "Open popup stays open and receives new stock");
        assert(!popup.querySelector(".restaurant-price"), "Sold-out popup removes obsolete minimum price");
        assert(directionsMatch(popup.querySelector(".restaurant-directions-link"), 0, 0),
            "Stock refresh preserves directions to the selected restaurant");
        win.failRefresh = true;
        doc.querySelector("#refresh-restaurants").click();
        await waitFor(() => doc.querySelector("#data-status").textContent.includes("belum dapat"));
        assert(markers().length === 4 && !doc.querySelector("#refresh-restaurants").disabled, "Failed refresh retains data and allows retry");
        win.failRefresh = false;
        for (const [code, text] of [[1, "ditolak"], [2, "tidak tersedia"], [3, "habis"]]) {
            doc.querySelector("#locate-user").click();
            win.geoRequests.at(-1).error({code});
            assert(doc.querySelector("#location-status").textContent.includes(text), "Geolocation error " + code + " explained");
            assert(radius.disabled && radius.value === "all" && markers().length === 4, "Geolocation error " + code + " restores full map");
            assert(!doc.querySelector(".leaflet-overlay-pane path.leaflet-interactive"), "Geolocation error " + code + " removes user marker");
            assert(!doc.querySelector("#locate-user").disabled, "Geolocation error " + code + " permits retry");
            assert(cardDirectionsMatch(doc), "Geolocation error " + code + " preserves directions without requiring an origin");
        }
        doc.querySelector("#locate-user").click();
        win.geoRequests.at(-1).success({coords: {latitude: 91, longitude: 0}});
        assert(radius.disabled && doc.querySelector("#location-status").textContent.includes("tidak tersedia"), "Invalid coordinates rejected");
        doc.querySelector("#locate-user").click();
        win.geoRequests.at(-1).success({coords: {latitude: 45, longitude: 45}});
        radius.value = "1";
        radius.dispatchEvent(new win.Event("change"));
        assert(markers().length === 0 && doc.querySelector("#restaurant-list").textContent.includes("Tidak ada restoran"), "Empty radius has a useful message");
        assert(win.jsErrors.length === 0, "No unexpected JavaScript runtime errors");

        iframe.width = 1280;
        await new Promise(resolve => setTimeout(resolve, 100));
        assert(doc.documentElement.scrollWidth <= 1280, "Desktop layout has no horizontal page overflow");
        for (const mode of ["no_geo", "insecure", "no_leaflet", "geo_throw"]) {
            const item = await frame(mode);
            if (mode === "no_leaflet") {
                assert(item.doc.querySelector("#map-status").textContent.includes("Peta gagal"), "Leaflet failure is explained");
                assert(item.doc.querySelectorAll("#restaurant-list > li").length === 4, "Leaflet failure preserves server-rendered cards");
            } else if (mode === "geo_throw") {
                assert(item.doc.querySelector("#location-status").textContent.includes("tidak tersedia"), "Synchronous geolocation exception handled");
            } else {
                assert(item.doc.querySelector("#locate-user").disabled, mode + " disables geolocation");
                assert(item.doc.querySelectorAll(".restaurant-marker").length === 4, mode + " retains map markers");
            }
            assert(cardDirectionsMatch(item.doc), mode + " preserves external directions for every restaurant");
            assert(item.win.jsErrors.length === 0, mode + " has no unexpected JavaScript errors");
            item.iframe.remove();
        }
        document.querySelector("#result").dataset.state = "passed";
        document.querySelector("#result").textContent = JSON.stringify({passed: results.length, checks: results});
    } catch (error) {
        document.querySelector("#result").dataset.state = "failed";
        document.querySelector("#result").textContent = JSON.stringify({passed: results.length, error: String(error), checks: results});
    }
})();
