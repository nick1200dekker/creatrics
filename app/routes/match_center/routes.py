from flask import Blueprint, render_template, jsonify, request
from app.system.auth.middleware import optional_auth
from app.system.services.firebase_service import db
import logging
from datetime import datetime, timedelta

# Create logger
logger = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint('match_center', __name__, url_prefix='/match-center')

@bp.route('/')
@optional_auth
def index():
    """Match Center main page"""
    logger.info("Rendering Match Center page")
    return render_template('match_center/index.html')

@bp.route('/api/matches-data')
@optional_auth
def get_matches_data():
    """Get upcoming and recent matches with player data"""
    try:
        # Calculate date range: 2 weeks back, 4 weeks ahead
        today = datetime.now()
        start_date = today - timedelta(weeks=2)
        end_date = today + timedelta(weeks=4)
        
        logger.info(f"Date range: {start_date} to {end_date}, today: {today}")
        
        # Get all players to map teams to our players
        players_ref = db.collection('global_players')
        players_docs = players_ref.get()
        
        # Build team to players mapping
        team_players = {}
        for doc in players_docs:
            player = doc.to_dict()
            team_name = player.get('current_team', {}).get('name')
            if team_name:
                if team_name not in team_players:
                    team_players[team_name] = []
                team_players[team_name].append({
                    'id': doc.id,
                    'name': player.get('name', 'Unknown'),
                    'nickname': player.get('nickname', ''),
                    'display_name': player.get('nickname') or player.get('name', 'Unknown'),
                    'position': player.get('position', {}).get('name', 'Unknown'),
                    'position_category': player.get('position', {}).get('category', 'Unknown'),
                    'image_path': player.get('image_path', ''),
                    'tp_avg': player.get('tp_avg_10', 0)  # Add tournament points average
                })
        
        # First pass: Create a mapping of fixture_id -> player_id -> fdf_score for historical matches
        player_fdf_scores = {}
        
        for doc in players_docs:
            player = doc.to_dict()
            player_id = doc.id
            
            # Get historical matches with FDF scores
            match_level_stats = player.get('match_level_stats', {})
            historical_matches = match_level_stats.get('matches', [])
            
            for match in historical_matches:
                fixture_id = match.get('fixture_id')
                fdf_score = match.get('fdf_score', {}).get('total', 0)
                if fixture_id and fdf_score > 0:
                    if fixture_id not in player_fdf_scores:
                        player_fdf_scores[fixture_id] = {}
                    player_fdf_scores[fixture_id][player_id] = fdf_score
                    logger.debug(f"Added FDF score for player {player_id} in fixture {fixture_id}: {fdf_score}")
        
        # Second pass: Collect all matches from players within date range
        all_matches = []
        processed_fixtures = set()  # Avoid duplicates
        
        for doc in players_docs:
            player = doc.to_dict()
            
            # Get historical matches
            match_level_stats = player.get('match_level_stats', {})
            historical_matches = match_level_stats.get('matches', [])
            
            # Get upcoming matches
            team_matches = player.get('team_matches', {})
            upcoming_matches = team_matches.get('upcoming_matches', [])
            
            # Process both historical and upcoming matches
            all_player_matches = historical_matches + upcoming_matches
            
            for match in all_player_matches:
                if not match.get('date') or not match.get('fixture_id'):
                    continue
                    
                match_date = datetime.fromisoformat(match['date'].replace('Z', '+00:00'))
                fixture_id = match['fixture_id']
                
                # Skip if outside date range or already processed
                if match_date < start_date or match_date > end_date or fixture_id in processed_fixtures:
                    continue
                
                # Debug: Log match dates to understand data
                logger.debug(f"Processing match: {fixture_id}, date: {match_date}, is_future: {match_date > today}")
                
                processed_fixtures.add(fixture_id)
                
                # Get teams involved - handle different formats
                teams = match.get('teams', [])
                
                # For upcoming matches, teams might be in different format
                if not teams and 'home_team' in match and 'away_team' in match:
                    teams = [
                        {'name': match['home_team'], 'id': match.get('home_team_id')},
                        {'name': match['away_team'], 'id': match.get('away_team_id')}
                    ]
                
                if not teams:
                    continue
                
                # Check if any of our players are in these teams and group by team
                involved_players_by_team = {}
                for team_info in teams:
                    team_name = team_info.get('name', '')
                    if team_name in team_players:
                        # For recent matches, add individual player FDF scores
                        players_with_scores = []
                        for player in team_players[team_name]:
                            player_copy = player.copy()
                            # Add individual FDF score for this player in this match
                            if match_date <= today and fixture_id in player_fdf_scores:
                                player_id = player['id']
                                if player_id in player_fdf_scores[fixture_id]:
                                    player_copy['match_fdf_score'] = player_fdf_scores[fixture_id][player_id]
                            players_with_scores.append(player_copy)
                        involved_players_by_team[team_name] = players_with_scores
                
                # Flatten for backwards compatibility
                involved_players = []
                for team_players_list in involved_players_by_team.values():
                    involved_players.extend(team_players_list)
                
                if involved_players:
                    # Handle different data structures for historical vs upcoming matches
                    if 'league' in match and isinstance(match['league'], dict):
                        # Historical match format
                        league_name = match['league'].get('name', 'Unknown')
                        league_type = match['league'].get('type', 'unknown')
                    else:
                        # Upcoming match format
                        league_name = match.get('league', 'Unknown')
                        league_type = match.get('league_type', 'unknown')
                    
                    # Handle predictions for upcoming matches
                    predictions = match.get('predictions', {})
                    if predictions and any(predictions.values()):
                        prediction_text = f"Home: {predictions.get('home_win', 0):.1f}% | Draw: {predictions.get('draw', 0):.1f}% | Away: {predictions.get('away_win', 0):.1f}%"
                    else:
                        prediction_text = ''
                    
                    match_info = {
                        'fixture_id': fixture_id,
                        'date': match['date'],
                        'teams': teams,
                        'score': match.get('score', ''),
                        'league': league_name,
                        'league_type': league_type,
                        'is_upcoming': match_date > today,
                        'our_players': involved_players,
                        'players_by_team': involved_players_by_team,
                        'prediction': prediction_text
                    }
                    all_matches.append(match_info)
        
        # Determine live matches (within 2 hours of match time)
        live_matches = []
        upcoming_matches = []
        recent_matches = []
        
        for match in all_matches:
            match_date = datetime.fromisoformat(match['date'].replace('Z', '+00:00'))
            time_diff = (today - match_date).total_seconds() / 3600  # hours
            
            # Live match: started within last 2 hours and no final score yet
            is_live = (-0.25 <= time_diff <= 2.5) and not match.get('score')
            
            if is_live:
                match['is_live'] = True
                live_matches.append(match)
            elif match['is_upcoming']:
                upcoming_matches.append(match)
            else:
                recent_matches.append(match)
        
        # Sort upcoming by date (soonest first)
        upcoming_matches.sort(key=lambda x: datetime.fromisoformat(x['date'].replace('Z', '+00:00')))
        
        # Sort recent by date (latest first)
        recent_matches.sort(key=lambda x: datetime.fromisoformat(x['date'].replace('Z', '+00:00')), reverse=True)
        
        logger.info(f"Found {len(live_matches)} live, {len(upcoming_matches)} upcoming and {len(recent_matches)} recent matches")
        
        # Debug: Log sample player data to check tp_avg field
        if recent_matches:
            sample_match = recent_matches[0]
            if 'players_by_team' in sample_match:
                for team, players in sample_match['players_by_team'].items():
                    if players:
                        logger.info(f"Sample player data: {players[0]}")
                        break
        
        # Debug: Log some upcoming matches to see what we're getting
        if upcoming_matches:
            logger.info(f"Sample upcoming match: {upcoming_matches[0]['fixture_id']} on {upcoming_matches[0]['date']}")
        else:
            logger.warning("No upcoming matches found - check data structure")
        
        return jsonify({
            'success': True,
            'live_matches': live_matches,
            'upcoming_matches': upcoming_matches,
            'recent_matches': recent_matches,
            'total_matches': len(all_matches),
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching matches data: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
