// ColorPrint JavaScript Application (Multi-format support)
document.addEventListener("DOMContentLoaded", () => {
  // State
  const state = {
    fileId: null,
    filename: "",
    format: "pdf",
    originalExt: ".pdf",
    pageCount: 1,
    currentPage: 1,
    color: "#002060",
    mode: "selective",
    cleanBg: true,
    bgThreshold: 242,
    contrast: 1.15,
    dpi: 300,
    currentTab: "recolored", // "recolored" | "original"
    isProcessing: false,
    downloadImageUrl: null,
  };

  // Supported extensions list
  const validExtensions = [
    ".pdf", ".docx", ".doc", ".docm", ".dotx", ".dot",
    ".odt", ".rtf", ".xlsx", ".xls", ".xlsm", ".ods",
    ".pptx", ".ppt", ".potx", ".pot", ".odp",
    ".txt", ".csv", ".tsv", ".html", ".htm", ".md",
    ".xps", ".oxps", ".epub", ".cbz", ".fb2", ".svg",
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif",
    ".heic", ".heif", ".avif", ".gif", ".ico", ".psd", ".tga"
  ];

  // DOM Elements
  const dropzoneContainer = document.getElementById("dropzone-container");
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const uploadProgress = document.getElementById("upload-progress");
  const uploadBar = document.getElementById("upload-bar");
  const uploadPercentage = document.getElementById("upload-percentage");
  const uploadStatusText = document.getElementById("upload-status-text");

  const workspacePanel = document.getElementById("workspace-panel");
  const currentFilename = document.getElementById("current-filename");
  const currentFileMeta = document.getElementById("current-file-meta");
  const fileIconBox = document.getElementById("file-icon-box");
  const btnChangeFile = document.getElementById("btn-change-file");

  const colorPresets = document.querySelectorAll(".color-preset-btn");
  const customColorPicker = document.getElementById("custom-color-picker");
  const customColorHex = document.getElementById("custom-color-hex");
  const currentColorBadge = document.getElementById("current-color-badge");

  const radioModes = document.querySelectorAll('input[name="mode"]');
  const labelModeSelective = document.getElementById("label-mode-selective");
  const labelModeMonochrome = document.getElementById("label-mode-monochrome");

  const cleanBgCheckbox = document.getElementById("clean-bg-checkbox");
  const contrastSlider = document.getElementById("contrast-slider");
  const contrastValLabel = document.getElementById("contrast-val-label");
  const dpiSelect = document.getElementById("dpi-select");

  const tabRecolored = document.getElementById("tab-recolored");
  const tabOriginal = document.getElementById("tab-original");
  const pageNav = document.getElementById("page-nav");
  const btnPrevPage = document.getElementById("btn-prev-page");
  const btnNextPage = document.getElementById("btn-next-page");
  const currentPageNum = document.getElementById("current-page-num");
  const totalPagesNum = document.getElementById("total-pages-num");
  const previewImage = document.getElementById("preview-image");
  const previewLoader = document.getElementById("preview-loader");

  const btnProcessDownload = document.getElementById("btn-process-download");
  const btnPrintDirect = document.getElementById("btn-print-direct");
  const btnDownloadImage = document.getElementById("btn-download-image");
  const processingIndicator = document.getElementById("processing-indicator");
  const processingStatus = document.getElementById("processing-status");
  const printFrame = document.getElementById("print-frame");

  // Drag and Drop Events
  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files && files.length > 0) {
      handleFileUpload(files[0]);
    }
  });

  dropzone.addEventListener("click", () => {
    fileInput.click();
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileUpload(e.target.files[0]);
    }
  });

  btnChangeFile.addEventListener("click", () => {
    fileInput.value = "";
    fileInput.click();
  });

  // Get format badge color and label
  function getBadgeDetails(ext) {
    ext = ext.toLowerCase();
    if (ext === ".pdf") return { label: "PDF", class: "bg-red-100 text-red-600" };
    if ([".docx", ".doc", ".odt", ".rtf"].includes(ext)) return { label: "WORD", class: "bg-blue-100 text-blue-700" };
    if ([".xlsx", ".xls", ".ods", ".csv", ".tsv"].includes(ext)) return { label: "EXCEL", class: "bg-emerald-100 text-emerald-700" };
    if ([".pptx", ".ppt", ".odp"].includes(ext)) return { label: "PPT", class: "bg-amber-100 text-amber-700" };
    if ([".heic", ".heif"].includes(ext)) return { label: "HEIC", class: "bg-purple-100 text-purple-700" };
    if ([".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".gif"].includes(ext)) return { label: "IMG", class: "bg-indigo-100 text-indigo-700" };
    if (ext === ".svg") return { label: "SVG", class: "bg-teal-100 text-teal-700" };
    if (ext === ".epub") return { label: "EPUB", class: "bg-amber-100 text-amber-800" };
    return { label: ext.replace(".", "").toUpperCase().slice(0, 4), class: "bg-sky-100 text-sky-700" };
  }

  // File Upload Handler
  async function handleFileUpload(file) {
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (!validExtensions.includes(ext)) {
      alert("Formato no reconocido. Puedes subir PDF, Word, Excel, PowerPoint, imágenes (PNG, JPG, HEIC), SVG o texto.");
      return;
    }

    dropzoneContainer.classList.add("hidden");
    uploadProgress.classList.remove("hidden");
    uploadBar.style.width = "20%";
    uploadPercentage.textContent = "20%";
    uploadStatusText.textContent = "Subiendo archivo...";

    const formData = new FormData();
    formData.append("file", file);

    try {
      uploadBar.style.width = "45%";
      uploadPercentage.textContent = "45%";
      uploadStatusText.textContent = "Procesando y convirtiendo a formato imprimible...";

      const res = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Error subiendo archivo");
      }

      uploadBar.style.width = "100%";
      uploadPercentage.textContent = "100%";
      uploadStatusText.textContent = "¡Carga y conversión completada!";

      const data = await res.json();
      state.fileId = data.file_id;
      state.filename = data.filename;
      state.format = data.format;
      state.originalExt = data.original_ext;
      state.pageCount = data.page_count;
      state.currentPage = 1;

      // Update UI with file info
      currentFilename.textContent = data.filename;
      currentFileMeta.textContent = `${data.page_count} ${data.page_count === 1 ? "página" : "páginas"} &bull; Archivo ${data.original_ext.toUpperCase()}`;
      
      const badge = getBadgeDetails(data.original_ext);
      fileIconBox.textContent = badge.label;
      fileIconBox.className = `w-12 h-12 rounded-xl flex items-center justify-center font-bold text-xs ${badge.class}`;

      // Show/Hide Image download button
      if (data.format === "image") {
        btnDownloadImage.classList.remove("hidden");
      } else {
        btnDownloadImage.classList.add("hidden");
      }

      currentPageNum.textContent = "1";
      totalPagesNum.textContent = data.page_count;

      updatePageNavControls();

      // Show workspace
      uploadProgress.classList.add("hidden");
      workspacePanel.classList.remove("hidden");

      // Load preview
      updatePreview();
    } catch (err) {
      alert("Error: " + err.message);
      uploadProgress.classList.add("hidden");
      dropzoneContainer.classList.remove("hidden");
    }
  }

  // Update Page Navigation Buttons
  function updatePageNavControls() {
    currentPageNum.textContent = state.currentPage;
    totalPagesNum.textContent = state.pageCount;
    btnPrevPage.disabled = state.currentPage <= 1;
    btnNextPage.disabled = state.currentPage >= state.pageCount;
    if (state.pageCount <= 1) {
      pageNav.classList.add("opacity-50", "pointer-events-none");
    } else {
      pageNav.classList.remove("opacity-50", "pointer-events-none");
    }
  }

  btnPrevPage.addEventListener("click", () => {
    if (state.currentPage > 1) {
      state.currentPage--;
      updatePageNavControls();
      updatePreview();
    }
  });

  btnNextPage.addEventListener("click", () => {
    if (state.currentPage < state.pageCount) {
      state.currentPage++;
      updatePageNavControls();
      updatePreview();
    }
  });

  // Color Selection
  colorPresets.forEach((btn) => {
    btn.addEventListener("click", () => {
      const selectedColor = btn.getAttribute("data-color");
      setColor(selectedColor);
    });
  });

  customColorPicker.addEventListener("input", (e) => {
    setColor(e.target.value, false);
  });

  customColorHex.addEventListener("change", (e) => {
    let val = e.target.value.trim();
    if (!val.startsWith("#")) val = "#" + val;
    if (/^#[0-9A-Fa-f]{6}$/.test(val)) {
      setColor(val, true);
    }
  });

  function setColor(hex, updatePicker = true) {
    state.color = hex;
    currentColorBadge.textContent = hex.toUpperCase();

    if (updatePicker) {
      customColorPicker.value = hex;
      customColorHex.value = hex.toUpperCase();
    }

    // Preset active highlight
    colorPresets.forEach((btn) => {
      if (btn.getAttribute("data-color").toLowerCase() === hex.toLowerCase()) {
        btn.classList.add("active");
        btn.classList.remove("border-slate-200", "bg-white");
        btn.classList.add("border-sky-600", "bg-sky-50/50");
      } else {
        btn.classList.remove("active");
        btn.classList.remove("border-sky-600", "bg-sky-50/50");
        btn.classList.add("border-slate-200", "bg-white");
      }
    });

    debouncedUpdatePreview();
  }

  // Mode Selection
  radioModes.forEach((radio) => {
    radio.addEventListener("change", (e) => {
      state.mode = e.target.value;
      if (state.mode === "selective") {
        labelModeSelective.classList.add("border-sky-600", "bg-sky-50/40");
        labelModeSelective.classList.remove("border-slate-200", "bg-white");
        labelModeMonochrome.classList.remove("border-sky-600", "bg-sky-50/40");
        labelModeMonochrome.classList.add("border-slate-200", "bg-white");
      } else {
        labelModeMonochrome.classList.add("border-sky-600", "bg-sky-50/40");
        labelModeMonochrome.classList.remove("border-slate-200", "bg-white");
        labelModeSelective.classList.remove("border-sky-600", "bg-sky-50/40");
        labelModeSelective.classList.add("border-slate-200", "bg-white");
      }
      updatePreview();
    });
  });

  // Options
  cleanBgCheckbox.addEventListener("change", (e) => {
    state.cleanBg = e.target.checked;
    updatePreview();
  });

  contrastSlider.addEventListener("input", (e) => {
    const val = parseFloat(e.target.value);
    state.contrast = val;
    let label = "Normal";
    if (val < 1.0) label = "Suave (" + Math.round((val - 1) * 100) + "%)";
    else if (val > 1.0) label = "Intenso (+" + Math.round((val - 1) * 100) + "%)";
    contrastValLabel.textContent = label;
    debouncedUpdatePreview();
  });

  dpiSelect.addEventListener("change", (e) => {
    state.dpi = parseInt(e.target.value, 10);
  });

  // Tab Toggle (Transformado vs Original)
  tabRecolored.addEventListener("click", () => {
    state.currentTab = "recolored";
    tabRecolored.classList.add("bg-white", "text-slate-900", "shadow-sm");
    tabRecolored.classList.remove("text-slate-600");
    tabOriginal.classList.remove("bg-white", "text-slate-900", "shadow-sm");
    tabOriginal.classList.add("text-slate-600");
    updatePreview();
  });

  tabOriginal.addEventListener("click", () => {
    state.currentTab = "original";
    tabOriginal.classList.add("bg-white", "text-slate-900", "shadow-sm");
    tabOriginal.classList.remove("text-slate-600");
    tabRecolored.classList.remove("bg-white", "text-slate-900", "shadow-sm");
    tabRecolored.classList.add("text-slate-600");
    updatePreview();
  });

  // Debounce helper
  let debounceTimeout = null;
  function debouncedUpdatePreview() {
    clearTimeout(debounceTimeout);
    debounceTimeout = setTimeout(updatePreview, 180);
  }

  // Update Preview Image
  function updatePreview() {
    if (!state.fileId) return;

    previewLoader.classList.remove("hidden");
    previewImage.classList.add("loading");

    const params = new URLSearchParams({
      page: state.currentPage,
      type: state.currentTab,
      color: state.color,
      mode: state.mode,
      clean_bg: state.cleanBg,
      bg_threshold: state.bgThreshold,
      contrast: state.contrast,
      t: Date.now(),
    });

    const previewUrl = `/api/preview/${state.fileId}?${params.toString()}`;

    const tempImg = new Image();
    tempImg.onload = () => {
      previewImage.src = previewUrl;
      previewImage.classList.remove("loading");
      previewLoader.classList.add("hidden");
    };
    tempImg.onerror = () => {
      previewImage.classList.remove("loading");
      previewLoader.classList.add("hidden");
    };
    tempImg.src = previewUrl;
  }

  // Process Document
  async function triggerProcessing() {
    if (!state.fileId || state.isProcessing) return null;

    state.isProcessing = true;
    processingIndicator.classList.remove("hidden");
    processingStatus.textContent = "Procesando documento y generando archivos en alta resolución...";
    btnProcessDownload.disabled = true;
    btnPrintDirect.disabled = true;
    btnDownloadImage.disabled = true;

    try {
      const res = await fetch("/api/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_id: state.fileId,
          color: state.color,
          mode: state.mode,
          clean_bg: state.cleanBg,
          bg_threshold: state.bgThreshold,
          contrast: state.contrast,
          dpi: state.dpi,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Error al procesar");
      }

      const data = await res.json();
      state.downloadImageUrl = data.download_image_url || null;
      return data;
    } catch (err) {
      alert("Error: " + err.message);
      return null;
    } finally {
      state.isProcessing = false;
      processingIndicator.classList.add("hidden");
      btnProcessDownload.disabled = false;
      btnPrintDirect.disabled = false;
      btnDownloadImage.disabled = false;
    }
  }

  btnProcessDownload.addEventListener("click", async () => {
    const result = await triggerProcessing();
    if (result && result.download_url) {
      window.location.href = result.download_url;
    }
  });

  btnDownloadImage.addEventListener("click", async () => {
    const result = await triggerProcessing();
    if (result && result.download_image_url) {
      window.location.href = result.download_image_url;
    } else if (result && result.download_url) {
      window.location.href = result.download_url;
    }
  });

  btnPrintDirect.addEventListener("click", async () => {
    const result = await triggerProcessing();
    if (result && result.view_url) {
      printFrame.src = result.view_url;
      printFrame.onload = () => {
        try {
          printFrame.contentWindow.focus();
          printFrame.contentWindow.print();
        } catch (e) {
          window.open(result.view_url, "_blank");
        }
      };
    }
  });
});
