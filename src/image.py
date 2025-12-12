"""
Image processing module.
"""

from typing import Tuple, Dict
from io import BytesIO
import requests
from PIL import Image

class ImageProcessor:
    """Download and process cover images."""

    @staticmethod
    def download_and_save(url: str, output_path: str, size: Tuple[int, int] = (160, 160)) -> Dict:
        """
        Download image from URL, resize, and save as JPEG.

        Returns:
            Dict with 'success' and optional 'error'
        """
        try:
            # Download image
            response = requests.get(url, timeout=15)
            response.raise_for_status()

            # Open image
            img = Image.open(BytesIO(response.content))

            # Convert to RGB if necessary (for PNG with transparency)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background

            # Resize to 160x160 (thumbnail maintains aspect ratio then crops)
            img.thumbnail((size[0] * 2, size[1] * 2), Image.Resampling.LANCZOS)

            # Create square image (crop to center)
            if img.size[0] != img.size[1]:
                min_dim = min(img.size)
                left = (img.size[0] - min_dim) // 2
                top = (img.size[1] - min_dim) // 2
                img = img.crop((left, top, left + min_dim, top + min_dim))

            # Final resize to exact dimensions
            img = img.resize(size, Image.Resampling.LANCZOS)

            # Save as JPEG
            img.save(output_path, 'JPEG', quality=90, optimize=True)

            return {'success': True}

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
