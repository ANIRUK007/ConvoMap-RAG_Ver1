import re
import datetime
import json
import os

# --- STEP 1: PARSER (This function is new) ---

def parse_whatsapp_chat(filepath):
    """
    Parses a WhatsApp .txt export file into a list of message dictionaries.
    This version is updated for the 'M/D/YY, H:MM AM/PM - Author: Message' format.
    Filters out media placeholders and encryption notices.
    """
    
    # NEW Regex for: 9/2/23, 1:34 PM - Author: Message
    # Handles 12-hr clock, AM/PM, and " - " separator
    user_message_pattern = re.compile(
        # Group 1: Timestamp (e.g., "10/19/23, 8:30 PM")
        r'^(\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2}\s[AP]M) - '
        # Group 2: Author (e.g., "Divyanshu")
        r'([^:]+): '
        # Group 3: Message (e.g., "Heyy")
        r'(.+)'
    )
    
    # NEW Regex for system messages: 9/2/23, 1:34 PM - Message
    system_message_pattern = re.compile(
        # Group 1: Timestamp (e.g., "9/2/23, 1:34 PM")
        r'^(\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2}\s[AP]M) - '
        # Group 2: Message (e.g., "Messages and calls are...")
        r'(.+)'
    )
    
    # NEW Timestamp format string to match "10/19/23, 8:30 PM"
    # %m = month, %d = day, %y = 2-digit year
    # %I = 12-hour clock, %M = minute, %p = AM/PM
    timestamp_format_str = '%m/%d/%y, %I:%M %p'

    parsed_messages = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                user_match = user_message_pattern.match(line)
                system_match = system_message_pattern.match(line)
                
                if user_match:
                    # It's a user message
                    raw_timestamp, author, message = user_match.groups()
                    
                    # --- FILTER 1: Media Placeholders ---
                    if message == "<Media omitted>" or \
                       message == "<image omitted>" or \
                       message == "<video omitted>" or \
                       message == "<audio omitted>" or \
                       message == "<sticker omitted>" or \
                       message.endswith("(file attached)"):
                        continue  # Skip this media message
                        
                    # --- Parse Timestamp ---
                    try:
                        timestamp = datetime.datetime.strptime(raw_timestamp, timestamp_format_str)
                    except ValueError:
                        # Try with 4-digit year if 2-digit fails
                        timestamp = datetime.datetime.strptime(raw_timestamp, '%m/%d/%Y, %I:%M %p')
                        
                    parsed_messages.append({
                        'timestamp': timestamp,
                        'author': author,
                        'message': message
                    })
                    
                elif system_match:
                    # It's a system message (no 'Author:' format)
                    raw_timestamp, message = system_match.groups()
                    
                    # --- FILTER 2: Encryption Notices ---
                    if "Messages and calls are end-to-end encrypted" in message:
                        continue # Skip this encryption notice
                    
                    # --- Parse Timestamp ---
                    try:
                        timestamp = datetime.datetime.strptime(raw_timestamp, timestamp_format_str)
                    except ValueError:
                        timestamp = datetime.datetime.strptime(raw_timestamp, '%m/%d/%Y, %I:%M %p')

                    # Add system messages (like "Divyanshu is a contact")
                    parsed_messages.append({
                        'timestamp': timestamp,
                        'author': 'System', # Assign 'System' as the author
                        'message': message
                    })

                elif not user_match and not system_match and parsed_messages:
                    # It's a multi-line message. Append to the previous message.
                    if parsed_messages:
                         parsed_messages[-1]['message'] += '\n' + line
                         
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return []
    except Exception as e:
        print(f"An error occurred while parsing {filepath}: {e}")
        return []
    return parsed_messages

# --- STEP 2: SEGMENTER (This function is unchanged) ---

