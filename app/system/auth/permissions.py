"""
Permission checking utilities for team access control
"""

from flask import g
from app.system.services.firebase_service import db
import logging

logger = logging.getLogger('permissions')

def check_workspace_permission(permission_name):
    """
    Check if current user has a specific permission in the active workspace

    Args:
        permission_name: Name of the permission to check (e.g., 'analytics', 'content_calendar', 'content_wiki')

    Available permissions:
        - video_script, video_title, video_tags, video_description, thumbnail
        - analyze_video, optimize_video, keyword_research, analytics, competitors
        - x_post_editor, reply_guy, clip_spaces, niche
        - brain_dump, mind_map, content_wiki, content_calendar

    Returns:
        bool: True if user has permission, False otherwise
    """
    if not hasattr(g, 'user') or not g.user:
        return False

    user_id = g.user.get('id')
    workspace_id = g.get('active_workspace_id', user_id)

    # Owner always has all permissions
    if workspace_id == user_id:
        return True

    # Check team member permissions
    workspace_permissions = g.get('workspace_permissions', {})
    return workspace_permissions.get(permission_name, False)

def get_active_workspace_data():
    """
    Get data for the currently active workspace

    Returns:
        dict: Workspace data including owner info, credits, subscription plan
    """
    if not hasattr(g, 'user') or not g.user:
        return None

    user_id = g.user.get('id')
    workspace_id = g.get('active_workspace_id', user_id)

    # If it's the user's own workspace, return their data
    if workspace_id == user_id:
        return {
            'id': user_id,
            'is_owner': True,
            'credits': g.user.get('credits', 0),
            'subscription_plan': g.user.get('subscription_plan', 'Free Plan')
        }

    # Return workspace owner's data
    workspace_data = g.get('workspace_data', {})
    return {
        'id': workspace_id,
        'is_owner': False,
        'credits': workspace_data.get('credits', 0),
        'subscription_plan': workspace_data.get('subscription_plan', 'Free Plan'),
        'permissions': g.get('workspace_permissions', {}),
        'role': g.get('workspace_role', 'member'),
        'owner_email': workspace_data.get('email', '')
    }

def get_workspace_user_id():
    """
    Get the user ID for the current workspace (either own or team workspace)

    Returns:
        str: The user ID of the workspace owner
    """
    if not hasattr(g, 'user') or not g.user:
        return None

    # Return the active workspace ID, defaulting to user's own ID
    return g.get('active_workspace_id', g.user.get('id'))

def require_permission(permission_name):
    """
    Decorator to require specific permission for a route

    Usage:
        @app.route('/analytics')
        @auth_required
        @require_permission('analytics')
        def analytics():
            return render_template('analytics.html')
    """
    from functools import wraps
    from flask import jsonify, redirect, url_for, request

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not check_workspace_permission(permission_name):
                logger.warning(f"Permission denied: {permission_name} for user {g.user.get('id')} in workspace {g.get('active_workspace_id')}")

                # API routes return JSON error
                if request.path.startswith('/api/'):
                    return jsonify({
                        'success': False,
                        'error': f'Permission denied: {permission_name} access required'
                    }), 403

                # Regular routes redirect to dashboard with error
                return redirect(url_for('home.dashboard', error='permission_denied'))

            return f(*args, **kwargs)

        return decorated_function

    return decorator

def filter_menu_items(menu_items):
    """
    Filter menu items based on user permissions in current workspace

    Args:
        menu_items: List of menu items with 'permission' field

    Returns:
        list: Filtered menu items user has access to
    """
    if not hasattr(g, 'user') or not g.user:
        return []

    user_id = g.user.get('id')
    workspace_id = g.get('active_workspace_id', user_id)

    # Owner sees everything
    if workspace_id == user_id:
        return menu_items

    # Filter based on permissions
    filtered = []
    workspace_permissions = g.get('workspace_permissions', {})

    for item in menu_items:
        # Items without permission requirement are always shown
        if 'permission' not in item:
            filtered.append(item)
            continue

        # Check if user has the required permission
        if workspace_permissions.get(item['permission'], False):
            filtered.append(item)

    return filtered