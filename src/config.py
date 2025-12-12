"""
Configuration module for Mediascout.
"""

import os
import re
from typing import List

class Config:
    """Application configuration from environment or command line."""

    def __init__(self):
        self.media_directories: List[str] = []
        self.file_extensions: List[str] = []
        self.tmdb_api_key: str = ""
        self.tmdb_locale: str = "en-US"
        self.tmdb_base_url = "https://api.themoviedb.org/3"
        self.tmdb_image_base = "https://image.tmdb.org/t/p"

    def load_from_env(self):
        """Load configuration from environment variables."""
        dirs = os.getenv('MEDIA_DIRECTORIES', '')
        if dirs:
            self.media_directories = [d.strip() for d in dirs.split(',')]

        exts = os.getenv('FILE_EXTENSIONS', '')
        if exts:
            self.file_extensions = [e.strip().lower() for e in exts.split(',')]

        self.tmdb_api_key = os.getenv('TMDB_API_KEY', '')

        locale = os.getenv('TMDB_LOCALE', 'en-US')
        if locale:
            self.tmdb_locale = locale.strip()

    def load_from_args(self, args):
        """Load configuration from command line arguments."""
        if args.directories:
            self.media_directories = [d.strip() for d in args.directories.split(',')]
        if args.extensions:
            self.file_extensions = [e.strip().lower() for e in args.extensions.split(',')]
        if args.tmdb_key:
            self.tmdb_api_key = args.tmdb_key
        if args.tmdb_locale:
            self.tmdb_locale = args.tmdb_locale.strip()

    def validate(self):
        """Validate that all required configuration is present."""
        errors = []
        if not self.media_directories:
            errors.append("No media directories specified")
        if not self.file_extensions:
            errors.append("No file extensions specified")
        if not self.tmdb_api_key:
            errors.append("No TMDB API key specified")

        # Validate TMDB locale format (should be like en-US, fr-FR, de-DE, etc.)
        locale_pattern = re.compile(r'^[a-z]{2}-[A-Z]{2}')

        if not locale_pattern.match(self.tmdb_locale):
            errors.append(f"Invalid TMDB locale format: '{self.tmdb_locale}'. Expected format: 'en-US', 'fr-FR', 'de-DE', etc.")

        for directory in self.media_directories:
            if not os.path.exists(directory):
                errors.append(f"Directory does not exist: {directory}")
            elif not os.path.isdir(directory):
                errors.append(f"Not a directory: {directory}")

        return errors
