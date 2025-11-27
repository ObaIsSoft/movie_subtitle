import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from dotenv import load_dotenv
from tmdb_client import get_movie_data
from srt_parser import parse_srt 
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address 

from fetch_from_api import fetch_all_movies 

load_dotenv()

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'super_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL').replace("postgres://", "postgresql://", 1) if os.getenv('DATABASE_URL') else None
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Logging Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

db = SQLAlchemy(app)

# Rate Limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)



# --- Models ---
class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    year = db.Column(db.Integer)
    imdb_id = db.Column(db.String(20), unique=True, nullable=True)
    subtitles = db.relationship('Subtitle', backref='movie', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Movie {self.title}>'

class Subtitle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False, index=True) # Added index for performance
    start_time = db.Column(db.String(20), nullable=True)
    end_time = db.Column(db.String(20), nullable=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), nullable=False)

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
        # Robust search: Filter subtitles where text matches query
        # We use a join to ensure the movie relationship is valid (though backref usually handles this)
        subtitles = Subtitle.query.join(Movie).filter(Subtitle.text.ilike(f'%{query}%')).limit(100).all()
    else:
        subtitles = [] 
    return render_template('index.html', subtitles=subtitles, query=query)

@app.route('/quote/<int:subtitle_id>')
def quote_detail(subtitle_id):
    subtitle = Subtitle.query.get_or_404(subtitle_id)
    movie = subtitle.movie
    tmdb_data = get_movie_data(movie.title, movie.year, country_code="NG")
    
    # Fetch Context (Previous and Next lines)
    prev_subtitle = Subtitle.query.filter_by(movie_id=movie.id).filter(Subtitle.id < subtitle.id).order_by(Subtitle.id.desc()).first()
    next_subtitle = Subtitle.query.filter_by(movie_id=movie.id).filter(Subtitle.id > subtitle.id).order_by(Subtitle.id.asc()).first()

    return render_template('quote_detail.html', 
                         subtitle=subtitle, 
                         prev_subtitle=prev_subtitle,
                         next_subtitle=next_subtitle,
                         watch_link=tmdb_data.get('watch_link'),
                         tmdb_id=tmdb_data.get('tmdb_id'),
                         poster_url=tmdb_data.get('poster_url'))

@app.route('/api/autocomplete')
def autocomplete():
    q = request.args.get('q', '')
    if not q or len(q) < 2:
        return jsonify([])
    
    # Improved Autocomplete: Join with Movie to return correct title
    results = db.session.query(Subtitle, Movie).join(Movie).filter(Subtitle.text.ilike(f'%{q}%')).limit(5).all()
    
    suggestions = []
    for sub, movie in results:
        suggestions.append({
            'id': sub.id,
            'text': sub.text,
            'movie': movie.title,
            'year': movie.year
        })
    return jsonify(suggestions)

@app.route('/api/export_movies')
def export_movies():
    movies = Movie.query.all()
    movie_list = [{'title': m.title, 'year': m.year} for m in movies]
    
    response = jsonify(movie_list)
    response.headers.set('Content-Disposition', 'attachment', filename='quoted_movies.json')
    return response

@app.route('/add', methods=['GET', 'POST'])
@app.route('/add', methods=['GET', 'POST'])
def add_entry():
    if request.method == 'POST':
        user_title = request.form.get('title').strip()
        try:
            user_year = int(request.form.get('year'))
        except ValueError:
            flash('Invalid year format.', 'error')
            return redirect(request.url)
        
        if 'subtitle_file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
            
        file = request.files['subtitle_file']
        
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)

        # --- Metadata Verification ---
        from tmdb_client import search_movie_metadata
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

        # Case-insensitive check for existing movie with same year
        existing_movie = Movie.query.filter(
            func.lower(Movie.title) == func.lower(movie_title),
            Movie.year == movie_year
        ).first()
        
        if existing_movie:
            flash(f"Subtitles for '{existing_movie.title}' ({existing_movie.year}) are already in the database.", 'info')
            return redirect(url_for('index'))

        if not file.filename.lower().endswith('.srt'):
            flash('Invalid file format. Please upload a .srt file.', 'error')
            return redirect(request.url)

        content = ""
        try:
            content = file.read().decode('utf-8')
        except UnicodeDecodeError:
            try:
                file.seek(0) 
                content = file.read().decode('latin-1')
            except Exception as e:
                flash(f'Encoding error: {str(e)}', 'error')
                return redirect(request.url)

        parsed_subs = parse_srt(content)
        
        if not parsed_subs:
            flash('Could not parse subtitles. The file format might be incorrect or empty.', 'error')
            return redirect(request.url)

        try:
            # Create new movie
            new_movie = Movie(title=movie_title, year=movie_year, imdb_id=imdb_id)
            db.session.add(new_movie)
            db.session.commit()
            movie_id = new_movie.id
            flash(f"Added new movie: {movie_title} ({movie_year})", 'success')
            
            new_subs = []
            for sub_data in parsed_subs:
                new_subs.append(Subtitle(
                    text=sub_data['text'],
                    start_time=sub_data['start'],
                    end_time=sub_data['end'],
                    movie_id=movie_id # Explicitly link using ID
                ))
            
            db.session.add_all(new_subs)
            db.session.commit()
            
            flash(f'Successfully imported {len(parsed_subs)} lines for "{movie_title}"!', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Database error: {str(e)}', 'error')
            return redirect(request.url)

    return render_template('add.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)