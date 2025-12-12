"""
TMDB Client module.
"""

from typing import Optional, Dict, List
import requests

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
