/* Halaman Hapus Teks / Watermark: pilih area teks dengan menggeser di atas pratinjau gambar. */
(() => {
  "use strict";

  const form = document.getElementById("tool-form");
  const stage = document.getElementById("roi-stage");
  if (!form || !stage) return;

  const image = document.getElementById("roi-image");
  const box = document.getElementById("roi-box");
  const hint = document.getElementById("roi-hint");
  const noPreview = document.getElementById("roi-no-preview");
  const fields = {
    left: document.getElementById("roi-left"),
    top: document.getElementById("roi-top"),
    right: document.getElementById("roi-right"),
    bottom: document.getElementById("roi-bottom"),
  };

  const PREVIEWABLE = [".jpg", ".jpeg", ".png", ".webp", ".bmp"];
  let currentUrl = null;

  const clamp = (value) => Math.max(0, Math.min(100, value));
  const round1 = (value) => Math.round(value * 10) / 10;

  function drawBox() {
    const left = parseFloat(fields.left.value);
    const top = parseFloat(fields.top.value);
    const right = parseFloat(fields.right.value);
    const bottom = parseFloat(fields.bottom.value);
    const valid = [left, top, right, bottom].every((v) => !Number.isNaN(v)) && right > left && bottom > top;

    box.classList.toggle("d-none", !valid);
    if (!valid) return;
    box.style.left = left + "%";
    box.style.top = top + "%";
    box.style.width = (right - left) + "%";
    box.style.height = (bottom - top) + "%";
  }

  function setRoi(left, top, right, bottom) {
    fields.left.value = round1(clamp(left));
    fields.top.value = round1(clamp(top));
    fields.right.value = round1(clamp(right));
    fields.bottom.value = round1(clamp(bottom));
    drawBox();
  }

  /* ---------- Preset ---------- */
  document.querySelectorAll("[data-roi]").forEach((button) => {
    button.addEventListener("click", () => {
      const [l, t, r, b] = button.dataset.roi.split(",").map(Number);
      setRoi(l, t, r, b);
    });
  });

  /* ---------- Angka manual ---------- */
  Object.values(fields).forEach((input) => input.addEventListener("input", drawBox));

  /* ---------- Gambar kotak dengan menggeser pointer ---------- */
  let dragStart = null;

  function pointToPercent(event) {
    const rect = image.getBoundingClientRect();
    return {
      x: clamp(((event.clientX - rect.left) / rect.width) * 100),
      y: clamp(((event.clientY - rect.top) / rect.height) * 100),
    };
  }

  stage.addEventListener("pointerdown", (event) => {
    if (!image.src || image.classList.contains("d-none")) return;
    event.preventDefault();
    stage.setPointerCapture(event.pointerId);
    dragStart = pointToPercent(event);
  });

  stage.addEventListener("pointermove", (event) => {
    if (!dragStart) return;
    const now = pointToPercent(event);
    setRoi(
      Math.min(dragStart.x, now.x), Math.min(dragStart.y, now.y),
      Math.max(dragStart.x, now.x), Math.max(dragStart.y, now.y)
    );
  });

  const endDrag = (event) => {
    if (!dragStart) return;
    dragStart = null;
    if (stage.hasPointerCapture(event.pointerId)) stage.releasePointerCapture(event.pointerId);
  };
  stage.addEventListener("pointerup", endDrag);
  stage.addEventListener("pointercancel", endDrag);

  /* ---------- Pratinjau gambar pertama ---------- */
  function clearPreview() {
    if (currentUrl) URL.revokeObjectURL(currentUrl);
    currentUrl = null;
    image.removeAttribute("src");
    image.classList.add("d-none");
    box.classList.add("d-none");
    hint.classList.add("d-none");
  }

  form.addEventListener("filesChanged", (event) => {
    const first = event.detail.files[0];
    clearPreview();
    noPreview.classList.add("d-none");
    if (!first) return;

    const dot = first.name.lastIndexOf(".");
    const ext = dot >= 0 ? first.name.slice(dot).toLowerCase() : "";
    if (!PREVIEWABLE.includes(ext)) {
      noPreview.classList.remove("d-none"); // HEIC tidak bisa ditampilkan browser
      return;
    }

    currentUrl = URL.createObjectURL(first);
    image.src = currentUrl;
    image.classList.remove("d-none");
    hint.classList.remove("d-none");
    drawBox();
  });

  drawBox();
})();
