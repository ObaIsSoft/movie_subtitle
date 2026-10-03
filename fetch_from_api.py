import os
import sys
import time
import datetime
import logging
import requests
from dotenv import load_dotenv # Import dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# Imports from app are done inside functions to avoid a circular dependency

# --- CREDENTIALS (loaded from environment / .env) ---
CONFIG = {
    "API_KEY": os.getenv("OPENSUBTITLES_API_KEY"),
    "USERNAME": os.getenv("OPENSUBTITLES_USERNAME"),
    "PASSWORD": os.getenv("OPENSUBTITLES_PASSWORD")
}

API_BASE_URL = "https://api.opensubtitles.com/api/v1"
REQUEST_TIMEOUT = 20 # seconds

START_YEAR = 1970
MOVIES_PER_CYCLE = 10 # TMDB pages hold 20 movies; each cycle covers half a page per year
MAX_DOWNLOADS = 20    # OpenSubtitles daily download quota

class APIError(Exception): pass

class QuotaExhausted(APIError): pass

def get_api_token(session):
    login_url = f"{API_BASE_URL}/login"
    payload = {"username": CONFIG["USERNAME"], "password": CONFIG["PASSWORD"]}
    headers = {"Content-Type": "application/json", "Api-Key": CONFIG["API_KEY"]}

    try:
        r = session.post(login_url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return data.get('token')
    except Exception as e:
        logger.error(f"OpenSubtitles login failed: {e}")
        raise APIError("Login failed")

def find_best_subtitle(subtitle_list):
    if not subtitle_list: return None
    clean_subs = []

    for sub in subtitle_list:
        attrs = sub.get('attributes', {})
        if attrs.get('ai_translated') == True: continue
        if not attrs.get('files'): continue
        clean_subs.append(attrs)

    if clean_subs:
        clean_subs.sort(key=lambda s: s.get('download_count', 0), reverse=True)
        return clean_subs[0]['files'][0]['file_id']
    return None

def movie_exists(title, year, imdb_id=None):
    """True if the movie is already stored (live or awaiting review), by IMDb ID or title + year."""
    from app import Movie
    from sqlalchemy import func, or_, and_

    checks = [and_(func.lower(Movie.title) == func.lower(title), Movie.year == year)]
    if imdb_id:
        checks.append(Movie.imdb_id == imdb_id)
    return Movie.query.filter(or_(*checks)).first() is not None

def fetch_movie_subtitles(session, token, imdb_id, movie_title, movie_year):
    """
    Downloads and stores English subtitles for one movie.
    Returns True if the movie was imported. Raises QuotaExhausted when the daily quota is used up.
    """
    from app import db, Movie, Subtitle
    from srt_parser import parse_srt, decode_srt_bytes

    logger.info(f"Processing: {movie_title} ({movie_year})")

    # Search
    search_url = f"{API_BASE_URL}/subtitles"
    headers = {"Authorization": f"Bearer {token}", "Api-Key": CONFIG["API_KEY"]}
    params = {"imdb_id": imdb_id, "languages": "en"}

    try:
        r = session.get(search_url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        results = r.json()
        file_id = find_best_subtitle(results.get('data'))

        if not file_id: return False

        # Download Link
        download_request_url = f"{API_BASE_URL}/download"
        r = session.post(download_request_url, headers=headers, json={"file_id": file_id}, timeout=REQUEST_TIMEOUT)
        download_data = r.json()
        download_link = download_data.get('link')

        if r.status_code == 406:
            raise QuotaExhausted(download_data.get('message', 'Download quota reached'))
        if not download_link:
            logger.warning(f"No download link (HTTP {r.status_code}): {download_data.get('message')}")
            return False

        # Download Content (decode bytes ourselves; requests guesses the encoding wrong for many .srt files)
        r_srt = session.get(download_link, timeout=REQUEST_TIMEOUT)
        srt_content = decode_srt_bytes(r_srt.content)

        parsed_subtitles = parse_srt(srt_content)
        if not parsed_subtitles: return False

        # Movie and all its lines are saved in one transaction
        new_movie = Movie(title=movie_title, year=movie_year, imdb_id=imdb_id, is_approved=True, subtitles=[
            Subtitle(text=sub_data['text'], start_time=sub_data['start'], end_time=sub_data['end'])
            for sub_data in parsed_subtitles
        ])
        db.session.add(new_movie)
        db.session.commit()
        logger.info(f"Imported {len(parsed_subtitles)} lines.")
        return True

    except QuotaExhausted:
        raise
    except Exception as e:
        logger.error(f"Error importing {movie_title} ({movie_year}): {e}")
        db.session.rollback()
        return False

def _get_setting(key, default):
    from app import db, AppSettings
    setting = db.session.get(AppSettings, key)
    if not setting:
        setting = AppSettings(key=key, value=str(default))
        db.session.add(setting)
        db.session.commit()
    return setting

def fetch_all_movies(time_budget_seconds=None):
    """
    Fetches subtitles for popular movies, from the current year back to 1970.

    Each "cycle" covers MOVIES_PER_CYCLE movies per year (cycle 0: TMDB page 1, results 1-10;
    cycle 1: page 1, results 11-20; cycle 2: page 2, results 1-10; ...).
    Progress (cycle + next year to process) is saved in AppSettings after every year, so a run
    that stops early (download quota, time budget, crash) resumes where it left off next time.

    time_budget_seconds: stop starting new work after this many seconds (None = no limit).
    Returns a summary dict.
    """
    from app import app, db
    from tmdb_client import discover_popular_movies, get_imdb_id

    if not all(CONFIG.values()):
        raise APIError("OpenSubtitles credentials are not configured.")

    deadline = time.monotonic() + time_budget_seconds if time_budget_seconds else None
    current_year = datetime.datetime.now().year

    with app.app_context():
        cycle_setting = _get_setting('fetch_cycle', 0)
        year_setting = _get_setting('fetch_next_year', current_year)
        current_cycle = int(cycle_setting.value)
        next_year = min(int(year_setting.value), current_year)

        tmdb_page = (current_cycle // 2) + 1
        start_index = (current_cycle % 2) * MOVIES_PER_CYCLE
        end_index = start_index + MOVIES_PER_CYCLE

        logger.info(f"Starting fetch: cycle {current_cycle} (TMDB page {tmdb_page}, "
                    f"results {start_index + 1}-{end_index}), resuming at year {next_year}")

        session = requests.Session()
        session.headers.update({'User-Agent': 'MovieQuoteSearch v1.0'})
        token = get_api_token(session)

        downloads_count = 0
        stop_reason = None

        for year in range(next_year, START_YEAR - 1, -1):
            movies = discover_popular_movies(year, page=tmdb_page)[start_index:end_index]

            for tmdb_id, title, movie_year in movies:
                if downloads_count >= MAX_DOWNLOADS:
                    stop_reason = 'download limit'
                elif deadline and time.monotonic() > deadline:
                    stop_reason = 'time budget'
                if stop_reason:
                    break

                # Skip known movies before spending a TMDB call on the IMDb ID
                if movie_exists(title, movie_year):
                    continue
                imdb_id = get_imdb_id(tmdb_id)
                if not imdb_id or movie_exists(title, movie_year, imdb_id):
                    continue

                try:
                    imported = fetch_movie_subtitles(session, token, imdb_id, title, movie_year)
                except QuotaExhausted as e:
                    logger.info(f"OpenSubtitles quota exhausted: {e}")
                    stop_reason = 'download quota'
                    break

                if imported:
                    downloads_count += 1
                    logger.info(f"Downloads this run: {downloads_count}/{MAX_DOWNLOADS}")
                    time.sleep(2) # Rate limiting to be nice to APIs

            if stop_reason:
                # This year isn't finished; next run starts here again (imported movies are skipped)
                year_setting.value = str(year)
                db.session.commit()
                break

            year_setting.value = str(year - 1)
            db.session.commit()

        if not stop_reason:
            # Every year done for this slice: move to the next slice and start from the current year again
            cycle_setting.value = str(current_cycle + 1)
            year_setting.value = str(current_year)
            db.session.commit()
            logger.info(f"Cycle {current_cycle} completed. Next cycle: {current_cycle + 1}.")
        else:
            logger.info(f"Stopped early ({stop_reason}) at year {year_setting.value}. Will resume next run.")

        return {
            'cycle': current_cycle,
            'downloads': downloads_count,
            'stopped_early': stop_reason,
            'next_year': int(year_setting.value),
        }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    try:
        print(fetch_all_movies())
    except Exception as e:
        logger.error(f"Fetch failed: {e}", exc_info=True)
        sys.exit(1)
