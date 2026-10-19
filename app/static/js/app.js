// ColorPrint 3.0 JavaScript Application
// Complete client-side controller: Anti-GCR swatches, vector/raster switching,
// 50/50 split comparison slider, dark mode, clipboard paste, immediate file deletion, and PWA.

document.addEventListener("DOMContentLoaded", () => {
  // Application State
  const state = {
    fileId: null,
    filename: "",
    format: "pdf",
    originalExt: ".pdf",
    pageCount: 1,
    currentPage: 1,
    color: "#0038A8",
    mode: "selective",
    cleanBg: true,
    bgThreshold: 242,
    contrast: 1.15,
    dpi: 300,
    engine: "vector",
    forceCmyk: false,
    scannerMode: false,
    pageRange: "",
    viewMode: "recolored", // "recolored" | "split" | "original"
    isProcessing: false,
    downloadImageUrl: null,
    localModeOnly: false,
  };

  // Supported Extensions
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
  const vectorBadge = document.getElementById("vector-badge");
  const btnChangeFile = document.getElementById("btn-change-file");
  const btnDeleteFile = document.getElementById("btn-delete-file");

  // Calibration elements
  const btnOpenCalibration = document.getElementById("btn-open-calibration");
  const btnHeroCalibration = document.getElementById("btn-hero-calibration");
  const btnCloseCalibration = document.getElementById("btn-close-calibration");
  const calibrationModal = document.getElementById("calibration-modal");
  const calibrationSelect = document.getElementById("calibration-select");
  const modalSwatchesGrid = document.getElementById("modal-swatches-grid");

  // Dark mode
  const btnDarkToggle = document.getElementById("btn-dark-toggle");
  const iconSun = document.getElementById("icon-sun");
  const iconMoon = document.getElementById("icon-moon");

  // Local mode toggle
  const btnLocalMode = document.getElementById("btn-local-mode");
  const localModeDot = document.getElementById("local-mode-dot");
  const localModeText = document.getElementById("local-mode-text");

  // Colors & Presets
  const colorPresets = document.querySelectorAll(".color-preset-btn");
  const customColorPicker = document.getElementById("custom-color-picker");
  const customColorHex = document.getElementById("custom-color-hex");
  const currentColorBadge = document.getElementById("current-color-badge");

  // Engine, Mode & Options
  const engineSelect = document.getElementById("engine-select");
  const radioModes = document.querySelectorAll('input[name="mode"]');
  const labelModeSelective = document.getElementById("label-mode-selective");
  const labelModeMonochrome = document.getElementById("label-mode-monochrome");
  const cleanBgCheckbox = document.getElementById("clean-bg-checkbox");
  const forceCmykCheckbox = document.getElementById("force-cmyk-checkbox");
  const scannerModeCheckbox = document.getElementById("scanner-mode-checkbox");
  const contrastSlider = document.getElementById("contrast-slider");
  const contrastValLabel = document.getElementById("contrast-val-label");
  const pageRangeInput = document.getElementById("page-range-input");
  const dpiSelect = document.getElementById("dpi-select");
  const modeIndicatorLabel = document.getElementById("mode-indicator-label");

  // Tabs & Preview
  const tabRecolored = document.getElementById("tab-recolored");
  const tabSplit = document.getElementById("tab-split");
  const tabOriginal = document.getElementById("tab-original");
  const pageNav = document.getElementById("page-nav");
  const btnPrevPage = document.getElementById("btn-prev-page");
  const btnNextPage = document.getElementById("btn-next-page");
  const currentPageNum = document.getElementById("current-page-num");
  const totalPagesNum = document.getElementById("total-pages-num");
  const previewImage = document.getElementById("preview-image");
  const previewOriginalOverlay = document.getElementById("preview-original-overlay");
  const splitWrapper = document.getElementById("split-wrapper");
  const splitDivider = document.getElementById("split-divider");
  const previewLoader = document.getElementById("preview-loader");

  // Action Buttons
  const btnProcessDownload = document.getElementById("btn-process-download");
  const btnPrintDirect = document.getElementById("btn-print-direct");
  const btnDownloadImage = document.getElementById("btn-download-image");
  const processingIndicator = document.getElementById("processing-indicator");
  const processingStatus = document.getElementById("processing-status");
  const printFrame = document.getElementById("print-frame");

  // Initialize Dark Mode
  function initDarkMode() {
    const saved = localStorage.getItem("color_theme");
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    if (saved === "dark" || (!saved && prefersDark)) {
      document.documentElement.classList.add("dark");
      iconSun.classList.remove("hidden");
      iconMoon.classList.add("hidden");
    } else {
      document.documentElement.classList.remove("dark");
      iconSun.classList.add("hidden");
      iconMoon.classList.remove("hidden");
    }
  }

  btnDarkToggle?.addEventListener("click", () => {
    const isDark = document.documentElement.classList.toggle("dark");
    localStorage.setItem("color_theme", isDark ? "dark" : "light");
    if (isDark) {
      iconSun.classList.remove("hidden");
      iconMoon.classList.add("hidden");
    } else {
      iconSun.classList.add("hidden");
      iconMoon.classList.remove("hidden");
    }
  });

  initDarkMode();

  // Load Calibration Swatches from API
  let cachedSwatches = [];
  async function loadCalibrationSwatches() {
    try {
      const res = await fetch("/api/calibration-swatches");
      if (!res.ok) return;
      const data = await res.json();
      cachedSwatches = Array.isArray(data) ? data : (data.swatches || []);

      if (calibrationSelect) {
        calibrationSelect.innerHTML = `<option value="">Seleccionar muestra #1..#24</option>`;
        cachedSwatches.forEach((s) => {
          const opt = document.createElement("option");
          opt.value = s.hex;
          opt.textContent = `#${s.id} ${s.name} (${s.hex.toUpperCase()})`;
          calibrationSelect.appendChild(opt);
        });
      }

      if (modalSwatchesGrid) {
        modalSwatchesGrid.innerHTML = "";
        cachedSwatches.forEach((s) => {
          const card = document.createElement("button");
          card.type = "button";
          card.className = "flex items-center gap-3 p-2.5 rounded-2xl border border-slate-200 dark:border-slate-800 hover:border-sky-500 dark:hover:border-sky-400 bg-slate-50 dark:bg-slate-800/60 hover:bg-white dark:hover:bg-slate-800 text-left transition shadow-xs group";
          card.innerHTML = `
            <span class="w-8 h-8 rounded-xl shrink-0 border border-white/60 shadow-xs" style="background-color: ${s.hex}"></span>
            <div class="min-w-0">
              <div class="flex items-center gap-1.5">
                <span class="text-[10px] font-extrabold px-1.5 py-0.2 rounded bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200">#${s.id}</span>
                <span class="font-bold text-xs text-slate-800 dark:text-slate-100 truncate">${s.name}</span>
              </div>
              <p class="text-[10px] text-slate-500 font-mono">C${s.cmyk[0]} M${s.cmyk[1]} Y${s.cmyk[2]} K${s.cmyk[3]}</p>
            </div>
          `;
          card.addEventListener("click", () => {
            setColor(s.hex, true);
            closeCalibrationModal();
          });
          modalSwatchesGrid.appendChild(card);
        });
      }
    } catch (e) {
      console.warn("Could not load calibration swatches", e);
    }
  }

  loadCalibrationSwatches();

  // Calibration Modal handlers
  function openCalibrationModal() {
    calibrationModal?.classList.remove("hidden");
  }
  function closeCalibrationModal() {
    calibrationModal?.classList.add("hidden");
  }

  btnOpenCalibration?.addEventListener("click", openCalibrationModal);
  btnHeroCalibration?.addEventListener("click", openCalibrationModal);
  btnCloseCalibration?.addEventListener("click", closeCalibrationModal);
  calibrationModal?.addEventListener("click", (e) => {
    if (e.target === calibrationModal) closeCalibrationModal();
  });

  calibrationSelect?.addEventListener("change", (e) => {
    if (e.target.value) {
      setColor(e.target.value, true);
    }
  });

  // Drag and Drop Events
  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone?.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzone?.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone?.addEventListener("drop", (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files && files.length > 0) {
      handleFileUpload(files[0]);
    }
  });

  dropzone?.addEventListener("click", () => {
    fileInput?.click();
  });

  fileInput?.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileUpload(e.target.files[0]);
    }
  });

  btnChangeFile?.addEventListener("click", () => {
    fileInput.value = "";
    fileInput.click();
  });

  // Clipboard Paste Support (Ctrl+V)
  window.addEventListener("paste", (e) => {
    const items = (e.clipboardData || e.originalEvent.clipboardData).items;
    for (const item of items) {
      if (item.kind === "file") {
        const file = item.getAsFile();
        if (file) {
          handleFileUpload(file);
          break;
        }
      }
    }
  });

  // Immediate File Deletion
  btnDeleteFile?.addEventListener("click", async () => {
    if (!state.fileId) return;
    if (!confirm("¿Deseas eliminar de forma definitiva este documento del servidor de inmediato?")) return;

    try {
      await fetch(`/api/file/${state.fileId}`, { method: "DELETE" });
    } catch (e) {
      console.warn("Delete error:", e);
    }

    state.fileId = null;
    state.filename = "";
    previewImage.src = "";
    previewOriginalOverlay.src = "";
    workspacePanel.classList.add("hidden");
    dropzoneContainer.classList.remove("hidden");
    fileInput.value = "";
  });

  // Badge Details
  function getBadgeDetails(ext) {
    ext = ext.toLowerCase();
    if (ext === ".pdf") return { label: "PDF", class: "bg-red-100 text-red-600 dark:bg-red-950/80 dark:text-red-400" };
    if ([".docx", ".doc", ".odt", ".rtf"].includes(ext)) return { label: "WORD", class: "bg-blue-100 text-blue-700 dark:bg-blue-950/80 dark:text-blue-400" };
    if ([".xlsx", ".xls", ".ods", ".csv", ".tsv"].includes(ext)) return { label: "EXCEL", class: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/80 dark:text-emerald-400" };
    if ([".pptx", ".ppt", ".odp"].includes(ext)) return { label: "PPT", class: "bg-amber-100 text-amber-700 dark:bg-amber-950/80 dark:text-amber-400" };
    if ([".heic", ".heif"].includes(ext)) return { label: "HEIC", class: "bg-purple-100 text-purple-700 dark:bg-purple-950/80 dark:text-purple-400" };
    if ([".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".gif"].includes(ext)) return { label: "IMG", class: "bg-indigo-100 text-indigo-700 dark:bg-indigo-950/80 dark:text-indigo-400" };
    if (ext === ".svg") return { label: "SVG", class: "bg-teal-100 text-teal-700 dark:bg-teal-950/80 dark:text-teal-400" };
    if (ext === ".epub") return { label: "EPUB", class: "bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300" };
    return { label: ext.replace(".", "").toUpperCase().slice(0, 4), class: "bg-sky-100 text-sky-700 dark:bg-sky-950/80 dark:text-sky-300" };
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
      uploadStatusText.textContent = "Analizando y preparando para impresión sin tinta negra...";

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
      uploadStatusText.textContent = "¡Completado!";

      const data = await res.json();
      state.fileId = data.file_id;
      state.filename = data.filename;
      state.format = data.format;
      state.originalExt = data.original_ext;
      state.pageCount = data.page_count;
      state.currentPage = 1;

      // Update UI with file info
      currentFilename.textContent = data.filename;
      currentFileMeta.textContent = `${data.page_count} ${data.page_count === 1 ? "página" : "páginas"} • Archivo ${data.original_ext.toUpperCase()}`;
      
      const badge = getBadgeDetails(data.original_ext);
      fileIconBox.textContent = badge.label;
      fileIconBox.className = `w-11 h-11 rounded-xl flex items-center justify-center font-bold text-xs ${badge.class}`;

      // Show/Hide vector badge
      if (data.original_ext.toLowerCase() === ".pdf") {
        vectorBadge?.classList.remove("hidden");
        state.engine = "vector";
        if (engineSelect) engineSelect.value = "vector";
      } else {
        vectorBadge?.classList.add("hidden");
        state.engine = "raster";
        if (engineSelect) engineSelect.value = "raster";
      }

      // Show/Hide Image download button
      if (data.format === "image") {
        btnDownloadImage?.classList.remove("hidden");
      } else {
        btnDownloadImage?.classList.add("hidden");
      }

      currentPageNum.textContent = "1";
      totalPagesNum.textContent = data.pageCount;

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

  btnPrevPage?.addEventListener("click", () => {
    if (state.currentPage > 1) {
      state.currentPage--;
      updatePageNavControls();
      updatePreview();
    }
  });

  btnNextPage?.addEventListener("click", () => {
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

  customColorPicker?.addEventListener("input", (e) => {
    setColor(e.target.value, false);
  });

  customColorHex?.addEventListener("change", (e) => {
    let val = e.target.value.trim();
    if (!val.startsWith("#")) val = "#" + val;
    if (/^#[0-9A-Fa-f]{6}$/.test(val)) {
      setColor(val, true);
    }
  });

  function setColor(hex, updatePicker = true) {
    state.color = hex;
    if (currentColorBadge) currentColorBadge.textContent = hex.toUpperCase();

    if (updatePicker) {
      if (customColorPicker) customColorPicker.value = hex;
      if (customColorHex) customColorHex.value = hex.toUpperCase();
    }

    if (calibrationSelect) {
      calibrationSelect.value = hex;
    }

    // Preset active highlight
    colorPresets.forEach((btn) => {
      if (btn.getAttribute("data-color").toLowerCase() === hex.toLowerCase()) {
        btn.classList.add("border-sky-600", "dark:border-sky-500", "bg-sky-50/50", "dark:bg-sky-950/40");
        btn.classList.remove("border-slate-200", "dark:border-slate-800");
      } else {
        btn.classList.remove("border-sky-600", "dark:border-sky-500", "bg-sky-50/50", "dark:bg-sky-950/40");
        btn.classList.add("border-slate-200", "dark:border-slate-800");
      }
    });

    debouncedUpdatePreview();
  }

  // Engine selection
  engineSelect?.addEventListener("change", (e) => {
    state.engine = e.target.value;
    if (modeIndicatorLabel) {
      modeIndicatorLabel.textContent = state.engine === "vector" ? "Motor Vectorial K=0" : "Motor Rasterizado 300 DPI";
    }
  });

  // Mode Selection
  radioModes.forEach((radio) => {
    radio.addEventListener("change", (e) => {
      state.mode = e.target.value;
      if (state.mode === "selective") {
        labelModeSelective.classList.add("border-sky-600", "bg-sky-50/40");
        labelModeSelective.classList.remove("border-slate-200", "dark:border-slate-800");
        labelModeMonochrome.classList.remove("border-sky-600", "bg-sky-50/40");
        labelModeMonochrome.classList.add("border-slate-200", "dark:border-slate-800");
      } else {
        labelModeMonochrome.classList.add("border-sky-600", "bg-sky-50/40");
        labelModeMonochrome.classList.remove("border-slate-200", "dark:border-slate-800");
        labelModeSelective.classList.remove("border-sky-600", "bg-sky-50/40");
        labelModeSelective.classList.add("border-slate-200", "dark:border-slate-800");
      }
      updatePreview();
    });
  });

  // Options
  cleanBgCheckbox?.addEventListener("change", (e) => {
    state.cleanBg = e.target.checked;
    updatePreview();
  });

  forceCmykCheckbox?.addEventListener("change", (e) => {
    state.forceCmyk = e.target.checked;
  });

  scannerModeCheckbox?.addEventListener("change", (e) => {
    state.scannerMode = e.target.checked;
    updatePreview();
  });

  contrastSlider?.addEventListener("input", (e) => {
    const val = parseFloat(e.target.value);
    state.contrast = val;
    let label = "Normal";
    if (val < 1.0) label = "Suave (" + Math.round((val - 1) * 100) + "%)";
    else if (val > 1.0) label = "Intenso (+" + Math.round((val - 1) * 100) + "%)";
    if (contrastValLabel) contrastValLabel.textContent = label;
    debouncedUpdatePreview();
  });

  pageRangeInput?.addEventListener("input", (e) => {
    state.pageRange = e.target.value.trim();
  });

  dpiSelect?.addEventListener("change", (e) => {
    state.dpi = parseInt(e.target.value, 10);
  });

  // Tab View Modes (Recolored | Split 50/50 | Original)
  function setViewTab(tab) {
    state.viewMode = tab;
    [tabRecolored, tabSplit, tabOriginal].forEach((btn) => {
      btn?.classList.remove("bg-white", "dark:bg-slate-900", "text-slate-900", "dark:text-white", "shadow-xs");
      btn?.classList.add("text-slate-600", "dark:text-slate-400");
    });

    if (tab === "recolored") {
      tabRecolored?.classList.add("bg-white", "dark:bg-slate-900", "text-slate-900", "dark:text-white", "shadow-xs");
      previewOriginalOverlay?.classList.add("hidden");
      splitDivider?.classList.add("hidden");
      updatePreview();
    } else if (tab === "split") {
      tabSplit?.classList.add("bg-white", "dark:bg-slate-900", "text-slate-900", "dark:text-white", "shadow-xs");
      previewOriginalOverlay?.classList.remove("hidden");
      splitDivider?.classList.remove("hidden");
      updateSplitPreview();
    } else if (tab === "original") {
      tabOriginal?.classList.add("bg-white", "dark:bg-slate-900", "text-slate-900", "dark:text-white", "shadow-xs");
      previewOriginalOverlay?.classList.add("hidden");
      splitDivider?.classList.add("hidden");
      updateOriginalPreview();
    }
  }

  tabRecolored?.addEventListener("click", () => setViewTab("recolored"));
  tabSplit?.addEventListener("click", () => setViewTab("split"));
  tabOriginal?.addEventListener("click", () => setViewTab("original"));

  // Split Comparison Slider Drag Logic
  let isDraggingSplit = false;
  function updateSplitPosition(clientX) {
    if (!splitWrapper) return;
    const rect = splitWrapper.getBoundingClientRect();
    if (rect.width <= 0) return;
    let pct = ((clientX - rect.left) / rect.width) * 100;
    pct = Math.max(0, Math.min(100, pct));
    splitWrapper.style.setProperty("--split-pct", `${pct.toFixed(1)}%`);
  }

  splitDivider?.addEventListener("mousedown", (e) => {
    isDraggingSplit = true;
    e.preventDefault();
  });

  window.addEventListener("mousemove", (e) => {
    if (isDraggingSplit) {
      updateSplitPosition(e.clientX);
    }
  });

  window.addEventListener("mouseup", () => {
    isDraggingSplit = false;
  });

  // Touch support for split slider
  splitDivider?.addEventListener("touchstart", (e) => {
    isDraggingSplit = true;
  }, { passive: true });

  window.addEventListener("touchmove", (e) => {
    if (isDraggingSplit && e.touches.length > 0) {
      updateSplitPosition(e.touches[0].clientX);
    }
  }, { passive: true });

  window.addEventListener("touchend", () => {
    isDraggingSplit = false;
  });

  // Debounce helper
  let debounceTimeout = null;
  function debouncedUpdatePreview() {
    clearTimeout(debounceTimeout);
    debounceTimeout = setTimeout(() => {
      if (state.viewMode === "split") {
        updateSplitPreview();
      } else {
        updatePreview();
      }
    }, 180);
  }

  // Build Preview URL
  function buildPreviewUrl(type = "recolored") {
    const params = new URLSearchParams({
      page: state.currentPage,
      type: type,
      color: state.color,
      mode: state.mode,
      clean_bg: state.cleanBg,
      bg_threshold: state.bgThreshold,
      contrast: state.contrast,
      scanner_mode: state.scannerMode,
      t: Date.now(),
    });
    return `/api/preview/${state.fileId}?${params.toString()}`;
  }

  // Update Standard Preview (Recolored)
  function updatePreview() {
    if (!state.fileId) return;

    previewLoader?.classList.remove("hidden");
    previewImage?.classList.add("loading");

    const previewUrl = buildPreviewUrl("recolored");
    const tempImg = new Image();
    tempImg.onload = () => {
      previewImage.src = previewUrl;
      previewImage.classList.remove("loading");
      previewLoader?.classList.add("hidden");
    };
    tempImg.onerror = () => {
      previewImage.classList.remove("loading");
      previewLoader?.classList.add("hidden");
    };
    tempImg.src = previewUrl;
  }

  // Update Original-Only Preview
  function updateOriginalPreview() {
    if (!state.fileId) return;

    previewLoader?.classList.remove("hidden");
    previewImage?.classList.add("loading");

    const originalUrl = buildPreviewUrl("original");
    const tempImg = new Image();
    tempImg.onload = () => {
      previewImage.src = originalUrl;
      previewImage.classList.remove("loading");
      previewLoader?.classList.add("hidden");
    };
    tempImg.onerror = () => {
      previewImage.classList.remove("loading");
      previewLoader?.classList.add("hidden");
    };
    tempImg.src = originalUrl;
  }

  // Update 50/50 Split Preview
  function updateSplitPreview() {
    if (!state.fileId) return;

    previewLoader?.classList.remove("hidden");
    previewImage?.classList.add("loading");

    const recoloredUrl = buildPreviewUrl("recolored");
    const originalUrl = buildPreviewUrl("original");

    let loaded = 0;
    function checkDone() {
      loaded++;
      if (loaded >= 2) {
        previewImage.classList.remove("loading");
        previewLoader?.classList.add("hidden");
      }
    }

    const img1 = new Image();
    img1.onload = () => {
      previewImage.src = recoloredUrl;
      checkDone();
    };
    img1.onerror = checkDone;
    img1.src = recoloredUrl;

    const img2 = new Image();
    img2.onload = () => {
      previewOriginalOverlay.src = originalUrl;
      checkDone();
    };
    img2.onerror = checkDone;
    img2.src = originalUrl;
  }

  // Process Document
  async function triggerProcessing() {
    if (!state.fileId || state.isProcessing) return null;

    state.isProcessing = true;
    processingIndicator?.classList.remove("hidden");
    if (processingStatus) {
      processingStatus.textContent = state.engine === "vector" 
        ? "Reescribiendo flujos vectoriales (CMYK K=0)..." 
        : "Procesando documento en alta resolución 300 DPI...";
    }
    btnProcessDownload.disabled = true;
    btnPrintDirect.disabled = true;
    if (btnDownloadImage) btnDownloadImage.disabled = true;

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
          engine: state.engine,
          force_cmyk_no_k: state.forceCmyk,
          scanner_mode: state.scannerMode,
          page_range: state.pageRange,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Error al procesar el documento");
      }

      const data = await res.json();
      state.downloadImageUrl = data.download_image_url || null;
      return data;
    } catch (err) {
      alert("Error: " + err.message);
      return null;
    } finally {
      state.isProcessing = false;
      processingIndicator?.classList.add("hidden");
      btnProcessDownload.disabled = false;
      btnPrintDirect.disabled = false;
      if (btnDownloadImage) btnDownloadImage.disabled = false;
    }
  }

  btnProcessDownload?.addEventListener("click", async () => {
    const result = await triggerProcessing();
    if (result && result.download_url) {
      window.location.href = result.download_url;
    }
  });

  btnDownloadImage?.addEventListener("click", async () => {
    const result = await triggerProcessing();
    if (result && result.download_image_url) {
      window.location.href = result.download_image_url;
    } else if (result && result.download_url) {
      window.location.href = result.download_url;
    }
  });

  btnPrintDirect?.addEventListener("click", async () => {
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

  // Register Service Worker for PWA Offline Shell
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch((err) => {
      console.debug("Service worker registration ignored or failed:", err);
    });
  }
});
