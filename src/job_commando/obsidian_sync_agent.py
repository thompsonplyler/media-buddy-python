import time
import os
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from . import config

# --- Configuration ---
API_ENDPOINT = "http://127.0.0.1:5000/api/submit_log"
WATCH_PATH = config.OBSIDIAN_LOG_PATH

# --- Debounce Logic ---
# To prevent multiple quick saves from firing many events
last_processed_time = {}
DEBOUNCE_SECONDS = 2

def is_valid_log_file(path):
    """Check if the file is a log file we should process (YYYY-MM-DD.md)."""
    filename = os.path.basename(path)
    if not filename.endswith('.md'):
        return False
    # A simple check for date-like filenames.
    # This can be improved with regex for more strictness.
    parts = os.path.splitext(filename)[0].split('-')
    return len(parts) == 3 and all(p.isdigit() for p in parts)

def process_file(file_path):
    """Reads a file and sends its content to the API."""
    
    # Debounce check
    now = time.time()
    if file_path in last_processed_time and now - last_processed_time[file_path] < DEBOUNCE_SECONDS:
        return
    last_processed_time[file_path] = now

    print(f"[Sync Agent] Detected change in: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        payload = {
            "filename": os.path.basename(file_path),
            "content": content
        }

        response = requests.post(API_ENDPOINT, json=payload)
        response.raise_for_status()
        print(f"[Sync Agent] Successfully submitted {payload['filename']}. Server response: {response.json().get('message')}")

    except FileNotFoundError:
        # This can happen if a file is created and quickly deleted.
        print(f"[Sync Agent] File not found during processing: {file_path}. Skipping.")
    except Exception as e:
        print(f"[Sync Agent] Error processing file {file_path}: {e}")


class LogFileHandler(FileSystemEventHandler):
    """Handles file system events for log files."""
    def on_created(self, event):
        if not event.is_directory and is_valid_log_file(event.src_path):
            process_file(event.src_path)

    def on_modified(self, event):
        if not event.is_directory and is_valid_log_file(event.src_path):
            process_file(event.src_path)


def run_sync_agent():
    """Starts the file system observer."""
    if not WATCH_PATH or not os.path.isdir(WATCH_PATH):
        print(f"[Sync Agent] Error: OBSIDIAN_LOG_PATH is not set or is not a valid directory.")
        print(f"Please set it in your .env file. Current value: '{WATCH_PATH}'")
        return

    print(f"[Sync Agent] Starting... Watching directory: {WATCH_PATH}")
    event_handler = LogFileHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_PATH, recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    
    observer.join()
    print("[Sync Agent] Stopped.") 