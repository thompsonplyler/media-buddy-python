"""
This module is responsible for taking raw match and timeline data from the
Riot API and turning it into a structured, insightful analysis.
"""

from . import config
from . import riot_api

def _get_player_participant_data(match_data: dict, puuid: str) -> dict | None:
    """
    Finds the specific participant block for a given player PUUID.
    """
    try:
        # The 'participants' list in metadata is a list of PUUIDs.
        # The index of our PUUID in this list corresponds to the participant object.
        player_index = match_data['metadata']['participants'].index(puuid)
        
        # The participant objects in the 'info' section have an ID from 1-10.
        # The player at index 0 of the metadata list is participantId 1.
        # Therefore, the participant data we want is at the same index.
        player_data = match_data['info']['participants'][player_index]
        
        # As a sanity check, Riot's participantId should be index + 1
        if player_data.get('puuid') == puuid or player_data.get('participantId') == player_index + 1:
            return player_data
        else:
            # This case should be rare, but we'll search just in case the order differs.
            for p in match_data['info']['participants']:
                if p.get('puuid') == puuid:
                    return p
            return None

    except (ValueError, IndexError) as e:
        print(f"Error finding player {puuid} in match data: {e}")
        return None

def _find_lane_opponent(all_participants: list, player_data: dict) -> dict | None:
    """Finds the direct lane opponent of the primary player."""
    player_position = player_data.get('teamPosition') or player_data.get('individualPosition')
    player_team_id = player_data.get('teamId')

    if not player_position or not player_team_id:
        return None

    for p in all_participants:
        opponent_position = p.get('teamPosition') or p.get('individualPosition')
        if p.get('teamId') != player_team_id and opponent_position == player_position:
            return p
    return None

def _analyze_laning_phase(timeline_data: dict, player_participant_id: int, opponent_participant_id: int) -> dict:
    """Analyzes the laning phase by comparing player and opponent at 10 minutes."""
    try:
        # Frames are every minute, so frame 10 is the state at 10:00.
        frame_10 = timeline_data['info']['frames'][10]['participantFrames']
        
        player_frame = frame_10.get(str(player_participant_id))
        opponent_frame = frame_10.get(str(opponent_participant_id))

        if not player_frame or not opponent_frame:
            return {'error': 'Could not find player or opponent frame data at 10 minutes.'}

        player_cs = player_frame.get('minionsKilled', 0) + player_frame.get('jungleMinionsKilled', 0)
        player_gold = player_frame.get('totalGold', 0)
        opponent_cs = opponent_frame.get('minionsKilled', 0) + opponent_frame.get('jungleMinionsKilled', 0)
        opponent_gold = opponent_frame.get('totalGold', 0)

        return {
            'cs_at_10': player_cs,
            'opponent_cs_at_10': opponent_cs,
            'cs_lead_at_10': player_cs - opponent_cs,
            'gold_at_10': player_gold,
            'opponent_gold_at_10': opponent_gold,
            'gold_lead_at_10': player_gold - opponent_gold,
        }
    except (IndexError, KeyError) as e:
        return {'error': f'Could not process timeline data for laning phase: {e}'}

def _analyze_teamfights(timeline_data: dict, player_participant_id: int) -> list:
    """Identifies and analyzes major teamfights from the timeline."""
    FIGHT_MIN_KILLS = 3
    FIGHT_WINDOW_SECONDS = 20

    all_events = []
    for frame in timeline_data['info']['frames']:
        all_events.extend(frame['events'])

    kill_events = [e for e in all_events if e.get('type') == 'CHAMPION_KILL']
    
    fights = []
    processed_kill_indices = set()

    for i, start_kill in enumerate(kill_events):
        if i in processed_kill_indices:
            continue

        current_fight_kills = [start_kill]
        window_end_time = start_kill['timestamp'] + (FIGHT_WINDOW_SECONDS * 1000)

        for j in range(i + 1, len(kill_events)):
            next_kill = kill_events[j]
            if next_kill['timestamp'] <= window_end_time:
                current_fight_kills.append(next_kill)
            else:
                break
        
        if len(current_fight_kills) >= FIGHT_MIN_KILLS:
            fight_summary = {
                'start_time_minutes': round(start_kill['timestamp'] / 60000, 2),
                'kills': [],
                'blue_team_kills': 0,
                'red_team_kills': 0,
                'player_involvement': 'None'
            }
            
            player_involvement = set()

            for kill in current_fight_kills:
                processed_kill_indices.add(kill_events.index(kill))
                
                killer_id = kill.get('killerId', 0)
                victim_id = kill.get('victimId', 0)
                
                if 1 <= victim_id <= 5:
                    fight_summary['red_team_kills'] += 1
                else:
                    fight_summary['blue_team_kills'] += 1
                
                # Check player involvement
                if killer_id == player_participant_id:
                    player_involvement.add('Kill')
                if victim_id == player_participant_id:
                    player_involvement.add('Death')
                if player_participant_id in kill.get('assistingParticipantIds', []):
                    player_involvement.add('Assist')

            if player_involvement:
                fight_summary['player_involvement'] = ', '.join(sorted(list(player_involvement)))

            fights.append(fight_summary)

    return fights

