# Beyond Quoted — Real-World Applications, Techniques & AI Advancements

Your project isn't just a movie quote finder. It's built on **engineering patterns** that power products across every industry. This document maps each pattern to real-world applications and shows where AI takes them further.

---

## The 7 Core Patterns in Quoted

Before we look at applications, let's name the **reusable building blocks** in your project:

| # | Pattern | Where in Quoted |
|---|---------|----------------|
| 1 | **Parse-and-Index Pipeline** | Upload .srt → parse → store every line in a searchable database |
| 2 | **Multi-API Orchestration** | Chain TMDB + OpenSubtitles + OpenAI together to produce one result |
| 3 | **Dual-Strategy Degradation** | Try Web Speech API first → fall back to OpenAI Whisper |
| 4 | **Scheduled Data Enrichment** | Cron job discovers new movies daily and auto-populates the database |
| 5 | **Hybrid Input Search** | Accept text input OR voice input, both produce the same search |
| 6 | **Metadata Enrichment** | Start with a subtitle line → enrich with poster, streaming links, context |
| 7 | **Cost-Aware Rate Limiting** | Free features are generous, paid features (Whisper) are strictly capped |

Every application below is built from a **combination** of these same patterns.

---

## Real-World Applications

### 1. Legal Document Search

**The problem:** Law firms have thousands of contracts, case files, and legal briefs. A lawyer needs to find the clause that says something about "indemnification in the event of gross negligence" — but every contract phrases it differently.

**How Quoted's logic applies:**

| Quoted | Legal Search |
|--------|-------------|
| Upload .srt files | Upload PDF/DOCX contracts |
| Parse subtitles into individual lines | Parse documents into clauses and paragraphs |
| Search `ILIKE '%offer%'` | Search for "indemnification" across all contracts |
| Show movie title + timestamp | Show document name + page number + section |
| TMDB poster enrichment | Enrich with client name, contract date, counterparty |

**AI advancement:** Vector search would let a lawyer search *"who's responsible if something goes wrong"* and find clauses about indemnification, liability, force majeure — even if those exact words aren't used. This is already a billion-dollar market (companies like Harvey AI, Casetext, and Ironclad do this).

**Real product examples:** Harvey AI, Casetext (acquired by Thomson Reuters for $650M)

---

### 2. Medical Symptom & Research Search

**The problem:** A doctor remembers reading about a treatment for a rare condition but can't remember which paper or which drug. They remember *roughly* what it said.

**How Quoted's logic applies:**

| Quoted | Medical Search |
|--------|---------------|
| .srt subtitle files | Medical research papers (PubMed) |
| Parse into individual lines | Parse into sentences, abstracts, findings |
| Search for a half-remembered quote | Search for a half-remembered finding |
| Show which movie, what timestamp | Show which paper, which section, which author |
| Voice search with Whisper | Doctor dictates symptoms, system finds matching conditions |

**AI advancement:** An LLM layer could understand medical context — searching *"the drug that lowers cholesterol by blocking that liver enzyme"* would find papers about statins and HMG-CoA reductase inhibitors, even though the user didn't use those terms.

**Real product examples:** Elicit, Semantic Scholar, UpToDate

---

### 3. E-Commerce Product Discovery

**The problem:** A customer remembers seeing a product but can't describe it properly. "That kitchen thing that spirals vegetables" → spiralizer. "The face cream from the ad with the blue jar" → hard to search for.

**How Quoted's logic applies:**

| Quoted | Product Discovery |
|--------|------------------|
| Subtitle text | Product descriptions, reviews, ad copy |
| Parse .srt files | Ingest product catalogues from suppliers |
| Search by text or voice | "Find me that thing that peels garlic automatically" |
| TMDB enrichment (poster, links) | Enrich with product image, price, buy link, reviews |
| Autocomplete suggestions | "Did you mean: garlic press / garlic peeler / garlic rocker?" |
| Scheduled auto-populate | Daily sync with supplier catalogues for new products |

**AI advancement:** Combine text search with **image search** — customer uploads a photo, vector search finds visually similar products. This is how Pinterest's "visual search" and Google Lens work.

**Real product examples:** Algolia, Coveo, Amazon's product search

