from flask import Blueprint, request, jsonify, g, render_template
from app.system.auth.middleware import auth_required, optional_auth
from app.routes.core.core_routes import admin_required
from app.scripts.player_stats.player_service import PlayerStatsService
import logging

# Create logger
logger = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint('player_stats', __name__, url_prefix='/player-stats')

# Initialize service
player_service = PlayerStatsService()

@bp.route('/')
@optional_auth
def index():
    """Player Stats main page"""
    logger.info("Rendering player stats page")
    return render_template('player_stats/index.html')

@bp.route('/add-players')
@auth_required
@admin_required
def add_players():
    """Add Players Page - Admin only"""
    return render_template('player_stats/add_players.html')

@bp.route('/api/search')
@auth_required
def search_players():
    """API endpoint to search for players"""
    query = request.args.get('q', '')
    
    if not query or len(query) < 2:
        return jsonify({'error': 'Query must be at least 2 characters'}), 400
    
    logger.info(f"Searching for players: {query}")
    
    try:
        # Search players using SportMonks API
        players = player_service.search_players(query)
        
        # Format response for frontend
        formatted_players = []
        for player in players:
            # Get current team info - check multiple possible structures
            current_team = None
            
            # First check if teams data exists
            if player.get('teams') and isinstance(player['teams'], list):
                # Find the current domestic team
                for team_data in player['teams']:
                    if isinstance(team_data, dict):
                        team = team_data.get('team', {})
                        if isinstance(team, dict) and team.get('type') == 'domestic':
                            current_team = {
                                'id': team.get('id'),
                                'name': team.get('name', 'Unknown Club'),
                                'image_path': team.get('image_path')
                            }
                            break
            
            # If no team found, check for currentTeam field
            if not current_team and player.get('currentTeam'):
                current_team = {
                    'id': player['currentTeam'].get('id'),
                    'name': player['currentTeam'].get('name', 'Unknown Club'),
                    'image_path': player['currentTeam'].get('image_path')
                }
            
            # Get position - check multiple possible fields
            position_name = 'Unknown Position'
            
            # Try different position fields in order of preference
            if player.get('detailedPosition') and isinstance(player['detailedPosition'], dict):
                position_name = player['detailedPosition'].get('name', position_name)
            elif player.get('position') and isinstance(player['position'], dict):
                position_name = player['position'].get('name', position_name)
            elif player.get('position_id'):
                # Map position ID to name
                position_mapping = {
                    1: "Goalkeeper",
                    2: "Right Back", 
                    3: "Left Back",
                    4: "Centre Back",
                    5: "Sweeper",
                    6: "Defensive Midfielder",
                    7: "Right Midfielder",
                    8: "Central Midfielder", 
                    9: "Left Midfielder",
                    10: "Attacking Midfielder",
                    11: "Right Winger",
                    12: "Left Winger",
                    13: "Centre Forward",
                    14: "Striker",
                    15: "Second Striker",
                    24: "Goalkeeper",
                    25: "Defender",
                    26: "Midfielder",
                    27: "Attacker"
                }
                position_name = position_mapping.get(player['position_id'], f"Position {player['position_id']}")
            
            # Get position category for filtering
            def get_position_category(pos_id):
                if not pos_id:
                    return 'Unknown'
                # Goalkeeper IDs
                if pos_id in [1, 24]:
                    return 'Goalkeeper'
                # Defender IDs  
                elif pos_id in [2, 3, 4, 5, 25]:
                    return 'Defender'
                # Midfielder IDs
                elif pos_id in [6, 7, 8, 9, 10, 26]:
                    return 'Midfielder'
                # Attacker IDs
                elif pos_id in [11, 12, 13, 14, 15, 27]:
                    return 'Attacker'
                return 'Unknown'
            
            position_category = get_position_category(player['position_id'])
            
            formatted_player = {
                'id': player.get('id'),
                'name': player.get('name', ''),
                'display_name': player.get('display_name', ''),
                'common_name': player.get('common_name', ''),
                'position': position_name,
                'position_category': position_category,
                'image_path': player.get('image_path'),
                'age': player_service._calculate_age(player.get('date_of_birth')),
                'current_team': current_team
            }
            formatted_players.append(formatted_player)
        
        logger.info(f"Formatted {len(formatted_players)} players for search results")
        return jsonify({'players': formatted_players})
        
    except Exception as e:
        logger.error(f"Error searching players: {str(e)}")
        return jsonify({'error': 'Failed to search players'}), 500

@bp.route('/api/players')
@optional_auth
def get_user_players():
    """Get all players in the global database (visible to all users)"""
    try:
        players = player_service.get_all_players()
        return jsonify({'players': players})
    except Exception as e:
        logger.error(f"Error getting players: {str(e)}")
        return jsonify({'error': 'Failed to get players'}), 500

