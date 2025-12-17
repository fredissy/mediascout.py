"""
Authentication module for Mediascout with LDAP support.
"""

from typing import Optional, List
from functools import wraps
from flask import redirect, url_for, request
from flask_login import LoginManager, UserMixin, current_user
from ldap3 import Server, Connection, ALL, SIMPLE
from ldap3.core.exceptions import (LDAPException)


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
    
    def _search_and_extract_display_name(
        self,
        conn: Connection,
        username: str,
        display_name_attributes: List[str]
    ) -> Optional[str]:
        """
        Helper to search for user entry and extract a display name.
        
        Args:
            conn: An active LDAP connection object.
            username: The username to search for.
            display_name_attributes: A list of attributes to request and check for display name.
        
        Returns:
            The extracted display name, or None if search fails or no suitable attribute is found.
        """
        search_filter = self.config.ldap_search_filter.format(username=username)
        
        try:
            conn.search(
                search_base=self.config.ldap_base_dn,
                search_filter=search_filter,
                attributes=display_name_attributes
            )
            
            if conn.entries:
                entry = conn.entries[0]
                
                # Check for specific attributes in order of preference
                if 'display_name' in display_name_attributes and hasattr(entry, 'display_name') and entry.display_name:
                    return str(entry.display_name)
                elif 'displayName' in display_name_attributes and hasattr(entry, 'displayName') and entry.displayName:
                    return str(entry.displayName)
                elif hasattr(entry, 'cn') and entry.cn:
                    return str(entry.cn)
                else:
                    # Build full name from given name and surname variants, if available
                    given_name = ""
                    if (
                        'given_name' in display_name_attributes
                        and hasattr(entry, 'given_name')
                        and entry.given_name
                    ):
                        given_name = str(entry.given_name)
                    elif (
                        'givenName' in display_name_attributes
                        and hasattr(entry, 'givenName')
                        and entry.givenName
                    ):
                        given_name = str(entry.givenName)
                    sn = ""
                    if (
                        'sn' in display_name_attributes
                        and hasattr(entry, 'sn')
                        and entry.sn
                    ):
                        sn = str(entry.sn)
                    elif (
                        'surname' in display_name_attributes
                        and hasattr(entry, 'surname')
                        and entry.surname
                    ):
                        sn = str(entry.surname)
                    if given_name and sn:
                        return f"{given_name} {sn}"
            
        except LDAPException as e:
            # We don't want to propagate this error, but log it for debugging
            print(f"LDAP search for display name failed: {e}")
            # Continue to try next attribute set or default to None
            
        return None
    
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
                display_name = username
                
                # 1. Try LLDAP 0.6.x naming (underscore)
                attributes_underscore = ['cn', 'display_name', 'given_name', 'sn', 'surname']
                extracted_name = self._search_and_extract_display_name(conn, username, attributes_underscore)
                
                if extracted_name is None:
                    # 2. Try LLDAP 0.5.x naming (camelCase)
                    attributes_camelcase = ['cn', 'displayName', 'givenName', 'sn']
                    extracted_name = self._search_and_extract_display_name(conn, username, attributes_camelcase)

                if extracted_name:
                    display_name = extracted_name
                else:
                    print("Warning: Could not retrieve display name attributes, defaulting to username.")

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