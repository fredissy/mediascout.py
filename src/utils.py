from urllib.parse import urlparse
import re

def is_absolute(url):
    """Check if a URL is absolute."""
    return bool(urlparse.urlparse(url).netloc)

def get_target_directory(filename, media_directories):
    """
    Determine the target directory for a file based on its first letter.
    Expects directories to end with a letter range like 'A-F'.
    """
    if not filename:
        return None

    first_char = filename[0].upper()

    # Iterate through directories to find a matching range
    for directory in media_directories:
        # Regex to match directory ending with range, e.g., "Movies A-F" or "A-F"
        # Matches A-Z separated by hyphen at the end of string
        match = re.search(r'([A-Z])-([A-Z])$', directory, re.IGNORECASE)

        if match:
            start_char = match.group(1).upper()
            end_char = match.group(2).upper()

            # Check if character is within range
            if start_char <= first_char <= end_char:
                return directory

    return None
