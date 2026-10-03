import hmac
import os
import tempfile
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, CSRFError
from sqlalchemy import func, or_, and_, literal_column
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
from tmdb_client import get_movie_data, search_movie_metadata
from srt_parser import parse_srt, decode_srt_bytes
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from openai import OpenAI

from fetch_from_api import fetch_all_movies

load_dotenv()

app = Flask(__name__)

# Cloud Run sits behind Google's front end. Trust one proxy hop so request.remote_addr
# is the real client IP (the rate limiter keys on it) and redirects keep https.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
if not app.config['SECRET_KEY']:
    raise RuntimeError("SECRET_KEY environment variable is not set.")

# Largest accepted request body (.srt uploads, voice clips). Bigger requests get a 413.
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# Database URL — handles Supabase, Neon, Fly, and local Postgres
database_url = os.getenv('DATABASE_URL', '')
if database_url:
    database_url = database_url.replace("postgres://", "postgresql://", 1)
else:
    raise RuntimeError("DATABASE_URL environment variable is not set.")

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,       # Auto-reconnect if DB suspended the connection
    "pool_recycle": 300,          # Recycle connections every 5 min
    "connect_args": {
        # Supabase/Neon require SSL; set DB_SSLMODE=disable for a local Postgres without SSL
        "sslmode": os.getenv('DB_SSLMODE', 'require')
    }
}

# Logging Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

db = SQLAlchemy(app)

# Rate Limiter (limits apply per client IP, per route).
# memory:// is per instance; point RATELIMIT_STORAGE_URI at Redis to share limits across instances.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["2000 per day", "300 per hour"],
    storage_uri=os.getenv('RATELIMIT_STORAGE_URI', 'memory://')
)

# CSRF protection for every POST form; JS requests send the token in an X-CSRFToken header
csrf = CSRFProtect(app)

# OpenAI client is created on first use so the app still boots without OPENAI_API_KEY
_openai_client = None

def get_openai_client():
    global _openai_client
    if _openai_client is None and os.getenv('OPENAI_API_KEY'):
        _openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    return _openai_client

# 'simple' text-search config: no stemming and no stop-word removal, so quotes made of
# common words ("to be or not to be") still match. Must match ix_subtitle_text_fts.
FTS_CONFIG = literal_column("'simple'::regconfig")

def escape_like(value):
    """Escape LIKE wildcards so user input is matched literally."""
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


# --- Models ---
class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    year = db.Column(db.Integer)
    imdb_id = db.Column(db.String(20), unique=True, nullable=True)
    is_approved = db.Column(db.Boolean, default=False, server_default="false", nullable=False)
    subtitles = db.relationship('Subtitle', backref='movie', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Movie {self.title}>'

class Subtitle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Search indexes (full-text + trigram) live in migrations/001_search_indexes.sql
    text = db.Column(db.Text, nullable=False)
    start_time = db.Column(db.String(20), nullable=True)
    end_time = db.Column(db.String(20), nullable=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), nullable=False, index=True)

    def __repr__(self):
        return f'<Subtitle {self.text[:20]}...>'

