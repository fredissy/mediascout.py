"""
Authentication module for Mediascout with LDAP support.
"""

from typing import Optional
from functools import wraps
from flask import redirect, url_for, request
from flask_login import LoginManager, UserMixin, current_user
from ldap3 import Server, Connection, ALL, SIMPLE

# ============================================================================
# User Model
# ============================================================================

class User(UserMixin):
    """User model for Flask-Login."""
    
    def __init__(self, username: str, display_name: Optional[str] = None):
        self.id = username
        self.username = username
        self.display_name = display_name or username
    
    def __repr__(self):
        return f'<User {self.username}>'

# ============================================================================
# LDAP Authentication
# ============================================================================

class LDAPAuth:
    """LDAP authentication handler."""
    
    def __init__(self, config):
        self.config = config
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate user against LDAP server.
        
        Returns:
            User object if authentication successful, None otherwise
        """
        if not username or not password:
            return None
        
        try:
            # Build user DN
            user_dn = self.config.ldap_user_dn_template.format(username=username)
            
            # Connect to LDAP server
            server = Server(
                self.config.ldap_server,
                port=self.config.ldap_port,
                use_ssl=self.config.ldap_use_ssl,
                get_info=ALL
            )
            
            # Try to bind with user credentials
            conn = Connection(
                server,
                user=user_dn,
                password=password,
                authentication=SIMPLE,
                auto_bind=True
            )
            
            if conn.bound:
                # Search for user to get display name
                search_filter = self.config.ldap_search_filter.format(username=username)
                
                # Try to search with both old and new attribute names
                # First try LLDAP 0.6.x naming (underscore)
                display_name = username
                search_successful = False
                
                try:
                    conn.search(
                        search_base=self.config.ldap_base_dn,
                        search_filter=search_filter,
                        attributes=['cn', 'display_name', 'given_name', 'sn', 'surname']
                    )
                    search_successful = True
                    
                    if conn.entries:
                        entry = conn.entries[0]
                        # LLDAP 0.6.x attributes
                        if hasattr(entry, 'display_name') and entry.display_name:
                            display_name = str(entry.display_name)
                        elif hasattr(entry, 'cn') and entry.cn:
                            display_name = str(entry.cn)
                        elif hasattr(entry, 'given_name') and hasattr(entry, 'sn'):
                            display_name = f"{entry.given_name} {entry.sn}"
                        elif hasattr(entry, 'given_name') and hasattr(entry, 'surname'):
                            display_name = f"{entry.given_name} {entry.surname}"
                
                except Exception as e:
                    # If LLDAP 0.6.x attributes fail, try LLDAP 0.5.x (camelCase)
                    try:
                        conn.search(
                            search_base=self.config.ldap_base_dn,
                            search_filter=search_filter,
                            attributes=['cn', 'displayName', 'givenName', 'sn']
                        )
                        search_successful = True
                        
                        if conn.entries:
                            entry = conn.entries[0]
                            # LLDAP 0.5.x attributes
                            if hasattr(entry, 'displayName') and entry.displayName:
                                display_name = str(entry.displayName)
                            elif hasattr(entry, 'cn') and entry.cn:
                                display_name = str(entry.cn)
                            elif hasattr(entry, 'givenName') and hasattr(entry, 'sn'):
                                display_name = f"{entry.givenName} {entry.sn}"
                    
                    except Exception as e2:
                        # If both fail, just use username
                        print(f"Warning: Could not retrieve display name attributes: {e2}")
                        display_name = username
                
                conn.unbind()
                return User(username, display_name)
            
            return None
        
        except Exception as e:
            print(f"LDAP authentication error: {e}")
            return None

# ============================================================================
# Flask-Login Setup
# ============================================================================

def setup_auth(app, config):
    """
    Setup authentication for Flask app.
    
    Returns:
        LDAPAuth instance if auth is enabled, None otherwise
    """
    if not config.auth_enabled:
        print("✓ Authentication: DISABLED")
        return None
    
    # Configure Flask session
    app.config['SECRET_KEY'] = config.session_secret
    app.config['SESSION_COOKIE_SECURE'] = config.ldap_use_ssl
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message = 'Please log in to access this page.'
    
    # Initialize LDAP auth
    ldap_auth = LDAPAuth(config)
    
    @login_manager.user_loader
    def load_user(user_id):
        """Load user from session."""
        return User(user_id)
    
    print("=" * 80)
    print("✓ Authentication: ENABLED")
    print(f"✓ LDAP Server: {config.ldap_server}:{config.ldap_port}")
    print(f"✓ LDAP Base DN: {config.ldap_base_dn}")
    print(f"✓ SSL: {'Enabled' if config.ldap_use_ssl else 'Disabled'}")
    print("=" * 80)
    
    return ldap_auth

# ============================================================================
# Route Protection Decorator
# ============================================================================

def auth_required(config):
    """
    Decorator to protect routes with authentication.
    Only enforces if auth is enabled.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if config.auth_enabled and not current_user.is_authenticated:
                return redirect(url_for('login', next=request.url))
            return f(*args, **kwargs)
        return decorated_function
    return decorator