"""
Mediascout - Media Cover Manager
A companion app for minidlna to manage movie cover artwork.
"""

import os
import re
import argparse
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from datetime import datetime

from flask import Flask, render_template, request, jsonify, redirect, url_for
from PIL import Image
import requests
from io import BytesIO

# ============================================================================
# Configuration
# ============================================================================

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

# ============================================================================
# Filename Parser
# ============================================================================

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

# ============================================================================
# File Scanner
# ============================================================================

class FileScanner:
    """Scan directories for media files and check for existing covers."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def scan_directory(self, directory: str) -> Dict:
        """
        Scan a directory for media files without covers.
        
        Returns:
            Dict with directory info and list of movies
        """
        movies = []
        total_files = 0
        last_scan = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    # Check if file has valid extension
                    ext = Path(file).suffix[1:].lower()  # Remove the dot
                    if ext not in self.config.file_extensions:
                        continue
                    
                    total_files += 1
                    filepath = os.path.join(root, file)
                    
                    # Check if cover exists
                    cover_path = str(Path(filepath).with_suffix('.jpg'))
                    if os.path.exists(cover_path):
                        continue  # Skip files with existing covers
                    
                    # Parse filename
                    title, year = FilenameParser.parse(file)
                    
                    movies.append({
                        'filepath': filepath,
                        'filename': file,
                        'title': title,
                        'year': year,
                        'cover_path': cover_path
                    })
            
            return {
                'directory': directory,
                'total_files': total_files,
                'missing_covers': len(movies),
                'movies': movies,
                'last_scan': last_scan,
                'status': 'ok'
            }
        
        except Exception as e:
            return {
                'directory': directory,
                'error': str(e),
                'status': 'error'
            }
    
    def get_directory_stats(self, directory: str) -> Dict:
        """Get statistics for a directory without full scan."""
        total_files = 0
        missing_covers = 0
        last_modified = None
        
        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    ext = Path(file).suffix[1:].lower()
                    if ext not in self.config.file_extensions:
                        continue
                    
                    total_files += 1
                    filepath = os.path.join(root, file)
                    cover_path = str(Path(filepath).with_suffix('.jpg'))
                    
                    if not os.path.exists(cover_path):
                        missing_covers += 1
                    
                    # Track most recent modification
                    mtime = os.path.getmtime(filepath)
                    if last_modified is None or mtime > last_modified:
                        last_modified = mtime
            
            # Detect if directory is local or network mount
            location_type = self._detect_location_type(directory)
            
            # Check if directory is writable
            is_writable = os.access(directory, os.W_OK)
            
            return {
                'directory': directory,
                'total_files': total_files,
                'missing_covers': missing_covers,
                'last_modified': datetime.fromtimestamp(last_modified).strftime('%Y-%m-%d %H:%M') if last_modified else None,
                'status': 'ok' if missing_covers == 0 else 'action_needed',
                'location_type': location_type,
                'is_writable': is_writable
            }
        
        except Exception as e:
            return {
                'directory': directory,
                'error': str(e),
                'status': 'error',
                'location_type': 'unknown',
                'is_writable': False
            }
    
    def _detect_location_type(self, directory: str) -> str:
        """Detect if directory is local or network mount."""
        import platform
        
        system = platform.system()
        
        if system == 'Windows':
            # Check if it's a network drive (UNC path or mapped network drive)
            if directory.startswith('\\\\'):
                return 'network'
            # Check if drive letter is a network drive
            try:
                import subprocess
                drive = directory[:2]  # e.g., 'C:'
                result = subprocess.run(
                    ['net', 'use'], 
                    capture_output=True, 
                    text=True,
                    encoding='utf-8',
                    errors='ignore'  # Ignore encoding errors
                )
                if drive.upper() in result.stdout.upper():
                    return 'network'
            except Exception:
                # If detection fails, assume local
                pass
            return 'local'
        
        elif system in ('Linux', 'Darwin'):  # Linux or macOS
            # Read mount information
            try:
                with open('/proc/mounts' if system == 'Linux' else '/etc/mtab', 'r') as f:
                    mounts = f.read()
                
                # Common network filesystem types
                network_fs = ['nfs', 'cifs', 'smb', 'smbfs', 'fuse.sshfs', 'ftp', 'davfs']
                
                for line in mounts.split('\n'):
                    parts = line.split()
                    if len(parts) >= 3:
                        mount_point = parts[1]
                        fs_type = parts[2]
                        
                        # Check if directory is under this mount point
                        if directory.startswith(mount_point):
                            if fs_type in network_fs:
                                return 'network'
                
                return 'local'
            except Exception:
                return 'local'
        
        return 'local'

# ============================================================================
# TMDB Client
# ============================================================================

class TMDBClient:
    """Client for The Movie Database API."""
    
    def __init__(self, api_key: str, base_url: str, image_base: str, locale: str = "en-US"):
        self.api_key = api_key
        self.base_url = base_url
        self.image_base = image_base
        self.locale = locale
    
    def search_movie(self, title: str, year: Optional[int] = None) -> Dict:
        """
        Search for a movie by title and optional year.
        
        Returns:
            Dict with 'success', 'movie' (best match), 'posters', or 'error'
        """
        try:
            # Search for movie
            params = {
                'api_key': self.api_key,
                'query': title,
                'language': self.locale
            }
            if year:
                params['year'] = year
            
            response = requests.get(
                f"{self.base_url}/search/movie",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get('results'):
                return {
                    'success': False,
                    'error': 'No results found'
                }
            
            # Get most popular result
            movie = max(data['results'], key=lambda x: x.get('popularity', 0))
            
            # Get posters for this movie
            movie_id = movie['id']
            posters = self._get_movie_posters(movie_id)
            
            return {
                'success': True,
                'movie': {
                    'id': movie['id'],
                    'title': movie['title'],
                    'year': movie.get('release_date', '')[:4] if movie.get('release_date') else None,
                    'overview': movie.get('overview', ''),
                    'popularity': movie.get('popularity', 0)
                },
                'posters': posters
            }
        
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'TMDB API error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def _get_movie_posters(self, movie_id: int) -> List[Dict]:
        """Get available posters for a movie."""
        try:
            response = requests.get(
                f"{self.base_url}/movie/{movie_id}/images",
                params={'api_key': self.api_key},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            posters = []
            for poster in data.get('posters', [])[:6]:  # Limit to 6 posters
                posters.append({
                    'path': poster['file_path'],
                    'url_thumb': f"{self.image_base}/w185{poster['file_path']}",
                    'url_full': f"{self.image_base}/original{poster['file_path']}"
                })
            
            return posters
        
        except Exception:
            return []

# ============================================================================
# Image Processor
# ============================================================================

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

# ============================================================================
# Flask Application
# ============================================================================

app = Flask(__name__)
config = Config()
scanner = None
tmdb_client = None

@app.route('/')
def index():
    """Main page - directory listing."""
    directories = []
    for directory in config.media_directories:
        stats = scanner.get_directory_stats(directory)
        directories.append(stats)
    
    # Get success message from session if present
    success_msg = request.args.get('success')
    
    return render_template('index.html', 
                         directories=directories,
                         success_message=success_msg)

@app.route('/scan/<path:directory>')
def scan_directory(directory):
    """Scan directory and show movies without covers."""
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
    
    # Load configuration
    config.load_from_env()
    config.load_from_args(args)
    
    # Validate configuration
    errors = config.validate()
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        print("\nPlease provide configuration via environment variables or command line arguments.")
        print("\nEnvironment variables:")
        print("  MEDIA_DIRECTORIES=/path1,/path2")
        print("  FILE_EXTENSIONS=mkv,mp4,avi")
        print("  TMDB_API_KEY=your_key")
        print("  TMDB_LOCALE=en-US (or fr-FR, de-DE, etc.)")
        print("\nCommand line:")
        print("  --directories /path1,/path2")
        print("  --extensions mkv,mp4,avi")
        print("  --tmdb-key your_key")
        print("  --tmdb-locale en-US")
        return
    
    # Initialize global instances
    global scanner, tmdb_client
    scanner = FileScanner(config)
    tmdb_client = TMDBClient(config.tmdb_api_key, config.tmdb_base_url, config.tmdb_image_base, config.tmdb_locale)
    
    # Run Flask app
    print(f"\n✓ Mediascout starting on http://{args.host}:{args.port}")
    print(f"✓ Monitoring {len(config.media_directories)} director{'y' if len(config.media_directories) == 1 else 'ies'}")
    print(f"✓ File extensions: {', '.join(config.file_extensions)}")
    print(f"✓ TMDB Locale: {config.tmdb_locale}\n")
    
    app.run(host=args.host, port=args.port, debug=True)

if __name__ == '__main__':
    main()
