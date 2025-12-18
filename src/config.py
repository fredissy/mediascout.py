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
        
        # Authentication settings
        self.auth_enabled: bool = False
        self.ldap_server: str = ""
        self.ldap_port: int = 389
        self.ldap_use_ssl: bool = False
        self.ldap_base_dn: str = ""
        self.ldap_user_dn_template: str = ""
        self.ldap_search_filter: str = ""
        self.session_secret: str = ""

        # Minidlna integration
        self.portainer_webhook_url: str = ""
        self.minidlna_url: str = ""

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
        
        # Authentication environment variables
        self.auth_enabled = os.getenv('AUTH_ENABLED', 'false').lower() == 'true'
        self.ldap_server = os.getenv('LDAP_SERVER', '')
        self.ldap_port = int(os.getenv('LDAP_PORT', '389'))
        self.ldap_use_ssl = os.getenv('LDAP_USE_SSL', 'false').lower() == 'true'
        self.ldap_base_dn = os.getenv('LDAP_BASE_DN', '')
        self.ldap_user_dn_template = os.getenv('LDAP_USER_DN_TEMPLATE', '')
        self.ldap_search_filter = os.getenv('LDAP_SEARCH_FILTER', '(uid={username})')
        self.session_secret = os.getenv('SESSION_SECRET', '')
        if not self.session_secret and self.auth_enabled:
            self.session_secret = os.urandom(24).hex()

        self.portainer_webhook_url = os.getenv('PORTAINER_WEBHOOK_URL', '')
        self.minidlna_url = os.getenv('MINIDLNA_URL', '')

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
        
        # Authentication command line arguments
        if hasattr(args, 'auth_enabled') and args.auth_enabled is not None:
            self.auth_enabled = args.auth_enabled
        if hasattr(args, 'ldap_server') and args.ldap_server:
            self.ldap_server = args.ldap_server
        if hasattr(args, 'ldap_port') and args.ldap_port:
            self.ldap_port = args.ldap_port
        if hasattr(args, 'ldap_use_ssl') and args.ldap_use_ssl is not None:
            self.ldap_use_ssl = args.ldap_use_ssl
        if hasattr(args, 'ldap_base_dn') and args.ldap_base_dn:
            self.ldap_base_dn = args.ldap_base_dn
        if hasattr(args, 'session_secret') and args.session_secret:
            self.session_secret = args.session_secret

        if hasattr(args, 'portainer_webhook') and args.portainer_webhook:
            self.portainer_webhook_url = args.portainer_webhook
        if hasattr(args, 'minidlna_url') and args.minidlna_url:
            self.minidlna_url = args.minidlna_url

        if not self.ldap_user_dn_template and self.ldap_base_dn:
            self.ldap_user_dn_template = f'uid={{username}},ou=people,{self.ldap_base_dn}'

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
        locale_pattern = re.compile(r'^[a-z]{2}-[A-Z]{2}$')

        if not locale_pattern.match(self.tmdb_locale):
            errors.append(f"Invalid TMDB locale format: '{self.tmdb_locale}'. Expected format: 'en-US', 'fr-FR', 'de-DE', etc.")

        for directory in self.media_directories:
            if not os.path.exists(directory):
                errors.append(f"Directory does not exist: {directory}")
            elif not os.path.isdir(directory):
                errors.append(f"Not a directory: {directory}")
        
        # Validate authentication config if enabled
        if self.auth_enabled:
            if not self.ldap_server:
                errors.append("AUTH_ENABLED is true but LDAP_SERVER is not specified")
            if not self.ldap_base_dn:
                errors.append("AUTH_ENABLED is true but LDAP_BASE_DN is not specified")
            if not self.session_secret:
                errors.append("AUTH_ENABLED is true but SESSION_SECRET is not specified")

        return errors
