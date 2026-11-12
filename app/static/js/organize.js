(() => {
  "use strict";

  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const uploadSection = document.getElementById("upload-section");
  const editorSection = document.getElementById("editor-section");
  const pageGrid = document.getElementById("page-grid");
  const saveBtn = document.getElementById("save-btn");
  const pageCount = document.getElementById("page-count");
  const alertBox = document.getElementById("alert-box");
  const loadingUpload = document.getElementById("loading-upload");
  const loadingSave = document.getElementById("loading-save");
  const resetBtn = document.getElementById("reset-btn");
  
  // Modal elements
  const zoomModalEl = document.getElementById("zoomModal");
  const zoomModal = new bootstrap.Modal(zoomModalEl);
  const zoomImage = document.getElementById("zoom-image");

  let currentJobId = null;

  function showAlert(msg) {
    alertBox.textContent = msg;
    alertBox.classList.remove("d-none");
    if (loadingUpload) loadingUpload.classList.add("d-none");
  }

  // --- 1. UPLOAD FILE ---
  dropzone.addEventListener("click", () => fileInput.click());
  
  fileInput.addEventListener("change", async () => {
    if (!fileInput.files.length) return;

    // Validasi ekstensi semua file
    for (let file of fileInput.files) {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        showAlert("Semua file harus berformat PDF.");
        return;
      }
    }

    alertBox.classList.add("d-none");
    loadingUpload.classList.remove("d-none");

    const formData = new FormData();
    // Append semua file
    for (let file of fileInput.files) {
      formData.append("files", file);
    }

    try {
      const res = await fetch("/pdf/organize/upload", {
        method: "POST",
        body: formData
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.error || "Gagal upload");

      currentJobId = data.job_id;
      buildEditor(data.thumbnails);
      
    } catch (err) {
      showAlert(err.message);
    }
  });

  // --- 2. BANGUN UI EDITOR ---
  function buildEditor(thumbnails) {
    uploadSection.classList.add("d-none");
    editorSection.classList.remove("d-none");
    resetBtn.classList.remove("d-none");
    pageGrid.replaceChildren();
    pageCount.textContent = thumbnails.length;

    thumbnails.forEach((item, index) => {
      // item = { file_id: 0, url: "..." }
      const col = document.createElement("div");
      col.className = "col-6 col-md-4 col-lg-3 page-item";
      col.dataset.fileId = item.file_id;
      col.dataset.pageIndex = item.page_index;
      col.dataset.rotation = "0";

      const card = document.createElement("div");
      // Berikan border warna sesuai file_id (modulo 6 untuk perulangan warna)
      const colorClass = `border-pdf-${item.file_id % 6}`;
      card.className = `card h-100 shadow-sm position-relative page-card ${colorClass}`;

      // Gambar Thumbnail
      const img = document.createElement("img");
      img.src = item.url;
      img.className = "card-img-top p-2";
      img.style.transition = "transform 0.3s ease";
      img.draggable = false;

      // Overlay tombol aksi
      const actions = document.createElement("div");
      actions.className = "position-absolute top-0 end-0 p-2 d-flex gap-1";
      
      // Tombol Zoom
      const zoomBtn = document.createElement("button");
      zoomBtn.className = "btn btn-sm btn-primary opacity-75";
      zoomBtn.innerHTML = '<i class="bi bi-zoom-in"></i>';
      zoomBtn.title = "Perbesar (Zoom)";
      zoomBtn.onclick = (e) => {
        e.stopPropagation();
        zoomImage.src = img.src;
        zoomModal.show();
      };

      // Tombol Rotate
      const rotateBtn = document.createElement("button");
      rotateBtn.className = "btn btn-sm btn-dark opacity-75";
      rotateBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i>';
      rotateBtn.title = "Putar 90°";
      rotateBtn.onclick = (e) => {
        e.stopPropagation();
        let rot = (parseInt(col.dataset.rotation) + 90) % 360;
        col.dataset.rotation = rot;
        img.style.transform = `rotate(${rot}deg) scale(${rot % 180 === 0 ? 1 : 0.8})`;
      };

      // Tombol Delete
      const deleteBtn = document.createElement("button");
      deleteBtn.className = "btn btn-sm btn-danger opacity-75";
      deleteBtn.innerHTML = '<i class="bi bi-x-lg"></i>';
      deleteBtn.title = "Hapus Halaman";
      deleteBtn.onclick = (e) => {
        e.stopPropagation();
        if (pageGrid.children.length <= 1) {
          alert("Minimal harus ada 1 halaman di dalam PDF.");
          return;
        }
        col.remove();
        pageCount.textContent = pageGrid.children.length;
        updatePageNumbers();
      };

      actions.append(zoomBtn, rotateBtn, deleteBtn);
      
      // Badge Nomor Halaman
      const badge = document.createElement("span");
      badge.className = "position-absolute bottom-0 start-0 m-2 badge bg-primary page-badge";
      
      card.append(img, actions, badge);
      col.append(card);
      pageGrid.append(col);
    });

    updatePageNumbers();
    initSortable();
  }

  // --- 3. SORTABLE JS (DRAG & DROP) ---
  function initSortable() {
    new Sortable(pageGrid, {
      animation: 150,
      ghostClass: "sortable-ghost",
      filter: "button", 
      onEnd: () => {
        updatePageNumbers();
      }
    });
  }

  function updatePageNumbers() {
    Array.from(pageGrid.children).forEach((col, index) => {
      const badge = col.querySelector(".page-badge");
      if (badge) badge.textContent = index + 1;
    });
  }

  // --- 4. SIMPAN PERUBAHAN ---
  saveBtn.addEventListener("click", async () => {
    if (!currentJobId) return;
    
    loadingSave.classList.remove("d-none");
    saveBtn.disabled = true;

    // Kumpulkan data
    const operations = Array.from(pageGrid.children).map((col, index) => ({
      file_id: parseInt(col.dataset.fileId),
      page_index: parseInt(col.dataset.pageIndex), // index ke berapa di dalam file asal
      rotation: parseInt(col.dataset.rotation) || 0
    }));

    try {
      const res = await fetch(`/pdf/organize/save/${currentJobId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ operations })
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Gagal menyimpan");

      window.location.href = data.download_url;
      
    } catch (err) {
      alert(err.message);
      saveBtn.disabled = false;
    } finally {
      loadingSave.classList.add("d-none");
    }
  });

})();