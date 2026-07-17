from __future__ import annotations

import argparse
import json
import sys
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Excepciones
# ---------------------------------------------------------------------------

class DimensionDetectorError(Exception):
    """Excepción base del módulo."""


class UnsupportedFormatError(DimensionDetectorError):
    """El formato del archivo no está soportado."""


class MissingDependencyError(DimensionDetectorError):
    """Falta instalar una dependencia externa."""


class CorruptFileError(DimensionDetectorError):
    """El archivo existe pero no se pudo leer/parsear."""


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

POINTS_PER_INCH = 72.0
CM_PER_INCH = 2.54
DEFAULT_DPI = 96.0  # usado solo cuando no hay metadata de resolución

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif",
    ".webp", ".ico", ".ppm", ".pgm", ".pbm",
}
PDF_EXTENSIONS = {".pdf"}


# ---------------------------------------------------------------------------
# Conversión de unidades
# ---------------------------------------------------------------------------

class UnitConverter:
    """Centraliza toda la lógica de conversión entre unidades."""

    @staticmethod
    def px_to_in(px: float, dpi: float) -> float:
        return px / dpi

    @staticmethod
    def in_to_px(inches: float, dpi: float) -> float:
        return inches * dpi

    @staticmethod
    def in_to_cm(inches: float) -> float:
        return inches * CM_PER_INCH

    @staticmethod
    def cm_to_in(cm: float) -> float:
        return cm / CM_PER_INCH

    @staticmethod
    def pt_to_in(points: float) -> float:
        return points / POINTS_PER_INCH

    @staticmethod
    def in_to_pt(inches: float) -> float:
        return inches * POINTS_PER_INCH


# ---------------------------------------------------------------------------
# Modelos de datos
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PageDimensions:
    """Dimensiones de una página (o de la imagen completa) en varias unidades."""

    page_number: int
    width_px: float
    height_px: float
    width_in: float
    height_in: float
    width_cm: float
    height_cm: float
    dpi_x: float
    dpi_y: float
    dpi_is_estimated: bool  # True si el DPI no venía en el archivo y se asumió/definió

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DetectionResult:
    """Resultado completo para un archivo (puede tener varias páginas)."""

    file_path: str
    file_type: str  # "image" | "pdf"
    pages: List[PageDimensions]

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "file_type": self.file_type,
            "pages": [p.to_dict() for p in self.pages],
        }


# ---------------------------------------------------------------------------
# Detectores (patrón Strategy)
# ---------------------------------------------------------------------------

class DimensionDetector(ABC):
    """Interfaz que debe implementar cada detector concreto."""

    @abstractmethod
    def supports(self, path: Path) -> bool:
        """True si este detector sabe procesar el archivo dado."""

    @abstractmethod
    def detect(self, path: Path, dpi_override: Optional[float] = None) -> DetectionResult:
        """Devuelve las dimensiones del archivo."""


class ImageDimensionDetector(DimensionDetector):
    """Detecta dimensiones de imágenes (png, jpg, bmp, tiff, webp, etc.) vía Pillow."""

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in IMAGE_EXTENSIONS

    def detect(self, path: Path, dpi_override: Optional[float] = None) -> DetectionResult:
        if Image is None:
            raise MissingDependencyError(
                "Pillow no está instalado. Ejecuta: pip install pillow"
            )
        try:
            with Image.open(path) as img:
                width_px, height_px = img.size
                dpi_is_estimated = dpi_override is not None

                if dpi_override is not None:
                    dpi_x = dpi_y = dpi_override
                else:
                    dpi_info = img.info.get("dpi")
                    if dpi_info:
                        dpi_x, dpi_y = dpi_info
                    else:
                        dpi_x = dpi_y = DEFAULT_DPI
                        dpi_is_estimated = True
        except (OSError, ValueError) as exc:
            raise CorruptFileError(f"No se pudo leer la imagen: {path}") from exc

        width_in = UnitConverter.px_to_in(width_px, dpi_x)
        height_in = UnitConverter.px_to_in(height_px, dpi_y)

        page = PageDimensions(
            page_number=1,
            width_px=width_px,
            height_px=height_px,
            width_in=width_in,
            height_in=height_in,
            width_cm=UnitConverter.in_to_cm(width_in),
            height_cm=UnitConverter.in_to_cm(height_in),
            dpi_x=dpi_x,
            dpi_y=dpi_y,
            dpi_is_estimated=dpi_is_estimated,
        )
        return DetectionResult(file_path=str(path), file_type="image", pages=[page])


