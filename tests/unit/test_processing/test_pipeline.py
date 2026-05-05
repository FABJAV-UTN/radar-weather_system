"""
Tests unitarios del Subsistema 1: procesamiento de radar.

Diseñados para correr SIN datotifs reales y SIN la DB.
Se crean imágenes sintéticas en memoria para validar cada paso del pipeline.
"""

import numpy as np
import pytest
from PIL import Image
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.processing.algorithms.dbz_colors import classify_pixel, classify_array, DBZ_COLOR_MAP
from app.processing.algorithms.cropper import crop_margins, detect_bank_image_type, CROP_MARGINS
from app.processing.algorithms.cleaner import clean_image, WATERMARK_REGION
from app.processing.algorithms.hole_filler import fill_gaps
from app.processing.algorithms.timestamp_extractor import format_filename, _parse_timestamp
from app.processing.algorithms.georeferencer import GeoReferenceLoader, _placeholder_geo_reference


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _make_gif(width: int = 400, height: int = 300) -> Image.Image:
    """GIF sintético con márgenes negros y área interior de color."""
    img = Image.new("RGB", (width, height), color=(0, 0, 0))
    return img


def _make_storm_image(width: int = 300, height: int = 250) -> Image.Image:
    """
    Imagen sintética con una 'tormenta' en el centro (color dBZ 60: #FF5F00).
    El resto es negro (fondo).
    """
    img = Image.new("RGB", (width, height), color=(0, 0, 0))
    pixels = img.load()
    # Tormenta en el centro (50x50 píxeles)
    storm_color = (0xFF, 0x5F, 0x00)  # dBZ=60
    for y in range(100, 150):
        for x in range(100, 150):
            pixels[x, y] = storm_color
    return img


# ─── Tests: clasificación DBZ ─────────────────────────────────────────────────

class TestDBZClassification:
    def test_exact_match_dbz_60(self):
        result = classify_pixel(0xFF, 0x5F, 0x00)
        assert result == 60

    def test_exact_match_dbz_10(self):
        result = classify_pixel(0x42, 0x3F, 0x8C)
        assert result == 10

    def test_near_match_within_threshold(self):
        # Color ligeramente distinto (simula compresión GIF)
        result = classify_pixel(0xFF, 0x60, 0x02)  # dBZ=60 con leve variación
        assert result == 60

    def test_black_background_not_classified(self):
        result = classify_pixel(0, 0, 0)
        assert result is None

    def test_white_not_classified(self):
        result = classify_pixel(255, 255, 255)
        assert result is None

    def test_classify_array_vectorized(self):
        """Verifica que classify_array y classify_pixel den resultados consistentes."""
        # Array con un pixel de cada color DBZ
        colors = list(DBZ_COLOR_MAP.values())
        dbz_values = list(DBZ_COLOR_MAP.keys())

        arr = np.array(colors, dtype=np.uint8).reshape(1, len(colors), 3)
        result = classify_array(arr)  # (1, N)

        for i, expected_dbz in enumerate(dbz_values):
            assert result[0, i] == expected_dbz, \
                f"dBZ esperado {expected_dbz}, obtenido {result[0, i]}"

    def test_classify_array_black_pixels_are_zero(self):
        arr = np.zeros((10, 10, 3), dtype=np.uint8)
        result = classify_array(arr)
        assert np.all(result == 0)


# ─── Tests: recorte de márgenes ───────────────────────────────────────────────

