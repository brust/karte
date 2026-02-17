window.karteApp = {
  map: null,
  markers: [],
  directionsRenderer: null,
  expectingClick: false,

  async init() {
    const { Map } = await google.maps.importLibrary("maps");
    await google.maps.importLibrary("routes");
    this.map = new Map(document.getElementById("map"), {
      center: { lat: -23.55, lng: -46.63 },  // São Paulo default
      zoom: 13,
      mapId: "karte-map",
    });

    this.map.addListener("click", (e) => this.handleClick(e));
  },

  handleClick(e) {
    if (!this.expectingClick) return;
    this.expectingClick = false;

    const lat = e.latLng.lat();
    const lng = e.latLng.lng();

    this.showTyping();

    fetch("/map/click", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: `lat=${lat}&lng=${lng}`,
    })
      .then((r) => r.text())
      .then((html) => {
        document.getElementById("chat-messages").innerHTML = html;
        this.scrollChat();
        this.refreshPins();
      });
  },

  loadPins(pins) {
    // Clear old markers and route
    this.markers.forEach((m) => m.setMap(null));
    this.markers = [];
    if (this.directionsRenderer) {
      this.directionsRenderer.setMap(null);
      this.directionsRenderer = null;
    }

    pins.forEach((pin, i) => {
      const letter = String.fromCharCode(65 + (i % 26));
      const marker = new google.maps.Marker({
        position: { lat: pin.lat, lng: pin.lng },
        map: this.map,
        title: pin.name || pin.category,
        label: pin.status === "draft"
          ? { text: letter, color: "#333" }
          : { text: letter, color: "#fff" },
        icon: pin.status === "draft"
          ? "http://maps.google.com/mapfiles/ms/icons/yellow-dot.png"
          : undefined,
      });
      this.markers.push(marker);
    });

    // Draw walking route connecting all pins in order
    if (pins.length >= 2) {
      this.drawWalkingRoute(pins);
    }
  },

  drawWalkingRoute(pins) {
    const origin = { lat: pins[0].lat, lng: pins[0].lng };
    const destination = { lat: pins[pins.length - 1].lat, lng: pins[pins.length - 1].lng };
    const waypoints = pins.slice(1, -1).map((p) => ({
      location: { lat: p.lat, lng: p.lng },
      stopover: true,
    }));

    const service = new google.maps.DirectionsService();
    service.route(
      {
        origin,
        destination,
        waypoints,
        travelMode: google.maps.TravelMode.WALKING,
      },
      (result, status) => {
        if (status === "OK") {
          this.directionsRenderer = new google.maps.DirectionsRenderer({
            map: this.map,
            directions: result,
            suppressMarkers: true,
            preserveViewport: true,
            polylineOptions: {
              strokeColor: "#4285F4",
              strokeOpacity: 0.8,
              strokeWeight: 4,
            },
          });
        }
      }
    );
  },

  async refreshPins() {
    const resp = await fetch("/map/pins");
    const pins = await resp.json();
    this.loadPins(pins);
  },

  requestMapClick() {
    this.expectingClick = true;
  },

  scrollChat() {
    const el = document.getElementById("chat-messages");
    el.scrollTop = el.scrollHeight;
  },

  showTyping() {
    const el = document.getElementById("chat-messages");
    const bubble = document.createElement("div");
    bubble.className = "chat-msg chat-msg--assistant chat-typing";
    bubble.innerHTML =
      '<span class="chat-role">assistant</span>' +
      '<span class="chat-typing-dots">' +
        '<span class="chat-loading-dot"></span>' +
        '<span class="chat-loading-dot"></span>' +
        '<span class="chat-loading-dot"></span>' +
      '</span>';
    el.appendChild(bubble);
    this.scrollChat();
  },

  hideTyping() {
    const el = document.querySelector(".chat-typing");
    if (el) el.remove();
  },

  onChatSubmit(form) {
    const input = form.querySelector("input");
    const text = input.value.trim();
    input.value = "";
    form.querySelector("button").disabled = true;

    // Show the user message immediately
    if (text) {
      const el = document.getElementById("chat-messages");
      const bubble = document.createElement("div");
      bubble.className = "chat-msg chat-msg--user";
      bubble.innerHTML =
        '<span class="chat-role">user</span>' +
        '<span class="chat-text">' + text.replace(/</g, "&lt;").replace(/>/g, "&gt;") + '</span>';
      el.appendChild(bubble);
    }

    this.showTyping();
  },

  onChatDone(form) {
    form.querySelector("button").disabled = false;
    this.hideTyping();
  },

  moveMap(data) {
    if (!this.map) return;
    if (data.target === "fit_all") {
      if (this.markers.length === 0) return;
      const bounds = new google.maps.LatLngBounds();
      this.markers.forEach((m) => bounds.extend(m.getPosition()));
      this.map.fitBounds(bounds);
    } else if (data.target === "center" && data.lat != null && data.lng != null) {
      this.map.setCenter({ lat: data.lat, lng: data.lng });
      if (data.zoom) this.map.setZoom(data.zoom);
    }
  },
};

// After every htmx swap on chat, scroll to bottom and check for click-request
document.addEventListener("htmx:afterSwap", (e) => {
  if (e.detail.target.id === "chat-messages") {
    window.karteApp.scrollChat();
    // Check if assistant requested a map click
    if (document.querySelector("[data-request-click]")) {
      window.karteApp.requestMapClick();
    }
    // Check if assistant requested a map move
    const moveEl = document.querySelector("[data-move-map]");
    if (moveEl) {
      try {
        const moveData = JSON.parse(moveEl.getAttribute("data-move-map"));
        // Refresh pins first so markers are current, then move
        window.karteApp.refreshPins().then(() => {
          window.karteApp.moveMap(moveData);
        });
        return;
      } catch (_) {}
    }
    // Refresh map pins after any chat update (covers confirm actions)
    window.karteApp.refreshPins();
  }
});