def segment_conversations(messages, source_name, time_threshold_minutes=60):
    """
    Segments a list of parsed messages into conversation chunks.
    'source_name' is used to create unique chunk_ids.
    """
    if not messages:
        return []

    chunks = []
    chunk_id_counter = 0

    current_chunk_messages = []
    current_chunk_authors = set()
    current_chunk_start = messages[0]['timestamp']
    last_message_time = messages[0]['timestamp']

    for msg in messages:
        delta = msg['timestamp'] - last_message_time
        
        if delta.total_seconds() / 60 > time_threshold_minutes:
            if current_chunk_messages:
                raw_text = "\n".join(f"[{auth}]: {txt}" for auth, txt in current_chunk_messages)
                chunks.append({
                    'chunk_id': f"{source_name}_chunk_{chunk_id_counter}",
                    'source_type': 'whatsapp',
                    'source_file': f"{source_name}.txt",
                    'participants': list(current_chunk_authors),
                    'start_timestamp': current_chunk_start,
                    'end_timestamp': last_message_time,
                    'raw_text': raw_text
                })
                chunk_id_counter += 1
            
            current_chunk_messages = [(msg['author'], msg['message'])]
            current_chunk_authors = {msg['author']}
            current_chunk_start = msg['timestamp']
        else:
            current_chunk_messages.append((msg['author'], msg['message']))
            current_chunk_authors.add(msg['author'])
        
        last_message_time = msg['timestamp']

    if current_chunk_messages:
        raw_text = "\n".join(f"[{auth}]: {txt}" for auth, txt in current_chunk_messages)
        chunks.append({
            'chunk_id': f"{source_name}_chunk_{chunk_id_counter}",
            'source_type': 'whatsapp',
            'source_file': f"{source_name}.txt",
            'participants': list(current_chunk_authors),
            'start_timestamp': current_chunk_start,
            'end_timestamp': last_message_time,
            'raw_text': raw_text
        })

    return chunks

# --- STEP 3: MAIN EXECUTION (This function is unchanged) ---

def process_chat_directory(directory_path, output_json_file):
    """
    Processes all .txt files in a directory, parses them,
    segments them, and saves all chunks to a single JSON file.
    """
    all_chunks = []
    
    try:
        filenames = os.listdir(directory_path)
    except FileNotFoundError:
        print(f"Error: Directory not found at {directory_path}")
        print("Please make sure 'CHAT_DIRECTORY' variable is set correctly.")
        return

    chat_files = [f for f in filenames if f.endswith('.txt')]
    
    if not chat_files:
        print(f"No .txt files found in {directory_path}")
        return

    print(f"Found {len(chat_files)} chat files to process...")

    for filename in chat_files:
        filepath = os.path.join(directory_path, filename)
        source_name = os.path.splitext(filename)[0] 
        
        print(f"--- Processing {filename} ---")
        
        parsed_messages = parse_whatsapp_chat(filepath)
        if not parsed_messages:
            print(f"No usable messages found in {filename}. Skipping.")
            continue
            
        conversation_chunks = segment_conversations(parsed_messages, source_name, time_threshold_minutes=60)
        
        print(f"Found {len(conversation_chunks)} conversation chunks.")
        
        all_chunks.extend(conversation_chunks)

    print(f"\n--- Total Processing Complete ---")
    print(f"Processed {len(chat_files)} files.")
    print(f"Found a total of {len(all_chunks)} conversation chunks.")

    try:
        with open(output_json_file, 'w', encoding='utf-8') as f:
            class DateTimeEncoder(json.JSONEncoder):
                def default(self, obj):
                    if isinstance(obj, datetime.datetime):
                        return obj.isoformat()
                    return super(DateTimeEncoder, self).default(obj)
            
            json.dump(all_chunks, f, indent=2, cls=DateTimeEncoder)
        
        # Using a simple checkmark that works in Windows console
        print(f"\n[+] Successfully saved all chunks to {output_json_file}")
        
    except Exception as e:
        print(f"\nError saving to JSON file: {e}")


CHAT_DIRECTORY = 'Raw Chat Data WA' 
OUTPUT_FILE = 'all_chunks.json'

process_chat_directory(CHAT_DIRECTORY, OUTPUT_FILE)