class AppSettings(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f'<AppSettings {self.key}={self.value}>'

# --- Routes ---

@app.route('/')
def index():
    query = request.args.get('q')
    if query:
        # Full-Text Search: every word must appear; lines containing the exact phrase rank first
        ts_query = func.plainto_tsquery(FTS_CONFIG, query)
        ts_vector = func.to_tsvector(FTS_CONFIG, Subtitle.text)
        exact_phrase = Subtitle.text.ilike(f'%{escape_like(query.strip())}%')

        subtitles = Subtitle.query.join(Movie).filter(
            ts_vector.op('@@')(ts_query),
            Movie.is_approved == True
        ).order_by(
            exact_phrase.desc(),
            func.ts_rank_cd(ts_vector, ts_query).desc()
        ).limit(100).all()
    else:
        subtitles = [] 
    return render_template('index.html', subtitles=subtitles, query=query)

@app.route('/quote/<int:subtitle_id>')
def quote_detail(subtitle_id):
    subtitle = Subtitle.query.get_or_404(subtitle_id)
    movie = subtitle.movie
    if not movie.is_approved:
        abort(404)  # pending uploads stay hidden until approved
    tmdb_data = get_movie_data(movie.title, movie.year, country_code="NG")
    
    # Fetch Context (Previous and Next lines)
    prev_subtitle = Subtitle.query.filter_by(movie_id=movie.id).filter(Subtitle.id < subtitle.id).order_by(Subtitle.id.desc()).first()
    next_subtitle = Subtitle.query.filter_by(movie_id=movie.id).filter(Subtitle.id > subtitle.id).order_by(Subtitle.id.asc()).first()

    return render_template('quote_detail.html', 
                         subtitle=subtitle, 
                         prev_subtitle=prev_subtitle,
                         next_subtitle=next_subtitle,
                         watch_link=tmdb_data.get('watch_link'),
                         justwatch_link=tmdb_data.get('justwatch_link'),
                         google_watchlist_link=tmdb_data.get('google_watchlist_link'),
                         tmdb_id=tmdb_data.get('tmdb_id'),
                         poster_url=tmdb_data.get('poster_url'))

@app.route('/api/autocomplete')
@limiter.limit("60 per minute")  # fires while typing, so it gets its own, higher limit
def autocomplete():
    q = request.args.get('q', '').strip()
    if len(q) < 3:  # the trigram index needs at least 3 characters
        return jsonify([])

    # Improved Autocomplete: Join with Movie to return correct title, filter by approved
    results = db.session.query(Subtitle, Movie).join(Movie).filter(
        Subtitle.text.ilike(f'%{escape_like(q)}%'),
        Movie.is_approved == True
    ).limit(5).all()
    
    suggestions = []
    for sub, movie in results:
        suggestions.append({
            'id': sub.id,
            'text': sub.text,
            'movie': movie.title,
            'year': movie.year
        })
    return jsonify(suggestions)

@app.route('/api/transcribe', methods=['POST'])
@limiter.limit("10 per hour") # Strict limit for API costs
def transcribe_audio():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio']
    if audio_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    openai_client = get_openai_client()
    if openai_client is None:
        return jsonify({'error': 'Voice transcription is not configured'}), 503

    # Save to a temporary file
    suffix = ".webm"
    if audio_file.filename.endswith('.mp4'): suffix = ".mp4"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_audio:
        audio_file.save(temp_audio.name)
        temp_path = temp_audio.name

    try:
        file_size = os.path.getsize(temp_path)
        logger.info(f"Received audio file: {audio_file.filename}, Size: {file_size} bytes")

        if file_size == 0:
            return jsonify({'error': 'Empty audio file'}), 400

        with open(temp_path, "rb") as audio_file_obj:
            logger.info("Sending to OpenAI Whisper...")
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file_obj
            )

        text = transcript.text.strip()
        logger.info(f"Transcription success: '{text}'")

        # Remove trailing punctuation for better search
        if text.endswith('.'): text = text[:-1]

        return jsonify({'text': text})

    except Exception as e:
        logger.error(f"Transcription error: {str(e)}", exc_info=True)
        return jsonify({'error': 'Transcription failed. Please try again.'}), 500
    finally:
        os.remove(temp_path)

@app.route('/api/export_movies')
def export_movies():
    movies = Movie.query.filter_by(is_approved=True).all()
    movie_list = [{'title': m.title, 'year': m.year} for m in movies]
    
    response = jsonify(movie_list)
    response.headers.set('Content-Disposition', 'attachment', filename='quoted_movies.json')
    return response

@app.route('/add', methods=['GET', 'POST'])
def add_entry():
    if request.method == 'POST':
        raw_title = request.form.get('title')
        if not raw_title or not raw_title.strip():
            flash('Movie title is required.', 'error')
            return redirect(request.url)
        user_title = raw_title.strip()

        try:
            user_year = int(request.form.get('year'))
        except (ValueError, TypeError):
            flash('Invalid year format.', 'error')
            return redirect(request.url)
        
        if 'subtitle_file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
            
        file = request.files['subtitle_file']
        
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)

        if not file.filename.lower().endswith('.srt'):
            flash('Invalid file format. Please upload a .srt file.', 'error')
            return redirect(request.url)

        parsed_subs = parse_srt(decode_srt_bytes(file.read()))

        if not parsed_subs:
            flash('Could not parse subtitles. The file format might be incorrect or empty.', 'error')
            return redirect(request.url)

        # --- Metadata Verification ---
        verified_data = search_movie_metadata(user_title, user_year)
        
        if verified_data:
            movie_title = verified_data['title']
            movie_year = verified_data['year']
            imdb_id = verified_data['imdb_id']
            
            # Inform user if we corrected their input
            if movie_title.lower() != user_title.lower() or movie_year != user_year:
                flash(f"Auto-corrected: Found '{movie_title}' ({movie_year}) matching your input.", 'success')
        else:
            # Fallback to user input if no match found
            movie_title = user_title
            movie_year = user_year
            imdb_id = None
            flash(f"Could not verify metadata. Using '{movie_title}' ({movie_year}) as entered.", 'warning')

        # Already in the database (live or awaiting review)? Match on IMDb ID or title + year.
        duplicate_checks = [and_(func.lower(Movie.title) == func.lower(movie_title), Movie.year == movie_year)]
        if imdb_id:
            duplicate_checks.append(Movie.imdb_id == imdb_id)
        existing_movie = Movie.query.filter(or_(*duplicate_checks)).first()

        if existing_movie:
            if existing_movie.is_approved:
                flash(f"Subtitles for '{existing_movie.title}' ({existing_movie.year}) are already in the database.", 'info')
            else:
                flash(f"'{existing_movie.title}' ({existing_movie.year}) was already submitted and is awaiting review.", 'info')
            return redirect(url_for('index'))

        try:
            # Movie and all its lines are saved in one transaction, so a failure leaves nothing behind.
            # is_approved=False by default for community uploads.
            new_movie = Movie(title=movie_title, year=movie_year, imdb_id=imdb_id, subtitles=[
                Subtitle(text=sub_data['text'], start_time=sub_data['start'], end_time=sub_data['end'])
                for sub_data in parsed_subs
            ])
            db.session.add(new_movie)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            logger.error("Failed to save upload", exc_info=True)
            flash('Something went wrong saving your upload. Please try again.', 'error')
            return redirect(request.url)

        flash(f'Submitted {len(parsed_subs)} lines for "{movie_title}" ({movie_year}). They will go live after admin approval.', 'success')
        return redirect(url_for('index'))

    return render_template('add.html')

