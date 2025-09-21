
"""
CURRENT CODE
Player Stats Service for SportMonks API integration - FANTASY FOOTBALL OPTIMIZED VERSION
Handles fetching, storing, and analyzing player data with focus on recent performance and seasonal stats
Includes team injuries and suspensions tracking
"""
import http.client
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from firebase_admin import firestore
from app.system.services.firebase_service import db

logger = logging.getLogger(__name__)

class PlayerStatsService:
    def __init__(self):
        self.api_token = "i4zoD5475PEGTaTfD4pwCNflW2phaCZU59HeO30VHeqcFMowHAkycay8E2ga"
        self.base_url = "api.sportmonks.com"

    def fetch_player_data(self, player_id: int) -> Optional[Dict]:
        """
        Fetch comprehensive player data from SportMonks API - FANTASY FOOTBALL VERSION
        Focus on recent matches (last 4 weeks) and seasonal statistics
        Now includes team injuries and suspensions
        
        Args:
            player_id: SportMonks player ID
            
        Returns:
            Player data dictionary or None if error
        """
        try:
            conn = http.client.HTTPSConnection(self.base_url)
            # Optimized includes for fantasy football: recent matches + seasonal stats + ratings
            includes = "trophies.league;trophies.season;trophies.trophy;trophies.team;teams.team;statistics.details.type;statistics.team;statistics.season.league;latest.fixture.participants;latest.fixture.league;latest.fixture.scores;latest.details.type;nationality;detailedPosition;metadata.type"
            endpoint = f"/v3/football/players/{player_id}?api_token={self.api_token}&include={includes}"
            
            logger.info(f"Fetching fantasy football player data from: {endpoint}")
            conn.request("GET", endpoint, "", {})
            response = conn.getresponse()
            data = response.read()
            conn.close()
            
            logger.info(f"API response status: {response.status}")
            if response.status == 200:
                result = json.loads(data.decode("utf-8"))
                player_data = result.get('data')
                
                # Fetch team matches if player has a current team
                if player_data and 'teams' in player_data and player_data['teams']:
                    club_teams = [team for team in player_data['teams'] 
                                if team.get('team', {}).get('type') == 'domestic']
                    if club_teams:
                        team_id = club_teams[0]['team']['id']
                        team_matches = self.fetch_team_matches(team_id)
                        
                        if team_matches:
                            player_data['team_matches'] = team_matches
                            
                            # NEW: Fetch injuries for relevant fixtures
                            fixture_ids = self.get_relevant_fixture_ids(team_matches)
                            if fixture_ids:
                                injuries_data = self.fetch_team_injuries_suspensions(team_id, fixture_ids)
                                player_data['team_injuries'] = injuries_data
                
                return player_data
            elif response.status == 404 or response.status == 403:
                logger.warning(f"Status {response.status}, trying minimal includes...")
                return self._fetch_player_data_minimal(player_id)
            else:
                error_data = data.decode("utf-8")
                logger.error(f"API request failed with status {response.status}: {error_data}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching player data: {str(e)}")
            return None
    
    def fetch_team_matches(self, team_id: int) -> Optional[Dict]:
        """
        Fetch team's recent and upcoming matches with predictions
        
        Args:
            team_id: SportMonks team ID
            
        Returns:
            Team matches data or None if error
        """
        try:
            conn = http.client.HTTPSConnection(self.base_url)
            # Add predictions to the includes for upcoming matches
            includes = "upcoming.participants;upcoming.league;upcoming.predictions.type;latest.participants;latest.scores;latest.league"
            endpoint = f"/v3/football/teams/{team_id}?api_token={self.api_token}&include={includes}"
            
            logger.info(f"Fetching team matches with predictions from: {endpoint}")
            conn.request("GET", endpoint, "", {})
            response = conn.getresponse()
            data = response.read()
            conn.close()
            
            if response.status == 200:
                result = json.loads(data.decode("utf-8"))
                return result.get('data')
            else:
                logger.error(f"Failed to fetch team matches: {response.status}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching team matches: {str(e)}")
            return None
    
    def fetch_team_injuries_suspensions(self, team_id: int, fixture_ids: List[int]) -> Dict:
        """
        Fetch team injuries and suspensions for specific fixtures
        
        Args:
            team_id: Team ID
            fixture_ids: List of fixture IDs (previous and next match)
            
        Returns:
            Dictionary with injury/suspension data for each fixture
        """
        try:
            injuries_data = {}
            
            for fixture_id in fixture_ids[:2]:  # Limit to 2 fixtures max
                conn = http.client.HTTPSConnection(self.base_url)
                includes = "sidelined.sideline.player;sidelined.sideline.type;participants;league;venue;state"
                endpoint = f"/v3/football/fixtures/{fixture_id}?api_token={self.api_token}&include={includes}"
                
                logger.info(f"Fetching injuries/suspensions for fixture {fixture_id}")
                conn.request("GET", endpoint, "", {})
                response = conn.getresponse()
                data = response.read()
                conn.close()
                
                if response.status == 200:
                    result = json.loads(data.decode("utf-8"))
                    fixture_data = result.get('data')
                    
                    if fixture_data:
                        processed_fixture = self._process_fixture_injuries(fixture_data, team_id)
                        injuries_data[fixture_id] = processed_fixture
                else:
                    logger.error(f"Failed to fetch injuries for fixture {fixture_id}: {response.status}")
                    
            return injuries_data
            
        except Exception as e:
            logger.error(f"Error fetching team injuries: {str(e)}")
            return {}
    
    def _fetch_player_data_minimal(self, player_id: int) -> Optional[Dict]:
        """
        Fetch player data with minimal includes for lower tier plans
        """
        try:
            conn = http.client.HTTPSConnection(self.base_url)
            includes = "nationality;teams.team;statistics.team;statistics.season;latest.fixture.participants;latest.fixture.league;latest.fixture.scores;detailedPosition"
            endpoint = f"/v3/football/players/{player_id}?api_token={self.api_token}&include={includes}"
            
            logger.info(f"Fetching minimal player data from: {endpoint}")
            conn.request("GET", endpoint, "", {})
            response = conn.getresponse()
            data = response.read()
            conn.close()
            
            if response.status == 200:
                result = json.loads(data.decode("utf-8"))
                return result.get('data')
            else:
                error_data = data.decode("utf-8")
                logger.error(f"Minimal API request failed with status {response.status}: {error_data}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching minimal player data: {str(e)}")
            return None
    
    def search_players(self, query: str) -> List[Dict]:
        """
        Search for players by name
        
        Args:
            query: Player name search query
            
        Returns:
            List of matching players
        """
        try:
            conn = http.client.HTTPSConnection(self.base_url)
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            endpoint = f"/v3/football/players/search/{encoded_query}?api_token={self.api_token}"
            
            logger.info(f"Making API request to: {endpoint}")
            conn.request("GET", endpoint, "", {})
            response = conn.getresponse()
            data = response.read()
            conn.close()
            
            logger.info(f"API response status: {response.status}")
            if response.status == 200:
                result = json.loads(data.decode("utf-8"))
                players = result.get('data', [])
                logger.info(f"Found {len(players)} players")
                return players
            else:
                error_data = data.decode("utf-8")
                logger.error(f"Player search failed with status {response.status}: {error_data}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching players: {str(e)}")
            return []
    
    def store_player_globally(self, player_data: Dict) -> bool:
        """Store player data in the global database"""
        try:
            if not player_data:
                logger.error("Player data is None or empty")
                return False
            
            logger.info(f"Processing player data with keys: {list(player_data.keys()) if player_data else 'None'}")
            
            # Debug position data for troubleshooting
            if player_data:
                logger.info(f"Position data - position: {player_data.get('position')}")
                logger.info(f"Position data - detailedposition: {player_data.get('detailedposition')}")
                logger.info(f"Position data - detailedPosition: {player_data.get('detailedPosition')}")
            
            processed_data = self._process_player_data(player_data)
            
            if not processed_data:
                logger.error("Processed data is None")
                return False
            
            if not processed_data.get('id'):
                logger.error("Player ID is missing from processed data")
                return False
            
            player_id = str(processed_data['id'])
            doc_ref = db.collection('global_players').document(player_id)

            # Check for existing document to preserve fields
            existing_doc = doc_ref.get()
            if existing_doc.exists:
                existing_data = existing_doc.to_dict()
                # Preserve nickname and original added_at timestamp
                if 'nickname' in existing_data:
                    processed_data['nickname'] = existing_data['nickname']
                if 'added_at' in existing_data:
                    processed_data['added_at'] = existing_data['added_at']
                
                # Update existing document
                processed_data['last_updated'] = datetime.utcnow()
                doc_ref.update(processed_data)
                logger.info(f"Updated player {processed_data.get('name', 'Unknown')} globally")
            else:
                # Create new document
                processed_data['added_at'] = datetime.utcnow()
                processed_data['last_updated'] = datetime.utcnow()
                doc_ref.set(processed_data)
                logger.info(f"Stored new player {processed_data.get('name', 'Unknown')} globally")
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing player globally: {str(e)}")
            return False
    
    def get_all_players(self) -> List[Dict]:
        """Get all players from the global database with fantasy football relevant data"""
        try:
            players_ref = db.collection('global_players')
            players_docs = players_ref.get()
            
            players = []
            for doc in players_docs:
                player_data = doc.to_dict()
                player_data['id'] = doc.id
                
                # Add fantasy football relevant summary data
                player_data['fantasy_summary'] = self._generate_fantasy_summary(player_data)
                players.append(player_data)
            
            logger.info(f"Retrieved {len(players)} players from global database")
            return players
            
        except Exception as e:
            logger.error(f"Error getting all players: {str(e)}")
            return []
    
    def _generate_fantasy_summary(self, player_data: Dict) -> Dict:
        """Generate fantasy football summary for player listing"""
        summary = {
            'avg_rating_last_3': None,
            'current_team': None,
            'position': None,
            'recent_form': 'N/A',
            'avg_tp_recent': None
        }
        
        try:
            # Get average rating from last 3 matches
            recent_matches = player_data.get('recent_matches', {})
            if recent_matches and 'matches' in recent_matches and recent_matches['matches']:
                # Get last 3 matches with ratings
                matches_with_ratings = [match for match in recent_matches['matches'][:5] 
                                      if match.get('rating') is not None]
                
                if len(matches_with_ratings) >= 3:
                    last_3_ratings = [match['rating'] for match in matches_with_ratings[:3]]
                    summary['avg_rating_last_3'] = round(sum(last_3_ratings) / len(last_3_ratings), 1)
                    
                    # Determine form based on average rating
                    if summary['avg_rating_last_3'] >= 7.5:
                        summary['recent_form'] = 'Excellent'
                    elif summary['avg_rating_last_3'] >= 7.0:
                        summary['recent_form'] = 'Good'
                    elif summary['avg_rating_last_3'] >= 6.5:
                        summary['recent_form'] = 'Average'
                    else:
                        summary['recent_form'] = 'Poor'
                elif len(matches_with_ratings) > 0:
                    # If less than 3 matches but some data exists, don't show form indicator
                    avg_rating = sum(match['rating'] for match in matches_with_ratings) / len(matches_with_ratings)
                    summary['avg_rating_last_3'] = round(avg_rating, 1)
                    summary['recent_form'] = 'N/A'  # Hide form indicator for insufficient data
            
            # Try summary data as fallback
            elif recent_matches and 'summary' in recent_matches:
                avg_rating = recent_matches['summary'].get('average_rating')
                if avg_rating:
                    summary['avg_rating_last_3'] = round(avg_rating, 1)
                    if avg_rating >= 7.5:
                        summary['recent_form'] = 'Excellent'
                    elif avg_rating >= 7.0:
                        summary['recent_form'] = 'Good'
                    elif avg_rating >= 6.5:
                        summary['recent_form'] = 'Average'
                    else:
                        summary['recent_form'] = 'Poor'
            
            # Calculate average TP from recent matches (last 4 weeks)
            match_level_stats = player_data.get('match_level_stats', {})
            matches = match_level_stats.get('matches', [])
            
            if matches:
                # Get matches from last 4 weeks with TP data
                from datetime import datetime, timedelta
                four_weeks_ago = datetime.now() - timedelta(weeks=4)
                
                recent_tp_matches = []
                for match in matches:
                    if match.get('fdf_score') and match.get('date'):
                        try:
                            match_date = datetime.fromisoformat(match['date'].replace('Z', '+00:00'))
                            if match_date >= four_weeks_ago:
                                tp_value = match['fdf_score']['total']
                                if tp_value > 0:  # Only count matches where player actually played
                                    recent_tp_matches.append(tp_value)
                        except (ValueError, TypeError):
                            continue
                
                if recent_tp_matches:
                    summary['avg_tp_recent'] = round(sum(recent_tp_matches) / len(recent_tp_matches))
            
            # Current team
            if player_data.get('current_team'):
                summary['current_team'] = player_data['current_team'].get('name')
            
            # Position - use the stored position data
            if player_data.get('position'):
                # Debug logging
                logger.info(f"Player {player_data.get('name')} position data: {player_data.get('position')}")
                
                if isinstance(player_data['position'], dict):
                    summary['position'] = player_data['position'].get('name', 'Unknown Position')
                else:
                    summary['position'] = str(player_data['position'])
            else:
                logger.warning(f"No position data for player {player_data.get('name')}")
                summary['position'] = 'Unknown Position'
                
        except Exception as e:
            logger.error(f"Error generating fantasy summary: {str(e)}")
        
        return summary
    
    def player_exists(self, player_id: int) -> bool:
        """Check if player already exists in global database"""
        try:
            doc_ref = db.collection('global_players').document(str(player_id))
            doc = doc_ref.get()
            return doc.exists
            
        except Exception as e:
            logger.error(f"Error checking if player exists: {str(e)}")
            return False
    
    def get_player_details_globally(self, player_id: str) -> Optional[Dict]:
        """Get detailed player information from global database"""
        try:
            doc_ref = db.collection('global_players').document(player_id)
            doc = doc_ref.get()
            
            if doc.exists:
                player_data = doc.to_dict()
                player_data['id'] = doc.id
                
                # Check if data needs refresh (older than 12 hours for fantasy football)
                last_updated = player_data.get('last_updated')
                if last_updated and isinstance(last_updated, datetime):
                    current_time = datetime.utcnow()
                    if hasattr(last_updated, 'tzinfo') and last_updated.tzinfo is not None:
                        last_updated = last_updated.replace(tzinfo=None)
                
                    if current_time - last_updated > timedelta(hours=12):
                        # Refresh data from API for fantasy football
                        fresh_data = self.fetch_player_data(int(player_id))
                        if fresh_data:
                            self.store_player_globally(fresh_data)
                            return self._process_player_data(fresh_data)
                
                return player_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting player details globally: {str(e)}")
            return None
    
    def remove_player_globally(self, player_id: str) -> bool:
        """Remove player from global database"""
        try:
            doc_ref = db.collection('global_players').document(player_id)
            doc_ref.delete()
            
            logger.info(f"Removed player {player_id} from global database")
            return True
            
        except Exception as e:
            logger.error(f"Error removing player globally: {str(e)}")
            return False

    def update_player_nickname(self, player_id: str, nickname: str) -> bool:
        """Update a player's nickname in the global database."""
        try:
            player_ref = db.collection('global_players').document(player_id)
            player_doc = player_ref.get()

            if not player_doc.exists:
                logger.error(f"Player with ID {player_id} not found in global_players.")
                return False

            player_ref.update({'nickname': nickname.strip()})
            logger.info(f"Updated nickname for player {player_id} to '{nickname.strip()}' in global_players.")
            return True

        except Exception as e:
            logger.error(f"Error updating player nickname for ID {player_id}: {str(e)}")
            return False
    
    # PLAYER REGISTRY METHODS FOR SCHEDULED UPDATES
    def add_player_to_registry(self, player_id: int, name: str, metadata: Dict = None) -> bool:
        """
        Add player to registry for scheduled updates
        
        Args:
            player_id: SportMonks player ID
            name: Player name
            metadata: Additional player metadata (team, position, etc.)
            
        Returns:
            Success boolean
        """
        try:
            registry_ref = db.collection('player_registry')
            
            registry_data = {
                'player_id': str(player_id),
                'name': name,
                'added_date': datetime.utcnow(),
                'last_updated': None,
                'status': 'active',
                'update_priority': 'normal',
                'source': 'manual_add',
                'metadata': metadata or {},
                'update_count': 0,
                'last_error': None
            }
            
            # Use player_id as document ID
            registry_ref.document(str(player_id)).set(registry_data)
            logger.info(f"Added player {name} (ID: {player_id}) to registry")
            return True
            
        except Exception as e:
            logger.error(f"Error adding player to registry: {str(e)}")
            return False
    
    def get_all_registry_players(self) -> List[Dict]:
        """Get all players from registry for bulk updates"""
        try:
            registry_ref = db.collection('player_registry')
            players_docs = registry_ref.where('status', '==', 'active').get()
            
            players = []
            for doc in players_docs:
                player_data = doc.to_dict()
                player_data['registry_id'] = doc.id
                players.append(player_data)
            
            logger.info(f"Retrieved {len(players)} players from registry")
            return players
            
        except Exception as e:
            logger.error(f"Error getting registry players: {str(e)}")
            return []
    
    def update_registry_player_status(self, player_id: str, status: str, error: str = None) -> bool:
        """Update player registry status after update attempt"""
        try:
            registry_ref = db.collection('player_registry').document(str(player_id))
            
            update_data = {
                'last_updated': datetime.utcnow(),
                'status': status,
                'update_count': firestore.Increment(1)
            }
            
            if error:
                update_data['last_error'] = error
            else:
                update_data['last_error'] = None
                
            registry_ref.update(update_data)
            return True
            
        except Exception as e:
            logger.error(f"Error updating registry status: {str(e)}")
            return False
    
    def bulk_update_players(self, max_players: int = 50) -> Dict:
        """
        Bulk update players from registry - for scheduled jobs
        
        Args:
            max_players: Maximum number of players to update in one batch
            
        Returns:
            Update summary statistics
        """
        summary = {
            'total_attempted': 0,
            'successful_updates': 0,
            'failed_updates': 0,
            'errors': [],
            'updated_players': []
        }
        
        try:
            # Get players that need updating (prioritize those not updated recently)
            registry_players = self.get_all_registry_players()
            
            # Sort by last_updated (oldest first) and limit
            def get_sort_key(player):
                last_updated = player.get('last_updated')
                if last_updated is None:
                    return datetime.min.replace(tzinfo=None)
                # Ensure datetime is timezone-naive for comparison
                if hasattr(last_updated, 'tzinfo') and last_updated.tzinfo is not None:
                    return last_updated.replace(tzinfo=None)
                return last_updated
            
            registry_players.sort(key=get_sort_key)
            players_to_update = registry_players[:max_players]
            
            logger.info(f"Starting bulk update of {len(players_to_update)} players")
            
            for player_registry in players_to_update:
                player_id = player_registry['player_id']
                player_name = player_registry['name']
                summary['total_attempted'] += 1
                
                try:
                    # Fetch fresh data from API
                    fresh_data = self.fetch_player_data(int(player_id))
                    
                    if fresh_data:
                        # Store updated data
                        success = self.store_player_globally(fresh_data)
                        
                        if success:
                            # Update registry status
                            self.update_registry_player_status(player_id, 'active')
                            summary['successful_updates'] += 1
                            summary['updated_players'].append({
                                'id': player_id,
                                'name': player_name,
                                'status': 'success'
                            })
                            logger.info(f"Successfully updated player {player_name} (ID: {player_id})")
                        else:
                            raise Exception("Failed to store player data")
                    else:
                        raise Exception("Failed to fetch player data from API")
                        
                except Exception as e:
                    error_msg = str(e)
                    self.update_registry_player_status(player_id, 'error', error_msg)
                    summary['failed_updates'] += 1
                    summary['errors'].append({
                        'player_id': player_id,
                        'player_name': player_name,
                        'error': error_msg
                    })
                    logger.error(f"Failed to update player {player_name} (ID: {player_id}): {error_msg}")
            
            logger.info(f"Bulk update completed: {summary['successful_updates']}/{summary['total_attempted']} successful")
            return summary
            
        except Exception as e:
            logger.error(f"Error in bulk update: {str(e)}")
            summary['errors'].append({'general_error': str(e)})
            return summary
    
    def get_relevant_fixture_ids(self, team_matches: Dict) -> List[int]:
        """
        Get the most relevant fixture IDs for injury checking
        Returns: [last_match_id, next_match_id] where available
        """
        fixture_ids = []
        
        # Get last match from 'latest' field
        if 'latest' in team_matches and team_matches['latest']:
            last_match = team_matches['latest'][0]
            if last_match and 'id' in last_match:
                fixture_ids.append(last_match['id'])
                logger.info(f"Added last match fixture ID: {last_match['id']}")
        
        # Get next match from 'upcoming' field
        if 'upcoming' in team_matches and team_matches['upcoming']:
            next_match = team_matches['upcoming'][0]
            if next_match and 'id' in next_match:
                fixture_ids.append(next_match['id'])
                logger.info(f"Added upcoming match fixture ID: {next_match['id']}")
            else:
                logger.warning(f"Upcoming match missing ID: {next_match}")
        else:
            logger.warning(f"No upcoming matches found in team_matches keys: {list(team_matches.keys()) if team_matches else 'None'}")
        
        return fixture_ids
    
    def _get_position_from_player(self, player_data: Dict) -> Dict:
        """
        Extract position information from player data
        Priority: detailedposition -> detailedPosition -> position -> position_id fallback
        """
        # Priority 1: detailedposition (lowercase - most common from API)
        if player_data.get('detailedposition'):
            logger.info(f"Using detailedposition field for player")
            return player_data['detailedposition']
        
        # Priority 2: detailedPosition (camelCase alternative)
        if player_data.get('detailedPosition'):
            logger.info(f"Using detailedPosition field for player")
            return player_data['detailedPosition']
        
        # Priority 3: position field
        if player_data.get('position'):
            logger.info(f"Using position field for player")
            return player_data['position']
        
        # Priority 4: Fallback to position_id mapping
        position_id = player_data.get('detailed_position_id') or player_data.get('position_id')
        if position_id:
            logger.info(f"Using position_id {position_id} fallback mapping for player")
            
            # SportMonks position ID mappings
            position_mapping = {
                # Detailed positions (150+ range)
                151: {'name': 'Centre Forward', 'code': 'centre-forward', 'id': 151},
                152: {'name': 'Right Winger', 'code': 'right-winger', 'id': 152},
                153: {'name': 'Left Winger', 'code': 'left-winger', 'id': 153},
                154: {'name': 'Right Back', 'code': 'right-back', 'id': 154},
                155: {'name': 'Left Back', 'code': 'left-back', 'id': 155},
                156: {'name': 'Centre Back', 'code': 'centre-back', 'id': 156},
                157: {'name': 'Defensive Midfielder', 'code': 'defensive-midfielder', 'id': 157},
                158: {'name': 'Central Midfielder', 'code': 'central-midfielder', 'id': 158},
                159: {'name': 'Attacking Midfielder', 'code': 'attacking-midfielder', 'id': 159},
                160: {'name': 'Goalkeeper', 'code': 'goalkeeper', 'id': 160},
                
                # Basic positions (1-15 range)
                1: {'name': 'Goalkeeper', 'code': 'goalkeeper', 'id': 1},
                2: {'name': 'Right Back', 'code': 'right-back', 'id': 2},
                3: {'name': 'Left Back', 'code': 'left-back', 'id': 3},
                4: {'name': 'Centre Back', 'code': 'centre-back', 'id': 4},
                5: {'name': 'Sweeper', 'code': 'sweeper', 'id': 5},
                6: {'name': 'Defensive Midfielder', 'code': 'defensive-midfielder', 'id': 6},
                7: {'name': 'Right Midfielder', 'code': 'right-midfielder', 'id': 7},
                8: {'name': 'Central Midfielder', 'code': 'central-midfielder', 'id': 8},
                9: {'name': 'Left Midfielder', 'code': 'left-midfielder', 'id': 9},
                10: {'name': 'Attacking Midfielder', 'code': 'attacking-midfielder', 'id': 10},
                11: {'name': 'Right Winger', 'code': 'right-winger', 'id': 11},
                12: {'name': 'Left Winger', 'code': 'left-winger', 'id': 12},
                13: {'name': 'Centre Forward', 'code': 'centre-forward', 'id': 13},
                14: {'name': 'Striker', 'code': 'striker', 'id': 14},
                15: {'name': 'Second Striker', 'code': 'second-striker', 'id': 15},
                
                # General categories (25+ range)
                25: {'name': 'Defender', 'code': 'defender', 'id': 25},
                26: {'name': 'Midfielder', 'code': 'midfielder', 'id': 26},
                27: {'name': 'Attacker', 'code': 'attacker', 'id': 27}
            }
            
            if position_id in position_mapping:
                return position_mapping[position_id]
            else:
                logger.warning(f"Position ID {position_id} not in mapping")
        
        # Final fallback: unknown position
        logger.warning(f"No position data found for player, using unknown fallback")
        return {
            'name': 'Unknown Position',
            'code': 'unknown',
            'id': None
        }
    
    def _process_fixture_injuries(self, fixture_data: Dict, team_id: int) -> Dict:
        """Process injury and suspension data from fixture"""
        
        # Determine if this is an upcoming match
        fixture_date = fixture_data.get('starting_at')
        is_upcoming = False
        if fixture_date:
            from datetime import datetime
            try:
                match_date = datetime.fromisoformat(fixture_date.replace('Z', '+00:00'))
                current_date = datetime.now(match_date.tzinfo)
                is_upcoming = match_date > current_date
            except:
                # If we can't parse the date, assume it's upcoming if no score exists
                is_upcoming = not bool(fixture_data.get('scores'))
        
        processed = {
            'fixture_id': fixture_data.get('id'),
            'date': fixture_date,
            'is_upcoming': is_upcoming,
            'league': None,
            'venue': None,
            'team_sidelined': [],
            'opponent_sidelined': []
        }
        
        # Process league info
        if 'league' in fixture_data and fixture_data['league']:
            league = fixture_data['league']
            processed['league'] = {
                'id': league.get('id'),
                'name': league.get('name'),
                'image_path': league.get('image_path')
            }
        
        # Process venue info
        if 'venue' in fixture_data and fixture_data['venue']:
            venue = fixture_data['venue']
            processed['venue'] = {
                'id': venue.get('id'),
                'name': venue.get('name'),
                'city': venue.get('city_name')
            }
        
        # Process sidelined players
        if 'sidelined' in fixture_data and fixture_data['sidelined']:
            for sidelined_entry in fixture_data['sidelined']:
                sideline = sidelined_entry.get('sideline', {})
                player_data = sideline.get('player', {})
                type_data = sideline.get('type', {})
                
                # Get position from player data
                position_info = self._get_position_from_player(player_data)
                
                sidelined_info = {
                    'player_id': player_data.get('id'),
                    'player_name': player_data.get('name') or player_data.get('display_name'),
                    'player_position': position_info.get('name', 'Unknown Position'),
                    'player_image': player_data.get('image_path'),
                    'category': sideline.get('category', 'unknown'),  # 'injury' or 'suspended'
                    'type': type_data.get('name', 'Unknown'),
                    'type_code': type_data.get('code', 'unknown'),
                    'start_date': sideline.get('start_date'),
                    'end_date': sideline.get('end_date'),
                    'games_missed': sideline.get('games_missed'),
                    'completed': sideline.get('completed', False)
                }
                
                # Determine which team the player belongs to
                participant_id = sidelined_entry.get('participant_id')
                if participant_id == team_id:
                    processed['team_sidelined'].append(sidelined_info)
                else:
                    processed['opponent_sidelined'].append(sidelined_info)
        
        return processed
    
    def _process_player_data(self, raw_data: Dict) -> Dict:
        """
        Process and clean raw player data from API - FANTASY FOOTBALL OPTIMIZED VERSION
        Focus on recent performance and seasonal statistics
        
        Args:
            raw_data: Raw data from SportMonks API
            
        Returns:
            Processed player data optimized for fantasy football
        """
        if not raw_data:
            logger.error("Raw data is None or empty")
            return None
        
        try:
            logger.info("Creating fantasy football optimized processed data structure...")
            processed = {
                'id': raw_data.get('id'),
                'name': raw_data.get('name', ''),
                'nickname': raw_data.get('nickname', ''),  # Add nickname support
                'display_name': raw_data.get('display_name', ''),
                'common_name': raw_data.get('common_name', ''),
                'firstname': raw_data.get('firstname', ''),
                'lastname': raw_data.get('lastname', ''),
                'date_of_birth': raw_data.get('date_of_birth'),
                'age': self._calculate_age(raw_data.get('date_of_birth')),
                'height': raw_data.get('height'),
                'weight': raw_data.get('weight'),
                'image_path': raw_data.get('image_path'),
                'position_id': raw_data.get('position_id'),
                'detailed_position_id': raw_data.get('detailed_position_id'),
                'nationality_id': raw_data.get('nationality_id'),
                'country_id': raw_data.get('country_id'),
            }
            
            # Process nationality
            if 'nationality' in raw_data and raw_data['nationality']:
                nationality_data = raw_data['nationality']
                if nationality_data:
                    processed['nationality'] = nationality_data.get('name', '')
            
            # Process current team (filter for domestic teams)
            if 'teams' in raw_data and raw_data['teams'] and len(raw_data['teams']) > 0:
                club_teams = [team for team in raw_data['teams'] 
                            if team.get('team', {}).get('type') == 'domestic']
                
                if club_teams:
                    team_data = club_teams[0]
                    current_team = team_data.get('team', {})
                    if current_team:
                        processed['current_team'] = {
                            'id': current_team.get('id'),
                            'name': current_team.get('name'),
                            'short_code': current_team.get('short_code'),
                            'image_path': current_team.get('image_path'),
                            'jersey_number': team_data.get('jersey_number'),
                        }
                        processed['current_team_id'] = current_team.get('id')
            
            # Process position using the direct API data
            position_info = self._get_position_from_player(raw_data)
            
            # Use position_id from raw_data (not position_info.id which can be null)
            position_id = raw_data.get('position_id')
            position_category = 'Unknown'
            
            if position_id:
                # Goalkeeper IDs
                if position_id in [1, 24]:
                    position_category = 'Goalkeeper'
                # Defender IDs  
                elif position_id in [2, 3, 4, 5, 25]:
                    position_category = 'Defender'
                # Midfielder IDs
                elif position_id in [6, 7, 8, 9, 10, 26]:
                    position_category = 'Midfielder'
                # Attacker IDs
                elif position_id in [11, 12, 13, 14, 15, 27]:
                    position_category = 'Attacker'
            
            processed['position'] = {
                'id': position_info.get('id'),
                'name': position_info.get('name', 'Unknown Position'),
                'code': position_info.get('code'),
                'category': position_category
            }
            
            # Store position_id at root level for reference
            processed['position_id'] = position_id
            
            # FANTASY FOOTBALL FOCUS: Process seasonal statistics (current + last season only)
            if 'statistics' in raw_data and raw_data['statistics']:
                processed['seasonal_stats'] = self._process_seasonal_statistics_enhanced(raw_data['statistics'])
            
            # FANTASY FOOTBALL FOCUS: Process recent matches (last 4 weeks only)
            if 'latest' in raw_data and raw_data['latest']:
                processed['recent_matches'] = self._process_recent_matches_fantasy(raw_data['latest'])
            
            # NEW: Store comprehensive match-level statistics for all available matches
            if 'latest' in raw_data and raw_data['latest']:
                processed['match_level_stats'] = self._process_all_match_stats(raw_data['latest'], processed)
            
            # FANTASY FOOTBALL FOCUS: Process recent trophies only (last 2 years)
            if 'trophies' in raw_data and raw_data['trophies']:
                processed['recent_trophies'] = self._process_recent_trophies(raw_data['trophies'])
            
            # Process team matches data if available
            if 'team_matches' in raw_data and raw_data['team_matches']:
                # Pass player's recent matches to cross-reference
                player_match_ids = []
                if processed.get('recent_matches', {}).get('matches'):
                    player_match_ids = [match['fixture_id'] for match in processed['recent_matches']['matches'] if match.get('fixture_id')]
                processed['team_matches'] = self._process_team_matches(raw_data['team_matches'], player_match_ids)
            
            # Process team injuries data if available
            if 'team_injuries' in raw_data and raw_data['team_injuries']:
                processed['team_injuries'] = self._process_team_injuries_summary(
                    raw_data['team_injuries'], 
                    processed.get('id')
                )
            
            return processed
        
        except Exception as e:
            logger.error(f"Error processing player data: {str(e)}")
            return None
    
    def delete_player(self, player_id: int) -> bool:
        """Delete a player from the registry"""
        try:
            doc_ref = db.collection('global_players').document(str(player_id))
            doc = doc_ref.get()
            
            if doc.exists:
                doc_ref.delete()
                logger.info(f"Deleted player {player_id} from registry")
                return True
            else:
                logger.warning(f"Player {player_id} not found in registry")
                return False
        except Exception as e:
            logger.error(f"Error deleting player {player_id}: {str(e)}")
            return False
    
    def update_player_data(self, player_id: int) -> bool:
        """Update a specific player's data from SportMonks API"""
        try:
            # Fetch fresh data from API
            fresh_data = self.fetch_player_data(player_id)
            if not fresh_data:
                logger.error(f"Failed to fetch fresh data for player {player_id}")
                return False
            
            # Store updated data
            success = self.store_player_globally(fresh_data)
            if success:
                logger.info(f"Successfully updated player {player_id}")
                return True
            else:
                logger.error(f"Failed to store updated data for player {player_id}")
                return False
        except Exception as e:
            logger.error(f"Error updating player {player_id}: {str(e)}")
            return False
    
    def update_all_players(self) -> int:
        """Update all players in the registry"""
        updated_count = 0
        try:
            # Get all player IDs from Firebase
            players_ref = db.collection('global_players')
            players_docs = players_ref.get()
            
            player_ids = [doc.id for doc in players_docs]
            logger.info(f"Starting bulk update of {len(player_ids)} players")
            
            for player_id in player_ids:
                try:
                    if self.update_player_data(int(player_id)):
                        updated_count += 1
                        logger.info(f"Updated player {player_id} ({updated_count}/{len(player_ids)})")
                    else:
                        logger.warning(f"Failed to update player {player_id}")
                except Exception as e:
                    logger.error(f"Error updating player {player_id}: {str(e)}")
                    continue
            
            logger.info(f"Bulk update completed: {updated_count}/{len(player_ids)} players updated")
            return updated_count
        except Exception as e:
            logger.error(f"Error in bulk update: {str(e)}")
            return updated_count
    
    def _process_team_matches(self, team_data: Dict, player_match_ids: List[int] = None) -> Dict:
        """
        Process team's recent and upcoming matches with predictions
        """
        if not team_data:
            return {}
        
        processed = {
            'team_name': team_data.get('name'),
            'team_image': team_data.get('image_path'),
            'upcoming_matches': [],
            'recent_matches': []
        }
        
        # Process upcoming matches (get 5 matches)
        if 'upcoming' in team_data and team_data['upcoming']:
            upcoming = team_data['upcoming'][:5]  # Get 5 upcoming matches
            
            for match in upcoming:
                if not match:
                    continue
                
                participants = match.get('participants', [])
                home_team = None
                away_team = None
                
                for participant in participants:
                    if participant and participant.get('meta', {}).get('location') == 'home':
                        home_team = participant
                    elif participant and participant.get('meta', {}).get('location') == 'away':
                        away_team = participant
                
                league_data = match.get('league', {})
                
                # Process predictions - look for fulltime result probability
                match_predictions = {}
                predictions_list = match.get('predictions', [])
                
                for prediction in predictions_list:
                    if prediction and prediction.get('type'):
                        type_data = prediction['type']
                        if type_data.get('code') == 'fulltime-result-probability':
                            # Found the match result predictions
                            predictions_values = prediction.get('predictions', {})
                            match_predictions = {
                                'home_win': predictions_values.get('home', 0),
                                'draw': predictions_values.get('draw', 0),
                                'away_win': predictions_values.get('away', 0)
                            }
                            break
                
                processed_match = {
                    'fixture_id': match.get('id'),
                    'date': match.get('starting_at'),
                    'home_team': home_team.get('name') if home_team else 'Unknown',
                    'away_team': away_team.get('name') if away_team else 'Unknown',
                    'home_team_id': home_team.get('id') if home_team else None,
                    'away_team_id': away_team.get('id') if away_team else None,
                    'home_team_image': home_team.get('image_path') if home_team else None,
                    'away_team_image': away_team.get('image_path') if away_team else None,
                    'league': league_data.get('name', 'Unknown League'),
                    'league_type': league_data.get('sub_type'),
                    'venue_id': match.get('venue_id'),
                    'is_home': home_team and home_team.get('id') == team_data.get('id'),
                    'player_played': False,  # Future match, player hasn't played yet
                    'predictions': match_predictions  # Add predictions
                }
                processed['upcoming_matches'].append(processed_match)
        
        # Process recent matches from 'latest' field (limit to 10 for better checking)
        if 'latest' in team_data and team_data['latest']:
            latest = team_data['latest'][:10]  # Get more matches for better player participation checking
            
            for match in latest:
                if not match:
                    continue
                
                participants = match.get('participants', [])
                home_team = None
                away_team = None
                
                for participant in participants:
                    if participant and participant.get('meta', {}).get('location') == 'home':
                        home_team = participant
                    elif participant and participant.get('meta', {}).get('location') == 'away':
                        away_team = participant
                
                league_data = match.get('league', {})
                
                # Get score from scores array
                score = None
                home_score = 0
                away_score = 0
                if 'scores' in match and match['scores']:
                    for score_data in match['scores']:
                        if score_data.get('description') == 'CURRENT':
                            score_info = score_data.get('score', {})
                            if score_info.get('participant') == 'home':
                                home_score = score_info.get('goals', 0)
                            elif score_info.get('participant') == 'away':
                                away_score = score_info.get('goals', 0)
                    
                    score = f"{home_score}-{away_score}"
                
                processed_match = {
                    'fixture_id': match.get('id'),
                    'date': match.get('starting_at'),
                    'home_team': home_team.get('name') if home_team else 'Unknown',
                    'away_team': away_team.get('name') if away_team else 'Unknown',
                    'home_team_image': home_team.get('image_path') if home_team else None,
                    'away_team_image': away_team.get('image_path') if away_team else None,
                    'league': league_data.get('name', 'Unknown League'),
                    'league_type': league_data.get('sub_type'),
                    'venue_id': match.get('venue_id'),
                    'is_home': home_team and home_team.get('id') == team_data.get('id'),
                    'score': score,
                    'result_info': match.get('result_info'),
                    'player_played': player_match_ids and match.get('id') in player_match_ids if player_match_ids else False
                }
                processed['recent_matches'].append(processed_match)
        
        # Only keep the 5 most recent matches for display
        processed['recent_matches'] = processed['recent_matches'][:5]
        
        return processed
    
    def _process_seasonal_statistics_enhanced(self, statistics: List[Dict]) -> List[Dict]:
        """
        Process seasonal statistics with ALL available stats from API
        """
        if not statistics:
            return []
            
        processed_stats = []
        current_year = datetime.now().year
        
        for stat in statistics:
            if not stat:
                continue
                
            season_data = stat.get('season') or {}
            season_name = season_data.get('name', '')
            
            # Only include current and last season (2024/2025, 2025/2026, etc.)
            if not self._is_relevant_season(season_name, current_year):
                continue
                
            team_data = stat.get('team') or {}
            league_data = season_data.get('league') or {}
            
            # Process ALL detailed statistics from the API
            details = stat.get('details', [])
            all_stats = {}
            
            # Create a comprehensive mapping of all possible stats
            for detail in details:
                if detail and 'type' in detail and detail['type']:
                    type_data = detail['type']
                    stat_name = type_data.get('name')
                    stat_code = type_data.get('code')
                    stat_group = type_data.get('stat_group')
                    
                    # Debug: Log rating-related details
                    if stat_name and 'rating' in stat_name.lower():
                        logger.info(f"Found rating stat: {stat_name}, code: {stat_code}, value: {detail.get('value')}")
                    
                    if detail.get('value') is not None:
                        value_data = detail['value']
                        
                        # Handle different value formats
                        if isinstance(value_data, dict):
                            # For complex stats, only store the main total value
                            if 'total' in value_data:
                                all_stats[stat_name] = value_data.get('total', 0)
                            elif 'average' in value_data:
                                # For stats like Rating, use average
                                all_stats[stat_name] = value_data.get('average')
                                logger.info(f"Stored {stat_name} with average value: {value_data.get('average')}")
                            elif 'percentage' in value_data:
                                all_stats[stat_name] = value_data.get('percentage')
                            
                            # Don't store sub-values to avoid duplication
                        else:
                            # Simple numeric values
                            all_stats[stat_name] = value_data
            
            # Log all available stats for debugging
            logger.info(f"Season {season_name} - Available stats: {list(all_stats.keys())}")
            if 'Rating' in all_stats:
                logger.info(f"Season {season_name} - Rating value: {all_stats['Rating']}")
            
            processed_stat = {
                'season_id': stat.get('season_id'),
                'season_name': season_name,
                'league_name': league_data.get('name', 'Unknown League'),
                'league_short_code': league_data.get('short_code'),
                'team_name': team_data.get('name'),
                'team_image': team_data.get('image_path'),
                'jersey_number': stat.get('jersey_number'),
                
                # Store ALL stats dynamically
                'all_stats': all_stats,  # Store the complete stats dictionary
                
                # Common stats with proper extraction
                'appearances': all_stats.get('Appearances', 0),
                'minutes_played': all_stats.get('Minutes Played', 0),
                'rating': all_stats.get('Rating'),  # This should now properly get the average rating
                
                # Offensive stats
                'goals': all_stats.get('Goals', 0),
                'assists': all_stats.get('Assists', 0),
                'shots_total': all_stats.get('Shots Total', 0),
                'shots_on_target': all_stats.get('Shots On Target', 0),
                'shots_off_target': all_stats.get('Shots Off Target', 0),
                'shot_accuracy': all_stats.get('Shots On Target_percentage'),
                
                # Passing stats
                'passes': all_stats.get('Passes', 0),
                'passes_accurate': all_stats.get('Passes Accurate', 0),
                'pass_accuracy': all_stats.get('Pass Accuracy %') or all_stats.get('Passes_percentage'),
                'key_passes': all_stats.get('Key Passes', 0),
                'through_balls': all_stats.get('Through Balls', 0),
                'long_balls': all_stats.get('Long Balls', 0),
                'crosses': all_stats.get('Crosses', 0),
                'crosses_accurate': all_stats.get('Crosses Accurate', 0),
                
                # Defensive stats
                'tackles': all_stats.get('Tackles', 0),
                'tackles_won': all_stats.get('Tackles Won', 0),
                'interceptions': all_stats.get('Interceptions', 0),
                'clearances': all_stats.get('Clearances', 0),
                'blocks': all_stats.get('Blocks', 0),
                'duels': all_stats.get('Duels', 0),
                'duels_won': all_stats.get('Duels Won', 0),
                'aerial_duels': all_stats.get('Aerial Duels', 0),
                'aerial_duels_won': all_stats.get('Aerial Duels Won', 0),
                
                # Goalkeeper stats
                'saves': all_stats.get('Saves', 0),
                'clean_sheets': all_stats.get('Clean Sheets', 0),
                'goals_conceded': all_stats.get('Goals Conceded', 0),
                'penalties_saved': all_stats.get('Penalties Saved', 0),
                'punches': all_stats.get('Punches', 0),
                'catches': all_stats.get('Catches', 0),
                
                # Discipline
                'yellow_cards': all_stats.get('Yellowcards', 0),
                'red_cards': all_stats.get('Redcards', 0),
                'fouls': all_stats.get('Fouls', 0),
                'fouls_drawn': all_stats.get('Fouls Drawn', 0),
                'offsides': all_stats.get('Offsides', 0),
                
                # Other stats
                'dribbles': all_stats.get('Dribbles', 0),
                'dribbles_successful': all_stats.get('Dribbles Successful', 0),
                'dispossessed': all_stats.get('Dispossessed', 0),
                'touches': all_stats.get('Touches', 0),
                'bench': all_stats.get('Bench', 0),
                'substitutions_in': all_stats.get('Substitutions In', 0),
                'substitutions_out': all_stats.get('Substitutions Out', 0),
                
                # Calculated fantasy metrics
                'goals_per_game': round(all_stats.get('Goals', 0) / max(all_stats.get('Appearances', 1), 1), 2),
                'assists_per_game': round(all_stats.get('Assists', 0) / max(all_stats.get('Appearances', 1), 1), 2),
                'minutes_per_game': round(all_stats.get('Minutes Played', 0) / max(all_stats.get('Appearances', 1), 1), 0),
            }
            processed_stats.append(processed_stat)
        
        # Sort by season (most recent first)
        processed_stats.sort(key=lambda x: x.get('season_name', ''), reverse=True)
        
        return processed_stats
    
    def _is_relevant_season(self, season_name: str, current_year: int) -> bool:
        """Check if season is relevant (current or last season)"""
        if not season_name:
            return False
        
        # Check for current and last season patterns
        relevant_years = [str(current_year), str(current_year-1), str(current_year+1)]
        
        return any(year in season_name for year in relevant_years)
    
    def _process_recent_matches_fantasy(self, latest_data: List[Dict]) -> Dict:
        """
        Process ALL recent matches from API then filter for display
        """
        if not latest_data:
            return {'matches': [], 'summary': {}, 'rating_trend': [], 'all_matches': []}
        
        # Process ALL matches first
        all_matches_by_fixture = {}
        
        for match_entry in latest_data:
            fixture_data = match_entry.get('fixture', {})
            if not fixture_data:
                continue
            
            fixture_id = match_entry.get('fixture_id')
            if fixture_id:
                if fixture_id not in all_matches_by_fixture:
                    all_matches_by_fixture[fixture_id] = {
                        'fixture_id': fixture_id,
                        'fixture_info': fixture_data,
                        'player_stats': []
                    }
                
                if 'details' in match_entry:
                    all_matches_by_fixture[fixture_id]['player_stats'].extend(match_entry['details'])
        
        # Process all matches
        all_processed_matches = []
        
        for fixture_id, match_data in all_matches_by_fixture.items():
            fixture_info = match_data.get('fixture_info', {})
            player_stats = match_data.get('player_stats', [])
            
            if not fixture_info:
                continue
        
            # Extract match stats
            match_stats = {}
            for stat in player_stats:
                if not stat or not stat.get('type'):
                    continue
                    
                type_data = stat['type']
                data_data = stat.get('data', {})
                stat_name = type_data.get('name', 'Unknown')
                stat_value = data_data.get('value')
                match_stats[stat_name] = stat_value
            
            processed_match = {
                'fixture_id': fixture_id,
                'date': fixture_info.get('starting_at'),
                'goals': match_stats.get('Goals', 0) or 0,
                'assists': match_stats.get('Assists', 0) or 0,
                'minutes_played': match_stats.get('Minutes Played', 0) or 0,
                'rating': match_stats.get('Rating'),
            }
            
            all_processed_matches.append(processed_match)
        
        # Sort all matches by date
        all_processed_matches.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # Store all match IDs for team match checking
        all_match_ids = [m['fixture_id'] for m in all_processed_matches]
        
        # Now filter for last 4 weeks for display
        four_weeks_ago = datetime.utcnow() - timedelta(weeks=4)
        recent_matches_for_display = []
        
        for match in all_processed_matches:
            match_date_str = match.get('date')
            if match_date_str:
                try:
                    match_date = datetime.fromisoformat(match_date_str.replace('Z', '+00:00').replace('+00:00', ''))
                    if match_date >= four_weeks_ago:
                        # Re-fetch full match details for recent matches
                        for fixture_id, match_data in all_matches_by_fixture.items():
                            if fixture_id == match['fixture_id']:
                                fixture_info = match_data.get('fixture_info', {})
                                player_stats = match_data.get('player_stats', [])
                                
                                # Extract enhanced match stats
                                match_stats = {}
                                for stat in player_stats:
                                    if not stat or not stat.get('type'):
                                        continue
                                        
                                    type_data = stat['type']
                                    data_data = stat.get('data', {})
                                    stat_name = type_data.get('name', 'Unknown')
                                    stat_value = data_data.get('value')
                                    match_stats[stat_name] = stat_value
                                
                                league_data = fixture_info.get('league', {})
                                
                                full_match = {
                                    'fixture_id': fixture_id,
                                    'date': fixture_info.get('starting_at'),
                                    'league': league_data.get('name', 'Unknown League'),
                                    'league_short_code': league_data.get('short_code'),
                                    'league_type': league_data.get('sub_type'),
                                    'teams': [],
                                    'score': None,
                                    'goals': match_stats.get('Goals', 0) or 0,
                                    'assists': match_stats.get('Assists', 0) or 0,
                                    'minutes_played': match_stats.get('Minutes Played', 0) or 0,
                                    'yellow_cards': match_stats.get('Yellowcards', 0) or 0,
                                    'red_cards': match_stats.get('Redcards', 0) or 0,
                                    'rating': match_stats.get('Rating'),
                                    'shots': match_stats.get('Shots Total', 0) or 0,
                                    'passes': match_stats.get('Passes', 0) or 0,
                                    'touches': match_stats.get('Touches', 0) or 0,
                                    # Defensive stats
                                    'tackles': match_stats.get('Tackles', 0) or 0,
                                    'interceptions': match_stats.get('Interceptions', 0) or 0,
                                    'clearances': match_stats.get('Clearances', 0) or 0,
                                    'blocks': match_stats.get('Blocks', 0) or 0,
                                    'duels_won': match_stats.get('Duels Won', 0) or 0,
                                    'aerial_duels_won': match_stats.get('Aerial Duels Won', 0) or 0,
                                    # Goalkeeper stats
                                    'saves': match_stats.get('Saves', 0) or 0,
                                    'goals_conceded': match_stats.get('Goals Conceded', 0) or 0,
                                    'clean_sheet': match_stats.get('Clean Sheets', 0) or match_stats.get('Cleansheets', 0) or 0,
                                }
                                
                                # Extract teams and score
                                if 'participants' in fixture_info and fixture_info['participants']:
                                    full_match['teams'] = [p.get('name', 'Unknown') for p in fixture_info['participants'] if p]
                                
                                if 'scores' in fixture_info and fixture_info['scores']:
                                    home_score = None
                                    away_score = None
                                    
                                    for score in fixture_info['scores']:
                                        if not score or score.get('description') != 'CURRENT':
                                            continue
                                        score_data = score.get('score', {})
                                        if score_data.get('participant') == 'home':
                                            home_score = score_data.get('goals')
                                        elif score_data.get('participant') == 'away':
                                            away_score = score_data.get('goals')
                                    
                                    if home_score is not None and away_score is not None:
                                        full_match['score'] = f"{home_score}-{away_score}"
                                
                                recent_matches_for_display.append(full_match)
                                break
                except:
                    continue
        
        # Calculate summary for recent matches
        rating_trend = []
        total_goals = 0
        total_assists = 0
        total_minutes = 0
        total_yellow_cards = 0
        total_red_cards = 0
        total_rating = 0
        rating_count = 0
        
        for match in recent_matches_for_display:
            if match['rating'] and match['date']:
                rating_trend.append({
                    'date': match['date'],
                    'rating': match['rating'],
                    'opponent': ' vs '.join(match['teams']) if match['teams'] else 'Unknown'
                })
            
            total_goals += match['goals']
            total_assists += match['assists']
            total_minutes += match['minutes_played']
            total_yellow_cards += match['yellow_cards']
            total_red_cards += match['red_cards']
            
            if match['rating']:
                total_rating += match['rating']
                rating_count += 1
        
        summary = {
            'total_matches': rating_count,  # Use rating_count for accurate matches played
            'total_goals': total_goals,
            'total_assists': total_assists,
            'total_minutes': total_minutes,
            'total_yellow_cards': total_yellow_cards,
            'total_red_cards': total_red_cards,
            'average_rating': round(total_rating / rating_count, 2) if rating_count > 0 else None,
            'goals_per_match': round(total_goals / rating_count, 2) if rating_count > 0 else 0,
            'assists_per_match': round(total_assists / rating_count, 2) if rating_count > 0 else 0,
            'minutes_per_match': round(total_minutes / rating_count, 0) if rating_count > 0 else 0,
            'recent_form': recent_matches_for_display[:5] if recent_matches_for_display else []
        }
        
        return {
            'matches': recent_matches_for_display,
            'summary': summary,
            'rating_trend': rating_trend[:10],  # Last 10 matches for chart
            'all_match_ids': all_match_ids  # Store all match IDs for team match checking
        }
    
    def _process_recent_trophies(self, trophies: List[Dict]) -> List[Dict]:
        """Process trophies from last 2 years only - WINNERS ONLY (no runner-up)"""
        if not trophies:
            return []
        
        processed_trophies = []
        current_year = datetime.now().year
        cutoff_year = current_year - 2
        
        for trophy in trophies:
            if not trophy:
                continue
                
            trophy_data = trophy.get('trophy') or {}
            
            # ONLY INCLUDE WINNERS (position 1) - Skip all other positions
            position = trophy_data.get('position')
            trophy_name = trophy_data.get('name', '')
            
            # Filter out runner-up entries by position AND name
            if position and position != 1:
                continue
            if 'runner-up' in trophy_name.lower() or 'second' in trophy_name.lower():
                continue
                
            season_data = trophy.get('season') or {}
            season_name = season_data.get('name', '')
            
            # Only include trophies from last 2 years
            try:
                # Extract year from season name (e.g., "2023/2024" -> 2023)
                if '/' in season_name:
                    year_str = season_name.split('/')[0]
                elif '-' in season_name:
                    year_str = season_name.split('-')[0]
                else:
                    year_str = season_name
                
                if year_str.isdigit():
                    season_year = int(year_str)
                    if season_year < cutoff_year:
                        continue
                else:
                    # If we can't parse the year, skip very old entries
                    continue
            except:
                # If we can't parse the year, include it anyway for current data
                pass
                
            league_data = trophy.get('league') or {}
            team_data = trophy.get('team') or {}
            
            # Get proper league name with fallbacks
            league_name = league_data.get('name')
            if not league_name or league_name == 'Unknown League':
                # Try to map some known league IDs to names
                league_id = league_data.get('id')
                league_name = self._get_league_name_fallback(league_id, league_data.get('short_code'))
            
            processed_trophy = {
                'position': 1,  # Only winners make it here
                'trophy_name': trophy_name or 'Winner',
                'league_name': league_name or 'Unknown Competition',
                'season_name': season_name or 'Unknown Season',
                'team_name': team_data.get('name') or 'Unknown Team',
            }
            processed_trophies.append(processed_trophy)
        
        # Sort by season (most recent first) and limit to reasonable number
        processed_trophies.sort(key=lambda x: x.get('season_name', ''), reverse=True)
        
        # Limit to most recent 8 winners to avoid cluttering
        return processed_trophies[:8]
    
    def _get_league_name_fallback(self, league_id: int, short_code: str) -> str:
        """Get league name fallback for common leagues"""
        league_mapping = {
            564: 'La Liga',
            82: 'Bundesliga',
            8: 'Premier League',
            301: 'Ligue 1',
            384: 'Serie A',
            2: 'Champions League',
            1101: 'Club Friendlies',
            1452: 'FIFA Club World Cup',
            109: 'DFB Pokal',
            169: 'German Super Cup',
            1251: 'Spanish Super Cup',
            1328: 'UEFA Super Cup',
            1726: 'Joan Gamper Trophy'
        }
        
        if league_id and league_id in league_mapping:
            return league_mapping[league_id]
        elif short_code:
            return short_code
        else:
            return None
    
    def _process_team_injuries_summary(self, injuries_data: Dict, player_id: int) -> Dict:
        """Process team injuries into a summary format"""
        
        summary = {
            'player_status': 'available',  # available, injured, suspended
            'player_injury_details': None,
            'last_match': None,
            'next_match': None,
            'team_impact': {
                'total_unavailable': 0,
                'key_players_out': []
            }
        }
        
        # Process each fixture's injury data
        for fixture_id, fixture_data in injuries_data.items():
            if not fixture_data:
                continue
                
            fixture_summary = {
                'date': fixture_data.get('date'),
                'opponent': fixture_data.get('teams', {}).get('opponent', {}).get('name'),
                'is_upcoming': fixture_data.get('is_upcoming'),
                'team_sidelined_count': len(fixture_data.get('team_sidelined', [])),
                'sidelined_players': []
            }
            
            # Check if our player is sidelined
            for sidelined in fixture_data.get('team_sidelined', []):
                if sidelined.get('player_id') == player_id:
                    summary['player_status'] = sidelined.get('category', 'unavailable')
                    summary['player_injury_details'] = {
                        'type': sidelined.get('type'),
                        'category': sidelined.get('category'),
                        'start_date': sidelined.get('start_date'),
                        'end_date': sidelined.get('end_date'),
                        'games_missed': sidelined.get('games_missed')
                    }
                
                # Add to sidelined list
                fixture_summary['sidelined_players'].append({
                    'name': sidelined.get('player_name'),
                    'position': sidelined.get('player_position'),
                    'type': sidelined.get('type'),
                    'category': sidelined.get('category'),
                    'image': sidelined.get('player_image')  # Add image
                })
            
            # Assign to last or next match
            if fixture_data.get('is_upcoming'):
                summary['next_match'] = fixture_summary
            else:
                summary['last_match'] = fixture_summary
        
        # Calculate team impact
        all_sidelined = []
        if summary['last_match']:
            all_sidelined.extend(summary['last_match'].get('sidelined_players', []))
        if summary['next_match']:
            all_sidelined.extend(summary['next_match'].get('sidelined_players', []))
        
        # Remove duplicates and count
        unique_players = {p['name']: p for p in all_sidelined}.values()
        summary['team_impact']['total_unavailable'] = len(unique_players)
        
        # Identify key players (starters/important positions)
        key_positions = ['Goalkeeper', 'Centre Back', 'Striker', 'Attacking Midfielder']
        summary['team_impact']['key_players_out'] = [
            p for p in unique_players 
            if any(pos in p.get('position', '') for pos in key_positions)
        ]
        
        return summary
    
    def analyze_player_performance(self, player_data: Dict) -> Dict:
        """
        Analyze player performance trends - FANTASY FOOTBALL VERSION
        
        Args:
            player_data: Player data with statistics and match data
            
        Returns:
            Performance analysis
        """
        analysis = {
            'performance_trend': 'stable',
            'key_strengths': [],
            'areas_for_improvement': [],
            'season_comparison': {},
            'overall_rating': 'good'
        }
        
        try:
            # Analyze based on seasonal statistics if available
            seasonal_stats = player_data.get('seasonal_stats', [])
            if len(seasonal_stats) >= 2:
                current_season = seasonal_stats[0]
                previous_season = seasonal_stats[1]
                
                # Compare goals
                current_goals = current_season.get('goals', 0) or 0
                previous_goals = previous_season.get('goals', 0) or 0
                
                # Compare assists
                current_assists = current_season.get('assists', 0) or 0
                previous_assists = previous_season.get('assists', 0) or 0
                
                # Compare appearances
                current_apps = current_season.get('appearances', 0) or 0
                previous_apps = previous_season.get('appearances', 0) or 0
                
                analysis['season_comparison'] = {
                    'goals_change': current_goals - previous_goals,
                    'assists_change': current_assists - previous_assists,
                    'appearances_change': current_apps - previous_apps,
                    'current_season': {
                        'goals': current_goals,
                        'assists': current_assists,
                        'appearances': current_apps,
                        'season_name': current_season.get('season_name', 'Current Season')
                    },
                    'previous_season': {
                        'goals': previous_goals,
                        'assists': previous_assists,
                        'appearances': previous_apps,
                        'season_name': previous_season.get('season_name', 'Previous Season')
                    }
                }
                
                # Determine performance trend
                if current_goals > previous_goals and current_assists >= previous_assists:
                    analysis['performance_trend'] = 'improving'
                elif current_goals < previous_goals:
                    analysis['performance_trend'] = 'declining'

                # Key strengths based on position
                position_info = player_data.get('position', {})
                position = position_info.get('name', '').lower() if position_info else ''

                if 'back' in position or 'defender' in position:
                    if current_season.get('clean_sheets', 0) > 10:
                        analysis['key_strengths'].append('Defensive Wall')
                    if current_goals > 3:
                        analysis['key_strengths'].append('Goal Threat from Defense')
                elif 'midfield' in position:
                    if current_assists > 10:
                        analysis['key_strengths'].append('Elite Playmaker')
                    if current_season.get('key_passes', 0) > 50:
                        analysis['key_strengths'].append('Creative Force')
                    if current_goals > 10:
                        analysis['key_strengths'].append('Goal-Scoring Midfielder')
                else:  # Forwards
                    if current_goals > 20:
                        analysis['key_strengths'].append('Elite Goal Scorer')
                    elif current_goals > 15:
                        analysis['key_strengths'].append('Prolific Goal Scorer')
                    elif current_goals > 10:
                        analysis['key_strengths'].append('Consistent Goal Scorer')
                    
                    if current_assists > 10:
                        analysis['key_strengths'].append('Complete Forward')
                    
                if current_apps > 30:
                    analysis['key_strengths'].append('Highly Available')
                elif current_apps > 25:
                    analysis['key_strengths'].append('Consistent Starter')
            
            # Analyze based on recent matches
            recent_matches = player_data.get('recent_matches', {})
            if recent_matches and 'summary' in recent_matches:
                summary = recent_matches['summary']
                
                total_goals = summary.get('total_goals', 0)
                total_assists = summary.get('total_assists', 0)
                avg_rating = summary.get('average_rating')
                
                # Overall performance assessment
                if avg_rating:
                    if avg_rating >= 8.0:
                        analysis['overall_rating'] = 'world class'
                    elif avg_rating >= 7.5:
                        analysis['overall_rating'] = 'excellent'
                    elif avg_rating >= 7.0:
                        analysis['overall_rating'] = 'very good'
                    elif avg_rating >= 6.5:
                        analysis['overall_rating'] = 'good'
                    elif avg_rating >= 6.0:
                        analysis['overall_rating'] = 'average'
                    else:
                        analysis['overall_rating'] = 'below average'
                
                # Recent form analysis
                recent_form = summary.get('recent_form', [])
                if len(recent_form) >= 3:
                    recent_goals = sum(match.get('goals', 0) for match in recent_form[:3])
                    if recent_goals >= 3:
                        analysis['key_strengths'].append('In Scoring Form')
                    
                    recent_ratings = [match.get('rating') for match in recent_form[:5] if match.get('rating')]
                    if recent_ratings and len(recent_ratings) >= 3:
                        avg_recent_rating = sum(recent_ratings) / len(recent_ratings)
                        if avg_recent_rating >= 7.5:
                            analysis['key_strengths'].append('Excellent Recent Form')
                        elif avg_recent_rating < 6.0:
                            analysis['areas_for_improvement'].append('Recent Form Concerns')
        
        except Exception as e:
            logger.error(f"Error analyzing player performance: {str(e)}")
        
        return analysis

    def _process_all_match_stats(self, latest_data: List[Dict], player_data: Dict = None) -> Dict:
        """
        Process and store comprehensive match-level statistics for all available matches
        Now includes FDF scoring for each match
        
        Args:
            latest_data: Raw match data from API
            player_data: Player data for position information
            
        Returns:
            Dictionary containing all match-level stats organized by fixture_id with FDF scores
        """
        if not latest_data:
            return {'matches': [], 'total_matches': 0, 'stat_types': []}
        
        all_matches_by_fixture = {}
        all_stat_types = set()
        
        # Group match data by fixture_id
        for match_entry in latest_data:
            fixture_data = match_entry.get('fixture', {})
            if not fixture_data:
                continue
            
            fixture_id = match_entry.get('fixture_id')
            if fixture_id:
                if fixture_id not in all_matches_by_fixture:
                    all_matches_by_fixture[fixture_id] = {
                        'fixture_id': fixture_id,
                        'fixture_info': fixture_data,
                        'player_stats': []
                    }
                
                if 'details' in match_entry:
                    all_matches_by_fixture[fixture_id]['player_stats'].extend(match_entry['details'])
        
        # Process each match to extract all available stats
        processed_matches = []
        
        for fixture_id, match_data in all_matches_by_fixture.items():
            fixture_info = match_data.get('fixture_info', {})
            player_stats = match_data.get('player_stats', [])
            
            if not fixture_info:
                continue
            
            # Extract all match stats
            match_stats = {}
            for stat in player_stats:
                if not stat or not stat.get('type'):
                    continue
                    
                type_data = stat['type']
                data_data = stat.get('data', {})
                stat_name = type_data.get('name', 'Unknown')
                stat_value = data_data.get('value')
                
                # Store the stat
                match_stats[stat_name] = stat_value
                all_stat_types.add(stat_name)
            
            # Extract match metadata
            league_data = fixture_info.get('league', {})
            
            processed_match = {
                'fixture_id': fixture_id,
                'date': fixture_info.get('starting_at'),
                'league': {
                    'id': league_data.get('id'),
                    'name': league_data.get('name', 'Unknown League'),
                    'short_code': league_data.get('short_code'),
                    'type': league_data.get('sub_type')
                },
                'teams': [],
                'score': None,
                'stats': match_stats  # All available match stats
            }
            
            # Extract teams with home/away designation
            if 'participants' in fixture_info and fixture_info['participants']:
                teams_data = []
                for p in fixture_info['participants']:
                    if p:
                        team_info = {
                            'id': p.get('id'),
                            'name': p.get('name', 'Unknown'),
                            'short_code': p.get('short_code'),
                            'is_home': p.get('meta', {}).get('location') == 'home'
                        }
                        teams_data.append(team_info)
                
                # Sort so home team is first, away team is second
                teams_data.sort(key=lambda x: not x['is_home'])
                processed_match['teams'] = teams_data
            
            # Extract score
            if 'scores' in fixture_info and fixture_info['scores']:
                home_score = None
                away_score = None
                
                for score in fixture_info['scores']:
                    if not score or score.get('description') != 'CURRENT':
                        continue
                    score_data = score.get('score', {})
                    if score_data.get('participant') == 'home':
                        home_score = score_data.get('goals')
                    elif score_data.get('participant') == 'away':
                        away_score = score_data.get('goals')
                
                if home_score is not None and away_score is not None:
                    processed_match['score'] = f"{home_score}-{away_score}"
            
            # Calculate FDF score for this match
            if player_data:
                position_category = self._get_player_position_category(player_data)
                league_info = processed_match['league']
                
                # Determine team result based on player's actual team
                team_result = None
                if processed_match.get('score') and processed_match.get('teams') and player_data:
                    try:
                        home_goals, away_goals = map(int, processed_match['score'].split('-'))
                        teams = processed_match['teams']
                        player_team_id = player_data.get('current_team', {}).get('id')
                        
                        if len(teams) >= 2 and player_team_id:
                            # Find which team the player belongs to
                            player_is_home = False
                            for team in teams:
                                if team.get('id') == player_team_id:
                                    player_is_home = team.get('is_home', False)
                                    break
                            
                            # Determine result based on player's team position
                            if player_is_home:
                                # Player is on home team
                                if home_goals > away_goals:
                                    team_result = 'win'
                                elif home_goals < away_goals:
                                    team_result = 'loss'
                                else:
                                    team_result = 'draw'
                            else:
                                # Player is on away team
                                if away_goals > home_goals:
                                    team_result = 'win'
                                elif away_goals < home_goals:
                                    team_result = 'loss'
                                else:
                                    team_result = 'draw'
                    except (ValueError, IndexError):
                        team_result = None
                
                fdf_breakdown = self.calculate_fdf_score(
                    match_stats, 
                    position_category, 
                    league_info, 
                    team_result
                )
                processed_match['fdf_score'] = fdf_breakdown
            
            processed_matches.append(processed_match)
        
        # Sort matches by date (most recent first)
        processed_matches.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        return {
            'matches': processed_matches,
            'total_matches': len(processed_matches),
            'stat_types': sorted(list(all_stat_types))
        }

    def calculate_fdf_score(self, match_stats: Dict, position_category: str, league_info: Dict = None, 
                           team_result: str = None) -> Dict:
        """
        Calculate Fantasy Draft Football (FDF) score for a match
        
        Args:
            match_stats: Dictionary of match statistics
            position_category: Player position (Goalkeeper, Defender, Midfielder, Attacker)
            league_info: League information for competition quality assessment
            team_result: Team result (win/draw/loss) if available
            
        Returns:
            Dictionary with FDF score breakdown and total
        """
        fdf_breakdown = {
            'base_points': 0,
            'goals_assists': 0,
            'shooting': 0,
            'passing': 0,
            'defensive': 0,
            'attacking': 0,
            'clean_sheet': 0,
            'goalkeeper_saves': 0,
            'errors_discipline': 0,
            'win_draw_bonus': 0,
            'total': 0
        }
        
        try:
            # Base Points - Starting XI vs Substitute
            minutes_played = match_stats.get('Minutes Played', 0) or 0
            if minutes_played > 0:
                if minutes_played >= 60:  # Assume starter if 60+ minutes
                    fdf_breakdown['base_points'] = 10
                else:
                    fdf_breakdown['base_points'] = 5
            
            # Goals & Assists
            goals = match_stats.get('Goals', 0) or 0
            assists = match_stats.get('Assists', 0) or 0
            fdf_breakdown['goals_assists'] = (goals * 50) + (assists * 30)
            
            # Shooting (position-dependent)
            shots_on_target = match_stats.get('Shots On Target', 0) or 0
            shots_blocked = match_stats.get('Shots Blocked', 0) or 0
            shots_off_target = match_stats.get('Shots Off Target', 0) or 0
            big_chances_missed = match_stats.get('Big Chances Missed', 0) or 0
            
            # Base shooting points
            fdf_breakdown['shooting'] = (shots_on_target * 10) + (shots_blocked * 3)
            
            # Shots off target penalties (position-dependent)
            if shots_off_target > 0:
                if position_category == 'Midfielder':
                    fdf_breakdown['shooting'] += shots_off_target * -1
                elif position_category == 'Attacker':
                    fdf_breakdown['shooting'] += shots_off_target * -3
            
            # Big chance missed penalties (base + position-dependent)
            if big_chances_missed > 0:
                base_penalty = big_chances_missed * -10
                position_penalty = 0
                if position_category == 'Attacker':
                    position_penalty = big_chances_missed * -5
                elif position_category == 'Midfielder':
                    position_penalty = big_chances_missed * -3
                
                fdf_breakdown['shooting'] += base_penalty + position_penalty
            
            # Passing - Enhanced system with proper point values
            accurate_passes = match_stats.get('Accurate Passes', 0) or 0
            big_chances_created = match_stats.get('Big Chances Created', 0) or 0
            
            if accurate_passes > 0:
                # Better position-based estimation for opponent vs own half
                if position_category in ['Attacker', 'Midfielder']:
                    opponent_half_passes = accurate_passes * 0.7
                    own_half_passes = accurate_passes * 0.3
                else:  # Defender/Goalkeeper
                    opponent_half_passes = accurate_passes * 0.3
                    own_half_passes = accurate_passes * 0.7
                
                # Official FDF passing points
                fdf_breakdown['passing'] = (opponent_half_passes * 0.75) + (own_half_passes * 0.25)
            
            # Big Chances Created bonus
            fdf_breakdown['passing'] += big_chances_created * 10
            
            # Attacking Actions - Dribbles, Fouls Won, etc.
            successful_dribbles = match_stats.get('Successful Dribbles', 0) or 0
            fouls_drawn = match_stats.get('Fouls Drawn', 0) or 0
            
            # Dribbling points (5 points per successful dribble)
            fdf_breakdown['attacking'] = successful_dribbles * 5
            
            # Fouls won points (2 points per foul drawn)
            fdf_breakdown['attacking'] += fouls_drawn * 2
            
            # Defensive Actions - Enhanced with additional stats
            tackles_won = match_stats.get('Tackles', 0) or 0
            interceptions = match_stats.get('Interceptions', 0) or 0
            blocks = match_stats.get('Blocks', 0) or match_stats.get('Blocked Shots', 0) or 0
            clearances = match_stats.get('Clearances', 0) or 0
            recoveries = match_stats.get('Recoveries', 0) or 0
            ball_recovery = match_stats.get('Ball Recovery', 0) or 0
            duels_won = match_stats.get('Duels Won', 0) or 0
            total_duels = match_stats.get('Total Duels', 0) or 0
            last_man_tackle = match_stats.get('Last Man Tackle', 0) or 0
            
            # Base defensive points (corrected values)
            fdf_breakdown['defensive'] = (tackles_won * 3) + (interceptions * 3) + (blocks * 5)
            
            # Additional defensive actions
            fdf_breakdown['defensive'] += (clearances * 1) + (recoveries * 2) + (ball_recovery * 2) + (duels_won * 3)
            
            # Last man tackles (special bonus)
            fdf_breakdown['defensive'] += last_man_tackle * 10
            
            # Duels lost penalties (position-dependent)
            if total_duels > 0:
                duels_lost = max(0, total_duels - duels_won)
                if duels_lost > 0:
                    if position_category in ['Goalkeeper', 'Defender']:
                        fdf_breakdown['defensive'] += duels_lost * -3
                    elif position_category == 'Midfielder':
                        fdf_breakdown['defensive'] += duels_lost * -2
                    else:  # Attacker
                        fdf_breakdown['defensive'] += duels_lost * -1
            
            # Clean Sheets (for 60+ minutes played)
            if minutes_played >= 60:
                clean_sheets = match_stats.get('Clean Sheets', 0) or match_stats.get('Cleansheets', 0) or 0
                goals_conceded = match_stats.get('Goals Conceded', 0) or 0
                
                # If no explicit clean sheet stat, infer from goals conceded = 0
                if clean_sheets > 0 or goals_conceded == 0:
                    if position_category == 'Goalkeeper':
                        fdf_breakdown['clean_sheet'] = 40
                    elif position_category == 'Defender':
                        fdf_breakdown['clean_sheet'] = 30
                    elif position_category == 'Midfielder':
                        fdf_breakdown['clean_sheet'] = 10
            
            # Goalkeeper Saves and Actions
            if position_category == 'Goalkeeper':
                saves_inside_box = match_stats.get('Saves Insidebox', 0) or 0
                total_saves = match_stats.get('Saves', 0) or 0
                saves_outside_box = max(0, total_saves - saves_inside_box)
                punches = match_stats.get('Punches', 0) or 0
                
                # Save points
                fdf_breakdown['goalkeeper_saves'] = (saves_inside_box * 5) + (saves_outside_box * 3)
                
                # Goalkeeper actions (punches, catches, etc.)
                fdf_breakdown['goalkeeper_saves'] += (punches * 3)  # 3 points per punch
                
                # Penalty saves (estimate from high-value saves)
                if saves_inside_box > 3:  # Heuristic for potential penalty save
                    fdf_breakdown['goalkeeper_saves'] += 30
            
            # Errors & Discipline - Enhanced with position-specific penalties
            errors_goal = match_stats.get('Error Lead To Goal', 0) or 0
            errors_shot = match_stats.get('Error Lead To Shot', 0) or 0
            yellow_cards = match_stats.get('Yellowcards', 0) or 0
            red_cards = match_stats.get('Redcards', 0) or 0
            dispossessed = match_stats.get('Dispossessed', 0) or 0
            offsides = match_stats.get('Offsides', 0) or 0
            fouls = match_stats.get('Fouls', 0) or 0
            
            # Base discipline penalties
            fdf_breakdown['errors_discipline'] = (yellow_cards * -10) + (red_cards * -20) + (fouls * -3)
            
            # Position-specific error penalties for errors leading to goal
            if errors_goal > 0:
                if position_category in ['Goalkeeper', 'Defender']:
                    fdf_breakdown['errors_discipline'] += errors_goal * -20
                else:  # Midfielder/Attacker
                    fdf_breakdown['errors_discipline'] += errors_goal * -10
            
            # Position-specific error penalties for errors leading to shot
            if errors_shot > 0:
                if position_category in ['Goalkeeper', 'Defender']:
                    fdf_breakdown['errors_discipline'] += errors_shot * -10
                else:  # Midfielder/Attacker
                    fdf_breakdown['errors_discipline'] += errors_shot * -5
            
            # Dispossession penalties (position-dependent)
            if dispossessed > 0:
                if position_category in ['Goalkeeper', 'Defender']:
                    fdf_breakdown['errors_discipline'] += dispossessed * -5
                elif position_category == 'Midfielder':
                    fdf_breakdown['errors_discipline'] += dispossessed * -3
                else:  # Attacker
                    fdf_breakdown['errors_discipline'] += dispossessed * -1
            
            # Offsides penalties (only for attacking positions)
            if offsides > 0 and position_category in ['Midfielder', 'Attacker']:
                fdf_breakdown['errors_discipline'] += offsides * -3
            
            # Win/Draw Bonus - Official FDF Competition Scoring
            if team_result:
                win_points, draw_points = self._get_competition_points(league_info)
                if team_result.lower() == 'win':
                    fdf_breakdown['win_draw_bonus'] = win_points
                elif team_result.lower() == 'draw':
                    fdf_breakdown['win_draw_bonus'] = draw_points
            else:
                # Try to infer result from score if available
                score = match_stats.get('score', '')
                teams = match_stats.get('teams', [])
                
                if score and '-' in score and teams and len(teams) >= 2:
                    try:
                        home_goals, away_goals = map(int, score.split('-'))
                        
                        # Determine if player's team won, drew, or lost
                        # For now, check both possibilities since we don't know home/away
                        team_won = (home_goals > away_goals) or (away_goals > home_goals)
                        team_drew = (home_goals == away_goals)
                        
                        if team_won:
                            win_points, _ = self._get_competition_points(league_info)
                            fdf_breakdown['win_draw_bonus'] = win_points
                        elif team_drew:
                            _, draw_points = self._get_competition_points(league_info)
                            fdf_breakdown['win_draw_bonus'] = draw_points
                    except (ValueError, AttributeError):
                        pass
            
            # Calculate total
            fdf_breakdown['total'] = sum([
                fdf_breakdown['base_points'],
                fdf_breakdown['goals_assists'],
                fdf_breakdown['shooting'],
                fdf_breakdown['passing'],
                fdf_breakdown['defensive'],
                fdf_breakdown['attacking'],
                fdf_breakdown['clean_sheet'],
                fdf_breakdown['goalkeeper_saves'],
                fdf_breakdown['errors_discipline'],
                fdf_breakdown['win_draw_bonus']
            ])
            
        except Exception as e:
            logger.error(f"Error calculating FDF score: {str(e)}")
            fdf_breakdown['total'] = 0
        
        return fdf_breakdown
    
    def _get_competition_points(self, league_info: Dict = None) -> tuple:
        """
        Get win/draw points based on official FDF competition scoring
        Returns: (win_points, draw_points)
        """
        if not league_info:
            return (10, 5)  # Default for unknown competitions
        
        league_id = league_info.get('id')
        
        # Tier 1: Maximum points (30/15) - Only Premier League gets max
        tier_1_leagues = [
            8,    # Premier League
            2,    # Champions League - Knockouts
        ]
        
        # Tier 2: High points (20/10) - Major European leagues
        tier_2_leagues = [
            564,  # La Liga
            82,   # Bundesliga
            384,  # Serie A
            271,  # Ligue 1
            5,    # Europa League - Knockouts
        ]
        
        # Tier 3: Medium points (10/5)
        tier_3_leagues = [
            # Nations League and other competitions
            # Add specific league IDs as needed
        ]
        
        if league_id in tier_1_leagues:
            return (30, 15)
        elif league_id in tier_2_leagues:
            return (20, 10)
        elif league_id in tier_3_leagues:
            return (10, 5)
        else:
            # Default for unknown competitions
            return (10, 5)
    
    def _is_top_league(self, league_info: Dict = None) -> bool:
        """Determine if league is a top-tier competition (legacy method)"""
        win_points, _ = self._get_competition_points(league_info)
        return win_points >= 20
    
    def _get_player_position_category(self, player_data: Dict) -> str:
        """Extract position category from player data"""
        if not player_data:
            return 'Unknown'
        
        position = player_data.get('position', {})
        if position:
            return position.get('category', 'Unknown')
        
        # Fallback to position_id
        position_id = player_data.get('position_id')
        if position_id:
            if position_id in [1, 24]:
                return 'Goalkeeper'
            elif position_id in [2, 3, 4, 5, 25]:
                return 'Defender'
            elif position_id in [6, 7, 8, 9, 10, 26]:
                return 'Midfielder'
            elif position_id in [11, 12, 13, 14, 15, 27]:
                return 'Attacker'
        
        return 'Unknown'

    def _calculate_age(self, date_of_birth: str) -> Optional[int]:
        """Calculate age from date of birth"""
        if not date_of_birth:
            return None
        
        try:
            birth_date = datetime.strptime(date_of_birth, '%Y-%m-%d')
            today = datetime.now()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            return age
        except:
            return None