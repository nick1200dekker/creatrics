from flask import jsonify, g
from app.system.auth.middleware import auth_required
from app.system.services.firebase_service import db
from datetime import datetime
import logging

logger = logging.getLogger('teams.notifications')

def get_pending_invitations():
    """Get pending team invitations for current user"""
    try:
        user_id = g.user['id']
        user_email = g.user.get('data', {}).get('email', '')

        # Get invitations by user ID
        invitations_by_id = db.collection('team_members') \
            .where('member_id', '==', user_id) \
            .where('status', '==', 'pending') \
            .get()

        # Get invitations by email
        invitations_by_email = db.collection('team_members') \
            .where('email', '==', user_email) \
            .where('status', '==', 'pending') \
            .get()

        invitations = []
        seen_ids = set()

        # Process all invitations
        for invite in list(invitations_by_id) + list(invitations_by_email):
            invite_data = invite.to_dict()
            invite_id = invite.id

            if invite_id in seen_ids:
                continue
            seen_ids.add(invite_id)

            # Skip if not pending (might be removed or declined)
            if invite_data.get('status') != 'pending':
                continue

            # Get owner information
            owner_doc = db.collection('users').document(invite_data['owner_id']).get()
            owner_data = owner_doc.to_dict() if owner_doc.exists else {}

            invitations.append({
                'id': invite_id,
                'from': owner_data.get('email', 'Unknown'),
                'from_name': owner_data.get('name', owner_data.get('email', 'Unknown')),
                'permissions': invite_data.get('permissions', {}),
                'invited_at': invite_data.get('invited_at'),
                'workspace_id': invite_data['owner_id']
            })

        return invitations
    except Exception as e:
        logger.error(f"Error getting pending invitations: {str(e)}")
        return []

def get_notifications():
    """Get all notifications for current user including team invites"""
    try:
        user_id = g.user['id']

        # Get notifications from user's notifications subcollection
        notifications_ref = db.collection('users').document(user_id).collection('notifications') \
            .where('read', '==', False) \
            .order_by('created_at', direction='DESCENDING') \
            .limit(10) \
            .get()

        notifications = []
        for notif in notifications_ref:
            notif_data = notif.to_dict()
            notif_data['id'] = notif.id
            notifications.append(notif_data)

        # Also check for pending invitations
        pending_invites = get_pending_invitations()

        # Convert invitations to notification format
        for invite in pending_invites:
            notifications.append({
                'id': invite['id'],
                'type': 'team_invitation',
                'message': f"{invite['from_name']} invited you to join their workspace",
                'from_user': invite['from'],
                'workspace_id': invite['workspace_id'],
                'invite_id': invite['id'],
                'created_at': invite['invited_at'],
                'read': False
            })

        # Sort by created_at
        notifications.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return notifications
    except Exception as e:
        logger.error(f"Error getting notifications: {str(e)}")
        return []

def mark_notification_read(notification_id):
    """Mark a notification as read"""
    try:
        user_id = g.user['id']
        db.collection('users').document(user_id).collection('notifications').document(notification_id).update({
            'read': True,
            'read_at': datetime.now().isoformat()
        })
        return True
    except Exception as e:
        logger.error(f"Error marking notification as read: {str(e)}")
        return False