def _consolidate_fights_into_engagements(fights: list) -> list:
    """Merges sequential fights that are close together into single engagements."""
    if not fights:
        return []

    ENGAGEMENT_WINDOW_MINUTES = 0.75  # 45 seconds

    engagements = []
    current_engagement = fights[0].copy()
    current_engagement['kills'] = None # No longer need individual kill tracking

    for i in range(1, len(fights)):
        next_fight = fights[i]
        time_difference = next_fight['start_time_minutes'] - current_engagement['start_time_minutes']

        if time_difference <= ENGAGEMENT_WINDOW_MINUTES:
            # Merge this fight into the current engagement
            current_engagement['blue_team_kills'] += next_fight['blue_team_kills']
            current_engagement['red_team_kills'] += next_fight['red_team_kills']
            
            # Combine player involvement, avoiding duplicates
            p1_involvement = set(current_engagement['player_involvement'].split(', '))
            p2_involvement = set(next_fight['player_involvement'].split(', '))
            if 'None' in p1_involvement: p1_involvement.remove('None')
            if 'None' in p2_involvement: p2_involvement.remove('None')
            
            combined_involvement = p1_involvement.union(p2_involvement)
            if combined_involvement:
                current_engagement['player_involvement'] = ', '.join(sorted(list(combined_involvement)))
            else:
                current_engagement['player_involvement'] = 'None'
        else:
            # This fight is too far away, end the current engagement
            engagements.append(current_engagement)
            # Start a new one
            current_engagement = next_fight.copy()
            current_engagement['kills'] = None

    # Add the last engagement
    engagements.append(current_engagement)

    return engagements

def _analyze_objectives(timeline_data: dict) -> list:
    """Scans the timeline for major objective kills."""
    objectives = []
    all_events = []
    for frame in timeline_data['info']['frames']:
        all_events.extend(frame['events'])

    objective_kills = [e for e in all_events if e.get('type') == 'ELITE_MONSTER_KILL']

    for obj in objective_kills:
        team = "Blue" if obj.get('killerTeamId') == 100 else "Red"
        monster_type = obj.get('monsterType', 'UNKNOWN')
        if monster_type == 'DRAGON':
            monster_type = obj.get('monsterSubType', 'DRAGON') # Be more specific

        objectives.append({
            'time_minutes': round(obj['timestamp'] / 60000, 2),
            'team': team,
            'type': monster_type
        })
    
    return objectives

