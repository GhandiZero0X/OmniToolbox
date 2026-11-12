(() => {
  "use strict";

  /* =========================================================
   * Tema terang / gelap
   * ======================================================= */
  const themeToggle = document.getElementById("theme-toggle");
  const root = document.documentElement;

  function updateThemeIcon() {
    if (!themeToggle) return;
    const dark = root.getAttribute("data-bs-theme") === "dark";
    themeToggle.innerHTML = dark
      ? '<i class="bi bi-sun"></i>'
      : '<i class="bi bi-moon-stars"></i>';
  }

  if (themeToggle) {
    updateThemeIcon();
    themeToggle.addEventListener("click", () => {
      const next = root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-bs-theme", next);
      try { localStorage.setItem("omni-theme", next); } catch (e) { /* abaikan */ }
      updateThemeIcon();
    });
  }

  /* =========================================================
   * Utilitas
   * ======================================================= */
  function formatSize(bytes) {
    const units = ["B", "KB", "MB", "GB"];
    let size = bytes;
    let i = 0;
    while (size >= 1024 && i < units.length - 1) {
      size /= 1024;
      i += 1;
    }
    return (i === 0 ? size.toFixed(0) : size.toFixed(2)) + " " + units[i];
  }

  function extOf(name) {
    const dot = name.lastIndexOf(".");
    return dot >= 0 ? name.slice(dot).toLowerCase() : "";
  }

  // Urutan alami: "2.jpg" sebelum "10.jpg"
  function naturalCompare(a, b) {
    return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" });
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text; // textContent: aman dari XSS
    return node;
  }

  /* =========================================================
   * Slider (menampilkan nilai di <output>)
   * ======================================================= */
  document.querySelectorAll("input[type=range][data-output]").forEach((range) => {
    const output = document.getElementById(range.dataset.output);
    if (!output) return;
    const sync = () => { output.textContent = range.value; };
    range.addEventListener("input", sync);
    sync();
  });

  /* =========================================================
   * Form upload + hasil (dipakai semua halaman tool)
   * ======================================================= */
  const form = document.getElementById("tool-form");
  if (!form) return;

  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const fileList = document.getElementById("file-list");
  const submitBtn = document.getElementById("submit-btn");
  const resetBtn = document.getElementById("reset-btn");
  const sortBtn = document.getElementById("sort-btn");
  const alertBox = document.getElementById("alert-box");
  const progressWrap = document.getElementById("progress-wrap");
  const progressBar = document.getElementById("progress-bar");
  const statusText = document.getElementById("status-text");
  const percentText = document.getElementById("percent-text");
  const resultsCard = document.getElementById("results");
  const resultsBody = document.getElementById("results-body");
  const resultsSummary = document.getElementById("results-summary");
  const zipBtn = document.getElementById("zip-btn");
  const folderBtn = document.getElementById("folder-btn");     /* ← BARU */
  const folderInput = document.getElementById("folder-input"); /* ← BARU */

  /* ------- 7a. Deteksi "accept all" + helper path ------- */
  const acceptRaw = (form.dataset.accept || "").trim();              /* ← BARU */
  const allowedExt = acceptRaw === "*"                                /* ← BARU */
    ? []
    : acceptRaw.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  const acceptAll = acceptRaw === "*" || allowedExt.length === 0;    /* ← BARU */

  // Path relatif untuk upload folder (webkitdirectory); fallback ke nama
  function filePath(file) {                                          /* ← BARU */
    return file.webkitRelativePath || file.name;
  }

  const maxFiles = parseInt(form.dataset.maxFiles, 10) || 20;
  const maxBytes = (parseInt(form.dataset.maxMb, 10) || 200) * 1024 * 1024;
  const reorderEnabled = form.dataset.reorder === "true"; // urutan file = urutan halaman
  const submitHtml = submitBtn.innerHTML;                  // label asli tombol (dipulihkan setelah proses)

  let files = [];
  let busy = false;

  function showAlert(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function hideAlert() {
    alertBox.classList.add("d-none");
    alertBox.textContent = "";
  }

  function totalBytes() {
    return files.reduce((sum, f) => sum + f.size, 0);
  }

  function moveFile(index, delta) {
    const target = index + delta;
    if (busy || target < 0 || target >= files.length) return;
    const [moved] = files.splice(index, 1);
    files.splice(target, 0, moved);
    renderFileList();
  }

  function renderFileList() {
    fileList.replaceChildren();

    files.forEach((file, index) => {
      const li = el("li", "list-group-item");
      const path = filePath(file);                          /* ← BARU */

      if (reorderEnabled) {
        li.append(el("span", "badge text-bg-primary page-number", String(index + 1)));
      }
      li.append(
        el("i", "bi bi-file-earmark text-body-secondary"),
        el("span", "file-name", path),                       // ← ganti file.name -> path
        el("span", "badge text-bg-secondary", formatSize(file.size))
      );

      if (reorderEnabled) {
        const upBtn = el("button", "btn btn-sm btn-outline-secondary");
        upBtn.type = "button";
        upBtn.setAttribute("aria-label", "Naikkan " + path);   // ← ganti
        upBtn.innerHTML = '<i class="bi bi-arrow-up"></i>';
        upBtn.disabled = index === 0;
        upBtn.addEventListener("click", () => moveFile(index, -1));

        const downBtn = el("button", "btn btn-sm btn-outline-secondary");
        downBtn.type = "button";
        downBtn.setAttribute("aria-label", "Turunkan " + path); // ← ganti
        downBtn.innerHTML = '<i class="bi bi-arrow-down"></i>';
        downBtn.disabled = index === files.length - 1;
        downBtn.addEventListener("click", () => moveFile(index, 1));

        li.append(upBtn, downBtn);
      }

      const removeBtn = el("button", "btn btn-sm btn-outline-danger");
      removeBtn.type = "button";
      removeBtn.setAttribute("aria-label", "Hapus " + path);   // ← ganti
      removeBtn.innerHTML = '<i class="bi bi-x-lg"></i>';
      removeBtn.addEventListener("click", () => {
        if (busy) return;
        files.splice(index, 1);
        renderFileList();
      });
      li.append(removeBtn);
      fileList.append(li);
    });

    submitBtn.disabled = busy || files.length === 0;
    if (sortBtn) sortBtn.classList.toggle("d-none", !(reorderEnabled && files.length > 1));

    // Beri tahu skrip khusus halaman (misal pratinjau di halaman hapus watermark)
    form.dispatchEvent(new CustomEvent("filesChanged", { detail: { files: files.slice() } }));
  }

  function addFiles(newFiles) {
    hideAlert();
    const problems = [];
    const accepted = [];

    Array.from(newFiles).forEach((file) => {
      const path = filePath(file);                              // ← BARU
      if (!acceptAll && !allowedExt.includes(extOf(path))) {    // ← BARU (pakai acceptAll)
        problems.push(path + ": format tidak didukung");
        return;
      }
      const duplicate = files.some(
        (f) => filePath(f) === path && f.size === file.size && f.lastModified === file.lastModified // ← BARU
      );
      if (!duplicate) accepted.push(file);
    });

    // Halaman PDF: file yang baru dipilih diurutkan berdasarkan nama (1, 2, 10), lalu ditambahkan di akhir
    if (reorderEnabled) accepted.sort(naturalCompare);

    accepted.forEach((file) => {
      if (files.length >= maxFiles) {
        problems.push("Maksimal " + maxFiles + " file sekali proses");
        return;
      }
      files.push(file);
    });

    if (totalBytes() > maxBytes) {
      problems.push("Total ukuran melebihi " + formatSize(maxBytes));
    }

    renderFileList();
    if (problems.length) showAlert(Array.from(new Set(problems)).join(" | "));
  }

  /* ---------- Dropzone ---------- */
  dropzone.addEventListener("click", () => { if (!busy) fileInput.click(); });
  dropzone.addEventListener("keydown", (event) => {
    if ((event.key === "Enter" || event.key === " ") && !busy) {
      event.preventDefault();
      fileInput.click();
    }
  });
  fileInput.addEventListener("change", () => {
    addFiles(fileInput.files);
    fileInput.value = ""; // supaya file yang sama bisa dipilih ulang
  });

  ["dragenter", "dragover"].forEach((type) => {
    dropzone.addEventListener(type, (event) => {
      event.preventDefault();
      dropzone.classList.add("is-dragover");
    });
  });
  ["dragleave", "drop"].forEach((type) => {
    dropzone.addEventListener(type, (event) => {
      event.preventDefault();
      dropzone.classList.remove("is-dragover");
    });
  });
  dropzone.addEventListener("drop", (event) => {
    if (!busy) addFiles(event.dataTransfer.files);
  });

  /* ---------- 7c. Upload folder (webkitdirectory) ---------- */
  if (folderBtn && folderInput) {                                    /* ← BARU */
    folderBtn.addEventListener("click", () => { if (!busy) folderInput.click(); });
    folderInput.addEventListener("change", () => {
      if (folderInput.files.length) addFiles(folderInput.files);
      folderInput.value = ""; // supaya folder yang sama bisa dipilih ulang
    });
  }

  /* ---------- Urutkan berdasarkan nama ---------- */
  if (sortBtn) {
    sortBtn.addEventListener("click", () => {
      if (busy) return;
      files.sort(naturalCompare);
      renderFileList();
    });
  }

  /* ---------- Reset ---------- */
  function resetAll() {
    if (busy) return;
    files = [];
    renderFileList();
    hideAlert();
    progressWrap.classList.add("d-none");
    resultsCard.classList.add("d-none");
    resultsBody.replaceChildren();
  }
  resetBtn.addEventListener("click", resetAll);

  /* ---------- Progres ---------- */
  function setBusy(state) {
    busy = state;
    submitBtn.disabled = state || files.length === 0;
    resetBtn.disabled = state;
    if (folderBtn) folderBtn.disabled = state;      // ← TAMBAH
    submitBtn.innerHTML = state
      ? '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Memproses...'
      : submitHtml;
  }

  function setProgress(percent, label, indeterminate, percentLabel) {
    progressWrap.classList.remove("d-none");
    progressBar.style.width = percent + "%";
    progressBar.classList.toggle("progress-bar-striped", !!indeterminate);
    progressBar.classList.toggle("progress-bar-animated", !!indeterminate);
    statusText.textContent = label;
    if (percentLabel !== undefined) {
      percentText.textContent = percentLabel;
    } else {
      percentText.textContent = indeterminate ? "" : Math.round(percent) + "%";
    }
  }

  /* ---------- Tampilkan hasil ---------- */
  function renderNameCell(item) {
    const cell = el("td");
    cell.title = item.name;

    const wrap = el("div", "d-flex align-items-center gap-2");
    if (item.preview_url) {
      const link = el("a");
      link.href = item.preview_url;
      link.target = "_blank";
      link.rel = "noopener";
      const thumb = el("img", "result-thumb");
      thumb.src = item.thumb_url || item.preview_url;
      thumb.alt = "Pratinjau " + item.name;
      thumb.loading = "lazy";
      link.append(thumb);
      wrap.append(link);
    }

    const text = el("div", "min-w-0");
    text.append(el("div", "text-truncate", item.name));
    if (item.info) text.append(el("div", "small text-body-secondary text-wrap", item.info));
    if (item.note) text.append(el("div", "small text-warning text-wrap", item.note));
    wrap.append(text);

    cell.append(wrap);
    return cell;
  }

  function renderResults(data) {
    resultsBody.replaceChildren();

    data.results.forEach((item) => {
      const tr = el("tr");
      tr.append(renderNameCell(item));

      if (item.status === "success") {
        tr.append(el("td", "text-end text-nowrap", item.original_size_h));
        tr.append(el("td", "text-end text-nowrap", item.new_size_h));

        const savedCell = el("td", "text-end");
        if (item.badge) {
          // Fitur konversi/edit: tampilkan label (format atau jumlah halaman), bukan persen hemat
          savedCell.append(el("span", "badge text-bg-primary", item.badge));
        } else if (item.kept_original) {
          const badge = el("span", "badge text-bg-secondary", "Tetap");
          badge.title = "Tidak bisa diperkecil, file asli dipertahankan";
          savedCell.append(badge);
        } else {
          savedCell.append(el("span", "badge text-bg-success", "-" + item.saved_percent + "%"));
        }
        tr.append(savedCell);

        const actionCell = el("td", "text-end");
        const link = el("a", "btn btn-sm btn-primary");
        link.href = item.url;
        link.innerHTML = '<i class="bi bi-download me-1"></i>Unduh';
        actionCell.append(link);
        tr.append(actionCell);
      } else {
        const errorCell = el("td", "text-danger small", item.error || "Gagal diproses");
        errorCell.colSpan = 4;
        tr.append(errorCell);
      }

      resultsBody.append(tr);
    });

    const s = data.summary;
    let summary = s.success + " berhasil";
    if (s.failed) summary += ", " + s.failed + " gagal";
    if (s.success) {
      summary += " \u00b7 " + s.original_size_h + " \u2192 " + s.new_size_h;
      if (s.show_savings) summary += " (hemat " + s.saved_percent + "%)";
    }
    resultsSummary.textContent = summary;

    if (data.zip_url) {
      zipBtn.href = data.zip_url;
      zipBtn.classList.remove("d-none");
    } else {
      zipBtn.classList.add("d-none");
    }

    resultsCard.classList.remove("d-none");
    resultsCard.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /* ---------- Proses latar belakang (upscale): pantau progres ---------- */
  const pollInterval = () => parseInt(form.dataset.pollMs, 10) || 1500;   // bisa diatur lewat data-poll-ms
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function finishWithError(message) {
    setBusy(false);
    progressWrap.classList.add("d-none");
    showAlert(message);
  }

  async function pollJob(statusUrl) {
    let failures = 0;
    setProgress(0, "Menunggu giliran...", true, "");

    for (;;) {
      await sleep(pollInterval());

      let data;
      try {
        const response = await fetch(statusUrl, { headers: { Accept: "application/json" } });
        if (response.status === 404) {
          finishWithError("Proses tidak ditemukan atau sudah kedaluwarsa. Silakan unggah ulang.");
          return;
        }
        data = await response.json();
        failures = 0;
      } catch (error) {
        failures += 1;
        if (failures >= 5) {
          finishWithError("Koneksi ke server terputus saat memantau progres. Muat ulang halaman lalu coba lagi.");
          return;
        }
        continue;
      }

      if (data.state === "done") {
        setBusy(false);
        progressWrap.classList.add("d-none");
        renderResults(data);
        return;
      }

      const total = data.total || 0;
      const percent = total ? (data.done / total) * 100 : 0;
      setProgress(
        percent,
        "Memproses gambar " + data.done + " dari " + total + "...",
        data.done === 0,
        data.done + "/" + total
      );
    }
  }

  /* ---------- Kirim ke server ---------- */
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (busy || files.length === 0) return;

    if (totalBytes() > maxBytes) {
      showAlert("Total ukuran melebihi " + formatSize(maxBytes));
      return;
    }

    hideAlert();
    resultsCard.classList.add("d-none");

    // FormData dari form (opsi), lalu file sesuai urutan di daftar
    const formData = new FormData(form);
    formData.delete("files");
    files.forEach((file) => formData.append("files", file, filePath(file))); // ← ganti file.name -> filePath(file)

    const xhr = new XMLHttpRequest();
    xhr.open("POST", form.action);
    xhr.responseType = "json";

    xhr.upload.addEventListener("progress", (e) => {
      if (!e.lengthComputable) return;
      const percent = (e.loaded / e.total) * 100;
      if (percent >= 100) {
        setProgress(100, "Memproses di server...", true);
      } else {
        setProgress(percent, "Mengunggah...", false);
      }
    });

    xhr.addEventListener("load", () => {
      const data = xhr.response;

      // Server menerima tugas dan memprosesnya di latar belakang: pantau progresnya
      if (xhr.status === 202 && data && data.status_url) {
        files = [];
        renderFileList();
        pollJob(data.status_url);
        return;
      }

      setBusy(false);
      progressWrap.classList.add("d-none");

      if (xhr.status >= 200 && xhr.status < 300 && data && data.results) {
        renderResults(data);
        files = [];
        renderFileList();
      } else {
        showAlert((data && data.error) || "Terjadi kesalahan di server (kode " + xhr.status + ").");
      }
    });

    xhr.addEventListener("error", () => {
      setBusy(false);
      progressWrap.classList.add("d-none");
      showAlert("Tidak bisa terhubung ke server. Periksa koneksi lalu coba lagi.");
    });

    setBusy(true);
    setProgress(0, "Mengunggah...", false);
    xhr.send(formData);
  });

  renderFileList();
})();