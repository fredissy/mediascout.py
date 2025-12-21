"""
Routes for the Mediascout application.
"""

import sys
import base64
from functools import wraps
from flask import (
    Blueprint, render_template, request, jsonify,
    redirect, url_for, current_app
)
from flask_login import login_user, logout_user, login_required, current_user

from src.utils import is_absolute
from src.image import ImageProcessor

# Create Blueprint
bp = Blueprint('main', __name__)

@bp.app_template_filter('b64encode')
def b64encode_filter(s):
    return base64.urlsafe_b64encode(s.encode()).decode()

def auth_decorator(f):
    """
    Decorator to protect routes with authentication.
    Uses current_app.ms_config to check if auth is enabled.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_app.ms_config.auth_enabled and not current_user.is_authenticated:
            return redirect(url_for('main.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# ============================================================================
# Authentication Routes
# ============================================================================

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler."""
    if not current_app.ms_config.auth_enabled:
        return redirect(url_for('main.index'))

    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        ldap_auth = getattr(current_app, 'ldap_auth', None)
        if ldap_auth is None:
            error = 'Authentication is not configured'
        else:
            user = ldap_auth.authenticate(username, password)
            if user:
                login_user(user)
                next_page = request.args.get('next')
                return redirect(next_page if (next_page and not is_absolute(next_page)) else url_for('main.index'))
            else:
                error = 'Invalid username or password'

    return render_template('login.html', error=error)

@bp.route('/logout')
@login_required
def logout():
    """Logout handler."""
    logout_user()
    return redirect(url_for('main.login'))

# ============================================================================
# Main Application Routes
# ============================================================================

@bp.route('/')
@auth_decorator
def index():
    """Main page - directory listing."""
    directories = []
    for directory in current_app.ms_config.media_directories:
        # Use current_app.stats_cache
        stats = current_app.stats_cache.get(directory, ttl_seconds=300)  # 5 min TTL
        directories.append(stats)

    # Check Minidlna status if URL is configured
    minidlna_status = None
    if current_app.ms_config.minidlna_url:
        # Get cached status (TTL 60s)
        minidlna_status = current_app.minidlna_client.get_status(ttl_seconds=60)

    # Get success/error message from session if present
    success_msg = request.args.get('success')
    error_msg = request.args.get('error')

    return render_template('index.html',
                           directories=directories,
                           success_message=success_msg,
                           error_message=error_msg,
                           config=current_app.ms_config,
                           minidlna_status=minidlna_status)

@bp.route('/trigger-minidlna', methods=['POST'])
@auth_decorator
def trigger_minidlna():
    """Trigger Minidlna rescan via Portainer webhook."""
    if not current_app.ms_config.portainer_webhook_url:
        return redirect(url_for('main.index'))

    try:
        current_app.portainer_client.trigger_webhook()
        return redirect(url_for('main.index', success="Minidlna rescan triggered successfully"))
    except Exception as e:
        print(f"Error triggering webhook: {e}", file=sys.stderr)
        return redirect(url_for('main.index', error=f"Error triggering rescan: {str(e)}"))

@bp.route('/scan/<path:directory>')
@auth_decorator
def scan_directory(directory):
    """Scan directory and show movies without covers."""
    # Try to decode base64 if needed
    try:
        decoded_dir = base64.urlsafe_b64decode(directory).decode('utf-8')
        if decoded_dir in current_app.ms_config.media_directories:
            directory = decoded_dir
    except Exception:
        return "Invalid directory", 403
    # Validate directory is in config
    if directory not in current_app.ms_config.media_directories:
        return "Directory not allowed", 403

    scan_result = current_app.scanner.scan_directory(directory)

    if scan_result['status'] == 'error':
        return render_template('error.html', error=scan_result['error'])

    return render_template('scan.html', result=scan_result)

@bp.route('/api/get-movie-details/<int:movie_id>', methods=['GET'])
@auth_decorator
def get_movie_details(movie_id):
    """
    API endpoint to get detailed information for a specific movie.
    Used when user selects an alternative match.
    """
    if movie_id <= 0:
        return jsonify({'success': False, 'error': 'Invalid movie ID'})

    result = current_app.tmdb_client.get_movie_details(movie_id)
    return jsonify(result)

@bp.route('/api/search-movie', methods=['POST'])
@auth_decorator
def search_movie():
    """API endpoint to search TMDB for a movie."""
    data = request.json
    title = data.get('title')
    year = data.get('year')

    if not title:
        return jsonify({'success': False, 'error': 'No title provided'})

    result = current_app.tmdb_client.search_movie(title, year)
    return jsonify(result)

@bp.route('/api/save-covers', methods=['POST'])
@auth_decorator
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
