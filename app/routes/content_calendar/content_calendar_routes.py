from flask import render_template, request, jsonify, g
from . import bp
from app.system.auth.middleware import auth_required
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

@bp.route('/content-calendar')
@auth_required
def content_calendar():
    """Content calendar page"""
    return render_template('content_calendar/index.html')

@bp.route('/api/content-calendar/events', methods=['GET'])
@auth_required
def get_calendar_events():
    """Get calendar events for a specific month"""
    try:
        # Get month and year from query params
        month = request.args.get('month', datetime.now().month, type=int)
        year = request.args.get('year', datetime.now().year, type=int)
        
        # Import calendar manager here to avoid circular imports
        from app.scripts.content_calendar.calendar_manager import ContentCalendarManager
        
        # Get user ID from auth context
        user_id = g.user.get('id') if g.user else None
        if not user_id:
            return jsonify({'success': False, 'error': 'User not authenticated'}), 401
            
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Get all events
        events = calendar_manager.get_all_events()
        
        return jsonify({
            'success': True,
            'events': events,
            'month': month,
            'year': year
        })
    except Exception as e:
        logger.error(f"Error fetching calendar events: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/content-calendar/events', methods=['POST'])
@auth_required
def create_calendar_event():
    """Create a new calendar event"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['title', 'date', 'platform']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        
        # Import calendar manager
        from app.scripts.content_calendar.calendar_manager import ContentCalendarManager
        
        # Get user ID
        user_id = g.user.get('id') if g.user else None
        if not user_id:
            return jsonify({'success': False, 'error': 'User not authenticated'}), 401
            
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Create event
        event_id = calendar_manager.create_event(
            title=data.get('title'),
            publish_date=data.get('date'),
            is_paid=data.get('is_paid', False),
            is_free=data.get('is_free', True),
            is_sponsored=data.get('is_sponsored', False),
            category=data.get('category', ''),
            audience_type=data.get('audience_type', 'Public'),
            content_type=data.get('content_type', data.get('platform', '')),
            platform=data.get('platform'),
            description=data.get('description', ''),
            color=data.get('color', '#3b82f6'),
            content_link=data.get('content_link', ''),
            status=data.get('status', 'planned'),
            comments=data.get('comments', []),
            notes=data.get('notes', '')
        )
        
        # Get the created event
        event = calendar_manager.get_event(event_id)
        
        return jsonify({
            'success': True,
            'event': event,
            'message': 'Event created successfully'
        })
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/content-calendar/events/<event_id>', methods=['PUT'])
@auth_required
def update_calendar_event(event_id):
    """Update an existing calendar event"""
    try:
        data = request.json
        
        # Import calendar manager
        from app.scripts.content_calendar.calendar_manager import ContentCalendarManager
        
        # Get user ID
        user_id = g.user.get('id') if g.user else None
        if not user_id:
            return jsonify({'success': False, 'error': 'User not authenticated'}), 401
            
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Update event
        success = calendar_manager.update_event(event_id=event_id, **data)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Event updated successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Event not found'}), 404
            
    except Exception as e:
        logger.error(f"Error updating calendar event: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/content-calendar/events/<event_id>', methods=['DELETE'])
@auth_required
def delete_calendar_event(event_id):
    """Delete a calendar event"""
    try:
        # Import calendar manager
        from app.scripts.content_calendar.calendar_manager import ContentCalendarManager
        
        # Get user ID
        user_id = g.user.get('id') if g.user else None
        if not user_id:
            return jsonify({'success': False, 'error': 'User not authenticated'}), 401
            
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Delete event
        success = calendar_manager.delete_event(event_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Event deleted successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Event not found'}), 404
            
    except Exception as e:
        logger.error(f"Error deleting calendar event: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/content-calendar/ideas', methods=['GET'])
@auth_required
def get_content_ideas():
    """Get AI-generated content ideas"""
    try:
        platform = request.args.get('platform', 'youtube')
        
        # Sample content ideas - can be replaced with AI generation later
        ideas = {
            'youtube': [
                'Top 10 Productivity Apps for 2025',
                'Day in the Life of a Content Creator',
                'Budget Tech Setup Under $500',
                'How I Edit My Videos - Full Workflow',
                'Reacting to My Old Videos',
                'Q&A - Answering Your Questions'
            ],
            'tiktok': [
                'Quick Recipe in 60 Seconds',
                'Fashion Transformation Challenge',
                'Tech Tips You Didn\'t Know',
                'Behind the Scenes of Content Creation'
            ],
            'instagram': [
                'Aesthetic Desk Setup Tour',
                'Morning Routine Time-lapse',
                'Before & After Editing',
                'Tips for Better Photos'
            ],
            'x': [
                'Thread: 10 lessons learned this year',
                'Quick tech tip of the day',
                'Sharing my workflow setup',
                'Industry insights and trends'
            ]
        }
        
        return jsonify({
            'success': True,
            'ideas': ideas.get(platform.lower(), []),
            'platform': platform
        })
    except Exception as e:
        logger.error(f"Error generating content ideas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/content-calendar/events/<event_id>/comment', methods=['POST'])
@auth_required  
def add_comment(event_id):
    """Add a comment to an event"""
    try:
        data = request.json
        
        # Validate required fields
        if not data.get('text'):
            return jsonify({'error': 'Comment text is required'}), 400
            
        # Import calendar manager
        from app.scripts.content_calendar.calendar_manager import ContentCalendarManager
        
        # Get user ID
        user_id = g.user.get('id') if g.user else None
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
            
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Add comment
        success = calendar_manager.add_comment_to_event(event_id, data['text'])
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Event not found'}), 404
            
    except Exception as e:
        logger.error(f"Error adding comment: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/content-calendar/events/<event_id>/status', methods=['PUT'])
@auth_required
def update_event_status(event_id):
    """Update event status"""
    try:
        data = request.json
        
        # Validate required fields  
        if not data.get('status'):
            return jsonify({'error': 'Status is required'}), 400
            
        # Import calendar manager
        from app.scripts.content_calendar.calendar_manager import ContentCalendarManager
        
        # Get user ID
        user_id = g.user.get('id') if g.user else None
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
            
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Update status
        success = calendar_manager.update_event_status(event_id, data['status'])
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Event not found or invalid status'}), 404
            
    except Exception as e:
        logger.error(f"Error updating event status: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/content-calendar/events/<event_id>/notes', methods=['PUT'])
@auth_required
def update_event_notes(event_id):
    """Update event notes"""
    try:
        data = request.json
        
        # Import calendar manager
        from app.scripts.content_calendar.calendar_manager import ContentCalendarManager
        
        # Get user ID
        user_id = g.user.get('id') if g.user else None
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
            
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Update notes
        success = calendar_manager.update_event_notes(event_id, data.get('notes', ''))
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Event not found'}), 404
            
    except Exception as e:
        logger.error(f"Error updating event notes: {e}")
        return jsonify({'error': str(e)}), 500