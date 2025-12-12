"""
Filename parser module.
"""

import re
from pathlib import Path
from typing import Tuple, Optional

class FilenameParser:
    """Parse movie titles and years from filenames."""

    # Common video quality/source indicators to remove
    NOISE_PATTERNS = [
        r'\b(1080p|720p|480p|2160p|4k)\b',
        r'\b(bluray|blu-ray|brrip|bdrip|dvdrip|webrip|web-dl|hdtv)\b',
        r'\b(x264|x265|h264|h265|hevc|xvid|divx)\b',
        r'\b(aac|ac3|dts|mp3)\b',
        r'\b(proper|repack|unrated|extended|directors.cut)\b',
    ]

    @staticmethod
    def parse(filename: str) -> Tuple[str, Optional[int]]:
        """
        Extract movie title and year from filename.

        Returns:
            (title, year) tuple where year may be None
        """
        # Remove file extension
        name = Path(filename).stem

        # Replace dots and underscores with spaces
        name = name.replace('.', ' ').replace('_', ' ')

        # Remove noise patterns
        for pattern in FilenameParser.NOISE_PATTERNS:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)

        # Look for year (1900-2099) that's isolated
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', name)
        year = None
        title = name

        if year_match:
            potential_year = int(year_match.group(1))
            year_pos = year_match.start()

            # Check if this might be part of the title (e.g., "2012", "Blade Runner 2049")
            # Simple heuristic: if year is at the very start or preceded only by "the", it's likely the title
            prefix = name[:year_pos].strip().lower()
            if prefix in ['', 'the']:
                # Year is likely part of title (e.g., "2012" or "The 2012")
                title = name.strip()
            else:
                # Year is likely a release year
                year = potential_year
                title = name[:year_pos].strip()

        # Clean up extra spaces
        title = ' '.join(title.split())

        return title, year
