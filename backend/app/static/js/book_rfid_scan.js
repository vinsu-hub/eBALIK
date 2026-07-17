const addBookModal = document.getElementById("addBookModal");
const scanBtn = document.getElementById("btn-scan-tag");
const scanStatus = document.getElementById("scan-status");
const rfidInput = document.getElementById("rfid_uid_input");
const titleInput = document.getElementById("book_title_input");
let listenActive = false;
let listenTimer = null;
let duplicateBookId = null;
const LISTEN_SECONDS = 15;

function setScanState(state, extra) {
  if (!scanBtn || !scanStatus) return;
  scanBtn.disabled = true;
  switch (state) {
    case "idle":
      scanBtn.disabled = false;
      scanStatus.className = "scan-status";
      scanStatus.innerHTML = "";
      break;
    case "disabled":
      scanBtn.title = "Connect Arduino first";
      scanStatus.className = "scan-status";
      scanStatus.innerHTML = '<span class="text-muted small">Arduino not connected</span>';
      break;
    case "listening":
      scanBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Listening...';
      scanBtn.title = "";
      scanStatus.className = "scan-status text-info";
      scanStatus.innerHTML = 'Waiting for tag scan... <span id="scan-countdown">' + LISTEN_SECONDS + '</span>s';
      break;
    case "success":
      scanBtn.innerHTML = '<i class="bi bi-check-lg text-success"></i> Scan to Register';
      scanBtn.disabled = false;
      scanBtn.title = "";
      scanStatus.className = "scan-status text-success";
      scanStatus.innerHTML = '<i class="bi bi-check-circle-fill"></i> Tag <code>' + (extra || "") + '</code> will be assigned to <strong>"' + (titleInput ? titleInput.value : "") + '"</strong>';
      break;
    case "timeout":
      scanBtn.innerHTML = '<i class="bi bi-exclamation-triangle text-warning"></i> Scan to Register';
      scanBtn.disabled = false;
      scanBtn.title = "";
      scanStatus.className = "scan-status text-warning";
      scanStatus.innerHTML = '<i class="bi bi-exclamation-triangle-fill"></i> No tag detected — try again';
      break;
    case "duplicate":
      scanBtn.innerHTML = '<i class="bi bi-exclamation-triangle text-warning"></i> Scan to Register';
      scanBtn.disabled = true;
      scanBtn.title = "Scan a different tag or edit the UID field";
      scanStatus.className = "scan-status text-danger";
      scanStatus.innerHTML = '<i class="bi bi-x-circle-fill"></i> This tag is already registered to <strong>"' + (extra || "") + '"</strong> '
        + '<button class="btn btn-sm btn-outline-warning mt-1" id="btn-reassign-tag" type="button">Reassign to this book</button>';
      break;
    case "error":
      scanBtn.innerHTML = '<i class="bi bi-exclamation-triangle text-danger"></i> Scan to Register';
      scanBtn.disabled = false;
      scanBtn.title = "";
      scanStatus.className = "scan-status text-danger";
      scanStatus.innerHTML = '<i class="bi bi-x-circle-fill"></i> ' + (extra || "Error");
      break;
  }
}

function startScanListen() {
  if (listenActive) return;
  listenActive = true;
  setScanState("listening");
  let remaining = LISTEN_SECONDS;
  const countdown = document.getElementById("scan-countdown");
  listenTimer = setInterval(() => {
    remaining--;
    if (countdown) countdown.textContent = remaining;
    if (remaining <= 0) clearInterval(listenTimer);
  }, 1000);
  fetch("/api/rfid/start-listen", { method: "POST" })
    .then((r) => {
      if (!r.ok) throw new Error("Not connected");
      return r.json();
    })
    .then((data) => {
      if (!data.listening) throw new Error("Failed to start");
    })
    .catch((err) => {
      clearInterval(listenTimer);
      listenActive = false;
      setScanState("error", "Arduino is not connected.");
    });
}

