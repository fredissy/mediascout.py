"""
Mediascout - Media Cover Manager
A companion app for minidlna to manage movie cover artwork.
"""

import os
import base64
import argparse
import sys

from flask import Flask, render_template, request, jsonify, redirect, url_for

from src.config import Config
from src.tmdb import TMDBClient
from src.image import ImageProcessor
from src.scanner import FileScanner, DirectoryStatsCache

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


@app.template_filter('b64encode')
def b64encode_filter(s):
    return base64.urlsafe_b64encode(s.encode()).decode()

@app.route('/')
def index():
    """Main page - directory listing."""
    directories = []
    for directory in config.media_directories:
        stats = stats_cache.get(directory, ttl_seconds=300)  # 5 min TTL
        directories.append(stats)
    
    # Get success message from session if present
    success_msg = request.args.get('success')
    
    return render_template('index.html',
                           directories=directories,
                           success_message=success_msg)

@app.route('/scan/<path:directory>')
def scan_directory(directory):
    """Scan directory and show movies without covers."""
    # Try to decode base64 if needed
    try:
        decoded_dir = base64.urlsafe_b64decode(directory).decode('utf-8')
        if decoded_dir in config.media_directories:
            directory = decoded_dir
    except Exception:
        pass
    # Validate directory is in config
    if directory not in config.media_directories:
        return "Directory not allowed", 403

    scan_result = scanner.scan_directory(directory)
    
    if scan_result['status'] == 'error':
        return render_template('error.html', error=scan_result['error'])
    
    return render_template('scan.html', result=scan_result)

@app.route('/api/search-movie', methods=['POST'])
def search_movie():
    """API endpoint to search TMDB for a movie."""
    data = request.json
    title = data.get('title')
    year = data.get('year')
    
    if not title:
        return jsonify({'success': False, 'error': 'No title provided'})
    
    result = tmdb_client.search_movie(title, year)
    return jsonify(result)

@app.route('/api/save-covers', methods=['POST'])
def save_covers():
    """API endpoint to download and save selected covers."""
    data = request.json
    covers = data.get('covers', [])
    
    results = {
        'success': 0,
        'failed': 0,
        'errors': []
    }
    
    for cover_info in covers:
        result = ImageProcessor.download_and_save(
            cover_info['url'],
            cover_info['path']
        )
        
        if result['success']:
            results['success'] += 1
        else:
            results['failed'] += 1
            results['errors'].append({
                'file': cover_info['filename'],
                'error': result['error']
            })
    
    return jsonify(results)

# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Mediascout - Media Cover Manager')
    parser.add_argument('--directories', help='Comma-separated list of media directories')
    parser.add_argument('--extensions', help='Comma-separated list of file extensions')
    parser.add_argument('--tmdb-key', help='TMDB API key')
    parser.add_argument('--tmdb-locale', help='TMDB locale for movie info (e.g., en-US, fr-FR, de-DE)', default='en-US')
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
        print("\nCommand line:")
        print(" --directories /path1,/path2")
        print(" --extensions mkv,mp4,avi")
        print(" --tmdb-key your_key")
        print(" --tmdb-locale en-US")
        return

    # Re-initialize TMDBClient because it stores strings (api_key) internally
    # that might have changed if command line args were used.
    global tmdb_client
    tmdb_client = TMDBClient(
        config.tmdb_api_key,
        config.tmdb_base_url,
        config.tmdb_image_base,
        config.tmdb_locale
    )

    # Run Flask app
    print(f"\n✓ Mediascout starting on http://{args.host}:{args.port}")
    print(f"✓ Monitoring {len(config.media_directories)} director{'y' if len(config.media_directories) == 1 else 'ies'}")
    print(f"✓ File extensions: {', '.join(config.file_extensions)}")
    print(f"✓ TMDB Locale: {config.tmdb_locale}\n")
    
    app.run(host=args.host, port=args.port, debug=True)

if __name__ == '__main__':
    main()
