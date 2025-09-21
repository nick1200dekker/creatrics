from flask import render_template, request, jsonify, current_app, g
import traceback
from datetime import datetime
import uuid

from app.routes.content_calendar import bp
from app.system.auth.middleware import auth_required
from app.scripts.content_calendar.calendar_manager import ContentCalendarManager

@bp.route('/content-calendar')
@auth_required
def content_calendar():
    """Render the Content Calendar page"""
    return render_template('content_calendar/index.html')

@bp.route('/content-calendar/api/events', methods=['GET'])
@auth_required
def get_events():
    """API endpoint to get all calendar events"""
    try:
        user_id = g.user.get('id')
        
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Get all events
        events = calendar_manager.get_all_events()
        
        return jsonify(events)
    except Exception as e:
        current_app.logger.error(f"Error getting events: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@bp.route('/content-calendar/api/event', methods=['POST'])
@auth_required
def create_event():
    """API endpoint to create a new calendar event"""
    try:
        user_id = g.user.get('id')
        
        # Get form data
        data = request.json
        
        # Validate required fields
        if not data.get('title') or not data.get('publish_date'):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Create the event with new fields
        event_id = calendar_manager.create_event(
            title=data.get('title'),
            publish_date=data.get('publish_date'),
            is_paid=data.get('is_paid', False),
            is_free=data.get('is_free', True),  # This now represents "organic" content
            is_sponsored=data.get('is_sponsored', False),
            category=data.get('category', ''),
            audience_type=data.get('audience_type', 'Public'),
            content_type=data.get('content_type', data.get('platform', '')),  # Default to platform if content_type missing
            platform=data.get('platform', ''),
            description=data.get('description', ''),
            color=data.get('color', ''),  # Let the JS handle color assignment
            content_link=data.get('content_link', ''),  # New field
            status=data.get('status', 'planned'),  # New field with default
            comments=data.get('comments', []),  # New field
            notes=data.get('notes', '')  # New field
        )
        
        return jsonify({"success": True, "event_id": event_id})
    except Exception as e:
        current_app.logger.error(f"Error creating event: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@bp.route('/content-calendar/api/event/<event_id>', methods=['PUT'])
@auth_required
def update_event(event_id):
    """API endpoint to update an existing calendar event"""
    try:
        user_id = g.user.get('id')
        
        # Get form data
        data = request.json
        
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Prepare update data - only include fields that are present in request
        update_data = {}
        
        # Standard fields
        if 'title' in data:
            update_data['title'] = data['title']
        if 'publish_date' in data:
            update_data['publish_date'] = data['publish_date']
        if 'is_paid' in data:
            update_data['is_paid'] = data['is_paid']
        if 'is_free' in data:
            update_data['is_free'] = data['is_free']
        if 'is_sponsored' in data:
            update_data['is_sponsored'] = data['is_sponsored']
        if 'category' in data:
            update_data['category'] = data['category']
        if 'audience_type' in data:
            update_data['audience_type'] = data['audience_type']
        if 'content_type' in data:
            update_data['content_type'] = data['content_type']
        if 'platform' in data:
            update_data['platform'] = data['platform']
        if 'description' in data:
            update_data['description'] = data['description']
        if 'color' in data:
            update_data['color'] = data['color']
        
        # New fields
        if 'content_link' in data:
            update_data['content_link'] = data['content_link']
        if 'status' in data:
            update_data['status'] = data['status']
        if 'comments' in data:
            update_data['comments'] = data['comments']
        if 'notes' in data:
            update_data['notes'] = data['notes']
        
        # Update the event
        success = calendar_manager.update_event(event_id=event_id, **update_data)
        
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Event not found"}), 404
    except Exception as e:
        current_app.logger.error(f"Error updating event: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@bp.route('/content-calendar/api/event/<event_id>', methods=['DELETE'])
@auth_required
def delete_event(event_id):
    """API endpoint to delete a calendar event"""
    try:
        user_id = g.user.get('id')
        
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Delete the event
        success = calendar_manager.delete_event(event_id)
        
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Event not found"}), 404
    except Exception as e:
        current_app.logger.error(f"Error deleting event: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@bp.route('/content-calendar/api/event/<event_id>', methods=['GET'])
@auth_required
def get_event(event_id):
    """API endpoint to get a specific event"""
    try:
        user_id = g.user.get('id')
        
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Get the event
        event = calendar_manager.get_event(event_id)
        
        if event:
            return jsonify(event)
        else:
            return jsonify({"error": "Event not found"}), 404
    except Exception as e:
        current_app.logger.error(f"Error getting event: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@bp.route('/content-calendar/api/event/<event_id>/comment', methods=['POST'])
@auth_required
def add_comment(event_id):
    """API endpoint to add a comment to an event"""
    try:
        user_id = g.user.get('id')
        
        # Get form data
        data = request.json
        
        # Validate required fields
        if not data.get('text'):
            return jsonify({"error": "Comment text is required"}), 400
        
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Add comment to the event
        success = calendar_manager.add_comment_to_event(event_id, data['text'])
        
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Event not found"}), 404
    except Exception as e:
        current_app.logger.error(f"Error adding comment: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@bp.route('/content-calendar/api/event/<event_id>/status', methods=['PUT'])
@auth_required
def update_event_status(event_id):
    """API endpoint to update event status"""
    try:
        user_id = g.user.get('id')
        
        # Get form data
        data = request.json
        
        # Validate required fields
        if not data.get('status'):
            return jsonify({"error": "Status is required"}), 400
        
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Update event status
        success = calendar_manager.update_event_status(event_id, data['status'])
        
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Event not found or invalid status"}), 404
    except Exception as e:
        current_app.logger.error(f"Error updating event status: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@bp.route('/content-calendar/api/event/<event_id>/notes', methods=['PUT'])
@auth_required
def update_event_notes(event_id):
    """API endpoint to update event notes"""
    try:
        user_id = g.user.get('id')
        
        # Get form data
        data = request.json
        
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Update event notes
        success = calendar_manager.update_event_notes(event_id, data.get('notes', ''))
        
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Event not found"}), 404
    except Exception as e:
        current_app.logger.error(f"Error updating event notes: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@bp.route('/content-calendar/api/events/status/<status>', methods=['GET'])
@auth_required
def get_events_by_status(status):
    """API endpoint to get events by status"""
    try:
        user_id = g.user.get('id')
        
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Get events by status
        events = calendar_manager.get_events_by_status(status)
        
        return jsonify(events)
    except Exception as e:
        current_app.logger.error(f"Error getting events by status: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@bp.route('/content-calendar/api/events/date-range', methods=['GET'])
@auth_required
def get_events_by_date_range():
    """API endpoint to get events within a date range"""
    try:
        user_id = g.user.get('id')
        
        # Get query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 1000))
        
        if not start_date or not end_date:
            return jsonify({"error": "start_date and end_date are required"}), 400
        
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Get events by date range
        events = calendar_manager.get_events_by_date_range(start_date, end_date, limit)
        
        return jsonify(events)
    except Exception as e:
        current_app.logger.error(f"Error getting events by date range: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500