function cancelScanListen() {
  if (listenTimer) {
    clearInterval(listenTimer);
    listenTimer = null;
  }
  if (listenActive) {
    listenActive = false;
    fetch("/api/rfid/cancel-listen", { method: "POST" }).catch(() => {});
  }
}

function checkDuplicate(uid) {
  const exclude = addBookModal ? addBookModal.dataset.editId : "";
  const url = "/api/books/check-uid?uid=" + encodeURIComponent(uid) + (exclude ? "&exclude_id=" + exclude : "");
  fetch(url)
    .then((r) => r.json())
    .then((data) => {
      if (data.exists) {
        duplicateBookId = data.book_id;
        setScanState("duplicate", data.title);
      }
    })
    .catch(() => {});
}

function reassignTag() {
  if (!duplicateBookId || !rfidInput) return;
  const uid = rfidInput.value.trim();
  const exclude = addBookModal ? addBookModal.dataset.editId : "";
  const newBookId = exclude ? parseInt(exclude, 10) : null;
  if (!newBookId) return;

  if (!confirm("Move this tag from its current book to this one? The old book will lose its RFID binding.")) {
    return;
  }

  fetch("/api/books/reassign-tag", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({uid: uid, new_book_id: newBookId}),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.reassigned) {
        duplicateBookId = null;
        setScanState("success", uid);
      } else {
        setScanState("error", data.error || "Reassignment failed");
      }
    })
    .catch(() => {
      setScanState("error", "Network error");
    });
}

if (scanBtn) {
  scanBtn.addEventListener("click", startScanListen);
}

if (scanStatus) {
  scanStatus.addEventListener("click", (e) => {
    if (e.target.id === "btn-reassign-tag") {
      reassignTag();
    }
  });
}

if (addBookModal) {
  const titleField = titleInput;
  if (titleField) {
    titleField.addEventListener("input", () => {
      const status = scanStatus;
      if (status && status.classList.contains("text-success")) {
        const codeEl = status.querySelector("code");
        if (codeEl) {
          status.innerHTML = '<i class="bi bi-check-circle-fill"></i> Tag <code>' + codeEl.textContent + '</code> will be assigned to <strong>"' + titleField.value + '"</strong>';
        }
      }
    });
  }
  if (rfidInput) {
    rfidInput.addEventListener("input", () => {
      const status = scanStatus;
      if (status && (status.classList.contains("text-danger") || status.classList.contains("text-warning"))) {
        setScanState("idle");
      }
    });
  }
  addBookModal.addEventListener("hidden.bs.modal", function () {
    cancelScanListen();
    setScanState("idle");
    if (rfidInput) rfidInput.value = "";
    if (titleField) titleField.value = "";
  });
  addBookModal.addEventListener("show.bs.modal", function () {
    const badge = document.getElementById("device-status-badge");
    const isOnline = badge && badge.classList.contains("bg-success");
    if (!isOnline) {
      setScanState("disabled");
    } else {
      setScanState("idle");
    }
  });
}

window.addEventListener("ebalik:rfid_registration_scan", (e) => {
  const uid = e.detail.uid;
  if (listenActive) {
    cancelScanListen();
    if (rfidInput) rfidInput.value = uid;
    setScanState("success", uid);
    checkDuplicate(uid);
  }
});

window.addEventListener("ebalik:rfid_registration_timeout", () => {
  if (listenActive) {
    listenActive = false;
    if (listenTimer) clearInterval(listenTimer);
    setScanState("timeout");
  }
});

if (addBookModal && new URLSearchParams(window.location.search).get("auto_scan") === "1") {
  const bsModal = bootstrap.Modal.getOrCreateInstance(addBookModal);
  bsModal.show();
  addBookModal.dataset.autoScan = "1";
  window.history.replaceState({}, "", window.location.pathname);
}

if (addBookModal) {
  addBookModal.addEventListener("shown.bs.modal", function () {
    if (addBookModal.dataset.autoScan === "1") {
      delete addBookModal.dataset.autoScan;
      const badge = document.getElementById("device-status-badge");
      if (badge && badge.classList.contains("bg-success")) {
        startScanListen();
      }
    }
  });
}
