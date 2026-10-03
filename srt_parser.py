import re

# Timestamp line: 00:00:20,000 --> 00:00:24,400
# Flexible on whitespace, comma/dot separator, 1-2 digit hours and 1-3 digit milliseconds
TIME_PATTERN = re.compile(r'(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})')

# Speaker labels like "JOHN:", "MAN 1:" or "DR. JONES:". The first word must be 2+ capital
# letters, so text such as "10:30 tonight" or "A 10:30 meeting" is left alone.
SPEAKER_LABEL = re.compile(r"^[A-Z][A-Z.'-]+(?: [A-Z0-9.'-]+)*:(?:\s+|$)")

# Lines with fewer words are dropped as noise ("Yes.", "Okay.") while short
# iconic quotes like "Here's Johnny!" are kept.
MIN_WORDS = 2


def decode_srt_bytes(raw):
    """
    Decodes a raw .srt file. Most are UTF-8 (sometimes with a BOM);
    older Windows-made files are usually cp1252.
    """
    for encoding in ('utf-8-sig', 'cp1252'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode('latin-1')  # latin-1 can decode any byte sequence


def _strip_markup(line):
    # Remove HTML tags, including an unclosed tag at the end of the line
    line = re.sub(r'<[^>]*(?:>|$)', '', line)
    # Remove styling codes like {\an8}
    return re.sub(r'\{[^}]*\}', '', line)


def _split_speakers(text_lines):
    """Groups text lines into utterances; a line starting with '-' is a new speaker."""
    utterances = []
    for line in text_lines:
        line = _strip_markup(line).strip()
        if not line:
            continue
        if line.startswith('-') or not utterances:
            utterances.append(line.lstrip('-').strip())
        else:
            utterances[-1] += ' ' + line
    return utterances


def _clean_text(text):
    # JUNK FILTER: Remove [music playing], (sighs), etc.
    text = re.sub(r'\[.*?\]|\(.*?\)', '', text).strip()

    # JUNK FILTER: Remove speaker labels
    text = SPEAKER_LABEL.sub('', text)

    # Clean up common subtitle artifacts and collapse whitespace
    text = text.replace('"', '').replace('♪', '')
    return ' '.join(text.split())


def parse_srt(srt_content):
    """
    Parses SRT string content into a list of dictionaries.
    Returns: [{'start': '00:00:01,000', 'end': '00:00:04,000', 'text': 'Hello there'}]
    """
    # Normalize line endings
    srt_content = srt_content.replace('\r\n', '\n').replace('\r', '\n')

    # Split into blocks on blank lines (including lines that only contain spaces)
    blocks = re.split(r'\n\s*\n', srt_content.strip())

    parsed_subs = []

    for block in blocks:
        lines = block.strip().split('\n')

        # Find the timestamp line (the index number before it is sometimes missing)
        for i, line in enumerate(lines):
            time_match = TIME_PATTERN.search(line)
            if time_match:
                break
        else:
            continue

        start = time_match.group(1).replace('.', ',')  # Standardize to comma
        end = time_match.group(2).replace('.', ',')

        # Everything after the timestamp is text
        for utterance in _split_speakers(lines[i + 1:]):
            clean_text = _clean_text(utterance)

            # JUNK FILTER: Discard very short lines
            if len(clean_text.split()) < MIN_WORDS:
                continue

            parsed_subs.append({
                'start': start,
                'end': end,
                'text': clean_text
            })

    return parsed_subs