def _track_power_spikes(timeline_data: dict) -> dict:
    """
    Scans the timeline to identify moments when players gain significant power,
    such as completing a major item or achieving a multi-kill.
    """
    # NOTE: This is a sample list. A more robust solution would use a dynamic list of legendary items.
    LEGENDARY_ITEM_IDS = {3074, 3153, 6675, 3006, 6672, 3031, 3089, 4633, 6653, 6655}
    
    power_spikes = {i: [] for i in range(1, 11)} # Init for all 10 players

    all_events = []
    for frame in timeline_data['info']['frames']:
        all_events.extend(frame['events'])

    # 1. Track Major Item Completions
    item_events = [e for e in all_events if e.get('type') == 'ITEM_PURCHASED' and e.get('itemId') in LEGENDARY_ITEM_IDS]
    for event in item_events:
        player_id = event.get('participantId')
        spike = {
            'time_minutes': round(event['timestamp'] / 60000, 2),
            'type': 'Item Completion',
            'detail': f"Item ID {event.get('itemId')}" # A real version would map this to an item name
        }
        power_spikes[player_id].append(spike)

    # 2. Track Multi-kills (2+ kills in 30 seconds)
    kill_events = [e for e in all_events if e.get('type') == 'CHAMPION_KILL']
    for i, start_kill in enumerate(kill_events):
        killer_id = start_kill.get('killerId', 0)
        if killer_id == 0: continue # Minion/turret kill

        streak_count = 1
        window_end_time = start_kill['timestamp'] + 30000 # 30 second window

        for j in range(i + 1, len(kill_events)):
            next_kill = kill_events[j]
            if next_kill.get('killerId') == killer_id and next_kill['timestamp'] <= window_end_time:
                streak_count += 1
        
        if streak_count >= 2:
            spike = {
                'time_minutes': round(start_kill['timestamp'] / 60000, 2),
                'type': 'Killing Spree',
                'detail': f"{streak_count} kills"
            }
            # Avoid adding the same spree multiple times
            if not any(s['time_minutes'] == spike['time_minutes'] and s['type'] == 'Killing Spree' for s in power_spikes[killer_id]):
                 power_spikes[killer_id].append(spike)

    return power_spikes

def _generate_death_analysis(timeline_data: dict, match_data: dict, player_participant_id: int, power_spikes: dict) -> list:
    """Analyzes each player death to provide rich strategic context."""
    death_analyses = []
    all_events = []
    frames = timeline_data['info']['frames']
    for frame in frames:
        all_events.extend(frame['events'])

    player_deaths = [e for e in all_events if e.get('type') == 'CHAMPION_KILL' and e.get('victimId') == player_participant_id]

    for death in player_deaths:
        death_time_ms = death['timestamp']
        death_time_minutes = round(death_time_ms / 60000, 2)
        
        # Find the frame closest to the death for game state
        death_frame = None
        for frame in frames:
            if frame['timestamp'] >= death_time_ms:
                death_frame = frame['participantFrames']
                break
        
        analysis = {
            'time_minutes': death_time_minutes,
            'killed_by': "Unknown",
            'context': [],
            'outcome': []
        }

        # --- Analyze the Killer ---
        killer_id = death.get('killerId', 0)
        if killer_id > 0:
            for p in match_data['info']['participants']:
                if p['participantId'] == killer_id:
                    analysis['killed_by'] = p['championName']
                    break
            # Check if killer was on a power spike
            if killer_id in power_spikes:
                for spike in power_spikes[killer_id]:
                    if spike['time_minutes'] < death_time_minutes and spike['time_minutes'] > death_time_minutes - 1.5:
                        analysis['context'].append(f"Killer had recent '{spike['type']}' spike")
                        break
            # Check if killer was the most fed
            if death_frame:
                killer_gold = death_frame.get(str(killer_id), {}).get('totalGold', 0)
                enemy_team_ids = range(6, 11) if player_participant_id <= 5 else range(1, 6)
                is_strongest = True
                for team_id in enemy_team_ids:
                    if team_id != killer_id:
                        enemy_gold = death_frame.get(str(team_id), {}).get('totalGold', 0)
                        if enemy_gold > killer_gold:
                            is_strongest = False
                            break
                if is_strongest:
                    analysis['context'].append("Killer was their team's strongest player (by gold)")

        # --- Analyze Fight Context (Numerical Advantage & Gold Disparity) ---
        if death_frame:
            player_pos = death_frame.get(str(player_participant_id), {}).get('position', {})
            fight_participants_data = []

            if player_pos:
                # First, find all participants involved in the fight based on proximity
                for pid, p_frame in death_frame.items():
                    p_pos = p_frame.get('position', {})
                    if not p_pos: continue
                    distance = ((player_pos['x'] - p_pos['x'])**2 + (player_pos['y'] - p_pos['y'])**2)**0.5
                    if distance < 2000: # Increased radius for capturing fight participants
                        fight_participants_data.append(p_frame)

                # Numerical Advantage
                allies_nearby = sum(1 for p in fight_participants_data if (1 <= p['participantId'] <= 5) == (1 <= player_participant_id <= 5))
                enemies_nearby = len(fight_participants_data) - allies_nearby
                if allies_nearby != enemies_nearby:
                    analysis['context'].append(f"Fought in a {allies_nearby}v{enemies_nearby} situation")
                
                # Gold Disparity Analysis within the fight
                if len(fight_participants_data) > 1:
                    strongest_in_fight = max(fight_participants_data, key=lambda p: p['totalGold'])
                    weakest_in_fight = min(fight_participants_data, key=lambda p: p['totalGold'])
                    gold_diff = strongest_in_fight['totalGold'] - weakest_in_fight['totalGold']
                    
                    if gold_diff > 500: # Only note significant differences
                        analysis['context'].append(f"Fight gold disparity was {gold_diff}g")
                    
                    if killer_id == strongest_in_fight['participantId']:
                        analysis['context'].append("Killed by strongest in fight")
                    
                    if player_participant_id == weakest_in_fight['participantId']:
                        analysis['context'].append("Died as weakest in fight")

            # Game-wide strongest player check
            strongest_in_game = max(death_frame.values(), key=lambda p: p.get('totalGold', 0))
            if killer_id == strongest_in_game['participantId']:
                analysis['context'].append("Killed by strongest player in the game")

        # --- Analyze the Outcome (Objectives) ---
        for event in all_events:
            if event['timestamp'] > death_time_ms and event['timestamp'] <= death_time_ms + 60000:
                if event.get('type') == 'ELITE_MONSTER_KILL':
                    killer_team_id = 100 if 1 <= event.get('killerId', 0) <= 5 else 200
                    player_team_id = 100 if 1 <= player_participant_id <= 5 else 200
                    obj_type = event.get('monsterType', 'Objective')
                    if killer_team_id != player_team_id:
                        analysis['outcome'].append(f"Enemy took {obj_type}")
                    else:
                        analysis['outcome'].append(f"Allies took {obj_type} (trade)")
                    break

        if not analysis['context']: analysis['context'].append("No special circumstances noted.")
        if not analysis['outcome']: analysis['outcome'].append("No immediate objective change.")
        
        death_analyses.append(analysis)
        
    return death_analyses