class TestCropper:
    def test_crop_reduces_size_correctly(self):
        img = _make_gif(width=400, height=300)
        cropped = crop_margins(img)
        expected_w = 400 - CROP_MARGINS["izq"] - CROP_MARGINS["derecha"]
        expected_h = 300 - CROP_MARGINS["arriba"] - CROP_MARGINS["abajo"]
        assert cropped.size == (expected_w, expected_h)

    def test_crop_raises_on_too_small_image(self):
        img = _make_gif(width=100, height=100)
        with pytest.raises(ValueError):
            crop_margins(img)

    def test_detect_bank_type_large(self):
        img = Image.new("RGB", (800, 600))
        assert detect_bank_image_type(img) == 3

    def test_detect_bank_type_small(self):
        img = Image.new("RGB", (400, 300))
        assert detect_bank_image_type(img) == 2

    def test_detect_bank_type_exactly_799(self):
        img = Image.new("RGB", (799, 500))
        assert detect_bank_image_type(img) == 3

    def test_detect_bank_type_798(self):
        img = Image.new("RGB", (798, 500))
        assert detect_bank_image_type(img) == 2


# ─── Tests: limpieza ──────────────────────────────────────────────────────────

class TestCleaner:
    def test_clean_removes_background(self):
        img = _make_storm_image()
        clean_rgb, gap_mask = clean_image(img)

        # Los píxeles negros (fondo) deben quedar en 0
        h, w, _ = clean_rgb.shape
        for y in range(0, 50):  # esquina superior, sin tormenta
            for x in range(0, 50):
                assert tuple(clean_rgb[y, x]) == (0, 0, 0), \
                    f"Píxel de fondo no limpiado en ({x},{y})"

    def test_clean_preserves_storm(self):
        img = _make_storm_image()
        clean_rgb, _ = clean_image(img)

        # Los píxeles de tormenta deben estar presentes
        storm_pixels = clean_rgb[100:150, 100:150]
        assert np.any(storm_pixels > 0), "Los píxeles de tormenta fueron borrados"

    def test_gap_mask_is_boolean(self):
        img = _make_storm_image()
        _, gap_mask = clean_image(img)
        assert gap_mask.dtype == bool

    def test_gap_mask_shape_matches_image(self):
        img = _make_storm_image(width=200, height=150)
        _, gap_mask = clean_image(img)
        assert gap_mask.shape == (150, 200)


# ─── Tests: relleno de huecos ─────────────────────────────────────────────────

class TestHoleFiller:
    def _make_storm_with_gap(self):
        """Crea array con tormenta cuadrada y un hueco en el centro."""
        rgb = np.zeros((100, 100, 3), dtype=np.uint8)
        storm_color = np.array([0xFF, 0x5F, 0x00], dtype=np.uint8)

        # Tormenta: cuadrado 40x40
        rgb[30:70, 30:70] = storm_color

        # Hueco en el centro: 10x10 (simula marca de agua)
        gap_region = np.zeros((100, 100), dtype=bool)
        gap_region[45:55, 45:55] = True
        rgb[gap_region] = 0  # "borrar" la tormenta ahí

        return rgb, gap_region

    def test_fill_gap_inside_storm(self):
        rgb, gap_mask = self._make_storm_with_gap()
        result = fill_gaps(rgb, gap_mask)

        # Los píxeles del hueco deben haber sido rellenados
        gap_pixels = result[45:55, 45:55]
        assert np.any(gap_pixels > 0), "El hueco no fue rellenado"

    def test_no_expansion_outside_storm(self):
        rgb, gap_mask = self._make_storm_with_gap()
        result = fill_gaps(rgb, gap_mask)

        # Fuera del cuadrado de tormenta (margen), debe seguir en negro
        assert np.all(result[0:20, 0:20] == 0), \
            "Se expandió tormenta fuera del área original"

    def test_no_gap_mask_leaves_image_unchanged(self):
        rgb = np.zeros((50, 50, 3), dtype=np.uint8)
        rgb[20:30, 20:30] = [255, 100, 0]  # pequeña tormenta

        gap_mask = np.zeros((50, 50), dtype=bool)  # sin huecos

        result = fill_gaps(rgb, gap_mask, fill_general_holes=False)
        np.testing.assert_array_equal(result, rgb)


# ─── Tests: timestamp ─────────────────────────────────────────────────────────

