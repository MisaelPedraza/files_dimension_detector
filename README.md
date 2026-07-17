# Detector de dimensiones de imágenes y PDF

`dimension_detector.py` detecta las dimensiones de archivos de imagen y documentos PDF y las expresa en:

- Píxeles (`px`)
- Pulgadas (`in`)
- Centímetros (`cm`)
- DPI utilizados para la conversión

Puede analizar uno o varios archivos desde la línea de comandos y producir una tabla legible o una salida JSON para automatizaciones.

## Requisitos

- Python 3.8 o posterior
- [Pillow](https://python-pillow.org/) para imágenes
- [pypdf](https://pypdf.readthedocs.io/) para documentos PDF

Instala las dependencias con:

```powershell
python -m pip install pillow pypdf
```

Usar `python -m pip` ayuda a instalar los paquetes en el mismo intérprete de Python con el que se ejecutará el programa.

## Uso básico

Analizar un PDF y una imagen en una sola ejecución:

```powershell
python .\dimension_detector.py archivo.pdf imagen.png
```

Analizar una imagen usando 300 DPI para calcular su tamaño físico:

```powershell
python .\dimension_detector.py imagen.jpg --dpi 300
```

Obtener la salida en formato JSON:

```powershell
python .\dimension_detector.py imagen.png --json
```

Mostrar la ayuda integrada:

```powershell
python .\dimension_detector.py --help
```

## Analizar varios PNG en PowerShell

En algunos shells de Windows, `*.png` se entrega literalmente al programa en vez de expandirse como una lista de archivos. En PowerShell se puede construir la lista explícitamente:

```powershell
$archivos = Get-ChildItem -File -Filter "*.png" | Select-Object -ExpandProperty FullName
python .\dimension_detector.py $archivos --json
```

Si no existen archivos coincidentes, `$archivos` quedará vacío y el programa mostrará que falta el argumento obligatorio `archivos`.

## Cómo interpretar el DPI

En este programa, el DPI se utiliza como resolución para convertir entre píxeles y tamaño físico:

```text
pulgadas = píxeles / DPI
centímetros = pulgadas × 2.54
```

Por ejemplo, una imagen de `3000 × 2400 px` interpretada a 300 DPI corresponde a:

```text
10 × 8 in
25.4 × 20.32 cm
```

El parámetro `--dpi` no cambia el archivo, no aumenta su resolución y no crea detalle nuevo. Únicamente controla la conversión de unidades.

Si no se proporciona `--dpi`:

- En imágenes, el programa intenta usar el DPI guardado en los metadatos.
- Si la imagen no contiene DPI, se asumen 96 DPI y el resultado se marca como estimado.
- En PDFs, se asumen 96 DPI para calcular una posible representación en píxeles.

El valor de 300 DPI suele emplearse como referencia para impresión de buena calidad, pero debe elegirse según el destino del archivo o las especificaciones de impresión.

## Precisión de los resultados

### Imágenes

El ancho y el alto en píxeles provienen del encabezado del archivo y son valores exactos. El tamaño en pulgadas y centímetros depende del DPI usado:

- Con DPI válido en los metadatos, se utiliza ese valor.
- Con `--dpi`, se utiliza el valor indicado por el usuario y se marca como asumido.
- Sin metadatos ni `--dpi`, se utilizan 96 DPI y se marca como estimado.

### PDF

Un PDF puede contener gráficos vectoriales, texto e imágenes rasterizadas. El tamaño de cada página se obtiene de su `MediaBox`, expresado en puntos PDF, donde:

```text
1 punto = 1/72 de pulgada
```

Por eso, el tamaño de página en pulgadas y centímetros se deriva directamente de la geometría del PDF. Un PDF no tiene una única dimensión intrínseca en píxeles: ese valor depende del DPI al que se decida rasterizar la página y siempre se marca como estimado.

## Formatos compatibles

Imágenes:

```text
.png, .jpg, .jpeg, .gif, .bmp, .tiff, .tif,
.webp, .ico, .ppm, .pgm, .pbm
```

Documentos:

```text
.pdf
```

La selección del detector se realiza por la extensión del archivo. Una extensión compatible no garantiza que el contenido sea válido; si Pillow o pypdf no pueden leerlo, se reportará como archivo ilegible o corrupto.

## Salida de consola

La salida normal muestra una fila por página:

```text
Archivo: imagen.jpg  (image)
Pág.  px                in              cm              DPI
-----------------------------------------------------------
1     3000 x 2400       10.00 x 8.00    25.40 x 20.32   300*
* DPI estimado/asumido (no venía como metadata exacta en el archivo).
```

El asterisco junto al DPI indica que el valor fue asumido, indicado mediante `--dpi` o calculado para una futura rasterización de PDF.

## Salida JSON

La opción `--json` devuelve una lista de resultados:

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

Si se analizan varios archivos y alguno falla, los errores se escriben en la salida de error, los resultados válidos permanecen en el JSON y el proceso termina con código de salida `1`.

## Uso como módulo de Python

También se puede importar el analizador desde otro programa:

```python
from dimension_detector import DimensionAnalyzer

analyzer = DimensionAnalyzer()
result = analyzer.analyze("imagen.jpg", dpi_override=300)

for page in result.pages:
    print(page.width_px, page.height_px)
    print(page.width_cm, page.height_cm)
```

`analyze()` devuelve un objeto `DetectionResult` con la ruta, el tipo de archivo y una lista de objetos `PageDimensions`.

## Arquitectura

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

Para agregar un formato nuevo:

1. Crear una clase que herede de `DimensionDetector`.
2. Implementar `supports()` y `detect()`.
3. Registrar una instancia en `DetectorFactory._detectors`.

El resto del programa no necesita modificarse.

## Limitaciones actuales

- La detección del formato se basa en la extensión, no en la firma binaria del archivo.
- En PDFs se usa `MediaBox`; un `CropBox` o una rotación de página podría hacer que el tamaño visual esperado sea diferente.
- Los GIF y TIFF con varios fotogramas se tratan como una sola imagen y no se enumeran sus fotogramas.
- El programa espera un DPI mayor que cero. La versión actual no valida explícitamente valores cero o negativos.
- El programa solo lee los archivos y muestra resultados; no redimensiona, convierte ni modifica imágenes o PDFs.

