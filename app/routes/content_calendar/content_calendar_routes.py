from flask import render_template, request, jsonify, current_app, g
import traceback
from datetime import datetime
import uuid

from app.routes.content_calendar import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from app.scripts.content_calendar.calendar_manager import ContentCalendarManager

@bp.route('/content-calendar')
@auth_required
@require_permission('content_calendar')
def content_calendar():
    """Render the Content Calendar page"""
    return render_template('content_calendar/index.html')

@bp.route('/content-calendar/api/events', methods=['GET'])
@auth_required
@require_permission('content_calendar')
def get_events():
    """API endpoint to get all calendar events"""
    try:
        user_id = get_workspace_user_id()
        
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
@require_permission('content_calendar')
def create_event():
    """API endpoint to create a new calendar event"""
    try:
        user_id = get_workspace_user_id()
        
        # Get form data
        data = request.json
        
        # Validate required fields
        if not data.get('title'):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Determine content type
        content_type = data.get('content_type', 'organic')
        
        # Create the event with new fields
        event_id = calendar_manager.create_event(
            title=data.get('title'),
            publish_date=data.get('publish_date'),
            is_paid=content_type == 'deal',  # Deal = paid
            is_free=content_type == 'organic',  # Organic = free
            is_sponsored=content_type == 'deal',  # Deal = sponsored
            category=data.get('category', ''),
            audience_type=data.get('audience_type', 'Public'),
            content_type=content_type,  # Store the actual content type
            platform=data.get('platform', ''),
            description=data.get('description', ''),
            color=data.get('color', ''),
            content_link=data.get('content_link', ''),
            status=data.get('status', 'draft'),  # Default to draft
            comments=data.get('comments', []),
            notes=data.get('notes', '')
        )
        
        return jsonify({"success": True, "event_id": event_id})
    except Exception as e:
        current_app.logger.error(f"Error creating event: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@bp.route('/content-calendar/api/event/<event_id>', methods=['PUT'])
@auth_required
@require_permission('content_calendar')
def update_event(event_id):
    """API endpoint to update an existing calendar event"""
    try:
        user_id = get_workspace_user_id()
        
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
        
        # Handle content type
        if 'content_type' in data:
            content_type = data['content_type']
            update_data['content_type'] = content_type
            update_data['is_paid'] = content_type == 'deal'
            update_data['is_free'] = content_type == 'organic'
            update_data['is_sponsored'] = content_type == 'deal'
        else:
            # Legacy support for individual flags
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
        
        # If publish_date is being updated and event has Instagram or TikTok post, update Late.dev
        if 'publish_date' in data:
            event = calendar_manager.get_event(event_id)
            instagram_post_id = event.get('instagram_post_id') if event else None
            tiktok_post_id = event.get('tiktok_post_id') if event else None
            x_post_id = event.get('x_post_id') if event else None

            # Update Instagram post schedule
            if instagram_post_id:
                try:
                    import requests
                    import os
                    from datetime import datetime
                    from app.scripts.instagram_upload_studio.latedev_oauth_service import LateDevOAuthService

                    # Get Instagram account ID
                    account_id = LateDevOAuthService.get_account_id(user_id, 'instagram')
                    if not account_id:
                        current_app.logger.error("Instagram account not connected, cannot update post schedule")
                    else:
                        # Format the new publish date
                        new_publish_time = data['publish_date']
                        dt = datetime.fromisoformat(new_publish_time.replace('Z', '+00:00'))
                        formatted_time = dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')

                        headers = {
                            'Authorization': f'Bearer {os.environ.get("LATEDEV_API_KEY")}',
                            'Content-Type': 'application/json'
                        }

                        update_post_data = {
                            'scheduledFor': formatted_time,
                            'timezone': 'UTC',
                            'platforms': [{
                                'platform': 'instagram',
                                'accountId': account_id
                            }],
                            'isDraft': False  # Explicitly set to not draft
                        }

                        current_app.logger.info(f"Attempting to update Instagram post {instagram_post_id} schedule to {formatted_time}")
                        current_app.logger.info(f"Update payload: {update_post_data}")

                        response = requests.put(
                            f"https://getlate.dev/api/v1/posts/{instagram_post_id}",
                            headers=headers,
                            json=update_post_data,
                            timeout=30
                        )

                        if response.status_code in [200, 201]:
                            result = response.json()
                            status = result.get('post', {}).get('status', 'unknown')
                            current_app.logger.info(f"Updated Instagram post {instagram_post_id} schedule to {formatted_time}, status: {status}")
                            current_app.logger.info(f"Response: {response.text}")
                        else:
                            current_app.logger.error(f"Failed to update Instagram post schedule: {response.status_code}")
                            current_app.logger.error(f"Response body: {response.text}")
                except Exception as e:
                    current_app.logger.error(f"Error updating Instagram post schedule: {e}")
                    # Continue with calendar update even if Instagram update fails

            # Update TikTok post schedule
            if tiktok_post_id:
                try:
                    import requests
                    import os
                    from datetime import datetime
                    from app.scripts.instagram_upload_studio.latedev_oauth_service import LateDevOAuthService

                    # Get TikTok account ID
                    account_id = LateDevOAuthService.get_account_id(user_id, 'tiktok')
                    if not account_id:
                        current_app.logger.error("TikTok account not connected, cannot update post schedule")
                    else:
                        # Format the new publish date
                        new_publish_time = data['publish_date']
                        dt = datetime.fromisoformat(new_publish_time.replace('Z', '+00:00'))
                        formatted_time = dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')

                        headers = {
                            'Authorization': f'Bearer {os.environ.get("LATEDEV_API_KEY")}',
                            'Content-Type': 'application/json'
                        }

                        update_post_data = {
                            'scheduledFor': formatted_time,
                            'timezone': 'UTC',
                            'platforms': [{
                                'platform': 'tiktok',
                                'accountId': account_id
                            }],
                            'isDraft': False  # Explicitly set to not draft
                        }

                        current_app.logger.info(f"Attempting to update TikTok post {tiktok_post_id} schedule to {formatted_time}")
                        current_app.logger.info(f"Update payload: {update_post_data}")

                        response = requests.put(
                            f"https://getlate.dev/api/v1/posts/{tiktok_post_id}",
                            headers=headers,
                            json=update_post_data,
                            timeout=30
                        )

                        if response.status_code in [200, 201]:
                            result = response.json()
                            status = result.get('post', {}).get('status', 'unknown')
                            current_app.logger.info(f"Updated TikTok post {tiktok_post_id} schedule to {formatted_time}, status: {status}")
                            current_app.logger.info(f"Response: {response.text}")
                        else:
                            current_app.logger.error(f"Failed to update TikTok post schedule: {response.status_code}")
                            current_app.logger.error(f"Response body: {response.text}")
                except Exception as e:
                    current_app.logger.error(f"Error updating TikTok post schedule: {e}")
                    # Continue with calendar update even if TikTok update fails

            # Update X post schedule
            if x_post_id:
                try:
                    import requests
                    import os
                    from datetime import datetime
                    from app.scripts.instagram_upload_studio.latedev_oauth_service import LateDevOAuthService

                    # Get X account ID
                    account_id = LateDevOAuthService.get_account_id(user_id, 'x')
                    if not account_id:
                        current_app.logger.error("X account not connected, cannot update post schedule")
                    else:
                        # Format the new publish date
                        new_publish_time = data['publish_date']
                        dt = datetime.fromisoformat(new_publish_time.replace('Z', '+00:00'))
                        formatted_time = dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')

                        headers = {
                            'Authorization': f'Bearer {os.environ.get("LATEDEV_API_KEY")}',
                            'Content-Type': 'application/json'
                        }

                        update_post_data = {
                            'scheduledFor': formatted_time,
                            'timezone': 'UTC',
                            'platforms': [{
                                'platform': 'twitter',
                                'accountId': account_id
                            }],
                            'isDraft': False
                        }

                        current_app.logger.info(f"Attempting to update X post {x_post_id} schedule to {formatted_time}")
                        current_app.logger.info(f"Update payload: {update_post_data}")

                        response = requests.put(
                            f"https://getlate.dev/api/v1/posts/{x_post_id}",
                            headers=headers,
                            json=update_post_data,
                            timeout=30
                        )

                        if response.status_code in [200, 201]:
                            result = response.json()
                            status = result.get('post', {}).get('status', 'unknown')
                            current_app.logger.info(f"Updated X post {x_post_id} schedule to {formatted_time}, status: {status}")
                            current_app.logger.info(f"Response: {response.text}")
                        else:
                            current_app.logger.error(f"Failed to update X post schedule: {response.status_code}")
                            current_app.logger.error(f"Response body: {response.text}")
                except Exception as e:
                    current_app.logger.error(f"Error updating X post schedule: {e}")
                    # Continue with calendar update even if X update fails

            # Update YouTube video schedule
            youtube_video_id = event.get('youtube_video_id') if event else None
            if youtube_video_id:
                try:
                    from datetime import datetime
                    from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
                    from googleapiclient.discovery import build

                    # Initialize YouTube API
                    analytics = YouTubeAnalytics(user_id)
                    if not analytics.credentials:
                        current_app.logger.error("YouTube credentials not found, cannot update video schedule")
                    else:
                        youtube = build('youtube', 'v3', credentials=analytics.credentials)

                        # Format the new publish date (convert from ISO string to YouTube format)
                        new_publish_time = data['publish_date']
                        dt = datetime.fromisoformat(new_publish_time.replace('Z', '+00:00'))
                        formatted_time = dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')

                        current_app.logger.info(f"Attempting to update YouTube video {youtube_video_id} schedule to {formatted_time}")

                        # Update video publish time using YouTube API
                        youtube.videos().update(
                            part='status',
                            body={
                                'id': youtube_video_id,
                                'status': {
                                    'privacyStatus': 'private',
                                    'publishAt': formatted_time,
                                    'selfDeclaredMadeForKids': False
                                }
                            }
                        ).execute()

                        current_app.logger.info(f"Updated YouTube video {youtube_video_id} schedule to {formatted_time}")

                except Exception as e:
                    current_app.logger.error(f"Error updating YouTube video schedule: {e}")
                    # Continue with calendar update even if YouTube update fails

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
@require_permission('content_calendar')
def delete_event(event_id):
    """API endpoint to delete a calendar event"""
    try:
        user_id = get_workspace_user_id()

        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)

        # Get event details before deleting to check for YouTube video
        event = calendar_manager.get_event(event_id)

        if not event:
            return jsonify({"error": "Event not found"}), 404

        # If this event has a YouTube video, delete it from YouTube
        youtube_video_id = event.get('youtube_video_id')
        if youtube_video_id:
            try:
                from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
                yt_analytics = YouTubeAnalytics(user_id)

                if yt_analytics.credentials:
                    from googleapiclient.discovery import build
                    youtube = build('youtube', 'v3', credentials=yt_analytics.credentials)

                    # Delete the video from YouTube
                    youtube.videos().delete(id=youtube_video_id).execute()
                    current_app.logger.info(f"Deleted YouTube video {youtube_video_id}")
            except Exception as e:
                current_app.logger.error(f"Error deleting YouTube video {youtube_video_id}: {e}")
                # Continue with calendar event deletion even if YouTube deletion fails

        # If this event has an Instagram post, delete it from Late.dev
        instagram_post_id = event.get('instagram_post_id')
        if instagram_post_id:
            try:
                import requests
                import os

                headers = {
                    'Authorization': f'Bearer {os.environ.get("LATEDEV_API_KEY")}',
                    'Content-Type': 'application/json'
                }

                response = requests.delete(
                    f"https://getlate.dev/api/v1/posts/{instagram_post_id}",
                    headers=headers,
                    timeout=30
                )

                if response.status_code in [200, 201, 204]:
                    current_app.logger.info(f"Deleted Instagram post {instagram_post_id}")
                else:
                    current_app.logger.error(f"Failed to delete Instagram post {instagram_post_id}: {response.status_code}")
            except Exception as e:
                current_app.logger.error(f"Error deleting Instagram post {instagram_post_id}: {e}")
                # Continue with calendar event deletion even if Instagram deletion fails

        # If this event has a TikTok post, delete it from Late.dev
        tiktok_post_id = event.get('tiktok_post_id')
        if tiktok_post_id:
            try:
                import requests
                import os

                headers = {
                    'Authorization': f'Bearer {os.environ.get("LATEDEV_API_KEY")}',
                    'Content-Type': 'application/json'
                }

                response = requests.delete(
                    f"https://getlate.dev/api/v1/posts/{tiktok_post_id}",
                    headers=headers,
                    timeout=30
                )

                if response.status_code in [200, 201, 204]:
                    current_app.logger.info(f"Deleted TikTok post {tiktok_post_id}")
                else:
                    current_app.logger.error(f"Failed to delete TikTok post {tiktok_post_id}: {response.status_code}")
            except Exception as e:
                current_app.logger.error(f"Error deleting TikTok post {tiktok_post_id}: {e}")
                # Continue with calendar event deletion even if TikTok deletion fails

        # If this event has an X post, delete it from Late.dev and clear draft scheduled status
        x_post_id = event.get('x_post_id')
        if x_post_id:
            try:
                import requests
                import os
                from firebase_admin import firestore

                headers = {
                    'Authorization': f'Bearer {os.environ.get("LATEDEV_API_KEY")}',
                    'Content-Type': 'application/json'
                }

                response = requests.delete(
                    f"https://getlate.dev/api/v1/posts/{x_post_id}",
                    headers=headers,
                    timeout=30
                )

                if response.status_code in [200, 201, 204]:
                    current_app.logger.info(f"Deleted X post {x_post_id}")

                    # Find and clear the draft's scheduled status
                    # Get draft ID from event notes
                    notes = event.get('notes', '')
                    draft_id = None
                    if 'Draft ID:' in notes:
                        draft_id = notes.split('Draft ID:')[1].strip().split('\n')[0].strip()

                    if draft_id:
                        try:
                            db = firestore.client()
                            draft_ref = db.collection('users').document(str(user_id)).collection('post_drafts').document(draft_id)
                            draft_ref.update({
                                'is_scheduled': False,
                                'late_dev_post_id': firestore.DELETE_FIELD,
                                'scheduled_time': firestore.DELETE_FIELD,
                                'calendar_event_id': firestore.DELETE_FIELD,
                                'updated_at': firestore.SERVER_TIMESTAMP
                            })
                            current_app.logger.info(f"✅ Cleared scheduled status from draft {draft_id}")
                        except Exception as draft_error:
                            current_app.logger.error(f"Error clearing draft scheduled status: {draft_error}")
                else:
                    current_app.logger.error(f"Failed to delete X post {x_post_id}: {response.status_code}")
            except Exception as e:
                current_app.logger.error(f"Error deleting X post {x_post_id}: {e}")
                # Continue with calendar event deletion even if X deletion fails

        # Delete the calendar event
        success = calendar_manager.delete_event(event_id)

        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to delete event"}), 500
    except Exception as e:
        current_app.logger.error(f"Error deleting event: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@bp.route('/content-calendar/api/event/<event_id>', methods=['GET'])
@auth_required
@require_permission('content_calendar')
def get_event(event_id):
    """API endpoint to get a specific event"""
    try:
        user_id = get_workspace_user_id()
        
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
@require_permission('content_calendar')
def add_comment(event_id):
    """API endpoint to add a comment to an event"""
    try:
        user_id = get_workspace_user_id()
        
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
@require_permission('content_calendar')
def update_event_status(event_id):
    """API endpoint to update event status"""
    try:
        user_id = get_workspace_user_id()
        
        # Get form data
        data = request.json
        
        # Validate required fields
        if not data.get('status'):
            return jsonify({"error": "Status is required"}), 400
        
        # Validate status value (now includes 'ready' instead of 'done')
        valid_statuses = ['draft', 'in-progress', 'review', 'ready']
        if data['status'] not in valid_statuses:
            return jsonify({"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400
        
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Update event status
        success = calendar_manager.update_event_status(event_id, data['status'])
        
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Event not found"}), 404
    except Exception as e:
        current_app.logger.error(f"Error updating event status: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@bp.route('/content-calendar/api/event/<event_id>/notes', methods=['PUT'])
@auth_required
@require_permission('content_calendar')
def update_event_notes(event_id):
    """API endpoint to update event notes"""
    try:
        user_id = get_workspace_user_id()
        
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
@require_permission('content_calendar')
def get_events_by_status(status):
    """API endpoint to get events by status"""
    try:
        user_id = get_workspace_user_id()
        
        # Validate status value
        valid_statuses = ['draft', 'in-progress', 'review', 'ready']
        if status not in valid_statuses:
            return jsonify({"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400
        
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
@require_permission('content_calendar')
def get_events_by_date_range():
    """API endpoint to get events within a date range"""
    try:
        user_id = get_workspace_user_id()
        
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

@bp.route('/content-calendar/api/analytics/<period>', methods=['GET'])
@auth_required
@require_permission('content_calendar')
def get_analytics(period):
    """API endpoint to get analytics for a specific period"""
    try:
        user_id = get_workspace_user_id()
        
        # Get query parameters for month/year if needed
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int)
        
        # Initialize calendar manager
        calendar_manager = ContentCalendarManager(user_id)
        
        # Get all events
        all_events = calendar_manager.get_all_events()
        
        # Calculate analytics based on period
        if period == 'month' and month and year:
            # Filter events for specific month
            from datetime import date
            import calendar as cal
            
            month_start = date(year, month, 1)
            month_end = date(year, month, cal.monthrange(year, month)[1])
            
            events = [e for e in all_events if e.get('publish_date')]
            month_events = []
            
            for event in events:
                try:
                    event_date = datetime.fromisoformat(event['publish_date'].replace('Z', '+00:00')).date()
                    if month_start <= event_date <= month_end:
                        month_events.append(event)
                except:
                    continue
            
            # Calculate statistics
            total_posts = len(month_events)
            organic_posts = len([e for e in month_events if e.get('content_type') != 'deal'])
            deal_posts = len([e for e in month_events if e.get('content_type') == 'deal'])
            scheduled_posts = len([e for e in month_events if e.get('publish_date')])
            draft_posts = len([e for e in month_events if e.get('status') == 'draft'])
            progress_posts = len([e for e in month_events if e.get('status') == 'in-progress'])
            review_posts = len([e for e in month_events if e.get('status') == 'review'])
            ready_posts = len([e for e in month_events if e.get('status') == 'ready'])
            
            analytics = {
                'total_posts': total_posts,
                'organic_posts': organic_posts,
                'deal_posts': deal_posts,
                'organic_percentage': round((organic_posts / total_posts * 100) if total_posts > 0 else 0, 1),
                'deal_percentage': round((deal_posts / total_posts * 100) if total_posts > 0 else 0, 1),
                'scheduled_posts': scheduled_posts,
                'draft_posts': draft_posts,
                'progress_posts': progress_posts,
                'review_posts': review_posts,
                'ready_posts': ready_posts,
                'by_platform': {}
            }
            
            # Count by platform
            for event in month_events:
                platform = event.get('platform', 'Other')
                analytics['by_platform'][platform] = analytics['by_platform'].get(platform, 0) + 1
            
            return jsonify(analytics)
        else:
            return jsonify({"error": "Invalid period or missing parameters"}), 400
            
    except Exception as e:
        current_app.logger.error(f"Error getting analytics: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500