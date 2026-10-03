import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('TMDB_API_KEY')
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500" # Base URL for images
REQUEST_TIMEOUT = 10 # seconds; never let a slow TMDB response hang a web worker

import logging

logger = logging.getLogger(__name__)

def get_movie_data(title, year=None, country_code="NG"):
    """
    Returns a dictionary with streaming link, TMDb ID, and poster URL.
    """
    if not API_KEY:
        return {'watch_link': None, 'tmdb_id': None, 'poster_url': None}

    # 1. Search for Movie
    search_url = f"{BASE_URL}/search/movie"
    params = {"api_key": API_KEY, "query": title}
    if year:
        params['year'] = year

    movie_id = None
    poster_path = None

    try:
        response = requests.get(search_url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        if data['results']:
            first_result = data['results'][0]
            movie_id = first_result['id']
            poster_path = first_result.get('poster_path')
        else:
            return {'watch_link': None, 'tmdb_id': None, 'poster_url': None}

    except Exception as e:
        logger.error(f"Error finding movie: {e}")
        return {'watch_link': None, 'tmdb_id': None, 'poster_url': None}

    # 2. Get Watch Providers
    provider_url = f"{BASE_URL}/movie/{movie_id}/watch/providers"

    watch_link = None
    try:
        p_response = requests.get(provider_url, params={"api_key": API_KEY}, timeout=REQUEST_TIMEOUT)
        p_response.raise_for_status()
        p_data = p_response.json()

        results = p_data.get('results', {})

        if country_code in results:
            watch_link = results[country_code].get('link')
        elif 'US' in results:
            watch_link = results['US'].get('link')
        elif results:
            first_key = next(iter(results))
            watch_link = results[first_key].get('link')

    except Exception as e:
        logger.error(f"Error finding providers: {e}")

    # Construct full poster URL
    poster_url = f"{IMAGE_BASE_URL}{poster_path}" if poster_path else None

    # Construct JustWatch Search URL
    # Simple search URL. For more precision, we'd need the JustWatch API or a mapping.
    # Replacing spaces with '+' for the query.
    jw_query = title.replace(" ", "+")
    justwatch_link = f"https://www.justwatch.com/us/search?q={jw_query}"

    # Construct Google Watchlist Search URL
    # Query: "Title Year movie" to trigger the Knowledge Panel
    gw_query = f"{title} {year} movie".replace(" ", "+") if year else f"{title} movie".replace(" ", "+")
    google_watchlist_link = f"https://www.google.com/search?q={gw_query}"

    return {
        'watch_link': watch_link,
        'justwatch_link': justwatch_link,
        'google_watchlist_link': google_watchlist_link,
        'tmdb_id': movie_id,
        'poster_url': poster_url
    }

def discover_popular_movies(year, page=1):
    """
    Fetches popular movies for a specific year (one TMDB page, up to 20 results).
    Returns a list of tuples: (tmdb_id, title, year)
    The discover endpoint doesn't include IMDb IDs; look them up with get_imdb_id()
    only for the movies you actually need.
    """
    if not API_KEY:
        return []

    url = f"{BASE_URL}/discover/movie"
    params = {
        "api_key": API_KEY,
        "primary_release_year": year,
        "sort_by": "popularity.desc",
        "page": page,
        "include_adult": "false",
        "include_video": "false",
        "language": "en-US",
        "vote_count.gte": 100 # Filter out very obscure movies
    }

    movies = []
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        for result in data.get('results', []):
            movie_id = result.get('id')
            if movie_id:
                movies.append((movie_id, result.get('title'), year))

    except Exception as e:
        logger.error(f"Error discovering movies for year {year}: {e}")

    return movies

def get_imdb_id(tmdb_id):
    """Looks up a movie's IMDb ID from its TMDB ID. Returns None if unavailable."""
    if not API_KEY:
        return None
    try:
        detail_url = f"{BASE_URL}/movie/{tmdb_id}"
        d_response = requests.get(detail_url, params={"api_key": API_KEY}, timeout=REQUEST_TIMEOUT)
        if d_response.status_code == 200:
            return d_response.json().get('imdb_id')
    except Exception as e:
        logger.error(f"Error fetching details for movie {tmdb_id}: {e}")
    return None

def search_movie_metadata(query, year=None):
    """
    Searches for a movie by title and optional year to verify metadata.
    Returns a dictionary with correct title, year, imdb_id, and poster_url.
    """
    if not API_KEY:
        return None

    search_url = f"{BASE_URL}/search/movie"

    # First attempt: Search with year if provided
    if year:
        params = {"api_key": API_KEY, "query": query, "year": year}
        try:
            response = requests.get(search_url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            if data['results']:
                return _process_search_result(data['results'][0])
        except Exception as e:
            logger.error(f"Error searching with year: {e}")

    # Second attempt: Search without year (or if year search failed)
    params = {"api_key": API_KEY, "query": query}
    try:
        response = requests.get(search_url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if data['results']:
            return _process_search_result(data['results'][0])
    except Exception as e:
        logger.error(f"Error searching without year: {e}")

    return None

def _process_search_result(result):
    """Helper to extract details from a TMDB result."""
    movie_id = result.get('id')
    title = result.get('title')
    release_date = result.get('release_date', '')
    year = int(release_date.split('-')[0]) if release_date else None
    poster_path = result.get('poster_path')
    poster_url = f"{IMAGE_BASE_URL}{poster_path}" if poster_path else None

    return {
        'title': title,
        'year': year,
        'imdb_id': get_imdb_id(movie_id),
        'poster_url': poster_url
    }
