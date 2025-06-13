from flask import Blueprint, jsonify, request
import google.generativeai as genai
from . import config, db
from .models import User, DailyLog
from .riot_api import get_puuid_by_riot_id, get_match_ids_by_puuid, get_match_details_by_id, get_match_timeline_by_id
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

@main.route('/api/summ/set', methods=['POST'])
def set_summoner():
    data = request.json
    discord_id = data.get('discord_id')
    discord_name = data.get('discord_name')
    summoner_name = data.get('summoner_name')
    summoner_tag = data.get('summoner_tag')

    if not all([discord_id, discord_name, summoner_name, summoner_tag]):
        return jsonify({"error": "Missing required fields."}), 400

    puuid = get_puuid_by_riot_id(config.RIOT_API_KEY, summoner_name, summoner_tag)

    if not puuid:
        return jsonify({"error": f"Could not find a Riot account for {summoner_name}#{summoner_tag}. Please check the name and tag."}), 404

    # Check if user exists, if not create one
    user = User.query.get(discord_id)
    if not user:
        user = User(discord_id=discord_id, discord_name=discord_name)
    
    # Update user details
    user.lol_summoner_name = summoner_name
    user.lol_summoner_tag = summoner_tag
    user.puuid = puuid
    
    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": f"Successfully linked your Discord to {summoner_name}#{summoner_tag}.",
        "summoner_name": user.lol_summoner_name,
        "summoner_tag": user.lol_summoner_tag,
        "puuid": user.puuid
    })

@main.route('/api/summ/show/<int:discord_id>', methods=['GET'])
def show_summoner(discord_id):
    user = User.query.get(discord_id)
    if not user or not user.puuid:
        return jsonify({"error": "No Riot account is linked to this Discord ID. Use `$summ set <name>#<tag>` to link one."}), 404

    return jsonify({
        "discord_name": user.discord_name,
        "summoner_name": user.lol_summoner_name,
        "summoner_tag": user.lol_summoner_tag,
        "puuid": user.puuid # Included for testing as requested
    })

@main.route('/api/summ/last/<int:discord_id>', methods=['GET'])
def last_game_roast(discord_id):
    user = User.query.get(discord_id)
    if not user or not user.puuid:
        return jsonify({"error": "No Riot account is linked to this Discord ID. Use `$summ set <name>#<tag>` to link one."}), 404

    # 1. Get the last match ID
    match_ids = get_match_ids_by_puuid(config.RIOT_API_KEY, user.puuid, count=1)
    if not match_ids:
        return jsonify({"error": "Couldn't find any recent matches for your account."}), 404
    last_match_id = match_ids[0]

    # 2. Get match details and timeline
    match_details = get_match_details_by_id(config.RIOT_API_KEY, last_match_id)
    match_timeline = get_match_timeline_by_id(config.RIOT_API_KEY, last_match_id)

    if not match_details or not match_timeline:
        return jsonify({"error": "Could not retrieve full details for the last match."}), 500

    # 3. Read and prepare the roast prompt
    try:
        with open('ROAST_PROMPT.MD', 'r', encoding='utf-8') as f:
            roast_prompt_template = f.read()
        
        # Replace placeholders
        roast_prompt = roast_prompt_template.replace('{puuid}', user.puuid)
        roast_prompt = roast_prompt.replace('{discord_name}', user.discord_name)

    except FileNotFoundError:
        return jsonify({"error": "ROAST_PROMPT.MD not found on the server."}), 500
    except Exception as e:
        return jsonify({"error": f"Error reading prompt file: {e}"}), 500

    # 4. Combine all data for the Gemini prompt
    # We provide the system prompt (the roast instructions) and then the data
    system_prompt = roast_prompt
    full_user_prompt = (
        f"Here is the data for the match. Please provide the analysis as described in the instructions.\n\n"
        f"--- MATCH DETAILS ---\n"
        f"{json.dumps(match_details, indent=2)}\n\n"
        f"--- MATCH TIMELINE ---\n"
        f"{json.dumps(match_timeline, indent=2)}"
    )

    # 5. Call Gemini
    try:
        model = genai.GenerativeModel(
            'gemini-2.5-pro-preview-06-05',
            system_instruction=system_prompt
        )
        response = model.generate_content(full_user_prompt)
        roast_text = response.text
        
        return jsonify({"roast": roast_text})

    except Exception as e:
        print(f"Error calling Gemini API for roast: {e}")
        return jsonify({"error": "An error occurred while generating the roast from Gemini."}), 500 