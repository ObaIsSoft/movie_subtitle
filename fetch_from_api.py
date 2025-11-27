import os
import sys
import requests
import time
from dotenv import load_dotenv # Import dotenv

# Load environment variables from .env file
load_dotenv()

# Imports moved to inside functions to avoid circular dependency

# --- CREDENTIALS (Now loaded from .env) ---
CONFIG = {
    "API_KEY": os.getenv("OPENSUBTITLES_API_KEY"),
    "USERNAME": os.getenv("OPENSUBTITLES_USERNAME"),
    "PASSWORD": os.getenv("OPENSUBTITLES_PASSWORD")
}

# Check if credentials are present
if not all(CONFIG.values()):
    print("Error: OpenSubtitles credentials missing in .env file.")
    sys.exit(1)

API_BASE_URL = "https://api.opensubtitles.com/api/v1"

class APIError(Exception): pass

def get_api_token(session):
    login_url = f"{API_BASE_URL}/login"
    payload = {"username": CONFIG["USERNAME"], "password": CONFIG["PASSWORD"]}
    headers = {"Content-Type": "application/json", "Api-Key": CONFIG["API_KEY"]}
    
    try:
        r = session.post(login_url, json=payload, headers=headers)
        r.raise_for_status() 
        data = r.json()
        return data.get('token')
    except Exception as e:
        print(f"Login failed: {e}")
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

def fetch_movie_subtitles(session, token, imdb_id, movie_title, movie_year):
    from app import db, Movie, Subtitle
    from srt_parser import parse_srt

    print(f"\nProcessing: {movie_title} ({movie_year})")
    
    existing_movie = Movie.query.filter_by(imdb_id=imdb_id).first()
    if existing_movie:
        print("Skipping (Already exists)")
        return False 

    # Search
    search_url = f"{API_BASE_URL}/subtitles"
    headers = {"Authorization": f"Bearer {token}", "Api-Key": CONFIG["API_KEY"]}
    params = {"imdb_id": imdb_id, "languages": "en"}
    
    try:
        r = session.get(search_url, headers=headers, params=params)
        results = r.json()
        file_id = find_best_subtitle(results.get('data'))
        
        if not file_id: return False

        # Download Link
        download_request_url = f"{API_BASE_URL}/download"
        r = session.post(download_request_url, headers=headers, json={"file_id": file_id})
        download_link = r.json().get('link')
        
        # Download Content
        r_srt = requests.get(download_link)
        srt_content = r_srt.text 
        
        parsed_subtitles = parse_srt(srt_content)
        if not parsed_subtitles: return False
            
        new_movie = Movie(title=movie_title, year=movie_year, imdb_id=imdb_id)
        db.session.add(new_movie)
        db.session.commit() 
        
        for sub_data in parsed_subtitles:
            new_subtitle = Subtitle(
                text=sub_data['text'],
                start_time=sub_data['start'],
                end_time=sub_data['end'],
                movie_id=new_movie.id
            )
            db.session.add(new_subtitle)
            
        db.session.commit()
        print(f"Imported {len(parsed_subtitles)} lines.")
        return True 

    except Exception as e:
        print(f"Error: {e}")
        db.session.rollback() 
        return False

def fetch_all_movies():
    """
    Fetches subtitles for movies dynamically.
    Loops from current year back to 1970.
    Fetches 10 movies per year, cycling through popularity pages.
    """
    from app import app, db, AppSettings
    from tmdb_client import discover_popular_movies
    import datetime

    print("Starting scheduled dynamic fetch...")
    
    current_year = datetime.datetime.now().year
    start_year = 1970
    movies_per_cycle = 10
    
    with app.app_context():
        # Get current cycle from DB
        cycle_setting = AppSettings.query.get('fetch_cycle')
        if not cycle_setting:
            cycle_setting = AppSettings(key='fetch_cycle', value='0')
            db.session.add(cycle_setting)
            db.session.commit()
        
        current_cycle = int(cycle_setting.value)
        print(f"Current Fetch Cycle: {current_cycle}")

        # Calculate TMDB page and slice
        # TMDB returns 20 results per page.
        # Cycle 0: Page 1, Index 0-10
        # Cycle 1: Page 1, Index 10-20
        # Cycle 2: Page 2, Index 0-10
        # ...
        
        tmdb_page = (current_cycle // 2) + 1
        start_index = (current_cycle % 2) * 10
        end_index = start_index + 10

        session = requests.Session() 
        session.headers.update({'User-Agent': 'MovieQuoteSearch v1.0'})
        
        MAX_DOWNLOADS = 20
        downloads_count = 0

        try:
            token = get_api_token(session)
            
            for year in range(current_year, start_year - 1, -1):
                if downloads_count >= MAX_DOWNLOADS:
                    print(f"Daily download limit of {MAX_DOWNLOADS} reached. Stopping.")
                    break

                print(f"Fetching movies for year {year} (Page {tmdb_page})...")
                
                movies = discover_popular_movies(year, page=tmdb_page)
                
                # Slice the 10 movies for this cycle
                movies_to_process = movies[start_index:end_index]
                
                if not movies_to_process:
                    print(f"No more movies found for year {year} page {tmdb_page}.")
                    continue

                for imdb_id, title, year in movies_to_process:
                    if downloads_count >= MAX_DOWNLOADS:
                        print(f"Daily download limit of {MAX_DOWNLOADS} reached. Stopping.")
                        break

                    if fetch_movie_subtitles(session, token, imdb_id, title, year):
                        downloads_count += 1
                        print(f"Downloads today: {downloads_count}/{MAX_DOWNLOADS}")
                        # Rate limiting to be nice to APIs
                        time.sleep(2) 
            
            # Update cycle for next run ONLY if we finished the loop naturally (not by limit)
            # Actually, we should probably update the cycle anyway to progress, 
            # BUT if we hit the limit, we might have missed movies in this cycle.
            # However, for simplicity and forward progress, let's update the cycle. 
            # If we missed some, we missed some. We want to see new movies next time.
            if downloads_count < MAX_DOWNLOADS:
                 # Only increment cycle if we didn't hit the limit mid-way? 
                 # Or always increment? 
                 # If we hit the limit, we stop. Next day we run again.
                 # If we don't increment, we retry the same movies. 
                 # Since we skip existing, we will just skip them and move on.
                 # So we DON'T need to increment cycle here if we hit the limit.
                 # We only increment if we finished the *processing* of the cycle.
                 # But the loop goes through ALL years.
                 # The "Cycle" defines the *slice* (Top 1-10 vs Top 11-20).
                 # If we hit the limit at year 2020, we still haven't checked 1970 for this slice.
                 # So we should probably NOT increment the cycle if we hit the limit.
                 # We should let it run again tomorrow on the SAME cycle.
                 # It will skip the ones we already got, and continue to get the rest of the years.
                 pass
            else:
                 print("Hit limit, keeping same cycle for next run to finish remaining years.")

            # Logic refinement:
            # If we finished the loop (checked all years), THEN increment cycle.
            # If we broke early, DO NOT increment.
            
            if year == start_year and downloads_count < MAX_DOWNLOADS:
                cycle_setting.value = str(current_cycle + 1)
                db.session.commit()
                print(f"Cycle {current_cycle} completed. Updated to {current_cycle + 1}.")
            else:
                print(f"Cycle {current_cycle} incomplete (Limit reached or error). Will resume next run.")

        except Exception as e:
            print(f"Scheduled fetch failed: {e}")

if __name__ == "__main__":
    fetch_all_movies()