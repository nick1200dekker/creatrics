from flask import Blueprint, render_template, jsonify, request
from app.system.auth.middleware import optional_auth
from app.system.services.firebase_service import db
import logging
from datetime import datetime, timedelta

# Create logger
logger = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint('tp_analytics', __name__, url_prefix='/tp-analytics')

@bp.route('/')
@optional_auth
def index():
    """TP Analytics main page"""
    logger.info("Rendering TP Analytics page")
    return render_template('tp_analytics/index.html')

@bp.route('/api/player-tp-data')
@optional_auth
def get_player_tp_data():
    """Get TP data for all players based on last 10 matches"""
    try:
        logger.info("Fetching TP data")
        
        # Fetch all players from global_players collection
        players_ref = db.collection('global_players')
        players_docs = players_ref.get()
        
        players_data = []
        
        for doc in players_docs:
            player = doc.to_dict()
            player['id'] = doc.id
            
            # Check if player has match data
            match_level_stats = player.get('match_level_stats', {})
            matches = match_level_stats.get('matches', [])
            
            # Skip players without match data
            if not matches:
                continue
            
            # Only get all matches with TP data (only count non-zero scores)
            all_tp_matches = []
            for match in matches:  # Already sorted by date (most recent first)
                if match.get('fdf_score') and match.get('date'):
                    tp_value = round(match['fdf_score']['total'])
                    # Only include matches where player actually played (TP > 0)
                    if tp_value > 0:
                        all_tp_matches.append({
                            'date': match['date'],
                            'tp': tp_value,
                            'fixture_id': match['fixture_id'],
                            'teams': match.get('teams', []),
                            'score': match.get('score', 'N/A')
                        })
            
            if all_tp_matches:
                # Get last 10 matches where player played
                last_10_matches = all_tp_matches[:10]
                
                # Calculate statistics from last 10 matches ONLY
                if last_10_matches:
                    last_10_tp_values = [m['tp'] for m in last_10_matches]
                    
                    # Get display name (prefer nickname if available)
                    display_name = player.get('nickname') if player.get('nickname') else player.get('name', 'Unknown')
                    
                    player_summary = {
                        'id': player['id'],
                        'name': player.get('name', 'Unknown'),
                        'nickname': player.get('nickname', ''),
                        'display_name': display_name,
                        'position': player.get('position', {}).get('name', 'Unknown'),
                        'position_category': player.get('position', {}).get('category', 'Unknown'),
                        'team': player.get('current_team', {}).get('name', 'Free Agent'),
                        'image_path': player.get('image_path'),
                        'matches_played': len(last_10_matches),  # How many of last 10 they played
                        'tp_min_10': round(min(last_10_tp_values)),
                        'tp_max_10': round(max(last_10_tp_values)),
                        'tp_avg_10': round(sum(last_10_tp_values) / len(last_10_tp_values)),
                        'tp_total_10': round(sum(last_10_tp_values)),
                        'last_10_tp': last_10_matches  # For sparkline and timeline
                    }
                    players_data.append(player_summary)
        
        # Sort by average TP from last 10 matches (descending)
        players_data.sort(key=lambda x: x['tp_avg_10'], reverse=True)
        
        logger.info(f"Found {len(players_data)} players with TP data")
        
        return jsonify({
            'success': True,
            'players': players_data,
            'total_players': len(players_data)
        })
        
    except Exception as e:
        logger.error(f"Error fetching TP data: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/tp-timeline')
@optional_auth
def get_tp_timeline():
    """Get TP timeline data for charts"""
    try:
        # Get all players
        players_ref = db.collection('global_players')
        players_docs = players_ref.get()
        
        # Collect all matches with TP data
        all_matches = []
        
        for doc in players_docs:
            player = doc.to_dict()
            player_name = player.get('name', 'Unknown')
            player_nickname = player.get('nickname', '')
            display_name = player_nickname if player_nickname else player_name
            position_category = player.get('position', {}).get('category', 'Unknown')
            
            match_level_stats = player.get('match_level_stats', {})
            matches = match_level_stats.get('matches', [])
            
            # Only get last 10 matches for each player where they played
            player_matches = []
            for match in matches:
                if match.get('fdf_score') and match.get('date'):
                    tp_value = round(match['fdf_score']['total'])
                    # Only include matches where player actually played (TP > 0)
                    if tp_value > 0:
                        player_matches.append({
                            'date': match['date'],
                            'tp': tp_value,
                            'player_name': display_name,
                            'player_id': doc.id,
                            'position_category': position_category,
                            'fixture_id': match['fixture_id']
                        })
                        # Stop after 10 matches
                        if len(player_matches) >= 10:
                            break
            
            all_matches.extend(player_matches)
        
        # Sort by date
        all_matches.sort(key=lambda x: x['date'])
        
        # Group by date for timeline
        timeline_data = {}
        for match in all_matches:
            date = match['date'][:10]  # Get just the date part
            if date not in timeline_data:
                timeline_data[date] = {
                    'date': date,
                    'matches': [],
                    'avg_tp': 0,
                    'max_tp': 0,
                    'min_tp': float('inf')
                }
            
            timeline_data[date]['matches'].append(match)
            
        # Calculate daily statistics
        timeline_list = []
        for date, data in timeline_data.items():
            tp_values = [m['tp'] for m in data['matches']]
            data['avg_tp'] = round(sum(tp_values) / len(tp_values))
            data['max_tp'] = round(max(tp_values))
            data['min_tp'] = round(min(tp_values))
            data['match_count'] = len(data['matches'])
            timeline_list.append(data)
        
        # Sort by date and get last 30 days
        timeline_list.sort(key=lambda x: x['date'])
        timeline_list = timeline_list[-30:]  # Last 30 days with data
        
        return jsonify({
            'success': True,
            'timeline': timeline_list
        })
        
    except Exception as e:
        logger.error(f"Error fetching TP timeline: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/position-categories')
@optional_auth
def get_position_categories():
    """Get all unique position categories for filtering"""
    try:
        players_ref = db.collection('global_players')
        players_docs = players_ref.get()
        
        categories = set()
        
        for doc in players_docs:
            player = doc.to_dict()
            # Only include categories from players with match data
            match_level_stats = player.get('match_level_stats', {})
            if match_level_stats.get('matches'):
                category = player.get('position', {}).get('category')
                if category:
                    categories.add(category)
        
        return jsonify({
            'success': True,
            'categories': sorted(list(categories))
        })
        
    except Exception as e:
        logger.error(f"Error fetching position data: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500