---

### 4. Music Lyric Search (Direct Parallel)

**The problem:** You remember a lyric but not the song title or artist. "What's the song that goes 'is this the real life, is this just fantasy'?"

This is the **closest real-world parallel** to Quoted — just lyrics instead of movie subtitles.

| Quoted | Lyric Search |
|--------|-------------|
| .srt subtitle files | .lrc lyric files or scraped lyrics |
| Parse into timestamped lines | Parse into timestamped lyric lines |
| Search text | Search lyrics |
| Show movie + poster + streaming link | Show song + album art + Spotify/Apple Music link |
| Voice search → find the quote | Hum or sing → find the song |
| OpenSubtitles API | Genius API, Musixmatch API |
| TMDB API for posters | Spotify API for album art and playback |

**AI advancement:** Shazam already does audio fingerprinting (matching the actual sound). But for *humming* or *singing from memory*, Google's "Hum to Search" uses AI to match the melody — something audio fingerprinting can't do. Your voice search pattern is the same concept applied to text.

**Real product examples:** Genius, Musixmatch, Google's "Hum to Search"

---

### 5. Lecture & Educational Content Search

**The problem:** A student watched a 2-hour lecture and needs to find the part where the professor explained "the difference between TCP and UDP." Scrubbing through the video is painful.

**How Quoted's logic applies:**

| Quoted | Lecture Search |
|--------|---------------|
| .srt files from movies | Auto-generated transcripts from lectures (via Whisper) |
| Timestamped subtitle lines | Timestamped lecture segments |
| Search → shows timestamp | Search → **jump to that exact moment in the video** |
| Voice search | Student asks: "When did she talk about recursion?" |

**AI advancement:** Instead of just finding the timestamp, an LLM could **summarize** the relevant segment. "At 47:32, Professor Smith explains that TCP guarantees delivery order while UDP prioritises speed, using a postal service analogy."

**Real product examples:** Descript, Recall.ai, Notion's meeting notes, YouTube's transcript search

---

### 6. Customer Support Knowledge Base

**The problem:** A support agent gets a customer complaint: "My order arrived but the box was damaged and two items were missing." The agent needs to find the company's policy for this exact scenario.

**How Quoted's logic applies:**

| Quoted | Support KB |
|--------|-----------|
| Movie subtitle corpus | Internal policy documents, past ticket resolutions, SOPs |
| Parse and index | Index every paragraph of every policy document |
| Search | Agent types the customer's issue → finds relevant policy |
| Context (prev/next line) | Show surrounding paragraphs for full context |
| Voice search | Agent speaks the customer's complaint directly |
| Metadata enrichment | Enrich with: last updated date, which team owns this policy, resolution steps |

**AI advancement:** An LLM doesn't just FIND the policy — it **drafts the response** to the customer based on the policy. "Based on our Damaged Goods Policy (Section 4.2), I'd like to offer you a full replacement..."

**Real product examples:** Zendesk AI, Intercom Fin, Guru

---

### 7. Compliance & Regulatory Monitoring

**The problem:** A bank needs to monitor all employee communications (emails, chats) for phrases that might indicate insider trading, money laundering, or policy violations.

**How Quoted's logic applies:**

