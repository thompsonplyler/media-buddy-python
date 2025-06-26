from flask import Blueprint, jsonify, request
import google.generativeai as genai
from . import config, db
from .models import DailyLog
import os
import json
from datetime import date

main = Blueprint('main', __name__)

# Configure the Gemini API
if config.GEMINI_API_KEY:
    genai.configure(api_key=config.GEMINI_API_KEY)

def get_schematic_documents():
    """Reads and concatenates the content of the core schematic documents."""
    schematic_content = ""
    doc_paths = [
        os.path.join('private', 'MENTOR_PROTOCOL.md'),
        os.path.join('private', 'customization', 'PERSONALITY.MD')
    ]
    
    for path in doc_paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                schematic_content += f"--- Start of Document: {os.path.basename(path)} ---\n\n"
                schematic_content += f.read()
                schematic_content += f"\n\n--- End of Document: {os.path.basename(path)} ---\n\n"
        except FileNotFoundError:
            print(f"Warning: Schematic document not found at {path}")
        except Exception as e:
            print(f"Error reading schematic document {path}: {e}")
            
    return schematic_content

@main.route('/')
def index():
    return jsonify({"message": "Welcome to Job Commando!"})

@main.route('/api/prompt', methods=['POST'])
def handle_prompt():
    if not request.json or 'prompt' not in request.json:
        return jsonify({"error": "Invalid request. 'prompt' is required."}), 400

    user_prompt = request.json['prompt']
    chat_history = request.json.get('history', '') # Safely get history

    if not config.GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY not configured."}), 500
        
    try:
        # Augment the user prompt with context
        schematic_context = get_schematic_documents()
        
        # Combine the history and the latest user prompt
        full_prompt = f"{chat_history}\n\nUser Prompt: \"{user_prompt}\""

        # Use the new model with system instructions
        model = genai.GenerativeModel(
            'gemini-2.5-pro-preview-06-05',
            system_instruction=schematic_context
        )
        
        response = model.generate_content(full_prompt)
        gemini_response = response.text
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return jsonify({"error": "An error occurred while communicating with the Gemini API."}), 500

    return jsonify({"response": gemini_response})

@main.route('/api/submit_log', methods=['POST'])
def submit_log():
    if not request.json or 'filename' not in request.json or 'content' not in request.json:
        return jsonify({"error": "Invalid request. 'filename' and 'content' are required."}), 400

    filename = request.json['filename']
    content = request.json['content']

    try:
        # Extract date from filename, e.g., "2025-06-12.md"
        log_date_str = os.path.splitext(filename)[0]
        log_date = date.fromisoformat(log_date_str)

        # Check if a log for this date already exists
        existing_log = DailyLog.query.get(log_date)

        if existing_log:
            # Update existing log
            existing_log.content = content
            message = f"Log for {log_date_str} has been updated."
        else:
            # Create new log
            new_log = DailyLog(log_date=log_date, content=content)
            db.session.add(new_log)
            message = f"New log for {log_date_str} has been created."
        
        db.session.commit()
        
        return jsonify({"message": message})
        
    except ValueError:
        return jsonify({"error": f"Invalid filename format. Could not parse date from '{filename}'. Expected YYYY-MM-DD.md."}), 400
    except Exception as e:
        db.session.rollback()
        print(f"Error submitting log to database: {e}")
        return jsonify({"error": "An error occurred while submitting the log."}), 500

@main.route('/api/get_log/<string:log_date_str>', methods=['GET'])
def get_log(log_date_str):
    try:
        log_date = date.fromisoformat(log_date_str)
        log_entry = DailyLog.query.get(log_date)

        if not log_entry:
            return jsonify({"error": f"No log found for date {log_date_str}."}), 404
        
        return jsonify({
            "log_date": log_entry.log_date.isoformat(),
            "content": log_entry.content,
            "last_updated": log_entry.last_updated.isoformat()
        })

    except ValueError:
        return jsonify({"error": "Invalid date format. Please use YYYY-MM-DD."}), 400
    except Exception as e:
        print(f"Error retrieving log: {e}")
        return jsonify({"error": "An error occurred while retrieving the log."}), 500 

# Riot-related routes removed - functionality not needed for media-buddy 