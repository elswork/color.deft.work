<div align="center">

# 🎨 ColorPrint 3.0 (K=0)

**Imprime cualquier documento cuando falla la tinta negra &bull; Print any document when your black ink fails**

[![Web en Producción](https://img.shields.io/badge/Producci%C3%B3n-color.deft.work-0284c7?style=for-the-badge&logo=google-chrome&logoColor=white)](https://color.deft.work)
[![CI / Automated Tests](https://img.shields.io/github/actions/workflow/status/elswork/color.deft.work/ci.yml?branch=main&style=for-the-badge&logo=githubactions&logoColor=white&label=CI%20Tests)](https://github.com/elswork/color.deft.work/actions)
[![Licencia: MIT](https://img.shields.io/badge/Licencia-MIT-blue.svg?style=for-the-badge)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Listo-2496ED?style=for-the-badge&logo=docker&logoColor=white)](#-despliegue-con-docker)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)

<p align="center">
  <a href="https://color.deft.work"><strong>🌐 Probar aplicación en vivo: color.deft.work »</strong></a>
</p>

</div>

---

## 🇪🇸 Descripción en Español

### 📌 El Problema de Impresión: La Trampa GCR / UCR

Las impresoras de inyección de tinta funcionan con cuatro canales: **Cian (C), Magenta (M), Amarillo (Y) y Negro (K)**. Cuando el cartucho negro se agota o el cabezal se atasca, las impresoras expulsan páginas en blanco o texto ilegible.

**¿Por qué falla cambiar el texto a un "azul casi negro" o "negro sintético" (`#0d192d`)?**
Los controladores de impresora (drivers) ejecutan un algoritmo interno llamado **GCR (*Gray Component Replacement*)** o **UCR (*Under Color Removal*)**: cuando detectan un color con luminosidad muy baja o valores RGB casi idénticos, sustituyen automáticamente las tintas de color por tinta del cartucho negro para ahorrar tinta de color. Si tu cartucho negro está roto o vacío, **ese texto vuelve a desaparecer o salir en blanco**.

### 💡 La Solución de ColorPrint 3.0

ColorPrint evita completamente el cabezal negro mediante:

1. **Hoja de Calibración A4 Anti-GCR (24 Muestras Empíricas)**:
   Genera un PDF vectorial con 24 fórmulas cromáticas puras (**K=0 estricto**) ordenadas por familias tonales (Azules, Púrpuras, Borgoñas, Verdes y Sepias). El usuario imprime una sola hoja y selecciona visualmente el número que sale más nítido y oscuro en su máquina.
2. **Motor Vectorial Nativo para PDF**:
   Reescribe los flujos de contenido del PDF (`rg`, `RG`, `k`, `K`, `g`, `G`) preservando el texto 100% seleccionable, tipografías y nitidez vectorial infinita, sin rasterizar el documento a imagen a menos que el usuario lo solicite.
3. **Filtro de Escáner Móvil (Anti-Sombras)**:
   Normaliza la iluminación en fotos tomadas con el teléfono móvil (recibos, apuntes, contratos arrugados), eliminando sombras y fondos amarillentos antes de imprimir.
4. **Comparador Interactivo 50/50**:
   Permite deslizar una cortina divisoria para comparar en tiempo real el documento original con la versión transformada sin tinta negra.
5. **Privacidad y RGPD Total (0 CDNs)**:
   Todos los scripts (Tailwind, motores, fuentes del sistema) están empaquetados localmente. Sin rastreadores externos ni cookies. Borrado automático de documentos en 30 minutos o borrado instantáneo con un clic.
6. **Soporte de +40 Formatos**:
   PDF, Microsoft Office (Word `.docx`, Excel `.xlsx`, PowerPoint `.pptx`), LibreOffice (`.odt`, `.ods`, `.odp`), libros `.epub`, fotos de iPhone (`.heic`, `.heif`), imágenes (`.png`, `.jpg`, `.webp`, `.tiff`, `.psd`) y gráficos vectoriales `.svg`.

---

## 🇬🇧 English Summary

### 📌 The GCR / UCR Printing Trap

Standard inkjet printers use 4 channels: **Cyan (C), Magenta (M), Yellow (Y), and Black (K)**. When the black cartridge runs out or the printhead clogs, printing black text results in blank pages.

Attempting to replace black text with an ultra-dark navy or synthetic RGB black often fails because printer drivers execute **GCR (Gray Component Replacement)**: dark or neutral tones are routed to the black printhead regardless of RGB input.

### 💡 The ColorPrint 3.0 Solution

- **Empirical 24-Swatch Calibration Sheet (`/api/calibration-sheet`)**: Print a single A4 page with 24 pure CMY formulas ($K=0$) to find your printer's optimal tone.
- **Native Vector PDF Stream Rewriter**: Modifies PDF color operators directly, keeping text selectable, fonts embedded, and vectors sharp.
- **Mobile Scanner Mode**: Normalizes uneven lighting and removes shadows from camera photos of documents.
- **Interactive 50/50 Split Slider**: Real-time visual comparison between original and transformed documents.
- **100% GDPR Compliant**: Zero external CDNs or analytics, auto-pruning after 30 minutes, and instant deletion button.
- **40+ Formats Supported**: PDF, Word, Excel, PowerPoint, LibreOffice, ePub, HEIC, TIFF, PNG, JPG, and SVG.

---

## 📁 Formatos de Archivo Compatibles

| Categoría | Formatos soportados |
| :--- | :--- |
| **Documentos Estándar** | `.pdf`, `.xps`, `.oxps` |
| **Procesador de Texto** | Microsoft Word (`.docx`, `.doc`, `.docm`, `.dotx`, `.dot`), `.odt`, `.rtf`, `.txt`, `.md` |
| **Hojas de Cálculo** | Microsoft Excel (`.xlsx`, `.xls`, `.xlsm`), `.ods`, `.csv`, `.tsv` |
| **Presentaciones** | Microsoft PowerPoint (`.pptx`, `.ppt`, `.potx`), `.odp` |
| **Libros y Cómics** | `.epub`, `.fb2`, `.cbz` |
| **Vectores y Web** | `.svg`, `.html`, `.htm` |
| **Fotografías y Móvil** | Fotos de iPhone/Apple (`.heic`, `.heif`), Google WebP (`.webp`), `.avif` |
| **Imágenes Estándar** | `.png`, `.jpg`, `.jpeg`, `.bmp`, `.tiff`, `.tif`, `.gif`, `.ico`, `.psd` (Photoshop), `.tga` |

---

## 🛠️ Arquitectura y Tecnologías

- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11 asíncrono con `asyncio.to_thread` para tareas pesadas).
- **Motor PDF & Gráficos**: [PyMuPDF](https://pymupdf.readthedocs.io/) 2.0+, [NumPy](https://numpy.org/), [Pillow](https://python-pillow.org/) y [pillow-heif](https://github.com/bigcat88/pillow_heif).
- **Conversión Ofimática**: [LibreOffice Headless](https://www.libreoffice.org/) aislado con perfiles temporales únicos y semáforo de concurrencia.
- **Frontend**: Vanilla JavaScript modular reactivo, Tailwind CSS local (sin CDNs), PWA con Service Worker y modo oscuro.
- **Infraestructura**: Contenedor Docker auto-contenido, proxy inverso con SSL Let's Encrypt.
- **Pruebas Automatizadas**: Suite completa en `pytest` con integración continua en GitHub Actions.

---

## 🚀 Despliegue con Docker

### Requisitos previos
- [Docker](https://docs.docker.com/get-docker/) y [Docker Compose](https://docs.docker.com/compose/)

### 1. Clonar el repositorio
```bash
git clone https://github.com/elswork/color.deft.work.git
cd color.deft.work
```

### 2. Iniciar el servicio con Docker Compose
```bash
docker compose up -d --build
```

O si prefieres descargar directamente la imagen precompilada desde **GitHub Container Registry**:
```bash
docker pull ghcr.io/elswork/color.deft.work:latest
```

El servicio estará disponible de inmediato en:
```
http://localhost:5065
```

---

## 🧪 Ejecución de Pruebas Automatizadas

Para ejecutar la suite de pruebas unitarias y de integración dentro del contenedor:

```bash
docker compose exec app pytest -v
```

O localmente en tu entorno de desarrollo Python 3.11:

```bash
pip install -r requirements-dev.txt
pytest -v
```

---

## 🔌 API REST

ColorPrint incluye una API REST completa para integración con otros servicios:

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/health` / `/api/health` | Estado del servicio y versión. |
| `GET` | `/api/calibration-swatches` | Devuelve la lista JSON de las 24 fórmulas Anti-GCR. |
| `GET` | `/api/calibration-sheet` | Genera y descarga el PDF vectorial A4 de calibración. |
| `POST` | `/api/upload` | Sube y valida un documento o imagen (máx. 50 MB). |
| `GET` | `/api/preview/{file_id}` | Genera miniaturas en tiempo real (recoloreado u original). |
| `POST` | `/api/process` | Procesa el documento completo (motor vectorial o raster 300 DPI). |
| `DELETE` | `/api/file/{file_id}` | Elimina inmediatamente los archivos del servidor. |
| `GET` | `/api/download/{output_id}` | Descarga el PDF final generado. |
| `GET` | `/api/view/{output_id}` | Vista directa en el navegador para `window.print()`. |

---

## 🌐 Enlaces Cruzados

- **Aplicación web en producción**: [https://color.deft.work](https://color.deft.work)
- **Repositorio de código abierto en GitHub**: [https://github.com/elswork/color.deft.work](https://github.com/elswork/color.deft.work)

---

## 📄 Licencia

Este proyecto está distribuido bajo la [Licencia MIT](LICENSE). Código libre para uso personal y comercial.
