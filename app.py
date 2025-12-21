"""
Mediascout - Media Cover Manager
A companion app for minidlna to manage movie cover artwork.
"""

import argparse
import sys

from flask import Flask

from src.config import Config
from src.tmdb import TMDBClient
from src.scanner import FileScanner, DirectoryStatsCache
from src.auth import setup_auth
from src.minidlna import MinidlnaClient
from src.portainer import PortainerClient
from src.routes import bp as main_bp

# ============================================================================
# Flask Application
# ============================================================================

app = Flask(__name__)
config = Config()

# 1. Load Environment Configuration immediately (Required for Gunicorn)
config.load_from_env()

# 2. Check for critical errors (Optional: Logs to Gunicorn stderr)
validation_errors = config.validate()
if validation_errors:
    # We print to stderr so it shows up in Docker logs
    print("WARNING: Configuration issues detected during startup:", file=sys.stderr)
    for err in validation_errors:
        print(f" - {err}", file=sys.stderr)

# 3. Initialize global instances immediately
# FileScanner holds a reference to config, so it will see updates automatically
scanner = FileScanner(config)

# TMDBClient copies values, so it is initialized with currently loaded env vars
tmdb_client = TMDBClient(
    config.tmdb_api_key,
    config.tmdb_base_url,
    config.tmdb_image_base,
    config.tmdb_locale
)

# 4. Setup authentication
ldap_auth = setup_auth(app, config)

# --------------------------------------------------------------------------
# Background cache of directory stats
# --------------------------------------------------------------------------
# Calculate max workers based on media directories, max 8, min 1
max_workers = max(1, min(8, len(config.media_directories) or 1))
stats_cache = DirectoryStatsCache(scanner, max_workers=max_workers)

# Optional: pre-warm cache at startup (runs in background; first page load stays fast)
for d in config.media_directories:
    try:
        stats_cache.get(d, ttl_seconds=0)
    except Exception:
        pass

# --------------------------------------------------------------------------
# Integration Clients
# --------------------------------------------------------------------------
minidlna_client = MinidlnaClient(config.minidlna_url)
portainer_client = PortainerClient(config.portainer_webhook_url)

# Attach services to app instance for access in Blueprints
app.config.from_object(config)

app.ms_config = config
app.scanner = scanner
app.tmdb_client = tmdb_client
app.ldap_auth = ldap_auth
app.stats_cache = stats_cache
app.minidlna_client = minidlna_client
app.portainer_client = portainer_client

# Register Blueprint
app.register_blueprint(main_bp)

# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Mediascout - Media Cover Manager')
    parser.add_argument('--directories', help='Comma-separated list of media directories')
    parser.add_argument('--extensions', help='Comma-separated list of file extensions')
    parser.add_argument('--tmdb-key', help='TMDB API key')
    parser.add_argument('--tmdb-locale', help='TMDB locale for movie info (e.g., en-US, fr-FR, de-DE)', default='en-US')
    
    # Authentication arguments
    parser.add_argument('--auth-enabled', action='store_true', help='Enable LDAP authentication')
    parser.add_argument('--ldap-server', help='LDAP server hostname or IP')
    parser.add_argument('--ldap-port', type=int, help='LDAP server port (default: 389)')
    parser.add_argument('--ldap-use-ssl', action='store_true', help='Use LDAPS (SSL/TLS)')
    parser.add_argument('--ldap-base-dn', help='LDAP base DN (e.g., dc=example,dc=com)')
    parser.add_argument('--session-secret', help='Secret key for session encryption')
    
    # Minidlna integration arguments
    parser.add_argument('--portainer-webhook-url', help='Portainer webhook URL to trigger Minidlna rescan')
    parser.add_argument('--minidlna-url', help='Minidlna status URL')

    parser.add_argument('--port', type=int, default=8000, help='Port to run on (default: 8000)')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    
    args = parser.parse_args()

    ## config.load_from_env() has already run at module level :
    config.load_from_args(args)

    # Validate configuration
    errors = config.validate()
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f" - {error}")
        print("\nPlease provide configuration via environment variables or command line arguments.")
        print("\nEnvironment variables:")
        print(" MEDIA_DIRECTORIES=/path1,/path2")
        print(" FILE_EXTENSIONS=mkv,mp4,avi")
        print(" TMDB_API_KEY=your_key")
        print(" TMDB_LOCALE=en-US (or fr-FR, de-DE, etc.)")
        print("\nAuthentication (optional):")
        print(" AUTH_ENABLED=true")
        print(" LDAP_SERVER=ldap.example.com")
        print(" LDAP_BASE_DN=dc=example,dc=com")
        print(" SESSION_SECRET=your_secret")
        print("\nCommand line:")
        print(" --directories /path1,/path2")
        print(" --extensions mkv,mp4,avi")
        print(" --tmdb-key your_key")
        print(" --tmdb-locale en-US")
        print(" --auth-enabled --ldap-server ldap.example.com --ldap-base-dn dc=example,dc=com")
        return

    # Re-initialize TMDBClient and auth because config might have changed
    global tmdb_client, ldap_auth, minidlna_client, portainer_client
    tmdb_client = TMDBClient(
        config.tmdb_api_key,
        config.tmdb_base_url,
        config.tmdb_image_base,
        config.tmdb_locale
    )

    minidlna_client = MinidlnaClient(config.minidlna_url)
    portainer_client = PortainerClient(config.portainer_webhook_url)
    
    ldap_auth = setup_auth(app, config)

    # Update app instances
    app.ms_config = config
    app.tmdb_client = tmdb_client
    app.minidlna_client = minidlna_client
    app.portainer_client = portainer_client
    app.ldap_auth = ldap_auth
    app.scanner = scanner
    app.stats_cache = stats_cache

    # Run Flask app
    print(f"\n✓ Mediascout starting on http://{args.host}:{args.port}")
    print(f"✓ Monitoring {len(config.media_directories)} director{'y' if len(config.media_directories) == 1 else 'ies'}")
    print(f"✓ File extensions: {', '.join(config.file_extensions)}")
    print(f"✓ TMDB Locale: {config.tmdb_locale}\n")
    print(f"✓ MiniDLNA url: {config.minidlna_url}\n")
    
    app.run(host=args.host, port=args.port, debug=True)

if __name__ == '__main__':
    main()