| Quoted | Compliance Monitoring |
|--------|----------------------|
| Ingest .srt files | Ingest emails, Slack messages, phone call transcripts |
| Parse into searchable lines | Parse into individual messages/segments |
| Search for specific phrases | Search for suspicious language patterns |
| Scheduled cron job | Continuous monitoring (not daily — real-time) |
| Rate limiting | Alert throttling (don't flood compliance officers with 10,000 alerts) |

**AI advancement:** Instead of searching for exact phrases like "buy before the announcement," an LLM can detect **intent** — "I heard something interesting at the board meeting, maybe we should increase our position" — which is harder to catch with keyword search.

**Real product examples:** Relativity, NICE Actimize, Smarsh

---

### 8. Real Estate Listing Search

**The problem:** A buyer wants "a 3-bedroom house with a big backyard near good schools, under $500K." Existing search filters (beds, baths, price) miss the nuance of "big backyard" and "near good schools."

| Quoted | Real Estate Search |
|--------|-------------------|
| Subtitle text | Listing descriptions written by agents |
| Search text | "big backyard near schools" |
| TMDB enrichment | Enrich with photos, map, school ratings, crime stats |
| Auto-populate from API | Pull listings from MLS (Multiple Listing Service) daily |
| Voice search | Speak: "I want something with a view, modern kitchen, within 20 minutes of downtown" |

**AI advancement:** Vector search over listing descriptions + LLM interpretation of "big" (relative to the area's average lot size), "near" (walking distance vs driving distance), "good schools" (GreatSchools rating > 7).

---

### 9. Podcast & Audio Content Search

**The problem:** "I heard a great interview where someone talked about the psychology of procrastination — was it on Huberman Lab or Tim Ferriss?"

| Quoted | Podcast Search |
|--------|---------------|
| .srt files | Auto-transcribed podcast episodes |
| Timestamped lines | Timestamped segments |
| Search + voice search | Search by topic or spoken query |
| Movie poster + title | Podcast artwork + episode title + timestamp link |
| Auto-populate cron job | Automatically transcribe new episodes as they're published |

**Real product examples:** Podchaser, Listen Notes, Snipd

---

### 10. Recipe & Food Search

**The problem:** "What's that pasta dish where you use the pasta water and cheese to make the sauce creamy? No cream involved."

| Quoted | Recipe Search |
|--------|-------------|
| Subtitle text | Recipe instructions and ingredient lists |
| Parse .srt files | Parse recipe pages/PDFs into structured steps |
| Search | "pasta water cheese no cream" → finds Cacio e Pepe |
| Enrichment | Show recipe image, prep time, nutrition info, shopping list |
| Voice search | Ask while cooking: "How long do I bake the chicken?" |

---

## AI Advancements That Apply to ALL of These

### 1. Vector / Semantic Search

**What it is:** Instead of matching exact words, convert text into mathematical representations (vectors) that capture **meaning**. "Happy" and "joyful" have similar vectors even though they share no letters.

**Quoted today:** `ILIKE '%offer%'` — literal substring match
**With vectors:** Search "make him a deal he can't say no to" → finds "I'm gonna make him an offer he can't refuse"

**Applies to:** Every single application above. This is the single biggest improvement you could make.

### 2. LLM-Powered Query Understanding

**What it is:** Before searching, pass the user's query through an LLM to understand what they *actually* want.

**Example:**
- User types: "that sad scene at the end of the robot movie"
- LLM interprets: movie genre = sci-fi/animation, tone = sad, position = climax/ending
- Searches for: sad quotes from sci-fi movies near the end (high timestamp)

**Applies to:** Product discovery, legal search, medical search — anywhere user queries are vague or conversational.

### 3. Recommendation Engine ("Similar Quotes")

**What it is:** Once you have embeddings for every subtitle, you can find "nearest neighbours" — quotes that are semantically similar to the one you're viewing.

**Example:** Viewing "I'm gonna make him an offer he can't refuse" → suggests:
- "Say hello to my little friend" (crime/threat context)
- "I am the law" (power/authority context)

**Applies to:** "Similar products," "related articles," "patients with similar symptoms," "cases with similar facts."

### 4. Multi-Modal Search

**What it is:** Search across different types of content simultaneously — text, images, audio, video.

**Example:** A user uploads a blurry screenshot of a movie scene → the system identifies the movie and finds all quotes from that scene.

**Applies to:** Product search (upload a photo), real estate (search by photo of a house style), fashion (find similar outfits).

### 5. Knowledge Graphs

**What it is:** Instead of isolated search results, build a graph of relationships: Actor → appeared in → Movie → has quote → "I'll be back" → said by → Character: The Terminator.

**Example:** Search "Arnold Schwarzenegger catchphrases" → traverses the graph: Arnold → Terminator, Predator, Kindergarten Cop → their most famous quotes.

**Applies to:** Medical (drug → treats → condition → has symptom), legal (case → cites → precedent → overruled by), e-commerce (product → frequently bought with → accessory).

---

## Problem-Solving Techniques (Transferable to Any Project)

### 1. Graceful Degradation

**In Quoted:** Web Speech API fails? Fall back to Whisper. TMDB doesn't have Nigerian streaming info? Fall back to US. UTF-8 can't decode the file? Fall back to Latin-1.

**The principle:** Always have a Plan B. Design systems in layers where each layer catches what the previous one missed.

**Real-world examples:**
- Netflix: If your connection drops, it degrades video quality instead of stopping
- Google Maps: If GPS fails, it uses cell tower triangulation, then Wi-Fi positioning
- Payment systems: If Stripe is down, route to PayPal

### 2. Idempotent Operations

**In Quoted:** The cron job checks `if existing_movie: skip`. Running it twice produces the same result as running it once.

**The principle:** Operations should be safe to repeat. If a job crashes halfway through, you should be able to restart it without creating duplicates or corruption.

**Real-world examples:**
- Charging a credit card: If the network times out, the payment system checks if the charge already went through before retrying
- Database migrations: Each migration has a version number; re-running it skips already-applied changes

### 3. Separation of Concerns

**In Quoted:** `srt_parser.py` only parses files. `tmdb_client.py` only talks to TMDB. `app.py` only handles web requests. Each file has ONE job.

**The principle:** Each component should do one thing. This makes code easier to test, debug, and replace.

**Analogy:** In a restaurant, the chef cooks, the waiter serves, and the cashier handles payment. If the waiter also had to cook, everything would be slower and more error-prone.

### 4. Progressive Enhancement

**In Quoted:** The search works with just text input (basic). Voice search enhances the experience (advanced). Autocomplete adds another layer (premium). The app works fine at every level.

**The principle:** Build the core experience first, then layer enhancements on top. Each layer should be independently removable without breaking the layers below it.

### 5. Cost-Aware Architecture

**In Quoted:** Free browser APIs used first (Web Speech), paid APIs used as fallback (Whisper). Rate limits are stricter on expensive endpoints. The Fly.io machine sleeps when idle.

**The principle:** Design for cost from day one. Use free/cheap options where possible, pay only when necessary, and put guardrails around expensive operations.

### 6. Scheduled Batch Processing

**In Quoted:** Instead of fetching ALL movies at once (would take hours, hit API limits), the cron job fetches 20 per day, cycling through years and pages.

**The principle:** Break large jobs into small, repeatable batches. Track progress (the `fetch_cycle` bookmark) so you can resume where you left off.

**Real-world examples:**
- Email marketing: Send 10,000 emails in batches of 500 per hour
- Data migration: Migrate 10 million records in batches of 10,000
- Web scraping: Crawl 100 pages per day instead of 10,000 at once

### 7. Defensive Parsing

**In Quoted:** The SRT parser handles multiple encodings, missing index numbers, HTML tags in subtitles, dot vs comma in timestamps, and multi-line text blocks.

**The principle:** Never trust input data to be perfectly formatted. Real-world data is messy — files from different sources have different quirks. Build parsers that handle the mess gracefully instead of crashing.

**Analogy:** A mail sorting machine should handle envelopes that are slightly bent, have smudged ink, or are an unusual size — not just perfectly crisp letters.

---

## Summary: What You've Actually Built

Quoted isn't "just" a movie quote finder. You've built a system that demonstrates:

| Skill | How Quoted Uses It |
|-------|-------------------|
| **Full-stack web development** | Flask backend + Jinja templates + JavaScript frontend |
| **Database design** | Relational schema with foreign keys and cascading deletes |
| **API integration** | Chaining 4 external services into one product |
| **File parsing** | Turning unstructured text into structured data |
| **Authentication patterns** | Token-based auth, API keys, environment variables |
| **DevOps** | Docker containers, CI-like deployments, cron scheduling |
| **Cost management** | Rate limiting, graceful degradation, sleep-on-idle |
| **Search engineering** | Text matching, autocomplete, relevance (basic) |
| **Speech/audio processing** | Web Audio API, MediaRecorder, speech-to-text |
| **Responsive UI** | Mobile-friendly design, touch interactions, animations |

These same patterns, in different combinations, power products worth billions. The jump from Quoted to a legal search engine or a medical knowledge base is a change in **data and domain** — not a change in architecture.