def _analyze_duo_dynamics(match_data: dict, timeline_data: dict, player1_data: dict, player2_data: dict) -> dict:
    """Analyzes the interactions between two players in a match."""
    duo_analysis = {
        'kill_collaboration': {
            'p1_on_p2_kills': 0,
            'p2_on_p1_kills': 0,
            'total_p1_kills': player1_data.get('kills', 0),
            'total_p2_kills': player2_data.get('kills', 0),
        },
        'joint_objectives': []
    }
    
    p1_id = player1_data['participantId']
    p2_id = player2_data['participantId']

    all_events = []
    for frame in timeline_data['info']['frames']:
        all_events.extend(frame['events'])

    kill_events = [e for e in all_events if e.get('type') == 'CHAMPION_KILL']

    for kill in kill_events:
        killer_id = kill.get('killerId')
        assisting_ids = kill.get('assistingParticipantIds', [])
        
        # Player 1 killed, Player 2 assisted
        if killer_id == p1_id and p2_id in assisting_ids:
            duo_analysis['kill_collaboration']['p2_on_p1_kills'] += 1
            
        # Player 2 killed, Player 1 assisted
        if killer_id == p2_id and p1_id in assisting_ids:
            duo_analysis['kill_collaboration']['p1_on_p2_kills'] += 1

    objective_kills = [e for e in all_events if e.get('type') == 'ELITE_MONSTER_KILL']
    player_team_id = player1_data.get('teamId')

    for obj in objective_kills:
        if obj.get('killerTeamId') == player_team_id:
            involved_ids = [obj.get('killerId')] + obj.get('assistingParticipantIds', [])
            if p1_id in involved_ids and p2_id in involved_ids:
                monster_type = obj.get('monsterType', 'UNKNOWN')
                if monster_type == 'DRAGON':
                    monster_type = obj.get('monsterSubType', 'DRAGON')
                
                duo_analysis['joint_objectives'].append({
                    'time_minutes': round(obj['timestamp'] / 60000, 2),
                    'type': monster_type
                })

    return duo_analysis

