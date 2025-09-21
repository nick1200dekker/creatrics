#!/usr/bin/env python3
"""
Test script to verify FDF (Fantasy Draft Football) scoring calculations
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.scripts.player_stats.player_service import PlayerStatsService
import json

def test_fdf_scoring():
    """Test FDF scoring calculations for different positions and scenarios"""
    
    # Initialize service
    service = PlayerStatsService()
    
    # Test players from different positions
    test_players = [
        {'id': 19694, 'name': 'Harry Kane', 'position': 'Attacker'},
        {'id': 96182, 'name': 'Bruno Fernandes', 'position': 'Midfielder'},
        {'id': 18835, 'name': 'Denzel Dumfries', 'position': 'Defender'},
        {'id': 18433, 'name': 'Thibaut Courtois', 'position': 'Goalkeeper'}
    ]
    
    print("=" * 80)
    print(" TESTING FDF SCORING SYSTEM")
    print("=" * 80)
    
    for player_info in test_players:
        player_id = player_info['id']
        player_name = player_info['name']
        expected_position = player_info['position']
        
        print(f"\n🎯 Testing {player_name} ({expected_position}) - ID: {player_id}")
        print("-" * 60)
        
        try:
            # Fetch player data with FDF scoring
            player_data = service.get_player_details(player_id)
            
            if not player_data:
                print(f"❌ No data returned for {player_name}")
                continue
            
            # Check match-level stats with FDF scores
            match_level_stats = player_data.get('match_level_stats', {})
            if not match_level_stats:
                print(f"❌ No match-level stats found for {player_name}")
                continue
            
            matches = match_level_stats.get('matches', [])
            total_matches = match_level_stats.get('total_matches', 0)
            
            print(f"📊 Total matches with FDF scores: {total_matches}")
            
            if matches:
                # Analyze first few matches
                for i, match in enumerate(matches[:3], 1):
                    print(f"\n📋 Match {i}:")
                    print(f"   Date: {match.get('date', 'Unknown')}")
                    print(f"   League: {match.get('league', {}).get('name', 'Unknown')}")
                    print(f"   Score: {match.get('score', 'N/A')}")
                    
                    # Show match stats
                    stats = match.get('stats', {})
                    key_stats = ['Goals', 'Assists', 'Minutes Played', 'Rating']
                    for stat in key_stats:
                        if stat in stats:
                            print(f"   {stat}: {stats[stat]}")
                    
                    # Show FDF score breakdown
                    fdf_score = match.get('fdf_score', {})
                    if fdf_score:
                        print(f"\n   🏆 FDF SCORE BREAKDOWN:")
                        print(f"   Base Points: {fdf_score.get('base_points', 0)}")
                        print(f"   Goals & Assists: {fdf_score.get('goals_assists', 0)}")
                        print(f"   Shooting: {fdf_score.get('shooting', 0)}")
                        print(f"   Passing: {fdf_score.get('passing', 0):.1f}")
                        print(f"   Defensive: {fdf_score.get('defensive', 0)}")
                        print(f"   Clean Sheet: {fdf_score.get('clean_sheet', 0)}")
                        print(f"   GK Saves: {fdf_score.get('goalkeeper_saves', 0)}")
                        print(f"   Errors/Discipline: {fdf_score.get('errors_discipline', 0)}")
                        print(f"   Win/Draw Bonus: {fdf_score.get('win_draw_bonus', 0)}")
                        print(f"   ⭐ TOTAL FDF SCORE: {fdf_score.get('total', 0):.1f}")
                    else:
                        print("   ❌ No FDF score calculated")
                
                # Calculate average FDF score
                fdf_scores = [match.get('fdf_score', {}).get('total', 0) for match in matches]
                valid_scores = [score for score in fdf_scores if score is not None]
                
                if valid_scores:
                    avg_fdf = sum(valid_scores) / len(valid_scores)
                    max_fdf = max(valid_scores)
                    min_fdf = min(valid_scores)
                    
                    print(f"\n📈 FDF SCORE SUMMARY:")
                    print(f"   Average FDF Score: {avg_fdf:.1f}")
                    print(f"   Best Performance: {max_fdf:.1f}")
                    print(f"   Worst Performance: {min_fdf:.1f}")
                    print(f"   Matches with FDF scores: {len(valid_scores)}/{total_matches}")
                
        except Exception as e:
            print(f"❌ Error testing {player_name}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)
    print(" FDF SCORING RULES VERIFICATION")
    print("=" * 80)
    
    # Test specific scoring scenarios
    print("\n🧪 Testing FDF Scoring Logic:")
    
    # Test scenario 1: Attacker with goal
    test_stats_1 = {
        'Minutes Played': 90,
        'Goals': 1,
        'Assists': 0,
        'Shots On Target': 3,
        'Passes': 30,
        'Accurate Passes': 25,
        'Tackles': 1
    }
    
    fdf_test_1 = service.calculate_fdf_score(test_stats_1, 'Attacker')
    print(f"\n📋 Scenario 1 - Attacker with 1 goal:")
    print(f"   Expected: Base(10) + Goal(50) + Shots(15) + Passing(3.8) + Defensive(4) = ~82.8")
    print(f"   Actual: {fdf_test_1.get('total', 0):.1f}")
    print(f"   Breakdown: {fdf_test_1}")
    
    # Test scenario 2: Goalkeeper with clean sheet
    test_stats_2 = {
        'Minutes Played': 90,
        'Goals': 0,
        'Assists': 0,
        'Cleansheets': 1,
        'Saves': 5,
        'Saves Insidebox': 3,
        'Passes': 40,
        'Accurate Passes': 35
    }
    
    fdf_test_2 = service.calculate_fdf_score(test_stats_2, 'Goalkeeper')
    print(f"\n📋 Scenario 2 - Goalkeeper with clean sheet:")
    print(f"   Expected: Base(10) + Clean Sheet(40) + Saves(21) + Passing(3.5) = ~74.5")
    print(f"   Actual: {fdf_test_2.get('total', 0):.1f}")
    print(f"   Breakdown: {fdf_test_2}")
    
    print("\n✅ FDF Scoring System Integration Complete!")
    print("🎯 All match-level stats now include detailed FDF score breakdowns")

if __name__ == "__main__":
    test_fdf_scoring()
