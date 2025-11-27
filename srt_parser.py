import re

def parse_srt(srt_content):
    """
    Parses SRT string content into a list of dictionaries.
    Returns: [{'start': '00:00:01', 'end': '00:00:04', 'text': 'Hello'}]
    """
    # Normalize line endings
    srt_content = srt_content.replace('\r\n', '\n').replace('\r', '\n')
    
    # Split into blocks by double newlines
    blocks = srt_content.strip().split('\n\n')
    
    parsed_subs = []
    
    # Regex for timestamp line: 00:00:20,000 --> 00:00:24,400
    # Flexible on whitespace and comma/dot separator
    time_pattern = re.compile(r'(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})')

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            # Line 0 is usually the index number
            # Line 1 is usually the timestamp
            # Line 2+ is the text
            
            # Try to find the timestamp in the first few lines (sometimes index is missing)
            time_match = None
            text_lines = []
            
            for i, line in enumerate(lines):
                match = time_pattern.search(line)
                if match:
                    time_match = match
                    # Everything after this line is text
                    text_lines = lines[i+1:]
                    break
            
            if time_match and text_lines:
                start = time_match.group(1).replace('.', ',') # Standardize to comma
                end = time_match.group(2).replace('.', ',')
                
                # Join text lines and clean up
                full_text = " ".join(text_lines)
                # Remove HTML tags
                clean_text = re.sub(r'<[^>]+>', '', full_text).strip()
                
                # Clean up common subtitle artifacts
                clean_text = clean_text.replace('- ', '').strip()
                
                if clean_text:
                    parsed_subs.append({
                        'start': start,
                        'end': end,
                        'text': clean_text
                    })
            
    return parsed_subs