def _analyze_duo_death_context(timeline_data: dict, player1_data: dict, player2_data: dict) -> list:
    """Analyzes what happens to one player when the other dies."""
    p1_id = player1_data['participantId']
    p2_id = player2_data['participantId']
    p1_champ = player1_data.get('championName', 'Player 1')
    p2_champ = player2_data.get('championName', 'Player 2')

    shared_death_events = []
    all_events = []
    for frame in timeline_data['info']['frames']:
        all_events.extend(frame['events'])

    player_deaths = [e for e in all_events if e.get('type') == 'CHAMPION_KILL' and e.get('victimId') in [p1_id, p2_id]]
    
    processed_timestamps = set()

    for death_event in player_deaths:
        if death_event['timestamp'] in processed_timestamps:
            continue

        victim_id = death_event['victimId']
        death_time_ms = death_event['timestamp']
        time_minutes = round(death_time_ms / 60000, 2)
        
        context = {
            'time_minutes': time_minutes,
            'event': '',
            'outcome': 'Nothing significant happened.'
        }

        # Look in a window around the death for the other player's actions
        window_start = death_time_ms - 10000 # 10s before
        window_end = death_time_ms + 15000 # 15s after
        
        other_player_action_found = False
        for event in all_events:
            if event['timestamp'] > window_start and event['timestamp'] < window_end:
                event_type = event.get('type')
                
                # Case 1: The other player also dies (Co-Death)
                if event_type == 'CHAMPION_KILL' and event.get('victimId') == (p2_id if victim_id == p1_id else p1_id):
                    context['event'] = f"{p1_champ} and {p2_champ} died together"
                    context['outcome'] = f"Both died within {abs(round((death_time_ms - event['timestamp'])/1000))}s"
                    processed_timestamps.add(event['timestamp']) # Mark the other death as processed
                    other_player_action_found = True
                    break
                
                # Case 2: The other player gets a kill (Revenge)
                if event_type == 'CHAMPION_KILL' and event.get('killerId') == (p2_id if victim_id == p1_id else p1_id):
                    victim_champ = p1_champ if victim_id == p1_id else p2_champ
                    avenger_champ = p2_champ if victim_id == p1_id else p1_champ
                    context['event'] = f"{victim_champ} died"
                    context['outcome'] = f"{avenger_champ} got a revenge kill {abs(round((event['timestamp'] - death_time_ms)/1000))}s later"
                    other_player_action_found = True
                    break

        if other_player_action_found:
            shared_death_events.append(context)

    return sorted(shared_death_events, key=lambda x: x['time_minutes'])

