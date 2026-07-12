const socket = io();

function updateDeviceBadge(connected, port) {
  const badge = document.getElementById("device-status-badge");
  if (badge) {
    if (connected) {
      badge.className = "badge bg-success";
      badge.innerHTML = '<i class="bi bi-usb-symbol"></i> Arduino online' + (port ? ' (' + port + ')' : '');
    } else {
      badge.className = "badge bg-danger";
      badge.innerHTML = '<i class="bi bi-usb-symbol"></i> Arduino offline';
    }
  }
  const sidebarDevice = document.getElementById("sidebar-device-status");
  if (sidebarDevice) {
    if (connected) {
      sidebarDevice.innerHTML = '<i class="bi bi-usb-symbol" style="color: #4ade80;"></i> <span>Arduino online' + (port ? ' (' + port + ')' : '') + '</span>';
    } else {
      sidebarDevice.innerHTML = '<i class="bi bi-usb-symbol" style="color: #f87171;"></i> <span>Arduino offline</span>';
    }
  }
}

socket.on("connect", () => {
  console.log("[eBALIK] Connected to server");
  // Resync state on reconnect (fires on initial connect AND reconnect)
  fetch("/api/hw-status")
    .then((r) => r.json())
    .then((hw) => updateDeviceBadge(hw.connected, hw.port))
    .catch(() => {});
  if (typeof refreshStats === "function") {
    refreshStats();
  }
});

socket.on("device_status", (data) => {
  updateDeviceBadge(data.connected, "");
});

socket.on("hw_status_update", (data) => {
  updateDeviceBadge(data.connected, data.port);
  window.dispatchEvent(new CustomEvent("ebalik:hw_status_update", { detail: data }));
});

socket.on("scan_result", (data) => {
  window.dispatchEvent(new CustomEvent("ebalik:scan_result", { detail: data }));
});

socket.on("hardware_status", (data) => {
  window.dispatchEvent(new CustomEvent("ebalik:hardware_status", { detail: data }));
});

socket.on("book_returned", (data) => {
  window.dispatchEvent(new CustomEvent("ebalik:book_returned", { detail: data }));
});

socket.on("return_failed", (data) => {
  window.dispatchEvent(new CustomEvent("ebalik:return_failed", { detail: data }));
});

socket.on("rfid_registration_scan", (data) => {
  window.dispatchEvent(new CustomEvent("ebalik:rfid_registration_scan", { detail: data }));
});

socket.on("rfid_registration_timeout", () => {
  window.dispatchEvent(new CustomEvent("ebalik:rfid_registration_timeout"));
});

fetch("/api/device/status")
  .then((r) => r.json())
  .then((data) => {
    if (data.connected) {
      updateDeviceBadge(true, "");
    } else {
      fetch("/api/hw-status")
        .then((r) => r.json())
        .then((hw) => updateDeviceBadge(hw.connected, hw.port))
        .catch(() => updateDeviceBadge(false, ""));
    }
  })
  .catch(() => {});
