"""
Content Library API Routes
Provides endpoints for cross-platform content reposting
"""

import logging
from flask import jsonify, request, g
from app.routes.content_library import bp
from app.system.auth.middleware import auth_required
from app.system.services.content_library_service import ContentLibraryManager

logger = logging.getLogger('content_library_routes')


@bp.route('/', methods=['GET'])
@auth_required
def get_content_library():
    """
    Get recent content for reposting

    Query params:
        - media_type: Filter by 'video' or 'image' (optional)
        - hours: How many hours back to look (default 24)
    """
    try:
        user_id = g.user.get('id')
        media_type = request.args.get('media_type')
        hours = int(request.args.get('hours', 24))

        # Validate media_type
        if media_type and media_type not in ['video', 'image', 'all']:
            return jsonify({
                'success': False,
                'error': 'Invalid media_type. Must be "video", "image", or "all"'
            }), 400

        # Convert 'all' to None for the service layer
        if media_type == 'all':
            media_type = None

        # Get content
        content_list = ContentLibraryManager.get_recent_content(
            user_id=user_id,
            media_type_filter=media_type,
            hours=hours
        )

        # Convert datetime objects to ISO format for JSON
        for content in content_list:
            if 'created_at' in content and content['created_at']:
                content['created_at'] = content['created_at'].isoformat()

            # Convert platform timestamps
            if 'platforms_posted' in content:
                for platform, data in content['platforms_posted'].items():
                    if 'posted_at' in data and data['posted_at']:
                        data['posted_at'] = data['posted_at'].isoformat()
                    if 'scheduled_for' in data and data['scheduled_for']:
                        # scheduled_for might already be a string
                        if hasattr(data['scheduled_for'], 'isoformat'):
                            data['scheduled_for'] = data['scheduled_for'].isoformat()

        return jsonify({
            'success': True,
            'content': content_list,
            'count': len(content_list)
        })

    except Exception as e:
        logger.error(f"Error getting content library: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<content_id>', methods=['GET'])
@auth_required
def get_content_by_id(content_id):
    """Get specific content by ID"""
    try:
        user_id = g.user.get('id')

        content = ContentLibraryManager.get_content_by_id(
            user_id=user_id,
            content_id=content_id
        )

        if not content:
            return jsonify({
                'success': False,
                'error': 'Content not found'
            }), 404

        # Convert datetime to ISO format
        if 'created_at' in content and content['created_at']:
            content['created_at'] = content['created_at'].isoformat()

        if 'platforms_posted' in content:
            for platform, data in content['platforms_posted'].items():
                if 'posted_at' in data and data['posted_at']:
                    data['posted_at'] = data['posted_at'].isoformat()
                if 'scheduled_for' in data and data['scheduled_for']:
                    if hasattr(data['scheduled_for'], 'isoformat'):
                        data['scheduled_for'] = data['scheduled_for'].isoformat()

        return jsonify({
            'success': True,
            'content': content
        })

    except Exception as e:
        logger.error(f"Error getting content by ID: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<content_id>', methods=['DELETE'])
@auth_required
def delete_content(content_id):
    """Delete content from library"""
    try:
        user_id = g.user.get('id')

        success = ContentLibraryManager.delete_content(
            user_id=user_id,
            content_id=content_id
        )

        if success:
            return jsonify({
                'success': True,
                'message': 'Content deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to delete content'
            }), 500

    except Exception as e:
        logger.error(f"Error deleting content: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