class PDFDimensionDetector(DimensionDetector):
    """Detecta dimensiones de cada página de un PDF vía pypdf (lee el MediaBox).

    El tamaño en puntos/in/cm es exacto (viene del propio archivo). El
    tamaño en píxeles depende del DPI elegido para una futura
    rasterización y por eso siempre se marca como estimado.
    """

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in PDF_EXTENSIONS

    def detect(self, path: Path, dpi_override: Optional[float] = None) -> DetectionResult:
        if PdfReader is None:
            raise MissingDependencyError(
                "pypdf no está instalado. Ejecuta: pip install pypdf"
            )
        dpi = dpi_override or DEFAULT_DPI
        try:
            reader = PdfReader(str(path))
        except Exception as exc:  # pypdf puede lanzar distintos tipos de error
            raise CorruptFileError(f"No se pudo leer el PDF: {path}") from exc

        pages: List[PageDimensions] = []
        for i, page in enumerate(reader.pages, start=1):
            box = page.mediabox
            width_pt = float(box.width)
            height_pt = float(box.height)

            width_in = UnitConverter.pt_to_in(width_pt)
            height_in = UnitConverter.pt_to_in(height_pt)

            pages.append(
                PageDimensions(
                    page_number=i,
                    width_px=UnitConverter.in_to_px(width_in, dpi),
                    height_px=UnitConverter.in_to_px(height_in, dpi),
                    width_in=width_in,
                    height_in=height_in,
                    width_cm=UnitConverter.in_to_cm(width_in),
                    height_cm=UnitConverter.in_to_cm(height_in),
                    dpi_x=dpi,
                    dpi_y=dpi,
                    dpi_is_estimated=True,
                )
            )
        return DetectionResult(file_path=str(path), file_type="pdf", pages=pages)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class DetectorFactory:
    """Elige el detector adecuado según la extensión del archivo."""

    def __init__(self) -> None:
        # Para soportar un nuevo formato: agregar la clase aquí.
        self._detectors: List[DimensionDetector] = [
            ImageDimensionDetector(),
            PDFDimensionDetector(),
        ]

    def get_detector(self, path: Path) -> DimensionDetector:
        for detector in self._detectors:
            if detector.supports(path):
                return detector
        soportados = sorted(IMAGE_EXTENSIONS | PDF_EXTENSIONS)
        raise UnsupportedFormatError(
            f"Formato no soportado: '{path.suffix}'. Formatos válidos: {soportados}"
        )


# ---------------------------------------------------------------------------
# Fachada de alto nivel
# ---------------------------------------------------------------------------

class DimensionAnalyzer:
    """Punto de entrada de alto nivel. Es lo que se usa al importar el módulo."""

    def __init__(self, factory: Optional[DetectorFactory] = None) -> None:
        self._factory = factory or DetectorFactory()

    def analyze(self, file_path: str, dpi_override: Optional[float] = None) -> DetectionResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"No existe el archivo: {file_path}")
        detector = self._factory.get_detector(path)
        return detector.detect(path, dpi_override=dpi_override)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _format_table(result: DetectionResult) -> str:
    lines = [f"Archivo: {result.file_path}  ({result.file_type})"]
    header = f"{'Pág.':<6}{'px':<18}{'in':<16}{'cm':<16}{'DPI':<8}"
    lines.append(header)
    lines.append("-" * len(header))
    for p in result.pages:
        px = f"{p.width_px:.0f} x {p.height_px:.0f}"
        inch = f"{p.width_in:.2f} x {p.height_in:.2f}"
        cm = f"{p.width_cm:.2f} x {p.height_cm:.2f}"
        dpi = f"{p.dpi_x:.0f}{'*' if p.dpi_is_estimated else ''}"
        lines.append(f"{p.page_number:<6}{px:<18}{inch:<16}{cm:<16}{dpi:<8}")
    if any(p.dpi_is_estimated for p in result.pages):
        lines.append("* DPI estimado/asumido (no venía como metadata exacta en el archivo).")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detecta las dimensiones (px, in, cm) de PDFs e imágenes."
    )
    parser.add_argument("archivos", nargs="+", help="Rutas de archivos a analizar")
    parser.add_argument(
        "--dpi",
        type=float,
        default=None,
        help=f"DPI a usar en las conversiones (por defecto: metadata del archivo o {DEFAULT_DPI:.0f})",
    )
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")
    args = parser.parse_args()

    analyzer = DimensionAnalyzer()
    results: List[DetectionResult] = []
    exit_code = 0

    for file_path in args.archivos:
        try:
            result = analyzer.analyze(file_path, dpi_override=args.dpi)
            results.append(result)
            if not args.json:
                print(_format_table(result))
                print()
        except (DimensionDetectorError, FileNotFoundError) as exc:
            print(f"[ERROR] {file_path}: {exc}", file=sys.stderr)
            exit_code = 1

    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
