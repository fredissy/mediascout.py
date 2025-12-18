"""
Enhanced TMDB Client module with alternative matches support
"""

from typing import Dict, List, Optional
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
            Dict with 'success', 'movie' (best match, with posters), 'alternatives' (other matches), or 'error'
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
            
            # Get most popular result (primary match)
            results = data['results']
            primary_movie = results[0]
            
            # Get top 5 alternatives (excluding primary)
            alternatives = sorted(
                [r for r in results if r['id'] != primary_movie['id']],
                key=lambda x: x.get('popularity', 0),
                reverse=True
            )[:5]
            
            # Format primary movie
            primary_movie_data = self._format_movie(primary_movie)
            
            # Get posters for primary movie
            primary_movie_data['posters'] = self._get_movie_posters(primary_movie['id'])
            
            # Format alternatives (without posters for now - loaded on demand)
            alternatives_data = [self._format_movie(movie) for movie in alternatives]
            
            return {
                'success': True,
                'movie': primary_movie_data,
                'alternatives': alternatives_data
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
    
    def get_movie_details(self, movie_id: int) -> Dict:
        """
        Get detailed information for a specific movie including posters.
        Used when user selects an alternative match.
        
        Returns:
            Dict with 'success', 'movie', 'posters', or 'error'
        """
        try:
            # Get movie details
            response = requests.get(
                f"{self.base_url}/movie/{movie_id}",
                params={
                    'api_key': self.api_key,
                    'language': self.locale
                },
                timeout=10
            )
            response.raise_for_status()
            movie = response.json()
            
            # Format movie data
            movie_data = self._format_movie(movie)
            
            # Get posters
            movie_data['posters'] = self._get_movie_posters(movie_id)

            return {
                'success': True,
                'movie': movie_data
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

    def _format_movie(self, movie: Dict) -> Dict:
        """Format movie data into consistent structure."""
        return {
            'id': movie['id'],
            'title': movie['title'],
            'year': movie.get('release_date', '')[:4] if movie.get('release_date') else None,
            'overview': movie.get('overview', ''),
            'popularity': movie.get('popularity', 0),
            'vote_average': movie.get('vote_average', 0),
            'poster_path': movie.get('poster_path', '')
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
