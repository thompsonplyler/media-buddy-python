import sys
import os
import time
from datetime import datetime, timedelta
import threading

# --- Path Correction ---
# This must be the very first thing to run.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- Imports ---
# config will load .env and must be imported before other local modules.
from src.job_commando import config, create_app
from src.job_commando.discord_bot import run_bot
from src.job_commando.google_calendar import create_quick_checkin_event
from src.job_commando.riot_api import get_matches_played_today
from src.job_commando import state_manager
from src.job_commando import obsidian_api
from src.job_commando.obsidian_sync_agent import run_sync_agent

def get_timestamp():
    """Returns a formatted timestamp string for logging."""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# --- Main Application ---
def compassionate_monitor_loop():
    """The main loop for the compassionate monitor."""
    print(f"[{get_timestamp()}] Compassionate monitor thread started.")
    while True:
        try:
            now = datetime.now()
            today = now.date()
            
            # Load the current state from the file system
            state = state_manager.load_state(today)

            # --- Trigger 1: The "League Vortex" Check ---
            # We will ALWAYS check for matches to provide constant logging.
            if not config.RIOT_API_KEY or not config.RIOT_PUUID:
                print(f"[{get_timestamp()}] [RIOT] API key or PUUID not set. Skipping check.")
            else:
                print(f"[{get_timestamp()}] [RIOT] Checking for League of Legends activity...")
                try:
                    match_count = get_matches_played_today(config.RIOT_API_KEY, config.RIOT_PUUID)
                    print(f"[{get_timestamp()}] [RIOT] API call successful. Found {match_count} matches so far today.")

                    # Update the games_played count in the daily note
                    print(f"[{get_timestamp()}] [OBSIDIAN] Attempting to update games_played to {match_count}...")
                    obsidian_api.update_games_played_in_daily_log(match_count)

                    # The intervention, however, will only fire ONCE.
                    if match_count >= config.LEAGUE_TRIGGER_COUNT and not state.get("league_vortex_triggered"):
                        print(f"[{get_timestamp()}] [INTERVENTION] League trigger count of {config.LEAGUE_TRIGGER_COUNT} met. Firing intervention.")
                        
                        print(f"[{get_timestamp()}] [GCAL] Attempting to create quick check-in event...")
                        success = create_quick_checkin_event()
                        
                        if success:
                            print(f"[{get_timestamp()}] [GCAL] API call successful. Intervention event created.")
                            
                            print(f"[{get_timestamp()}] [OBSIDIAN] Attempting to log intervention...")
                            obsidian_api.log_intervention(
                                reason="League Vortex",
                                details=f"{match_count} matches played today."
                            )
                            state["league_vortex_triggered"] = True
                            state_manager.save_state(today, state) # Persist the change
                        else:
                            print(f"[{get_timestamp()}] [GCAL] API call FAILED. Could not create intervention event.")
                except Exception as e:
                    print(f"[{get_timestamp()}] [RIOT] API call FAILED. Error: {e}")

            
            # --- Trigger 2: The "Radio Silence" Check ---
            if not state.get("radio_silence_triggered"):
                if now.hour >= config.RADIO_SILENCE_HOUR:
                    print(f"[{get_timestamp()}] [OBSIDIAN] Checking for daily log...")
                    try:
                        log_exists = obsidian_api.daily_log_exists(today)
                        if not log_exists:
                            print(f"[{get_timestamp()}] [INTERVENTION] Daily log not found after {config.RADIO_SILENCE_HOUR}:00. Firing intervention.")
                            
                            print(f"[{get_timestamp()}] [GCAL] Attempting to create quick check-in event...")
                            success = create_quick_checkin_event()

                            if success:
                                print(f"[{get_timestamp()}] [GCAL] API call successful. Intervention event created.")
                                
                                print(f"[{get_timestamp()}] [OBSIDIAN] Attempting to create daily log with intervention...")
                                obsidian_api.create_daily_log_with_intervention(
                                    reason="Radio Silence",
                                    details=f"No daily log found by {config.RADIO_SILENCE_HOUR}:00."
                                )
                                state["radio_silence_triggered"] = True
                                state_manager.save_state(today, state)
                            else:
                                print(f"[{get_timestamp()}] [GCAL] API call FAILED. Could not create intervention event.")
                        else:
                            print(f"[{get_timestamp()}] [OBSIDIAN] API call successful. Daily log found.")
                    except Exception as e:
                        print(f"[{get_timestamp()}] [OBSIDIAN] API call FAILED while checking for daily log. Error: {e}")


            # --- Trigger 3: The "Unchecked Box" Follow-up ---
            if not state.get("follow_up_triggered"):
                yesterday = today - timedelta(days=1)
                print(f"[{get_timestamp()}] [OBSIDIAN] Checking yesterday's note ({yesterday.strftime(config.DATE_FORMAT)}) for incomplete follow-up...")
                try:
                    if obsidian_api.note_contains_string(yesterday, "- [ ] Did we connect?"):
                        print(f"[{get_timestamp()}] [INTERVENTION] Found incomplete follow-up from yesterday. Logging a gentle reminder.")
                        
                        print(f"[{get_timestamp()}] [OBSIDIAN] Attempting to log follow-up...")
                        success = obsidian_api.log_follow_up()
                        if success:
                            state["follow_up_triggered"] = True
                            state_manager.save_state(today, state)
                    else:
                        print(f"[{get_timestamp()}] [OBSIDIAN] API call successful. No incomplete follow-up found.")
                except Exception as e:
                    print(f"[{get_timestamp()}] [OBSIDIAN] API call FAILED while checking for follow-up. Error: {e}")


            # Wait for the next check
            print(f"[{get_timestamp()}] Monitor sleeping for {config.CHECK_INTERVAL_SECONDS / 60} minutes.")
            
        except Exception as e:
            import traceback
            timestamp = get_timestamp()
            print(f"[{timestamp}] ---! FATAL ERROR IN MONITOR THREAD !---")
            print(f"[{timestamp}] An unexpected error occurred: {e}")
            traceback.print_exc()
            print(f"[{timestamp}] ---! The monitor will attempt to restart the loop after a delay. !---")
        
        time.sleep(config.CHECK_INTERVAL_SECONDS)

def main():
    """The main entry point for the script."""
    print("Starting services...")

    # Set up threads for Flask app, Discord bot, Sync Agent, and Monitor Loop
    flask_thread = threading.Thread(target=lambda: create_app().run(debug=True, use_reloader=False, port=5000))
    discord_thread = threading.Thread(target=run_bot)
    sync_agent_thread = threading.Thread(target=run_sync_agent)
    monitor_thread = threading.Thread(target=compassionate_monitor_loop)

    # Start the threads
    flask_thread.start()
    print("Flask server thread started.")
    
    discord_thread.start()
    print("Discord bot thread started.")

    sync_agent_thread.start()
    print("Obsidian sync agent thread started.")

    monitor_thread.start()
    print("Compassionate monitor thread started.")

    # Wait for all threads to complete
    flask_thread.join()
    discord_thread.join()
    sync_agent_thread.join()
    monitor_thread.join()

    print("Services stopped.")

if __name__ == "__main__":
    main() 