@bp.route('/api/players', methods=['POST'])
@auth_required
@admin_required
def add_player():
    """Add a player to the global database (admin only)"""
    try:
            
        data = request.get_json()
        player_id = data.get('player_id')
        nickname = data.get('nickname', '').strip()
        
        if not player_id:
            return jsonify({'error': 'Player ID is required'}), 400
        
        # Check if player already exists
        if player_service.player_exists(player_id):
            return jsonify({'error': 'Player already exists in database'}), 400
        
        # Fetch detailed player data from API (includes team data)
        logger.info(f"Fetching detailed data for player ID: {player_id}")
        player_data = player_service.fetch_player_data(player_id)
        if not player_data:
            return jsonify({'error': 'Player not found'}), 404
        
        # Add nickname to player data if provided
        if nickname:
            player_data['nickname'] = nickname
            logger.info(f"Adding nickname '{nickname}' for player {player_data.get('name')}")
        
        # Log team data for debugging
        current_team = player_data.get('current_team', {})
        logger.info(f"Player {player_data.get('name')} team data: {current_team}")
        
        # Store player data with nickname
        success = player_service.store_player_globally(player_data)
        if success:
            # Also add to registry for scheduled updates
            metadata = {
                'team': current_team.get('name', 'Free Agent'),
                'position': player_data.get('position', {}).get('name', 'Unknown'),
                'league': current_team.get('league', {}).get('name', 'Unknown') if current_team.get('league') else 'Unknown'
            }
            player_service.add_player_to_registry(
                player_id, 
                nickname or player_data.get('name', 'Unknown Player'), 
                metadata
            )
            
            # Return formatted player data for immediate display
            formatted_player = {
                'id': player_data.get('id'),
                'name': player_data.get('name', ''),
                'nickname': nickname,
                'display_name': nickname or player_data.get('display_name', ''),
                'common_name': player_data.get('common_name', ''),
                'position': player_data.get('position', {}).get('name', 'Unknown'),
                'image_path': player_data.get('image_path'),
                'age': player_service._calculate_age(player_data.get('date_of_birth')),
                'current_team': current_team.get('name', 'Free Agent')
            }
            
            return jsonify({
                'message': 'Player added successfully', 
                'player': formatted_player
            })
        else:
            return jsonify({'error': 'Failed to store player data'}), 500
            
    except Exception as e:
        logger.error(f"Error adding player: {str(e)}")
        return jsonify({'error': 'Failed to add player'}), 500

@bp.route('/api/players/<player_id>', methods=['DELETE'])
@auth_required
@admin_required
def remove_player(player_id):
    """Remove a player from the global database (admin only)"""
    try:
        success = player_service.remove_player_globally(player_id)
        
        if success:
            return jsonify({'message': 'Player removed successfully'})
        else:
            return jsonify({'error': 'Failed to remove player'}), 500
    except Exception as e:
        logger.error(f"Error removing player: {str(e)}")
        return jsonify({'error': 'Failed to remove player'}), 500

@bp.route('/api/player-details/<player_id>')
@optional_auth
def get_player_details(player_id):
    """Get detailed player information and analysis from global database"""
    try:
        player_data = player_service.get_player_details_globally(player_id)
        
        if not player_data:
            return jsonify({'error': 'Player not found'}), 404
        
        # Generate performance analysis
        analysis = player_service.analyze_player_performance(player_data)
        
        response = {
            'player': player_data,
            'analysis': analysis
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting player details: {str(e)}")
        return jsonify({'error': 'Failed to get player details'}), 500

@bp.route('/player/<player_id>')
@optional_auth
def player_details(player_id):
    """Player details page"""
    return render_template('player_stats/player_details.html', player_id=player_id)

@bp.route('/api/registry')
@auth_required
@admin_required
def get_player_registry():
    """Get all players in the registry"""
    try:
        players = player_service.get_all_players()
        return jsonify({'players': players})
    except Exception as e:
        logger.error(f"Error getting player registry: {str(e)}")
        return jsonify({'error': 'Failed to get player registry'}), 500

@bp.route('/api/registry/update-all', methods=['POST'])
@auth_required
@admin_required
def update_all_players():
    """Update all players in the registry"""
    try:
        updated_count = player_service.update_all_players()
        return jsonify({
            'message': f'Updated {updated_count} players successfully',
            'updated_count': updated_count
        })
    except Exception as e:
        logger.error(f"Error updating all players: {str(e)}")
        return jsonify({'error': 'Failed to update all players'}), 500

@bp.route('/api/players/<player_id>/nickname', methods=['POST'])
@auth_required
@admin_required
def update_player_nickname(player_id):
    """API endpoint to update a player's nickname."""
    data = request.get_json()
    nickname = data.get('nickname')

    if nickname is None:
        return jsonify({'error': 'Nickname not provided'}), 400

    success = player_service.update_player_nickname(player_id, nickname)

    if success:
        return jsonify({'message': 'Nickname updated successfully'}), 200
    else:
        return jsonify({'error': 'Failed to update nickname'}), 500