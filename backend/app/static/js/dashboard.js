// Live-updates for the main dashboard page (relies on socket_client.js
// having already established the connection and dispatched custom events).

const liveIndicator = document.getElementById("live-indicator");
const liveLogList = document.getElementById("live-log-list");
const returnsTable = document.querySelector("#recent-returns-table tbody");

function setLiveIndicator(text, cls) {
  if (!liveIndicator) return;
  liveIndicator.className = `badge bg-${cls}`;
  liveIndicator.innerHTML = `<i class="bi bi-broadcast"></i> ${text}`;
}

function prependLog(typeBadgeClass, typeLabel, message, timestamp) {
  if (!liveLogList) return;
  const li = document.createElement("li");
  li.className = "list-group-item";
  li.innerHTML = `
    <span class="pill pill-${typeBadgeClass}">${typeLabel}</span>
    ${message}
    <div class="log-timestamp">${timestamp}</div>
  `;
  liveLogList.prepend(li);
  while (liveLogList.children.length > 15) {
    liveLogList.removeChild(liveLogList.lastChild);
  }
}

window.addEventListener("ebalik:scan_result", (e) => {
  const data = e.detail;
  if (data.valid) {
    setLiveIndicator(`Validating "${data.title}"...`, "info");
    prependLog("info", "INFO", `Book "${data.title}" validated for return`, new Date().toLocaleTimeString());
  } else {
    setLiveIndicator("Invalid tag scanned", "danger");
    prependLog("warning", "WARNING", `Invalid scan (${data.reason})`, new Date().toLocaleTimeString());
  }
});

window.addEventListener("ebalik:hardware_status", (e) => {
  const status = e.detail.status;
  const labelMap = {
    ENTRANCE_DETECTED: "Book entering slot...",
    FULL_ENTRY: "Book fully inserted, checking slot...",
    OBSTRUCTION: "Obstruction detected!",
    SLOT_CLOSED: "Slot closed",
  };
  const clsMap = {
    ENTRANCE_DETECTED: "info",
    FULL_ENTRY: "info",
    OBSTRUCTION: "danger",
    SLOT_CLOSED: "secondary",
  };
  setLiveIndicator(labelMap[status] || status, clsMap[status] || "secondary");
});

window.addEventListener("ebalik:book_returned", (e) => {
  const data = e.detail;
  setLiveIndicator(`"${data.title}" returned!`, "success");
  prependLog("success", "INFO", `Book "${data.title}" returned successfully`, new Date().toLocaleTimeString());

  if (returnsTable) {
    const emptyRow = returnsTable.querySelector("td[colspan]");
    if (emptyRow) emptyRow.closest("tr").remove();
    const row = document.createElement("tr");
    row.innerHTML = `
      <td class="text-primary" style="font-weight: var(--font-medium);">${data.title}</td>
      <td>${data.borrower || "--"}</td>
      <td>${new Date(data.returned_at).toLocaleString()}</td>
    `;
    returnsTable.prepend(row);
  }

  // Refresh the stat cards from the API so counts stay accurate.
  refreshStats();
});

window.addEventListener("ebalik:hw_status_update", (e) => {
  const data = e.detail;
  if (data.connected) {
    setLiveIndicator("Arduino connected", "success");
    prependLog("info", "INFO", "Arduino connected on " + data.port, new Date().toLocaleTimeString());
  } else {
    setLiveIndicator("Arduino disconnected", "danger");
    prependLog("warning", "WARNING", "Arduino disconnected", new Date().toLocaleTimeString());
  }
});

window.addEventListener("ebalik:return_failed", (e) => {
  const data = e.detail;
  setLiveIndicator(`Return failed: ${data.reason}`, "danger");
  prependLog("danger", "ERROR", `Return failed for "${data.title}" (${data.reason})`, new Date().toLocaleTimeString());
});

function refreshStats() {
  fetch("/api/stats")
    .then((r) => r.json())
    .then((data) => {
      const values = document.querySelectorAll(".stat-card .stat-value");
      if (values.length >= 4) {
        values[0].textContent = data.total_books;
        values[1].textContent = data.available;
        values[2].textContent = data.borrowed;
        values[3].textContent = data.returns_today;
      }
    })
    .catch(() => {});
}
