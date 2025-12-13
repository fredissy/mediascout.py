from urllib.parse import urlparse

def is_absolute(url):
    """Check if a URL is absolute."""
    return bool(urlparse.urlparse(url).netloc)
