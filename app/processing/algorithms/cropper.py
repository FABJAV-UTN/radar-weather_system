"""
Recorte de márgenes del GIF de radar DACC.

Las imágenes que vienen del DACC traen un marco fijo que hay que eliminar
antes de procesar. Las del banco local ya vienen recortadas.

Medidas del marco (en píxeles):
    izq:     5
    derecha: 146
    arriba:  58
    abajo:   29
"""

from PIL import Image

CROP_MARGINS: dict[str, int] = {
    "izq": 5,
    "derecha": 146,
    "arriba": 58,
    "abajo": 29,
}


def crop_margins(image: Image.Image, margins: dict[str, int] | None = None) -> Image.Image:
    """
    Recorta los márgenes del GIF del radar DACC.

    Args:
        image: Imagen PIL original (con marco).
        margins: Márgenes a recortar. Si None, usa CROP_MARGINS.

    Returns:
        Imagen PIL recortada.
    """
    m = margins or CROP_MARGINS
    w, h = image.size

    left = m["izq"]
    right = w - m["derecha"]
    top = m["arriba"]
    bottom = h - m["abajo"]

    if right <= left or bottom <= top:
        raise ValueError(
            f"Márgenes inválidos para imagen de {w}x{h}: "
            f"left={left}, right={right}, top={top}, bottom={bottom}"
        )

    return image.crop((left, top, right, bottom))


def detect_bank_image_type(image: Image.Image) -> int:
    """
    Detecta qué datotif usar para imágenes del banco local.

    Regla:
        - Si el ancho es mayor a 799px → datotif3
        - Si el ancho es menor o igual a 799px → datotif2

    Returns:
        2 o 3 (número de datotif a usar)
    """
    w, _ = image.size
    if w > 799:
        return 3
    return 2