class TestTimestamp:
    def test_format_filename(self):
        dt = datetime(2026, 5, 4, 20, 30, 0)
        name = format_filename("san_rafael", dt)
        assert name == "san_rafael_040526_203000"

    def test_parse_slash_format(self):
        result = _parse_timestamp("04/05/2026 20:30")
        assert result is not None
        assert result.day == 4
        assert result.month == 5
        assert result.year == 2026
        assert result.hour == 20

    def test_parse_dash_format(self):
        result = _parse_timestamp("2026-05-04 20:30")
        assert result is not None
        assert result.year == 2026

    def test_parse_garbage_returns_none(self):
        result = _parse_timestamp("XYZ NO DATE HERE")
        assert result is None


# ─── Tests: GeoReferenceLoader ────────────────────────────────────────────────

class TestGeoReferenceLoader:
    def test_load_all_uses_placeholder_when_no_files(self, tmp_path: Path):
        loader = GeoReferenceLoader(datotif_dir=tmp_path)
        loader.load_all()  # tmp_path está vacío → placeholders

        for datotif_id in [1, 2, 3]:
            geo = loader.get(datotif_id)
            assert geo.datotif_id == datotif_id
            assert geo.crs is not None
            assert geo.transform is not None

    def test_get_raises_if_not_loaded(self, tmp_path: Path):
        loader = GeoReferenceLoader(datotif_dir=tmp_path)
        # Sin llamar load_all()
        with pytest.raises(KeyError):
            loader.get(1)

    def test_placeholder_has_valid_transform(self):
        geo = _placeholder_geo_reference(1)
        assert geo.transform.a != 0  # pixel size X no es cero
        assert geo.transform.e != 0  # pixel size Y no es cero


# ─── Test de integración del pipeline ─────────────────────────────────────────

class TestRadarPipeline:
    """
    Test de integración end-to-end del pipeline completo.
    Sin DB, sin datotifs reales, usando mocks para OCR.
    """

    def test_pipeline_dacc_api_happy_path(self, tmp_path: Path):
        from app.processing.services.radar_pipeline import RadarPipeline

        # Preparar imagen GIF sintética
        img_path = tmp_path / "latest.gif"
        # Crear imagen con dimensiones suficientes para el recorte
        img = Image.new("RGB", (500, 400), color=(0, 0, 0))
        # Agregar algo de "tormenta" en el área post-recorte
        pixels = img.load()
        storm_color = (0xFF, 0x5F, 0x00)
        for y in range(100, 150):
            for x in range(100, 150):
                pixels[x, y] = storm_color
        img.save(img_path)

        # Cargar geo con placeholders
        loader = GeoReferenceLoader(datotif_dir=tmp_path)
        loader.load_all()

        # Patch del OCR para que no falle (no tenemos Tesseract en CI)
        fixed_ts = datetime(2026, 5, 4, 20, 30, 0)
        with patch(
            "app.processing.services.radar_pipeline.extract_timestamp",
            return_value=fixed_ts
        ):
            pipeline = RadarPipeline(geo_loader=loader, output_dir=tmp_path / "out")
            result = pipeline.process(img_path, source_type="dacc_api")

        assert result is not None
        assert result.exists()
        assert result.suffix == ".tif"
        assert "san_rafael" in result.name

    def test_pipeline_returns_none_when_ocr_fails_no_fallback(self, tmp_path: Path):
        from app.processing.services.radar_pipeline import RadarPipeline

        img_path = tmp_path / "radar.gif"
        Image.new("RGB", (500, 400)).save(img_path)

        loader = GeoReferenceLoader(datotif_dir=tmp_path)
        loader.load_all()

        with patch(
            "app.processing.services.radar_pipeline.extract_timestamp",
            return_value=None
        ):
            pipeline = RadarPipeline(geo_loader=loader, output_dir=tmp_path / "out")
            result = pipeline.process(img_path, source_type="dacc_api", fallback_timestamp=None)

        assert result is None