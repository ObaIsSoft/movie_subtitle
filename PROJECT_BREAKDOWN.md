# Quoted — The Complete Technical Deep-Dive

> Written as if you've never seen code before. Every concept has a real-world analogy.

---

## Table of Contents

1. [How the Database Works](#1-how-the-database-works)
2. [How We Access and Manipulate Data](#2-how-we-access-and-manipulate-data)
3. [Every Function Explained](#3-every-function-explained)
4. [Security — How We Protect Things](#4-security--how-we-protect-things)
5. [Docker — Why and How](#5-docker--why-and-how)
6. [Performance — Reducing Wait Times](#6-performance--reducing-wait-times)
7. [How the Frontend Works](#7-how-the-frontend-works)
8. [External APIs — Talking to Other Services](#8-external-apis--talking-to-other-services)
9. [Deployment — How It Goes Live](#9-deployment--how-it-goes-live)

---

## 1. How the Database Works

### The Analogy: A Filing Cabinet

Imagine your database is a **filing cabinet** in an office.

- The filing cabinet itself = **PostgreSQL** (the database server)
- Each drawer = a **table** (Movie, Subtitle, AppSettings)
- Each folder in a drawer = a **row** (one movie, one subtitle line)
- The labels on each folder = **columns** (title, year, text, etc.)

Your app has three drawers:

#### Drawer 1: The `Movie` Table

| id | title | year | imdb_id |
|----|-------|------|---------|
| 1 | The Godfather | 1972 | tt0068646 |
| 2 | Forrest Gump | 1994 | tt0109830 |
| 3 | The Dark Knight | 2008 | tt0468569 |

Every movie gets an `id` that the database auto-generates (1, 2, 3...). This is the **primary key** — like a unique serial number stamped on every folder.

The `imdb_id` is marked `unique=True`, meaning no two movies can have the same IMDb ID. This prevents accidentally importing the same movie twice.

#### Drawer 2: The `Subtitle` Table

| id | text | start_time | end_time | movie_id |
|----|------|-----------|---------|----------|
| 1 | I'm gonna make him an offer he can't refuse | 00:01:23,000 | 00:01:27,000 | 1 |
| 2 | Leave the gun. Take the cannoli. | 00:45:12,000 | 00:45:14,000 | 1 |
| 3 | Life is like a box of chocolates | 00:12:05,000 | 00:12:08,000 | 2 |

Notice `movie_id` — it tells us which movie each subtitle belongs to. Subtitle #1 has `movie_id = 1`, which points to "The Godfather". This is a **foreign key** — it's like writing "see Drawer 1, Folder #1" on a folder in Drawer 2.

**Real-world analogy:** Think of a school. Each student (subtitle) belongs to a class (movie). The student's enrollment card has a "Class ID" field that says which class they're in. That's a foreign key.

#### Drawer 3: The `AppSettings` Table

| key | value |
|-----|-------|
| fetch_cycle | 3 |

This is a tiny table that just remembers one thing: which batch of movies to fetch next time the daily cron job runs. Think of it as a **bookmark** — "I left off on page 3."

### How Tables Are Created

In [`app.py`](file:///Users/obafemi/Documents/dev/movie_subtitle/app.py#L45-L70), the tables are defined as Python classes:

```python
class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    year = db.Column(db.Integer)
    imdb_id = db.Column(db.String(20), unique=True, nullable=True)
    subtitles = db.relationship('Subtitle', backref='movie', lazy=True, cascade="all, delete-orphan")
```

Let's decode each line:

| Code | What it means |
|------|--------------|
| `class Movie(db.Model)` | "Create a table called Movie" |
| `id = db.Column(db.Integer, primary_key=True)` | "Give each row a unique auto-incrementing number" |
| `title = db.Column(db.String(200), nullable=False)` | "A text field, max 200 characters, cannot be empty" |
| `nullable=False` | "This field is required — you can't leave it blank" |
| `nullable=True` | "This field is optional — it's OK to leave it blank" |
| `unique=True` | "No two rows can have the same value here" |
| `subtitles = db.relationship(...)` | "Each movie has many subtitles — give me a shortcut to access them" |
| `backref='movie'` | "Also give each subtitle a shortcut to get back to its movie" |
| `cascade="all, delete-orphan"` | "If I delete a movie, automatically delete all its subtitles too" |

**The cascade analogy:** Imagine you're organising a school trip. If a class (movie) is cancelled, all the student registrations (subtitles) for that trip should be cancelled too. That's what cascade does — it prevents "orphan" records (subtitles that belong to a movie that no longer exists).

### Connecting to the Database

In [`app.py:22`](file:///Users/obafemi/Documents/dev/movie_subtitle/app.py#L22):

```python
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL').replace("postgres://", "postgresql://", 1)
```

This is the **connection string** — like a phone number for your database. It tells Python:
- What type of database (`postgresql://`)
- Who you are (`obafemi`)
- Where the database is (`localhost` for local, or a Fly.io URL for production)
- Which specific database (`movie_subtitle_db`)

The `.replace("postgres://", "postgresql://")` part is a compatibility fix. Fly.io gives you a URL starting with `postgres://`, but SQLAlchemy requires `postgresql://`. Same thing, different spelling — we just fix it automatically.

---

## 2. How We Access and Manipulate Data

### Reading Data (Queries)

Every time someone searches for a quote, we need to **ask the database a question**. In databases, questions are called **queries**.

**Analogy:** Imagine walking up to a librarian and saying "Find me all books that mention 'chocolate' in the title." The librarian goes through the catalog and brings back a stack of matching books. That's a query.

#### The Main Search Query

[`app.py:80`](file:///Users/obafemi/Documents/dev/movie_subtitle/app.py#L80):
```python
subtitles = Subtitle.query.join(Movie).filter(Subtitle.text.ilike(f'%{query}%')).limit(100).all()
```

Let's break this apart piece by piece:

| Part | What it does | Analogy |
|------|-------------|---------|
| `Subtitle.query` | "I want to search the Subtitle table" | "Go to the subtitle drawer" |
| `.join(Movie)` | "Also pull in the related Movie data" | "And grab the movie folder too while you're there" |
| `.filter(Subtitle.text.ilike(f'%{query}%'))` | "Only keep rows where the text contains my search term" | "Only bring back folders where the label contains 'chocolate'" |
| `ilike` | "Case-insensitive matching" | "Treat 'CHOCOLATE' and 'chocolate' as the same" |
| `%query%` | "The search term can appear anywhere in the text" | The `%` signs mean "anything can come before or after" |
| `.limit(100)` | "Give me at most 100 results" | "Don't bring me the entire library, just the first 100" |
| `.all()` | "Execute the query and give me a list" | "OK, go fetch them now" |

**Without the `.all()` at the end, nothing actually happens.** The query is just a plan — like writing a shopping list. `.all()` is when you actually go to the store.

#### The Autocomplete Query

[`app.py:112`](file:///Users/obafemi/Documents/dev/movie_subtitle/app.py#L112):
```python
results = db.session.query(Subtitle, Movie).join(Movie).filter(Subtitle.text.ilike(f'%{q}%')).limit(5).all()
```

Almost identical to the search, but:
- Returns both the `Subtitle` AND `Movie` objects (so we can show the movie title in the dropdown)
- Limited to 5 results (autocomplete should be fast and concise)

#### Finding a Specific Quote

[`app.py:87`](file:///Users/obafemi/Documents/dev/movie_subtitle/app.py#L87):
```python
subtitle = Subtitle.query.get_or_404(subtitle_id)
```

`get_or_404` means: "Find the subtitle with this exact ID. If it doesn't exist, show a 404 error page."

**Analogy:** "Bring me folder #42 from the subtitle drawer. If there's no folder #42, tell the customer 'not found'."

#### Getting Context (Previous and Next Lines)

[`app.py:92-93`](file:///Users/obafemi/Documents/dev/movie_subtitle/app.py#L92-L93):
```python
prev_subtitle = Subtitle.query.filter_by(movie_id=movie.id).filter(Subtitle.id < subtitle.id).order_by(Subtitle.id.desc()).first()
next_subtitle = Subtitle.query.filter_by(movie_id=movie.id).filter(Subtitle.id > subtitle.id).order_by(Subtitle.id.asc()).first()
```

This finds the lines spoken just **before** and **after** the matched quote, to give context.

For the previous line:
1. `filter_by(movie_id=movie.id)` — same movie only
2. `filter(Subtitle.id < subtitle.id)` — only lines that come before this one
3. `order_by(Subtitle.id.desc())` — sort them newest-first
4. `.first()` — grab just the top one (the one immediately before)

**Analogy:** You found page 42 in a book. To get context, you also look at page 41 (previous) and page 43 (next).

### Writing Data (Inserts)

#### Adding a New Movie and Its Subtitles

[`app.py:254-272`](file:///Users/obafemi/Documents/dev/movie_subtitle/app.py#L254-L272):
```python
# Step 1: Create the movie
new_movie = Movie(title=movie_title, year=movie_year, imdb_id=imdb_id)
db.session.add(new_movie)
db.session.commit()

# Step 2: Create all the subtitles
new_subs = []
for sub_data in parsed_subs:
    new_subs.append(Subtitle(
        text=sub_data['text'],
        start_time=sub_data['start'],
        end_time=sub_data['end'],
        movie_id=new_movie.id
    ))

db.session.add_all(new_subs)
db.session.commit()
```

**Understanding `session`, `add`, and `commit`:**

Think of a database transaction like writing a letter at the post office:

1. **`db.session`** = your desk at the post office. You can write and modify your letter here.
2. **`db.session.add(new_movie)`** = you've written the letter and placed it in the "outbox" tray. It's NOT mailed yet.
3. **`db.session.commit()`** = you hand the tray to the mail carrier. NOW it's permanent. It's been sent.

Why the two-step process? Because if something goes wrong between adding the movie and adding the subtitles, you can **undo everything**:

```python
except Exception as e:
    db.session.rollback()  # "Shred all the letters in the outbox — pretend nothing happened"
```

**`db.session.rollback()`** is your undo button. If the subtitles fail to save, the movie also gets undone, so you don't end up with a movie that has zero quotes.

### Checking for Duplicates

[`app.py:224-227`](file:///Users/obafemi/Documents/dev/movie_subtitle/app.py#L224-L227):
```python
existing_movie = Movie.query.filter(
    func.lower(Movie.title) == func.lower(movie_title),
    Movie.year == movie_year
).first()
```

Before adding a movie, we check if it already exists. `func.lower()` converts both the stored title and the user's input to lowercase, so "The Godfather" matches "the godfather".

**Analogy:** Before buying a book, you check your bookshelf to see if you already own it.

---

## 3. Every Function Explained

### `app.py` Functions

#### `index()` — The Home Page

```python
@app.route('/')
def index():
    query = request.args.get('q')
    if query:
        subtitles = Subtitle.query.join(Movie).filter(Subtitle.text.ilike(f'%{query}%')).limit(100).all()
    else:
        subtitles = []
    return render_template('index.html', subtitles=subtitles, query=query)
```

**Step by step:**
1. `@app.route('/')` — "When someone visits the homepage..."
2. `request.args.get('q')` — Check the URL for a search term. If the URL is `/?q=chocolate`, then `query = "chocolate"`. If just `/`, then `query = None`.
3. If there's a query, search the database. If not, return an empty list.
4. `render_template` — Take the `index.html` template, fill in the `subtitles` and `query` variables, and send the finished HTML page back to the browser.

**Analogy:** A restaurant waiter. The customer (browser) places an order (URL). The waiter checks if there are special requests (query parameters). Goes to the kitchen (database), gets the food (data), plates it nicely (template), and brings it to the table (HTTP response).

#### `quote_detail(subtitle_id)` — Single Quote Page

```python
@app.route('/quote/<int:subtitle_id>')
def quote_detail(subtitle_id):
    subtitle = Subtitle.query.get_or_404(subtitle_id)
    movie = subtitle.movie
    tmdb_data = get_movie_data(movie.title, movie.year, country_code="NG")
    ...
```

`<int:subtitle_id>` in the URL pattern means: "There will be a number here, capture it." So `/quote/42` sets `subtitle_id = 42`.

`subtitle.movie` — Remember the `backref='movie'` we set up earlier? This is it in action. Without it, we'd have to write another query like `Movie.query.get(subtitle.movie_id)`. The backref gives us a free shortcut.

`country_code="NG"` — Nigeria. When fetching streaming availability from TMDB, we ask for Nigerian providers first.

#### `autocomplete()` — Live Search Suggestions

```python
@app.route('/api/autocomplete')
def autocomplete():
    q = request.args.get('q', '')
    if not q or len(q) < 2:
        return jsonify([])
    ...
    return jsonify(suggestions)
```

`len(q) < 2` — Don't search if the user has typed less than 2 characters. Searching for "a" would match nearly everything and be useless.

`jsonify()` — Converts a Python list/dictionary into **JSON** format. JSON is the universal language for sending data between a server and a browser.

**Analogy:** `render_template` is like serving a plated meal (HTML page). `jsonify` is like handing over raw ingredients (data) — the browser's JavaScript will do the cooking (rendering).

#### `transcribe_audio()` — Voice Search Backend

```python
@app.route('/api/transcribe', methods=['POST'])
@limiter.limit("10 per hour")
def transcribe_audio():
```

`methods=['POST']` — This endpoint only accepts POST requests (data being sent TO the server), not GET requests (data being requested FROM the server). You POST audio data to it.

`@limiter.limit("10 per hour")` — Each user can only call this 10 times per hour. Why? Because every call costs money (OpenAI charges per audio minute). Without this limit, someone could write a script that calls it 10,000 times and run up your bill.

**The temporary file dance ([lines 135-158](file:///Users/obafemi/Documents/dev/movie_subtitle/app.py#L135-L158)):**

```python
with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_audio:
    audio_file.save(temp_audio.name)
    temp_path = temp_audio.name

# ... send to OpenAI ...

os.remove(temp_path)  # Clean up
```

The OpenAI API needs an actual file on disk, not data in memory. So we:
1. Create a temporary file (like a scratch piece of paper)
2. Save the uploaded audio to it
3. Send it to OpenAI
4. Delete the temp file (throw away the scratch paper)

**Why `delete=False`?** By default, temp files auto-delete when closed. We need it to stick around until OpenAI is done reading it, so we delete it manually later.

**The error handling ([lines 168-172](file:///Users/obafemi/Documents/dev/movie_subtitle/app.py#L168-L172)):**

```python
except Exception as e:
    if 'temp_path' in locals() and os.path.exists(temp_path):
        os.remove(temp_path)
    return jsonify({'error': str(e)}), 500
```

If anything goes wrong, we still clean up the temp file. `'temp_path' in locals()` checks if the variable was even created (the crash might have happened before we got that far). This prevents leaving junk files on the server.

#### `add_entry()` — Manual Upload

This is the longest function. Here's the flow:

```
User fills in title + year + uploads .srt file
    │
    ▼
Validate year is a number
    │
    ▼
Validate a file was uploaded
    │
    ▼
Ask TMDB: "Is this a real movie?" (metadata verification)
    │ 
    ├── TMDB found it → use TMDB's corrected title/year/IMDb ID
    │                    "You typed 'Godfther 1972' → corrected to 'The Godfather 1972'"
    │
    └── TMDB didn't find it → use what the user typed as-is
    │
    ▼
Check: is this movie already in our database?
    │
    ├── Yes → flash "already exists" message, redirect home
    │
    └── No → continue
    │
    ▼
Check: is the file actually a .srt file?
    │
    ▼
Read the file content (try UTF-8 encoding, fall back to Latin-1)
    │
    ▼
Parse the .srt content into structured data
    │
    ▼
Save movie + all subtitles to database
    │
    ▼
Flash success message, redirect home
```

**The encoding dance ([lines 237-246](file:///Users/obafemi/Documents/dev/movie_subtitle/app.py#L237-L246)):**

```python
try:
    content = file.read().decode('utf-8')
except UnicodeDecodeError:
    file.seek(0)
    content = file.read().decode('latin-1')
```

Text files can be encoded in different ways. **UTF-8** is the modern standard (handles emojis, accents, etc.). **Latin-1** is an older encoding common in European subtitle files.

**Analogy:** Imagine receiving a letter. You try to read it in English first. If the words look like gibberish, you try reading it in French. `file.seek(0)` means "go back to the beginning of the letter" (because you already read through it once during the first attempt).

### `srt_parser.py` — How .srt Files Are Parsed

#### `parse_srt(srt_content)`

An .srt file looks like this:

```
1
00:01:23,000 --> 00:01:27,000
I'm gonna make him an offer
he can't refuse.

2
00:01:28,000 --> 00:01:30,500
<i>That's my family, Kay.</i>
```

The parser breaks it down:

**Step 1: Normalise line endings**
```python
srt_content = srt_content.replace('\r\n', '\n').replace('\r', '\n')
```
Windows uses `\r\n` for new lines, Mac uses `\n`, old Mac used `\r`. We convert everything to `\n` so we don't have to worry about it.

**Analogy:** Some people end sentences with "." and some with "。" (Japanese period). We convert all of them to "." so our parsing rules work consistently.

**Step 2: Split into blocks**
```python
blocks = srt_content.strip().split('\n\n')
```
Each subtitle entry is separated by a blank line. `.split('\n\n')` chops the file at every blank line, giving us a list of blocks.

**Step 3: Find the timestamp**
```python
time_pattern = re.compile(r'(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})')
```

This is a **regular expression** (regex) — a pattern-matching language. It says:

```
\d{2}     → exactly 2 digits (like "00" or "23")
:         → a literal colon
\d{2}     → 2 more digits
:         → another colon
\d{2}     → 2 more digits
[,.]      → either a comma or a dot
\d{3}     → exactly 3 digits (milliseconds)
\s*       → any amount of whitespace
-->       → the literal arrow
```

So it matches patterns like `00:01:23,000 --> 00:01:27,000`.

**Analogy:** A regex is like a stencil. You lay it over text and it only lets through text that fits the holes in the stencil.

**Step 4: Clean the text**
```python
full_text = " ".join(text_lines)                    # Join multi-line text
clean_text = re.sub(r'<[^>]+>', '', full_text)      # Remove HTML tags
clean_text = clean_text.replace('- ', '').strip()   # Remove dialogue markers
```

- `" ".join(text_lines)` — If the subtitle spans two lines, merge them into one with a space
- `re.sub(r'<[^>]+>', '', ...)` — Removes HTML tags like `<i>`, `</i>`, `<b>`, etc. The regex `<[^>]+>` means "anything between < and >"
- `.replace('- ', '')` — Removes the dash at the start of lines (used when two characters are speaking in the same subtitle block)

### `tmdb_client.py` — Talking to TMDB

#### `get_movie_data(title, year, country_code)` — Get Poster + Streaming Links

This function makes **two HTTP requests** to TMDB:

**Request 1: Find the movie**
```python
search_url = f"{BASE_URL}/search/movie"
params = {"api_key": API_KEY, "query": title}
response = requests.get(search_url, params=params)
```

`requests.get()` is like your app making a phone call to TMDB: "Hey, do you have a movie called 'The Godfather'?"

TMDB responds with JSON data containing the movie's ID and poster path.

**Request 2: Get streaming providers**
```python
provider_url = f"{BASE_URL}/movie/{movie_id}/watch/providers"
p_response = requests.get(provider_url, params={"api_key": API_KEY})
```

"Now that I know the movie ID, where can people stream it?"

**The country fallback chain ([lines 58-64](file:///Users/obafemi/Documents/dev/movie_subtitle/tmdb_client.py#L58-L64)):**
```python
if country_code in results:         # Try Nigeria first
    watch_link = results[country_code].get('link')
elif 'US' in results:               # Fall back to US
    watch_link = results['US'].get('link')
elif results:                        # Fall back to any country
    first_key = next(iter(results))
    watch_link = results[first_key].get('link')
```

**Analogy:** You're looking for a product online. First you check if it ships to Nigeria. If not, check if it ships to the US. If not, check if it ships anywhere at all.

#### `discover_popular_movies(year, page)` — Find Movies to Auto-Import

```python
params = {
    "primary_release_year": year,
    "sort_by": "popularity.desc",
    "vote_count.gte": 100
}
```

This asks TMDB: "Give me the most popular movies from [year], sorted by popularity, but only ones with at least 100 votes." The vote count filter prevents importing obscure movies that nobody would search for.

**The N+1 problem ([lines 117-133](file:///Users/obafemi/Documents/dev/movie_subtitle/tmdb_client.py#L117-L133)):**

TMDB's discover endpoint returns movie titles but NOT their IMDb IDs. We need IMDb IDs to search OpenSubtitles. So for each movie in the list, we make ANOTHER API call to get the details:

```python
for result in data.get('results', []):
    # This is an EXTRA HTTP call for EACH movie
    detail_url = f"{BASE_URL}/movie/{movie_id}"
    d_response = requests.get(detail_url, params={"api_key": API_KEY})
```

If TMDB returns 20 movies, that's 1 + 20 = **21 HTTP requests**. This is called the **N+1 problem** — you make 1 query to get a list, then N more queries to get details for each item.

**Analogy:** You ask a receptionist for a list of 20 guests. Then you call each guest individually to ask for their phone number. It would be much faster if the receptionist just included phone numbers in the original list.

### `fetch_from_api.py` — The Auto-Populate Engine

#### `get_api_token(session)` — Logging In

```python
payload = {"username": CONFIG["USERNAME"], "password": CONFIG["PASSWORD"]}
headers = {"Content-Type": "application/json", "Api-Key": CONFIG["API_KEY"]}
r = session.post(login_url, json=payload, headers=headers)
return data.get('token')
```

OpenSubtitles uses **token-based authentication**:

1. You send your username/password
2. They send back a **token** (a long random string)
3. You include this token in all future requests

**Analogy:** Checking into a hotel. You show your ID at the front desk (login). They give you a keycard (token). You use the keycard to access your room, the pool, the gym (API endpoints). You don't show your ID every single time.

**Why `session = requests.Session()`?**

A `Session` object reuses the same network connection across multiple requests. Without it, every API call would open a new connection (like hanging up the phone and redialling for every question). With a session, you keep the line open.

#### `find_best_subtitle(subtitle_list)` — Picking the Best File

```python
for sub in subtitle_list:
    attrs = sub.get('attributes', {})
    if attrs.get('ai_translated') == True: continue    # Skip AI translations
    if not attrs.get('files'): continue                 # Skip if no file
    clean_subs.append(attrs)

clean_subs.sort(key=lambda s: s.get('download_count', 0), reverse=True)
return clean_subs[0]['files'][0]['file_id']
```

OpenSubtitles often has multiple subtitle files for the same movie. This function picks the best one:

1. **Reject AI-translated subtitles** — they're often lower quality
2. **Reject entries with no downloadable files**
3. **Sort by download count** — the most-downloaded subtitle is usually the most accurate
4. **Return the top result's file ID**

**`lambda s: s.get('download_count', 0)`** — A lambda is a tiny one-line function. This one says: "For each subtitle `s`, get its download count (or 0 if it doesn't have one)." It's used as the sorting key.

**Analogy:** You're at a restaurant reading reviews. You filter out chain restaurants, filter out closed ones, sort by number of reviews (most reviewed first), and pick the top result.

#### `fetch_movie_subtitles(...)` — The Core Import Function

This function does everything needed to import one movie:

```
1. Check if movie already exists → skip if yes
2. Search OpenSubtitles for English subtitles for this IMDb ID
3. Pick the best subtitle file
4. Request a download link (OpenSubtitles generates temporary URLs)
5. Download the actual .srt content
6. Parse it with srt_parser
7. Save the movie to the database
8. Save every subtitle line to the database
```

**Rate limiting with `time.sleep(2)` ([line 186](file:///Users/obafemi/Documents/dev/movie_subtitle/fetch_from_api.py#L186)):**

```python
time.sleep(2)  # Wait 2 seconds between downloads
```

This pauses execution for 2 seconds between each movie download. Why? Because if we hammered OpenSubtitles' API with rapid-fire requests, they would:
1. Temporarily block us (rate limiting)
2. Potentially ban our API key permanently

**Analogy:** If you're at a buffet, you take one plate at a time and come back. You don't shove all the food into a wheelbarrow — they'll kick you out.

---

## 4. Security — How We Protect Things

### Environment Variables (.env)

**The problem:** Your app needs API keys and passwords to function. If you put them directly in the code:

```python
# ❌ NEVER DO THIS
API_KEY = "abc123-your-real-key-here"
```

Anyone who sees your code (GitHub, a screenshot, a colleague) gets your keys.

**The solution:** Store secrets in a `.env` file and load them at runtime:

```python
# ✅ The code only contains the variable name, not the value
API_KEY = os.getenv("OPENSUBTITLES_API_KEY")
```

The actual value lives in the `.env` file, which is excluded from Git via `.gitignore`.

**For production (Cloud Run):** Secrets are set as environment variables on the Cloud Run service (ideally backed by Secret Manager). They're encrypted and never visible in your code or repository.

**Analogy:** Your code is a recipe that says "add salt to taste." The `.env` file is your actual salt shaker. You share the recipe with everyone, but you keep your salt shaker in your own kitchen.

> ⚠️ **Current issue:** Your `.env` file appears to have been committed to Git at some point. The keys in it should be considered compromised and rotated.

### Rate Limiting

[`app.py:32-37`](file:///Users/obafemi/Documents/dev/movie_subtitle/app.py#L32-L37):
```python
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)
```

| Setting | What it means |
|---------|--------------|
| `get_remote_address` | "Identify users by their IP address" |
| `200 per day` | "Each IP can make at most 200 requests per day" |
| `50 per hour` | "Each IP can make at most 50 requests per hour" |
| `storage_uri="memory://"` | "Store the counters in memory" (resets when the server restarts) |

The transcribe endpoint has a stricter limit:
```python
@limiter.limit("10 per hour")  # Because each call costs money (OpenAI)
```

**Analogy:** A nightclub bouncer. Everyone can enter (200/day), but if you keep going in and out too much (50/hour), you're cut off. The VIP room (transcription) has an even stricter policy (10/hour).

**What `"memory://"` means:** The rate limit counters are stored in the server's RAM, not in a database. If the server restarts, everyone's counters reset to zero. For a stricter setup, you'd use Redis (a fast in-memory database that persists across restarts).

### Input Validation

**File type checking ([`app.py:233-235`](file:///Users/obafemi/Documents/dev/movie_subtitle/app.py#L233-L235)):**
```python
if not file.filename.lower().endswith('.srt'):
    flash('Invalid file format. Please upload a .srt file.', 'error')
    return redirect(request.url)
```

Only `.srt` files are accepted. This runs **server-side** (Python), not just client-side (JavaScript). Why both?

- **Client-side validation** (the JavaScript in `add.html`) gives instant feedback — the user doesn't have to wait for a server round-trip
- **Server-side validation** actually enforces the rule — someone could easily bypass the JavaScript by sending requests directly to your API

**Analogy:** A locked door with a sign that says "Authorised Personnel Only." The sign (JavaScript) is a courtesy notice. The lock (Python) is what actually prevents entry.

**Year validation ([`app.py:188-192`](file:///Users/obafemi/Documents/dev/movie_subtitle/app.py#L188-L192)):**
```python
try:
    user_year = int(request.form.get('year'))
except ValueError:
    flash('Invalid year format.', 'error')
    return redirect(request.url)
```

`int()` converts text to a number. If someone types "abc" instead of "1972", `int("abc")` throws a `ValueError`. We catch it and show an error message.

### How SQLAlchemy Prevents SQL Injection

When you write:
```python
Subtitle.query.filter(Subtitle.text.ilike(f'%{query}%'))
```

SQLAlchemy doesn't just paste the user's input into the SQL string. It uses **parameterised queries**:

```sql
-- What SQLAlchemy actually sends to the database:
SELECT * FROM subtitle WHERE text ILIKE %(text_1)s
-- With parameter: text_1 = '%chocolate%'
```

The database treats `%(text_1)s` as pure data, not as SQL code. Even if someone searches for `'; DROP TABLE movie; --` (a classic attack), it's treated as literal text, not as a command.

**Analogy:** Imagine a form where you write your name. SQL injection is like writing "John; please also give me everyone's passwords" and the system executing it. Parameterised queries treat everything you write in the name field as a name, no matter what you write. The form doesn't execute instructions — it only stores text.

---

## 5. Docker — Why and How

### What Problem Does Docker Solve?

**The "it works on my machine" problem:**

Your Mac has Python 3.11, a specific version of PostgreSQL, certain system libraries. But the Fly.io server might have different versions. Your code might work locally but break in production because of tiny differences.

**Docker's solution:** Package your app + all its dependencies into a **container** — a lightweight virtual environment that runs identically everywhere.

**Analogy:** Imagine you're a chef who wants to cook the same dish at different restaurants. Instead of hoping each restaurant has the right ingredients and equipment, you bring your own portable kitchen (container) with everything pre-installed. You plug it in, and it produces the exact same meal every time, regardless of which restaurant you're in.

### The Dockerfile Line by Line

[`Dockerfile`](file:///Users/obafemi/Documents/dev/movie_subtitle/Dockerfile):

```dockerfile
FROM python:3.11-slim
```
**"Start with a pre-built Python 3.11 environment."**
`slim` means a minimal version — no extra tools we don't need. This keeps the container small and fast to build.

**Analogy:** Instead of building a kitchen from scratch, you start with a basic pre-fab kitchen that already has a stove, sink, and fridge.

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*
```
**"Install system-level tools."**
- `postgresql-client` — tools to interact with Postgres (needed for database setup)
- `curl` — a tool for downloading files from the internet (used to download Supercronic)
- `rm -rf /var/lib/apt/lists/*` — clean up the package cache to keep the image small

**Analogy:** Installing appliances in the kitchen — a blender and a mixer.

```dockerfile
WORKDIR /app
```
**"Everything from now on happens inside the `/app` folder."**

Like saying "this shelf is where all our recipe books go."

```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```
**"Copy the ingredients list, then install all ingredients."**

We copy `requirements.txt` FIRST and install dependencies BEFORE copying the rest of the code. Why? **Docker caching.** Docker remembers each step. If your code changes but your dependencies don't, Docker skips the (slow) pip install and reuses the cached result. If we copied everything first, any code change would invalidate the cache and force a full reinstall.

**Analogy:** You stock the pantry (install dependencies) before writing today's special menu (copying code). If you change the menu tomorrow, you don't need to restock the pantry.

```dockerfile
# Install Supercronic
ENV SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/...
RUN curl -fsSLO "$SUPERCRONIC_URL" \
    && echo "$SUPERCRONIC_SHA1SUM  $SUPERCRONIC" | sha1sum -c - \
    && chmod +x "$SUPERCRONIC" \
    && mv "$SUPERCRONIC" "/usr/local/bin/${SUPERCRONIC}" \
    && ln -s ... /usr/local/bin/supercronic
```
**"Download and install Supercronic (the cron scheduler for containers)."**

The `sha1sum -c -` part is a **checksum verification** — it confirms the downloaded file hasn't been tampered with. Like checking the seal on a medicine bottle.

```dockerfile
COPY . .
```
**"Copy all your application code into the container."**

```dockerfile
EXPOSE 8080
```
**"Tell Docker that this container listens on port 8080."** This is documentation, not enforcement — it's like putting a sign on a door saying "entrance here."

```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
```
**"When this container starts, run Gunicorn."**

`0.0.0.0` means "listen on all network interfaces" (accept connections from anywhere, not just localhost). `app:app` means "import the `app` variable from `app.py`."

---

## 6. Performance — Reducing Wait Times

### Debouncing (Autocomplete)

[`index.html:370`](file:///Users/obafemi/Documents/dev/movie_subtitle/templates/index.html#L370):
```javascript
debounceTimer = setTimeout(() => {
    fetch(`/api/autocomplete?q=${encodeURIComponent(query)}`)
    ...
}, 300);
```

Without debouncing, every keystroke triggers an API call. Typing "godfather" = 9 API calls (g, go, god, godf, godfa, godfat, godfath, godfahe, godfather).

With debouncing (300ms delay), we wait until the user **stops typing** for 300 milliseconds, then make ONE call. This typically reduces 9 calls to 1-2.

**Analogy:** When you're dictating to someone, you don't write down every syllable as they speak. You wait for them to finish a word, then write it down.

```javascript
clearTimeout(debounceTimer);  // Cancel the previous timer
debounceTimer = setTimeout(() => { ... }, 300);  // Start a new one
```

Every keystroke cancels the previous timer and starts a new one. Only when the user pauses for 300ms does the timer actually fire.

### Connection Reuse (requests.Session)

[`fetch_from_api.py:152`](file:///Users/obafemi/Documents/dev/movie_subtitle/fetch_from_api.py#L152):
```python
session = requests.Session()
session.headers.update({'User-Agent': 'MovieQuoteSearch v1.0'})
```

A `Session` keeps the TCP connection open between requests. Without it:

```
Request 1: Open connection → Send request → Get response → Close connection
Request 2: Open connection → Send request → Get response → Close connection
(repeat 50 times)
```

With a Session:
```
Open connection once
Request 1: Send request → Get response
Request 2: Send request → Get response
...
Request 50: Send request → Get response
Close connection
```

**Analogy:** Imagine calling a help desk. Without a session, you hang up after every question and call back, going through the menu system each time. With a session, you stay on the line and ask all your questions in one call.

### Lazy Loading (SQLAlchemy)

```python
subtitles = db.relationship('Subtitle', backref='movie', lazy=True)
```

`lazy=True` means: "Don't load the subtitles when I load a movie. Only load them if I actually ask for `movie.subtitles`."

If you load 100 movies and never access their subtitles, you've avoided loading potentially 150,000 subtitle rows. This is called **lazy loading**.

**Analogy:** A library catalog shows you book titles and locations. It doesn't photocopy every book and hand you the copies upfront — it waits for you to request a specific book, then retrieves it.

### What's NOT Optimised (Opportunities)

**1. No TMDB caching:**
Every time someone views a quote from "The Godfather", we call TMDB's API to get the poster. The poster doesn't change — we should cache it.

**2. Full table scan on search:**
`ILIKE '%term%'` scans every row in the subtitle table. With 100,000+ rows, this gets slow. A **trigram index** (GIN index) would make this dramatically faster.

**3. No pagination:**
Search results are limited to 100 but there's no "next page" button. If there are 500 matches, the user only sees the first 100.

---

## 7. How the Frontend Works

### Template Inheritance

Your HTML pages use **Jinja2 template inheritance** — a way to avoid repeating the same HTML structure on every page.

```
base.html (parent)
├── Navbar, fonts, CSS, footer, flash messages
├── {% block content %}{% endblock %}  ← "Put page-specific stuff here"
│
├── index.html (child)
│   {% extends 'base.html' %}
│   {% block content %}
│       Search bar, results, history sheet
│   {% endblock %}
│
├── quote_detail.html (child)
│   {% extends 'base.html' %}
│   {% block content %}
│       Poster, quote, streaming links
│   {% endblock %}
│
└── add.html (child)
    {% extends 'base.html' %}
    {% block content %}
        Upload form
    {% endblock %}
```

**Analogy:** A corporate letterhead template. Every letter (page) has the same header, logo, and footer (base.html). But the body content (block content) is different for each letter. You don't redesign the entire letterhead for every letter — you fill in the body.

### CSS Custom Properties (Design Tokens)

[`base.html:18-27`](file:///Users/obafemi/Documents/dev/movie_subtitle/templates/base.html#L18-L27):
```css
:root {
    --bg-black: #000000;
    --accent-yellow: #FFD700;
    --text-white: #ffffff;
    --text-grey: #b3b3b3;
    --input-bg: #1a1a1a;
    --border-color: #333333;
}
```

These are **CSS variables** — named colors you define once and use everywhere. To change the entire app's accent color from yellow to blue, you'd change ONE line (`--accent-yellow: #0088ff`) instead of finding and replacing yellow in 50 places.

**Analogy:** In a spreadsheet, instead of typing "10%" in every tax calculation cell, you define a named cell "TAX_RATE = 10%" and reference it. To change the tax rate, you update one cell.

### Flash Messages

```python
# In Python (app.py):
flash('Successfully imported 500 lines!', 'success')

# In HTML (base.html):
{% with messages = get_flashed_messages(with_categories=true) %}
    {% for category, message in messages %}
        <div class="alert">{{ message }}</div>
    {% endfor %}
{% endwith %}
```

Flash messages are **one-time notifications**. They appear once after a redirect and disappear when you navigate away (or after 10 seconds, thanks to the auto-dismiss JavaScript).

**Analogy:** A post-it note on your monitor. Someone sticks it there ("Upload complete!"), you read it, and you throw it away.

### localStorage (Search History)

```javascript
localStorage.setItem('quoteSearchHistory', JSON.stringify(history));
let history = JSON.parse(localStorage.getItem('quoteSearchHistory') || '[]');
```

`localStorage` is storage **in the user's browser**, not on your server. It persists even after closing the browser tab.

| Feature | localStorage | Database (PostgreSQL) |
|---------|-------------|----------------------|
| Where | User's browser | Your server |
| Who can see it | Only that user, on that device | Your server code |
| Persistence | Until cleared or browser data deleted | Until you delete it |
| Cost | Free | Server resources |

Search history uses localStorage because:
- It's per-user, per-device (private)
- It doesn't need to be shared across devices
- It doesn't cost you any server resources
- It works even if the user isn't logged in (you don't have user accounts)

**Analogy:** The "recently visited" list in your browser is stored on your device, not on every website you've visited. Quoted's search history works the same way.

---

## 8. External APIs — Talking to Other Services

Your app talks to **four external services**:

### TMDB (The Movie Database)

**What you get:** Movie posters, streaming links, metadata verification
**Authentication:** API key in the URL (`?api_key=...`)
**Cost:** Free (with reasonable usage)
**Used in:** [`tmdb_client.py`](file:///Users/obafemi/Documents/dev/movie_subtitle/tmdb_client.py)

### OpenSubtitles

**What you get:** Subtitle files (.srt) for movies
**Authentication:** API key in headers + username/password login → token
**Cost:** Free tier (has daily download limits)
**Used in:** [`fetch_from_api.py`](file:///Users/obafemi/Documents/dev/movie_subtitle/fetch_from_api.py)

### OpenAI (Whisper)

**What you get:** Audio-to-text transcription
**Authentication:** API key
**Cost:** $0.006 per minute of audio
**Used in:** [`app.py`](file:///Users/obafemi/Documents/dev/movie_subtitle/app.py#L150-L155) (the `/api/transcribe` endpoint)

### Web Speech API (Browser-native)

**What you get:** Real-time speech recognition
**Authentication:** None (it's a browser feature)
**Cost:** Free
**Used in:** [`audio_visualizer.js`](file:///Users/obafemi/Documents/dev/movie_subtitle/static/js/audio_visualizer.js#L94-L143)

**Why both OpenAI Whisper AND Web Speech API?**

Web Speech API is free and gives live transcription, but it **only works in Chrome and Edge**. Firefox and Safari don't support it. So:

```
Browser supports Web Speech API?
├── Yes (Chrome/Edge) → Use Web Speech API (free, live transcription)
└── No (Firefox/Safari) → Record audio → Send to OpenAI Whisper (paid, delayed)
```

The code detects this automatically:
```javascript
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const useWebSpeech = !!SpeechRecognition;  // true if the browser supports it
```

---

## 9. Deployment — How It Goes Live

### The Architecture

```
                    Internet
                       │
                       ▼
              ┌─── Fly.io ───┐
              │               │
              │  ┌─────────┐  │
              │  │   App   │  │ ← Gunicorn (web server)
              │  │ Process │  │   Handles user requests
              │  └────┬────┘  │
              │       │       │
              │  ┌────▼────┐  │
              │  │ Postgres │  │ ← Your database
              │  │    DB    │  │   Stores movies + subtitles
              │  └─────────┘  │
              │       ▲       │
              │  ┌────┴────┐  │
              │  │  Cron   │  │ ← Supercronic process
              │  │ Process │  │   Runs daily at 10:00 UTC
              │  └─────────┘  │
              │               │
              └───────────────┘
```

### What Happens When You `fly deploy`

1. **Build:** Docker reads the Dockerfile and creates a container image
2. **Push:** The image is uploaded to Fly's registry
3. **Release command:** `python init_db.py` runs — creates any new database tables
4. **Start processes:**
   - `app` process: Gunicorn starts serving web requests
   - `cron` process: Supercronic starts and waits for the scheduled time

### Fly.io Settings Explained

```toml
auto_stop_machines = 'stop'    # Shut down when no traffic (saves money)
auto_start_machines = true     # Restart when traffic arrives
min_machines_running = 0       # OK to have zero machines running
```

This means your app **goes to sleep** when nobody is using it. When someone visits the URL, Fly wakes it up (adds a few seconds to the first request). This keeps costs at $0 during quiet periods.

**Analogy:** A food truck that parks when there are no customers and drives back when someone calls. You only pay for gas when you're actually serving.

```toml
memory = '1gb'
cpu_kind = 'shared'
cpus = 1
```

Your app runs on a small, shared virtual machine with 1 CPU and 1GB of RAM. "Shared" means your CPU is shared with other Fly customers (cheaper but less predictable performance).
