from flask import Blueprint, render_template, jsonify, request, g
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
import json
import uuid
from datetime import datetime
import firebase_admin
from firebase_admin import firestore

mind_map_bp = Blueprint('mind_map', __name__)

@mind_map_bp.route('/mind-map')
@auth_required
@require_permission('mind_map')
def mind_map():
    return render_template('mind_map/index.html')

@mind_map_bp.route('/api/mind-map/save', methods=['POST'])
@auth_required
@require_permission('mind_map')
def save_mind_map():
    try:
        data = request.json
        user_id = get_workspace_user_id()
        
        print(f"Save mind map - user_id: {user_id}")
        print(f"Save mind map - g object: {dir(g)}")
        
        if not user_id:
            return jsonify({'success': False, 'error': 'User not authenticated'}), 401
        
        # Get Firestore client
        db = firestore.client()
        
        # Save to Firebase: /users/{user_id}/mind_maps/data
        doc_ref = db.collection('users').document(user_id).collection('mind_maps').document('data')
        
        mind_map_data = {
            'maps': data.get('maps', {}),
            'currentMapId': data.get('currentMapId', 'map1'),
            'updated': datetime.utcnow(),
            'version': 1
        }
        
        print(f"Saving mind map data: {len(mind_map_data['maps'])} maps")
        for map_id, map_data in mind_map_data['maps'].items():
            print(f"  Map {map_id}: {len(map_data.get('nodes', []))} nodes, {len(map_data.get('connections', []))} connections")
        
        doc_ref.set(mind_map_data)
        
        return jsonify({
            'success': True,
            'message': 'Mind maps saved successfully'
        })
        
    except Exception as e:
        print(f"Error saving mind map: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@mind_map_bp.route('/api/mind-map/load')
@auth_required
@require_permission('mind_map')
def load_mind_map():
    try:
        user_id = get_workspace_user_id()
        
        print(f"Load mind map - user_id: {user_id}")
        print(f"Load mind map - g object: {dir(g)}")
        
        if not user_id:
            return jsonify({'success': False, 'error': 'User not authenticated'}), 401
        
        # Get Firestore client
        db = firestore.client()
        
        # Load from Firebase: /users/{user_id}/mind_maps/data
        doc_ref = db.collection('users').document(user_id).collection('mind_maps').document('data')
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            maps_data = data.get('maps', {})
            print(f"Loading mind map data: {len(maps_data)} maps")
            for map_id, map_data in maps_data.items():
                print(f"  Map {map_id}: {len(map_data.get('nodes', []))} nodes, {len(map_data.get('connections', []))} connections")
            
            return jsonify({
                'success': True,
                'data': {
                    'maps': maps_data,
                    'currentMapId': data.get('currentMapId', 'map1')
                }
            })
        else:
            # Return default structure if no data exists
            return jsonify({
                'success': True,
                'data': {
                    'maps': {
                        'map1': {
                            'id': 'map1',
                            'name': 'Map 1',
                            'nodes': [],
                            'connections': [],
                            'created': datetime.utcnow().isoformat(),
                            'updated': datetime.utcnow().isoformat()
                        }
                    },
                    'currentMapId': 'map1'
                }
            })
            
    except Exception as e:
        print(f"Error loading mind map: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@mind_map_bp.route('/api/mind-map/list')
@auth_required
@require_permission('mind_map')
def list_mind_maps():
    try:
        # Here you would fetch user's mind maps from database
        # For now, return empty list
        return jsonify({
            'success': True,
            'maps': []
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500