<div align="center">

# 🎨 ColorPrint

**Imprime cualquier documento cuando falla la tinta negra**

[![Demo en vivo](https://img.shields.io/badge/Web%20en%20Producci%C3%B3n-color.deft.work-0284c7?style=for-the-badge&logo=google-chrome&logoColor=white)](https://color.deft.work)
[![Licencia: MIT](https://img.shields.io/badge/Licencia-MIT-blue.svg?style=for-the-badge)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Listo-2496ED?style=for-the-badge&logo=docker&logoColor=white)](#despliegue-con-docker)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)

<p align="center">
  <a href="https://color.deft.work"><strong>🌐 Probar aplicación en vivo: color.deft.work »</strong></a>
</p>

</div>

---

## 📌 ¿Qué problema resuelve?

Las impresoras de inyección de tinta funcionan habitualmente con cuatro canales: **Cian (C), Magenta (M), Amarillo (Y) y Negro (K)**. Cuando el cartucho negro se agota o el cabezal negro se obstruye o avería, las impresoras estándar se niegan a imprimir texto negro o expulsan hojas completamente en blanco.

**ColorPrint** transforma el texto, gráficos y trazos negros de tus documentos a **azul marino, cian profundo, borgoña, sepia o negro tricromía (CMY)**. De este modo, el controlador de la impresora recurre exclusivamente a los cartuchos de color en buen estado, permitiéndote imprimir documentos legibles, nítidos y profesionales sin necesidad de cambiar o arreglar el cartucho negro.

---

## ✨ Características Principales

- **Conversión Inteligente de Color**:
  - **Solo negros y grises (Inteligente)**: Convierte únicamente el texto y trazos negros o grises, manteniendo inalterados los sellos rojos, firmas o logotipos que ya tenían color.
  - **Monocromático Completo (Duotono)**: Mapea todo el documento a gradientes del color seleccionado (garantía de 0% uso de tinta negra).
- **Paleta de Colores Optimizada para Impresión**:
  - 🔵 **Azul Marino Clásico (`#002060`)**: Máximo contraste y aspecto formal para facturas, billetes y contratos.
  - 🔷 **Cian Profundo (`#00558f`)**: Nitidez ideal para códigos de barras y etiquetas legibles por escáner.
  - 🟣 **Borgoña / Vino (`#6b0f24`)**: Tono cálido con gran definición.
  - 🟢 **Verde Bosque (`#084d22`)**: Alto contraste mezclando cian y amarillo.
  - 🟫 **Sepia Cálido (`#42210b`)**: Acabado clásico estilo imprenta antigua.
  - ⬛ **Tricromía CMY "Negro Sintético" (`#0d192d`)**: Apariencia prácticamente negra compuesta exclusivamente por tintas de color.
  - 🎨 **Selector Personalizado**: Elige cualquier color RGB / HEX a tu gusto.
- **Herramientas de Optimización de Impresión**:
  - **Limpieza de fondo blanco**: Elimina el ruido grisáceo de documentos escaneados para ahorrar tinta.
  - **Potenciador de contraste**: Intensifica letras finas o tenues para mayor legibilidad sobre el papel.
  - **Resolución a 300 DPI**: Salida en alta resolución respetando las dimensiones físicas originales (A4, Carta, etc.).
- **Vista Previa Interactiva**: Comparación en tiempo real (Transformado vs. Original) y visor multipágina.
- **Acciones Directas**: Descarga de PDF de imprenta, descarga de imagen (PNG) e impresión directa desde el navegador (`window.print()`).

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

## 🛠️ Tecnologías Utilizadas

- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11), [PyMuPDF](https://pymupdf.readthedocs.io/) (fitz), [NumPy](https://numpy.org/), [Pillow](https://python-pillow.org/) y [pillow-heif](https://github.com/bigcat88/pillow_heif).
- **Conversión Ofimática**: [LibreOffice Headless](https://www.libreoffice.org/) (`libreoffice-*-nogui`) con tipografías DejaVu y Liberation.
- **Frontend**: HTML5, Tailwind CSS y Vanilla JavaScript reactivo.
- **Infraestructura**: Docker, Docker Compose y proxy inverso UWAS.

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

El servicio estará disponible en:
```
http://localhost:5065
```

---

## 🔌 API REST

ColorPrint incluye una API sencilla para integración con otras herramientas o flujos de trabajo:

- `POST /api/upload`: Sube cualquier documento o imagen y devuelve el identificador de sesión y número de páginas.
- `GET /api/preview/{file_id}?page=1&color=%23002060`: Genera en tiempo real una miniatura de la página seleccionada.
- `POST /api/process`: Procesa el documento completo a 300 DPI y genera el PDF resultante.
- `GET /api/download/{output_id}`: Descarga el archivo PDF transformado.
- `GET /api/view/{output_id}`: Visualización directa en el navegador para impresión inmediata.
- `GET /api/download-image/{output_id}`: Descarga de la imagen resultante (en caso de subidas de imágenes).

---

## 🌐 Enlaces Cruzados

- **Aplicación web en producción**: [https://color.deft.work](https://color.deft.work)
- **Repositorio de código abierto**: [https://github.com/elswork/color.deft.work](https://github.com/elswork/color.deft.work)

---

## 📄 Licencia

Este proyecto está bajo la [Licencia MIT](LICENSE). Siéntete libre de utilizarlo, modificarlo y desplegarlo en tu propia infraestructura.