# --- Admin Routes ---
from functools import wraps
from flask import request, session

def check_auth(username, password):
    admin_user = os.getenv('ADMIN_USER', 'admin')
    admin_pass = os.getenv('ADMIN_PASS')
    if not admin_pass or not username or not password:
        return False  # no default password: admin login stays disabled until ADMIN_PASS is set
    user_ok = hmac.compare_digest(username.encode(), admin_user.encode())
    pass_ok = hmac.compare_digest(password.encode(), admin_pass.encode())
    return user_ok and pass_ok

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please log in to access the admin panel.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=['POST'])  # slow down password guessing
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if check_auth(username, password):
            session['admin_logged_in'] = True
            flash('Welcome to the Moderation Queue!', 'success')
            return redirect(url_for('admin_panel'))
        elif not os.getenv('ADMIN_PASS'):
            flash('Admin login is disabled: set the ADMIN_PASS environment variable.', 'error')
        else:
            flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/admin')
@requires_auth
def admin_panel():
    # (movie, line_count) pairs, counted in SQL instead of loading every subtitle row
    pending_movies = db.session.query(Movie, func.count(Subtitle.id)).outerjoin(Subtitle).filter(
        Movie.is_approved == False
    ).group_by(Movie.id).order_by(Movie.id).all()
    return render_template('admin.html', movies=pending_movies)

@app.route('/admin/approve/<int:movie_id>', methods=['POST'])
@requires_auth
def approve_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    movie.is_approved = True
    db.session.commit()
    flash(f"Approved {movie.title}!", 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete/<int:movie_id>', methods=['POST'])
@requires_auth
def delete_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    title = movie.title
    # Delete the lines in one statement instead of loading and deleting them one by one
    Subtitle.query.filter_by(movie_id=movie.id).delete(synchronize_session=False)
    db.session.delete(movie)
    db.session.commit()
    flash(f"Deleted {title}!", 'success')
    return redirect(url_for('admin_panel'))

@app.route('/api/cron/fetch', methods=['POST'])
@csrf.exempt
@limiter.exempt
def cron_fetch():
    """Triggered daily by Cloud Scheduler (job: quoted-daily-fetch) to fetch new movies."""
    cron_secret = request.headers.get('X-Cron-Secret', '')
    expected_secret = os.getenv('CRON_SECRET', '')
    if not expected_secret or not hmac.compare_digest(cron_secret.encode(), expected_secret.encode()):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        # Stop well inside Cloud Scheduler's 180s attempt deadline. Progress is saved,
        # so the next run resumes where this one stopped.
        budget = int(os.getenv('FETCH_TIME_BUDGET_SECONDS', '150'))
        summary = fetch_all_movies(time_budget_seconds=budget)
        return jsonify({'status': 'ok', **summary}), 200
    except Exception as e:
        logger.error(f"Cron fetch failed: {e}", exc_info=True)
        return jsonify({'error': 'Fetch failed; see server logs'}), 500

# --- Error Handlers ---

@app.errorhandler(413)
def request_too_large(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'File too large (max 5 MB)'}), 413
    flash('File too large. The maximum upload size is 5 MB.', 'error')
    return redirect(request.url)

@app.errorhandler(CSRFError)
def csrf_error(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Session expired. Please reload the page.'}), 400
    flash('Your session expired. Please try again.', 'error')
    return redirect(url_for('admin_panel') if request.path.startswith('/admin') else request.url)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)