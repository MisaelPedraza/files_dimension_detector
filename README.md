# Image and PDF Dimension Detector

`dimension_detector.py` detects the dimensions of image files and PDF documents and expresses them in:

- Pixels (`px`)
- Inches (`in`)
- Centimeters (`cm`)
- DPI used for conversion

It can analyze one or more files from the command line and produce a readable table or JSON output for automation.

## Requirements

- Python 3.8 or later
- [Pillow](https://python-pillow.org/) for images
- [pypdf](https://pypdf.readthedocs.io/) for PDF documents

Install the dependencies with:

```powershell
python -m pip install pillow pypdf
```

Using `python -m pip` helps install the packages into the same Python interpreter that will run the program.

## Basic Usage

Analyze a PDF and an image in a single run:

```powershell
python .\dimension_detector.py archivo.pdf imagen.png
```

Analyze an image using 300 DPI to calculate its physical size:

```powershell
python .\dimension_detector.py imagen.jpg --dpi 300
```

Get the output in JSON format:

```powershell
python .\dimension_detector.py imagen.png --json
```

Show the built-in help:

```powershell
python .\dimension_detector.py --help
```

## Analyze Multiple PNG Files in PowerShell

In some Windows shells, `*.png` is passed literally to the program instead of expanding into a list of files. In PowerShell, you can build the list explicitly:

```powershell
$archivos = Get-ChildItem -File -Filter "*.png" | Select-Object -ExpandProperty FullName
python .\dimension_detector.py $archivos --json
```

If no matching files exist, `$archivos` will be empty and the program will report that the required `archivos` argument is missing.

## How to Interpret DPI

In this program, DPI is used as the resolution for converting between pixels and physical size:

```text
pulgadas = píxeles / DPI
centímetros = pulgadas × 2.54
```

For example, an image of `3000 × 2400 px` interpreted at 300 DPI corresponds to:

```text
10 × 8 in
25.4 × 20.32 cm
```

The `--dpi` parameter does not change the file, increase its resolution, or create new detail. It only controls the unit conversion.

If `--dpi` is not provided:

- For images, the program tries to use the DPI stored in metadata.
- If the image does not contain DPI, 96 DPI is assumed and the result is marked as estimated.
- For PDFs, 96 DPI is assumed to calculate a possible pixel representation.

300 DPI is often used as a reference for good print quality, but it should be chosen according to the file's destination or print specifications.

## Result Accuracy

### Images

The width and height in pixels come from the file header and are exact values. The size in inches and centimeters depends on the DPI used:

- With valid DPI in metadata, that value is used.
- With `--dpi`, the value specified by the user is used and marked as assumed.
- Without metadata or `--dpi`, 96 DPI is used and marked as estimated.

### PDF

A PDF can contain vector graphics, text, and raster images. The size of each page comes from its `MediaBox`, expressed in PDF points, where:

```text
1 punto = 1/72 de pulgada
```

For that reason, page size in inches and centimeters is derived directly from the PDF geometry. A PDF does not have a single intrinsic pixel dimension: that value depends on the DPI used to rasterize the page and is always marked as estimated.

## Supported Formats

Images:

```text
.png, .jpg, .jpeg, .gif, .bmp, .tiff, .tif,
.webp, .ico, .ppm, .pgm, .pbm
```

Documents:

```text
.pdf
```

Detector selection is based on the file extension. A supported extension does not guarantee that the content is valid; if Pillow or pypdf cannot read it, it will be reported as unreadable or corrupted.

## Console Output

Normal output shows one row per page:

```text
Archivo: imagen.jpg  (image)
Pág.  px                in              cm              DPI
-----------------------------------------------------------
1     3000 x 2400       10.00 x 8.00    25.40 x 20.32   300*
* DPI estimado/asumido (no venía como metadata exacta en el archivo).
```

The asterisk next to DPI indicates that the value was assumed, provided via `--dpi`, or calculated for a future PDF rasterization.

## JSON Output

The `--json` option returns a list of results:

```json
[
  {
    "file_path": "imagen.png",
    "file_type": "image",
    "pages": [
      {
        "page_number": 1,
        "width_px": 1920,
        "height_px": 1080,
        "width_in": 20.0,
        "height_in": 11.25,
        "width_cm": 50.8,
        "height_cm": 28.575,
        "dpi_x": 96.0,
        "dpi_y": 96.0,
        "dpi_is_estimated": true
      }
    ]
  }
]
```

If multiple files are analyzed and one fails, the errors are written to standard error, valid results remain in the JSON, and the process exits with code `1`.

## Using It as a Python Module

You can also import the analyzer from another program:

```python
from dimension_detector import DimensionAnalyzer

analyzer = DimensionAnalyzer()
result = analyzer.analyze("imagen.jpg", dpi_override=300)

for page in result.pages:
    print(page.width_px, page.height_px)
    print(page.width_cm, page.height_cm)
```

`analyze()` returns a `DetectionResult` object with the path, file type, and a list of `PageDimensions` objects.

## Architecture

```text
PageDimensions / DetectionResult  -> modelos de datos (dataclasses)
UnitConverter                     -> conversiones de unidades centralizadas
DimensionDetector (ABC)           -> interfaz común (patrón Strategy)
    ImageDimensionDetector        -> implementación para imágenes con Pillow
    PDFDimensionDetector          -> implementación para PDF con pypdf
DetectorFactory                   -> selecciona el detector (patrón Factory)
DimensionAnalyzer                 -> fachada de alto nivel (patrón Facade)
CLI (main)                        -> interfaz de línea de comandos
```

To add a new format:

1. Crear una clase que herede de `DimensionDetector`.
2. Implementar `supports()` y `detect()`.
3. Registrar una instancia en `DetectorFactory._detectors`.

The rest of the program does not need to change.

## Current Limitations

- Format detection is based on the file extension, not the file's binary signature.
- PDFs use `MediaBox`; a `CropBox` or page rotation could make the expected visual size different.
- Multi-frame GIFs and TIFFs are treated as a single image, and their frames are not enumerated.
- The program expects a DPI greater than zero. The current version does not explicitly validate zero or negative values.
- The program only reads files and shows results; it does not resize, convert, or modify images or PDFs.