def analyze_match(match_id: str, puuids_to_analyze: list[str]) -> dict:
    """
    Performs a full analysis of a single match for a given list of players.

    Args:
        match_id: The ID of the match to analyze.
        puuids_to_analyze: A list of PUUIDs for the players to analyze.

    Returns:
        A dictionary containing the structured analysis for each player and duo dynamics.
    """
    full_analysis = {
        'match_id': match_id,
        'individual_reports': {},
        'duo_report': None
    }
    
    # 1. Fetch the raw data (only once)
    match_url = f"{config.RIOT_API_BASE_URL}/lol/match/v5/matches/{match_id}"
    timeline_url = f"{match_url}/timeline"
    headers = {"X-Riot-Token": config.RIOT_API_KEY}
    
    print(f"Fetching match data for {match_id}...")
    match_data = riot_api.make_api_request(match_url, headers)
    if not match_data:
        print("Failed to fetch match data. Aborting analysis.")
        return {"error": "Failed to fetch match data."}

    print(f"Fetching timeline data for {match_id}...")
    timeline_data = riot_api.make_api_request(timeline_url, headers)
    if not timeline_data:
        print("Failed to fetch timeline data. Some analyses will be skipped.")
        # We can continue without timeline, but many analyses will be empty

    # Pre-calculate power spikes for all players once
    power_spikes = _track_power_spikes(timeline_data) if timeline_data else {}

    all_player_data = {}
    for puuid in puuids_to_analyze:
        player_data = _get_player_participant_data(match_data, puuid)
        if not player_data:
            print(f"Warning: Could not find player with PUUID {puuid} in match data. Skipping.")
            continue
        all_player_data[puuid] = player_data

    # Generate individual reports
    for puuid, player_data in all_player_data.items():
        analysis = {}
        player_champion = player_data.get("championName", "Unknown")
        print(f"\\n--- Analyzing individual performance for {player_champion} ({puuid[:8]}...) ---")

        analysis['player_summary'] = {
            "championName": player_data.get("championName"),
            "lane": player_data.get("teamPosition") or player_data.get("lane"),
            "kills": player_data.get("kills"),
            "deaths": player_data.get("deaths"),
            "assists": player_data.get("assists"),
            "win": player_data.get("win"),
            "kda": player_data.get("challenges", {}).get("kda"),
            "killParticipation": player_data.get("challenges", {}).get("killParticipation"),
            "totalDamageDealtToChampions": player_data.get("totalDamageDealtToChampions"),
            "visionScore": player_data.get("visionScore"),
        }
        
        if timeline_data:
            opponent_data = _find_lane_opponent(match_data['info']['participants'], player_data)
            if opponent_data:
                analysis['laning_phase'] = _analyze_laning_phase(
                    timeline_data,
                    player_data['participantId'],
                    opponent_data['participantId']
                )
            
            raw_fights = _analyze_teamfights(
                timeline_data,
                player_data['participantId']
            )
            analysis['team_fights'] = _consolidate_fights_into_engagements(raw_fights)
            analysis['objectives'] = _analyze_objectives(timeline_data)
            analysis['death_analysis'] = _generate_death_analysis(
                timeline_data,
                match_data,
                player_data['participantId'],
                power_spikes
            )
        
        full_analysis['individual_reports'][player_champion] = analysis

    # Generate duo report if exactly two players were analyzed
    if len(all_player_data) == 2 and timeline_data:
        print("\\n--- Analyzing Duo Dynamics ---")
        puuids = list(all_player_data.keys())
        player1_data = all_player_data[puuids[0]]
        player2_data = all_player_data[puuids[1]]
        
        full_analysis['duo_report'] = _analyze_duo_dynamics(
            match_data, timeline_data, player1_data, player2_data
        )
        full_analysis['duo_report']['death_context'] = _analyze_duo_death_context(
            timeline_data, player1_data, player2_data
        )

    # --- Print Results ---
    for champion, report in full_analysis.get('individual_reports', {}).items():
        print(f"\\n--- Report for: {champion} ---")
        player_data = next((p for p in match_data['info']['participants'] if p['championName'] == champion), {})

        print("\\n--- Player Summary ---")
        for key, value in report.get('player_summary', {}).items():
            print(f"{key}: {value}")
        
        if 'laning_phase' in report:
            print("\\n--- Laning Phase Analysis (at 10:00) ---")
            for key, value in report['laning_phase'].items():
                print(f"{key}: {value}")
        
        if report.get('team_fights'):
            print("\\n--- Key Engagements Summary ---")
            for i, fight in enumerate(report['team_fights']):
                player_is_blue_team = 1 <= player_data.get('participantId', 0) <= 5
                
                if player_is_blue_team:
                    outcome = "Won" if fight['blue_team_kills'] > fight['red_team_kills'] else "Lost" if fight['red_team_kills'] > fight['blue_team_kills'] else "Even"
                else:
                    outcome = "Won" if fight['red_team_kills'] > fight['blue_team_kills'] else "Lost" if fight['blue_team_kills'] > fight['red_team_kills'] else "Even"

                print(f"  Engagement {i+1} around {fight['start_time_minutes']:.2f}m: Outcome: {outcome} ({fight['blue_team_kills']} vs {fight['red_team_kills']}) | Your Involvement: {fight['player_involvement']}")
        
        if report.get('objectives'):
            print("\\n--- Objective Control Timeline ---")
            for obj in report['objectives']:
                print(f"  {obj['time_minutes']:.2f}m: {obj['team']} team took {obj['type']}")
        
        if report.get('death_analysis'):
            print("\\n--- Death Analysis ---")
            player_champion_name = report.get('player_summary', {}).get('championName', 'Player')
            for death in report['death_analysis']:
                print(f"  - [{death['time_minutes']:.2f}m] {player_champion_name.upper()} DEATH killed by {death['killed_by']}")
                print(f"    - Context: {'; '.join(death['context'])}")
                print(f"    - Outcome: {'; '.join(death['outcome'])}")

    if full_analysis.get('duo_report'):
        duo_report = full_analysis['duo_report']
        p1_name = list(full_analysis['individual_reports'].keys())[0]
        p2_name = list(full_analysis['individual_reports'].keys())[1]
        
        print(f"\\n--- Duo Dynamics Report: {p1_name} & {p2_name} ---")

        # Kill Collaboration
        collab = duo_report['kill_collaboration']
        p1_total_kills = collab.get('total_p1_kills', 0)
        p2_total_kills = collab.get('total_p2_kills', 0)
        p1_assisted_by_p2 = collab.get('p1_on_p2_kills', 0)
        p2_assisted_by_p1 = collab.get('p2_on_p1_kills', 0)

        p1_percentage = (p2_assisted_by_p1 / p1_total_kills * 100) if p1_total_kills > 0 else 0
        p2_percentage = (p1_assisted_by_p2 / p2_total_kills * 100) if p2_total_kills > 0 else 0

        print("\\n- Kill Collaboration:")
        print(f"  - {p2_name} assisted on {p2_assisted_by_p1}/{p1_total_kills} of {p1_name}'s kills ({p1_percentage:.1f}%)")
        print(f"  - {p1_name} assisted on {p1_assisted_by_p2}/{p2_total_kills} of {p2_name}'s kills ({p2_percentage:.1f}%)")
        
        # Joint Objectives
        joint_objs = duo_report.get('joint_objectives', [])
        if joint_objs:
            print("\\n- Joint Objectives Taken:")
            for obj in joint_objs:
                print(f"  - [{obj['time_minutes']:.2f}m] {obj['type']}")
        else:
            print("\\n- No major objectives were taken with both players involved.")

        if full_analysis['duo_report'].get('death_context'):
            print("\\n- Shared Deaths & Trades:")
            for event in full_analysis['duo_report']['death_context']:
                print(f"  - [{event['time_minutes']:.2f}m] {event['event']}: {event['outcome']}")

    return full_analysis

