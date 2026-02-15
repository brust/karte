window.karteApp = {
  map: null,
  markers: [],
  expectingClick: false,

  async init() {
    const { Map } = await google.maps.importLibrary("maps");
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
    // Clear old markers
    this.markers.forEach((m) => m.setMap(null));
    this.markers = [];

    pins.forEach((pin) => {
      const marker = new google.maps.Marker({
        position: { lat: pin.lat, lng: pin.lng },
        map: this.map,
        title: pin.name || pin.category,
        icon: pin.status === "draft"
          ? "http://maps.google.com/mapfiles/ms/icons/yellow-dot.png"
          : undefined,
      });
      this.markers.push(marker);
    });
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
};

// After every htmx swap on chat, scroll to bottom and check for click-request
document.addEventListener("htmx:afterSwap", (e) => {
  if (e.detail.target.id === "chat-messages") {
    window.karteApp.scrollChat();
    // Check if assistant requested a map click
    if (document.querySelector("[data-request-click]")) {
      window.karteApp.requestMapClick();
    }
  }
});
