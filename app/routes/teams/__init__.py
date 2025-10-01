from flask import Blueprint, render_template, request, jsonify, g, redirect, url_for, current_app
from app.system.auth.middleware import auth_required
from app.system.auth.supabase import get_supabase_config
from app.system.services.firebase_service import db
from datetime import datetime
import uuid
import requests
import logging
from .notifications import get_pending_invitations, get_notifications, mark_notification_read

logger = logging.getLogger('teams')

teams_bp = Blueprint('teams', __name__, url_prefix='/teams')

@teams_bp.route('/')
@auth_required
def teams_dashboard():
    """Main teams dashboard"""
    # Get pending invitations for this user
    pending_invitations = get_pending_invitations()
    return render_template('teams/dashboard.html', pending_invitations=pending_invitations)


@teams_bp.route('/api/workspace')
@auth_required
def get_workspace():
    """Get current workspace data"""
    try:
        user_id = g.user['id']

        # Get workspaces user has access to
        workspaces = []

        # Get user's own workspace
        user_doc = db.collection('users').document(user_id).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            workspaces.append({
                'id': user_id,
                'name': user_data.get('name', user_data.get('email', 'My Workspace')),
                'role': 'owner',
                'is_owner': True,
                'is_active': g.get('active_workspace_id', user_id) == user_id
            })

        # Get workspaces where user is a team member
        team_memberships = db.collection('team_members') \
            .where('member_id', '==', user_id) \
            .where('status', '==', 'active') \
            .get()

        for membership in team_memberships:
            member_data = membership.to_dict()
            owner_doc = db.collection('users').document(member_data['owner_id']).get()
            if owner_doc.exists:
                owner_data = owner_doc.to_dict()
                workspaces.append({
                    'id': member_data['owner_id'],
                    'name': owner_data.get('name', owner_data.get('email', 'Team Workspace')),
                    'role': member_data.get('role', 'member'),
                    'is_owner': False,
                    'is_active': g.get('active_workspace_id', user_id) == member_data['owner_id'],
                    'permissions': member_data.get('permissions', {})
                })

        return jsonify({
            'success': True,
            'workspaces': workspaces,
            'active_workspace_id': g.get('active_workspace_id', user_id)
        })
    except Exception as e:
        logger.error(f"Error getting workspace: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@teams_bp.route('/api/switch-workspace', methods=['POST'])
@auth_required
def switch_workspace():
    """Switch to a different workspace"""
    try:
        data = request.json
        workspace_id = data.get('workspace_id')
        user_id = g.user['id']

        # Verify user has access to this workspace
        has_access = workspace_id == user_id  # Own workspace

        if not has_access:
            # Check if user is a team member
            membership = db.collection('team_members') \
                .where('member_id', '==', user_id) \
                .where('owner_id', '==', workspace_id) \
                .where('status', '==', 'active') \
                .limit(1).get()

            has_access = len(list(membership)) > 0

        if not has_access:
            return jsonify({'success': False, 'error': 'Access denied to this workspace'}), 403

        # Create response and set cookie for active workspace
        from flask import make_response
        response = make_response(jsonify({
            'success': True,
            'message': 'Workspace switched successfully',
            'workspace_id': workspace_id
        }))

        # Set cookie to remember active workspace
        response.set_cookie(
            'active_workspace_id',
            workspace_id,
            max_age=60*60*24*30,  # 30 days
            httponly=True,
            secure=True,
            samesite='Lax'
        )

        return response
    except Exception as e:
        logger.error(f"Error switching workspace: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@teams_bp.route('/api/members')
@auth_required
def get_team_members():
    """Get list of team members for current workspace"""
    try:
        workspace_id = g.get('active_workspace_id', g.user['id'])

        # Check if user has permission to view team members
        if workspace_id != g.user['id']:
            # Check permissions if not owner
            membership = db.collection('team_members') \
                .where('member_id', '==', g.user['id']) \
                .where('owner_id', '==', workspace_id) \
                .where('status', '==', 'active') \
                .limit(1).get()

            if not membership:
                return jsonify({'success': False, 'error': 'Access denied'}), 403

        # Get team members - only show pending and active, not removed
        members_ref = db.collection('team_members') \
            .where('owner_id', '==', workspace_id) \
            .get()

        members = []
        for member in members_ref:
            member_data = member.to_dict()
            # Skip removed members
            if member_data.get('status') == 'removed':
                continue

            members.append({
                'id': member.id,
                'email': member_data.get('email'),
                'name': member_data.get('name'),
                'role': member_data.get('role', 'member'),
                'status': member_data.get('status'),
                'permissions': member_data.get('permissions', {}),
                'invited_at': member_data.get('invited_at'),
                'accepted_at': member_data.get('accepted_at')
            })

        return jsonify({
            'success': True,
            'members': members
        })
    except Exception as e:
        logger.error(f"Error getting team members: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@teams_bp.route('/api/invite', methods=['POST'])
@auth_required
def invite_team_member():
    """Send invitation to a new team member"""
    try:
        data = request.json
        email = data.get('email')
        permissions = data.get('permissions', {})

        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400

        workspace_id = g.get('active_workspace_id', g.user['id'])

        # Only workspace owner can invite
        if workspace_id != g.user['id']:
            return jsonify({'success': False, 'error': 'Only workspace owner can invite members'}), 403

        # Check if member already exists (but ignore removed members)
        existing = db.collection('team_members') \
            .where('owner_id', '==', workspace_id) \
            .where('email', '==', email) \
            .get()

        # Check if there's an active or pending invitation
        for doc in existing:
            member_data = doc.to_dict()
            if member_data.get('status') in ['pending', 'active']:
                return jsonify({'success': False, 'error': 'Member already invited or active'}), 400
            elif member_data.get('status') == 'removed':
                # Delete the old removed record so we can create a fresh invitation
                doc.reference.delete()

        # Create invitation record
        invite_id = str(uuid.uuid4())
        invite_data = {
            'owner_id': workspace_id,
            'email': email,
            'permissions': permissions,
            'status': 'pending',
            'invite_token': invite_id,
            'invited_at': datetime.now().isoformat(),
            'invited_by': g.user['id']
        }

        # Save to Firestore
        db.collection('team_members').document(invite_id).set(invite_data)

        # Check if user exists and handle accordingly
        config = get_supabase_config()
        user_exists = False
        user_id = None
        invite_sent = False  # Initialize here to avoid the error

        if config['url'] and config['service_key']:
            # Check if user exists in Supabase
            url = f"{config['url']}/auth/v1/admin/users"

            try:
                response = requests.get(
                    url,
                    headers={
                        'Authorization': f"Bearer {config['service_key']}",
                        'apikey': config['service_key']
                    }
                )

                logger.debug(f"User check response status: {response.status_code}")

                if response.status_code == 200:
                    all_users = response.json().get('users', [])

                    # Filter users by email manually since the API might not filter correctly
                    matching_users = [u for u in all_users if u.get('email', '').lower() == email.lower()]

                    if matching_users:
                        # User exists - store their ID for notification
                        user_exists = True
                        user_id = matching_users[0].get('id')
                        logger.info(f"User {email} already exists with ID {user_id}")

                        # Update the invitation with the user_id for easier acceptance
                        db.collection('team_members').document(invite_id).update({
                            'member_id': user_id,
                            'user_exists': True
                        })

                        # Create a notification for the existing user
                        db.collection('users').document(user_id).collection('notifications').add({
                            'type': 'team_invitation',
                            'from_user': g.user.get('data', {}).get('email', 'A workspace owner'),
                            'workspace_id': workspace_id,
                            'invite_id': invite_id,
                            'message': f"You've been invited to join a team workspace",
                            'created_at': datetime.now().isoformat(),
                            'read': False
                        })

                        # For existing users, we'll just notify them in-app
                        logger.info(f"User {email} already exists - created in-app notification")
                    else:
                        logger.info(f"User {email} does not exist in Supabase")
                else:
                    logger.error(f"Failed to check user existence: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"Error checking user existence: {str(e)}")

        # Handle non-existing users
        if not user_exists:
            # User doesn't exist - send proper Supabase invitation
            invite_error = None

            logger.info(f"User {email} doesn't exist. Attempting to send Supabase invitation...")

            try:
                # Use the /auth/v1/invite endpoint
                invite_url = f"{config['url']}/auth/v1/invite"
                logger.debug(f"Sending invite request to: {invite_url}")

                # Send the invitation
                invite_response = requests.post(
                    invite_url,
                    headers={
                        'Authorization': f"Bearer {config['service_key']}",
                        'apikey': config['service_key'],
                        'Content-Type': 'application/json'
                    },
                    json={
                        'email': email,
                        'data': {  # This data will be included in the user's raw_user_meta_data
                            'invite_token': invite_id,
                            'workspace_id': workspace_id,
                            'invited_by': g.user.get('data', {}).get('email', 'workspace owner')
                        }
                    }
                )

                logger.debug(f"Supabase invite response status: {invite_response.status_code}")

                if invite_response.status_code in [200, 201]:
                    response_data = invite_response.json()
                    logger.info(f"Created Supabase user for {email}. User ID: {response_data.get('id')}")

                    # Update our stored invitation with the Supabase user ID
                    db.collection('team_members').document(invite_id).update({
                        'supabase_user_id': response_data.get('id')
                    })

                    # Supabase should send the email automatically
                    invite_sent = bool(response_data.get('confirmation_sent_at'))
                    if invite_sent:
                        logger.info(f"Supabase sent invitation email to {email}")
                    else:
                        logger.warning(f"Supabase user created but email may be delayed for {email}")
                else:
                    invite_error = invite_response.text
                    logger.error(f"Failed to send Supabase invite to {email}. Status: {invite_response.status_code}. Error: {invite_response.text}")

                    # Try to parse error for more details
                    try:
                        error_data = invite_response.json()
                        if 'message' in error_data:
                            logger.error(f"Error message: {error_data['message']}")
                    except:
                        pass
            except Exception as e:
                invite_error = str(e)
                logger.error(f"Exception sending Supabase invite to {email}: {str(e)}", exc_info=True)

        # Set email_sent based on whether Supabase handled it
        email_sent = invite_sent if not user_exists else False

        # Simple message
        if user_exists:
            message = f'User {email} already exists - they have been notified in-app'
        else:
            if invite_sent:
                message = f'Invitation sent to {email}. They will receive an email to set their password.'
            else:
                message = f'User created for {email} but email may be delayed. They can use password reset to access their account.'

        return jsonify({
            'success': True,
            'message': message,
            'invite_id': invite_id,
            'user_exists': user_exists,
            'email_sent': email_sent
        })
    except Exception as e:
        logger.error(f"Error inviting team member: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@teams_bp.route('/api/accept-invite', methods=['POST'])
@auth_required
def accept_invite():
    """Accept a team invitation"""
    try:
        data = request.json
        invite_token = data.get('invite_token')

        if not invite_token:
            return jsonify({'success': False, 'error': 'Invite token required'}), 400

        # Get invitation
        invite_doc = db.collection('team_members').document(invite_token).get()

        if not invite_doc.exists:
            return jsonify({'success': False, 'error': 'Invalid invitation'}), 404

        invite_data = invite_doc.to_dict()
        user_email = g.user.get('data', {}).get('email', '')
        user_id = g.user['id']

        # Check if invitation is for this user (by email or member_id)
        if (invite_data.get('email') != user_email and
            invite_data.get('member_id') != user_id):
            return jsonify({'success': False, 'error': 'This invitation is not for you'}), 403

        # Update invitation status
        db.collection('team_members').document(invite_token).update({
            'status': 'active',
            'member_id': user_id,
            'accepted_at': datetime.now().isoformat()
        })

        # Clear any notifications about this invite
        try:
            notifications = db.collection('users').document(user_id).collection('notifications') \
                .where('invite_id', '==', invite_token).get()
            for notif in notifications:
                notif.reference.update({'read': True})
        except Exception as notif_error:
            logger.warning(f"Could not clear notifications: {notif_error}")

        return jsonify({
            'success': True,
            'message': 'Invitation accepted successfully'
        })
    except Exception as e:
        logger.error(f"Error accepting invite: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@teams_bp.route('/api/update-permissions', methods=['POST'])
@auth_required
def update_member_permissions():
    """Update team member permissions"""
    try:
        data = request.json
        member_id = data.get('member_id')
        permissions = data.get('permissions', {})

        workspace_id = g.get('active_workspace_id', g.user['id'])

        # Only workspace owner can update permissions
        if workspace_id != g.user['id']:
            return jsonify({'success': False, 'error': 'Only workspace owner can update permissions'}), 403

        # Update permissions
        db.collection('team_members').document(member_id).update({
            'permissions': permissions,
            'updated_at': datetime.now().isoformat()
        })

        return jsonify({
            'success': True,
            'message': 'Permissions updated successfully'
        })
    except Exception as e:
        logger.error(f"Error updating permissions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@teams_bp.route('/api/remove-member', methods=['POST'])
@auth_required
def remove_team_member():
    """Remove a team member"""
    try:
        data = request.json
        member_id = data.get('member_id')
        permanent = data.get('permanent', False)  # Option to permanently delete

        workspace_id = g.get('active_workspace_id', g.user['id'])

        # Only workspace owner can remove members
        if workspace_id != g.user['id']:
            return jsonify({'success': False, 'error': 'Only workspace owner can remove members'}), 403

        if permanent:
            # Permanently delete the member record
            db.collection('team_members').document(member_id).delete()
            message = 'Member permanently deleted'
        else:
            # Soft delete - just update status
            db.collection('team_members').document(member_id).update({
                'status': 'removed',
                'removed_at': datetime.now().isoformat(),
                'removed_by': g.user['id']
            })
            message = 'Member removed successfully'

        return jsonify({
            'success': True,
            'message': message
        })
    except Exception as e:
        logger.error(f"Error removing member: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@teams_bp.route('/api/pending-invitations')
@auth_required
def get_pending_invites():
    """Get pending invitations for current user"""
    try:
        invitations = get_pending_invitations()
        return jsonify({
            'success': True,
            'invitations': invitations
        })
    except Exception as e:
        logger.error(f"Error getting pending invitations: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@teams_bp.route('/api/notifications')
@auth_required
def get_team_notifications():
    """Get notifications including team invitations"""
    try:
        notifications = get_notifications()
        return jsonify({
            'success': True,
            'notifications': notifications
        })
    except Exception as e:
        logger.error(f"Error getting notifications: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@teams_bp.route('/api/decline-invite', methods=['POST'])
@auth_required
def decline_invite():
    """Decline a team invitation"""
    try:
        data = request.json
        invite_token = data.get('invite_token')

        if not invite_token:
            return jsonify({'success': False, 'error': 'Invite token required'}), 400

        # Get invitation
        invite_doc = db.collection('team_members').document(invite_token).get()

        if not invite_doc.exists:
            return jsonify({'success': False, 'error': 'Invalid invitation'}), 404

        invite_data = invite_doc.to_dict()
        user_email = g.user.get('data', {}).get('email', '')
        user_id = g.user['id']

        # Check if invitation is for this user
        if (invite_data.get('email') != user_email and
            invite_data.get('member_id') != user_id):
            return jsonify({'success': False, 'error': 'This invitation is not for you'}), 403

        # Update invitation status
        db.collection('team_members').document(invite_token).update({
            'status': 'declined',
            'declined_at': datetime.now().isoformat()
        })

        # Clear any notifications
        try:
            notifications = db.collection('users').document(user_id).collection('notifications') \
                .where('invite_id', '==', invite_token).get()
            for notif in notifications:
                notif.reference.delete()
        except Exception as notif_error:
            logger.warning(f"Could not clear notifications: {notif_error}")

        return jsonify({
            'success': True,
            'message': 'Invitation declined'
        })
    except Exception as e:
        logger.error(f"Error declining invite: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500