def run_match_analysis_dynamically(match_id: str, primary_puuid: str, all_friends_puuids: list[str]) -> dict:
    """
    Analyzes a match, dynamically including a duo report if a known friend is present.

    Args:
        match_id: The ID of the match to analyze.
        primary_puuid: The PUUID of the main player.
        all_friends_puuids: A list of all potential friend PUUIDs to check for.

    Returns:
        The analysis dictionary.
    """
    # First, just fetch the match data to see who played
    match_url = f"{config.RIOT_API_BASE_URL}/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": config.RIOT_API_KEY}
    
    print(f"Fetching match participants for {match_id}...")
    match_data = riot_api.make_api_request(match_url, headers)
    if not match_data:
        print("Failed to fetch match data. Aborting analysis.")
        return {"error": "Failed to fetch match data."}
    
    match_participant_puuids = match_data['metadata']['participants']
    
    # The primary player is always analyzed
    puuids_to_analyze = [primary_puuid]
    
    # Check if any known friends were in this game
    for friend_puuid in all_friends_puuids:
        if friend_puuid in match_participant_puuids and friend_puuid != primary_puuid:
            print(f"Friend with PUUID {friend_puuid[:8]}... found in match. Adding to analysis.")
            puuids_to_analyze.append(friend_puuid)
            # Current design only supports one extra for duo, so break after finding one.
            break 
    
    # Now, call the main analysis engine with the determined list of players
    return analyze_match(match_id, puuids_to_analyze)

# --- Test Execution ---
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    # Force a reload of the .env file.
    load_dotenv(override=True)
    
    # --- CHOOSE A MATCH TO TEST ---
    # test_match_id = "NA1_5303507089" # A game with a friend
    # test_match_id = "NA1_5303910725" # A solo game
    #test_match_id = "NA1_5303904011" # The loss to analyze
    test_match_id = "NA1_5304525582" # Solo win to analyze
    
    primary_puuid = os.getenv("RIOT_PUUID")
    
    # Gather all potential friend PUUIDs from .env
    friends_puuids = [
        os.getenv("FRIEND1_RIOT_PUUID"),
        # Add os.getenv("FRIEND2_RIOT_PUUID") here in the future
    ]
    friends_puuids = [p for p in friends_puuids if p] # Filter out None values

    if not primary_puuid or not config.RIOT_API_KEY:
        print("Please ensure RIOT_PUUID and RIOT_API_KEY are set in your .env file.")
    else:
        print(f"--- Running Dynamic Analysis for Match: {test_match_id} ---")
        run_match_analysis_dynamically(test_match_id, primary_puuid, friends_puuids) 