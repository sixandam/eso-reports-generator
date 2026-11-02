"""
Generates multi-resolution Windows .ico file from assets/logo.png (or assets/ldhvfd_logo.png).
Produces assets/app_icon.ico containing 16, 24, 32, 48, 64, 128, and 256px mipmaps.
"""

from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"
if not LOGO_PATH.exists():
    LOGO_PATH = ASSETS_DIR / "ldhvfd_logo.png"
ICO_PATH = ASSETS_DIR / "app_icon.ico"


def generate_ico():
    if not LOGO_PATH.exists():
        raise FileNotFoundError(f"Source logo not found at {LOGO_PATH}")

    img = Image.open(LOGO_PATH).convert("RGBA")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

    ICO_PATH.parent.mkdir(parents=True, exist_ok=True)
    img.save(ICO_PATH, format="ICO", sizes=sizes)
    print(f"Successfully generated {ICO_PATH} with sizes: {sizes}")

    pkg_ico = PROJECT_ROOT / "src" / "eso_reports" / "assets" / "app_icon.ico"
    if pkg_ico.parent.exists():
        img.save(pkg_ico, format="ICO", sizes=sizes)
        print(f"Synchronized package icon to {pkg_ico}")


if __name__ == "__main__":
    generate_ico()
