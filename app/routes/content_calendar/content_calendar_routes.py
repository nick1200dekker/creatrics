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
            tags=data.get('tags', ''),
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

        current_app.logger.info(f"📥 UPDATE EVENT {event_id} - Received data:")
        current_app.logger.info(f"  - publish_date: {data.get('publish_date')}")
        current_app.logger.info(f"  - timezone: {data.get('timezone')}")
        current_app.logger.info(f"  - platform: {data.get('platform')}")
        
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
        if 'tags' in data:
            update_data['tags'] = data['tags']

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

                        # Get timezone from request, otherwise from event, otherwise UTC
                        timezone = data.get('timezone') or (event.get('timezone') if event else None) or 'UTC'

                        headers = {
                            'Authorization': f'Bearer {os.environ.get("LATEDEV_API_KEY")}',
                            'Content-Type': 'application/json'
                        }

                        update_post_data = {
                            'scheduledFor': formatted_time,
                            'timezone': timezone,
                            'platforms': [{
                                'platform': 'instagram',
                                'accountId': account_id
                            }],
                            'isDraft': False  # Explicitly set to not draft
                        }

                        current_app.logger.info(f"Instagram timezone: {timezone} (from request: {data.get('timezone')}, from event: {event.get('timezone') if event else None})")

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

                        # Get timezone from request, otherwise from event, otherwise UTC
                        timezone = data.get('timezone') or (event.get('timezone') if event else None) or 'UTC'

                        headers = {
                            'Authorization': f'Bearer {os.environ.get("LATEDEV_API_KEY")}',
                            'Content-Type': 'application/json'
                        }

                        update_post_data = {
                            'scheduledFor': formatted_time,
                            'timezone': timezone,
                            'platforms': [{
                                'platform': 'tiktok',
                                'accountId': account_id
                            }],
                            'isDraft': False  # Explicitly set to not draft
                        }

                        current_app.logger.info(f"TikTok timezone: {timezone} (from request: {data.get('timezone')}, from event: {event.get('timezone') if event else None})")
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

                        # Get timezone from request, otherwise from event, otherwise UTC
                        timezone = data.get('timezone') or (event.get('timezone') if event else None) or 'UTC'

                        headers = {
                            'Authorization': f'Bearer {os.environ.get("LATEDEV_API_KEY")}',
                            'Content-Type': 'application/json'
                        }

                        update_post_data = {
                            'scheduledFor': formatted_time,
                            'timezone': timezone,
                            'platforms': [{
                                'platform': 'twitter',
                                'accountId': account_id
                            }],
                            'isDraft': False
                        }

                        current_app.logger.info(f"X timezone: {timezone} (from request: {data.get('timezone')}, from event: {event.get('timezone') if event else None})")
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

            # Update YouTube post schedule via Late.dev
            youtube_video_id = event.get('youtube_video_id') if event else None
            if youtube_video_id:
                try:
                    import requests
                    import os
                    from datetime import datetime
                    from app.scripts.instagram_upload_studio.latedev_oauth_service import LateDevOAuthService

                    # Get YouTube account ID
                    account_id = LateDevOAuthService.get_account_id(user_id, 'youtube')
                    if not account_id:
                        current_app.logger.error("YouTube account not connected, cannot update post schedule")
                    else:
                        # Format the new publish date
                        new_publish_time = data['publish_date']
                        dt = datetime.fromisoformat(new_publish_time.replace('Z', '+00:00'))
                        formatted_time = dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')

                        # Get timezone from request, otherwise from event, otherwise UTC
                        timezone = data.get('timezone') or (event.get('timezone') if event else None) or 'UTC'

                        headers = {
                            'Authorization': f'Bearer {os.environ.get("LATEDEV_API_KEY")}',
                            'Content-Type': 'application/json'
                        }

                        update_post_data = {
                            'scheduledFor': formatted_time,
                            'timezone': timezone,
                            'platforms': [{
                                'platform': 'youtube',
                                'accountId': account_id
                            }],
                            'isDraft': False
                        }

                        current_app.logger.info(f"YouTube timezone: {timezone} (from request: {data.get('timezone')}, from event: {event.get('timezone') if event else None})")
                        current_app.logger.info(f"Attempting to update YouTube post {youtube_video_id} schedule to {formatted_time}")
                        current_app.logger.info(f"Update payload: {update_post_data}")

                        response = requests.put(
                            f"https://getlate.dev/api/v1/posts/{youtube_video_id}",
                            headers=headers,
                            json=update_post_data,
                            timeout=30
                        )

                        if response.status_code in [200, 201]:
                            result = response.json()
                            status = result.get('post', {}).get('status', 'unknown')
                            current_app.logger.info(f"Updated YouTube post {youtube_video_id} schedule to {formatted_time}, status: {status}")
                            current_app.logger.info(f"Response: {response.text}")
                        else:
                            current_app.logger.error(f"Failed to update YouTube post schedule: {response.status_code}")
                            current_app.logger.error(f"Response body: {response.text}")

                except Exception as e:
                    current_app.logger.error(f"Error updating YouTube post schedule: {e}")
                    # Continue with calendar update even if YouTube update fails

            # Update content library when rescheduling
            if event:
                content_id = event.get('content_id')
                platform = event.get('platform', '').lower()

                # Normalize platform names (Twitter/X can be stored as either 'x' or 'twitter')
                platform_mapping = {
                    'twitter': 'x',
                    'x': 'x',
                    'youtube': 'youtube',
                    'tiktok': 'tiktok',
                    'instagram': 'instagram'
                }
                platform = platform_mapping.get(platform, platform)

                current_app.logger.info(f"Reschedule check - content_id: {content_id}, platform: {platform}")

                if content_id and platform:
                    try:
                        from app.system.services.content_library_service import ContentLibraryManager

                        # Get current content
                        content = ContentLibraryManager.get_content_by_id(user_id, content_id)

                        if content:
                            current_app.logger.info(f"Found content in library. Platforms: {list(content.get('platforms_posted', {}).keys())}")
                        else:
                            current_app.logger.warning(f"Content {content_id} not found in library")

                        if content and platform in content.get('platforms_posted', {}):
                            # Update the platform's scheduled_for time and last_action_at
                            platform_data = content['platforms_posted'][platform].copy()
                            platform_data['scheduled_for'] = data['publish_date']

                            ContentLibraryManager.update_platform_status(
                                user_id=user_id,
                                content_id=content_id,
                                platform=platform,
                                platform_data=platform_data
                            )
                            current_app.logger.info(f"✅ Updated content library {content_id} {platform} scheduled_for to {data['publish_date']}")
                        else:
                            current_app.logger.warning(f"Platform {platform} not found in content library for {content_id}")

                    except Exception as e:
                        current_app.logger.error(f"Error updating content library on reschedule: {e}")
                else:
                    current_app.logger.info(f"Skipping content library update - missing content_id or platform")

        # Update content (title/description/tags/caption) in Late.dev if description or tags changed
        if 'description' in data or 'tags' in data or 'title' in data:
            event = calendar_manager.get_event(event_id)
            if event:
                instagram_post_id = event.get('instagram_post_id')
                tiktok_post_id = event.get('tiktok_post_id')
                x_post_id = event.get('x_post_id')
                youtube_video_id = event.get('youtube_video_id')

                # Update Instagram caption
                if instagram_post_id:
                    try:
                        import requests
                        import os
                        from app.scripts.instagram_upload_studio.latedev_oauth_service import LateDevOAuthService

                        account_id = LateDevOAuthService.get_account_id(user_id, 'instagram')
                        if account_id:
                            # Extract caption from description (format: "Caption: <caption text>")
                            description = data.get('description', event.get('description', ''))
                            caption = description.replace('Caption: ', '') if description.startswith('Caption: ') else description

                            headers = {
                                'Authorization': f'Bearer {os.environ.get("LATEDEV_API_KEY")}',
                                'Content-Type': 'application/json'
                            }

                            # Use user's timezone if provided, otherwise default to event's timezone or UTC
                            timezone = data.get('timezone') or event.get('timezone') or 'UTC'

                            # Use new publish_date if provided, otherwise keep existing
                            scheduled_for = data.get('publish_date') or event.get('publish_date')

                            update_post_data = {
                                'content': caption,
                                'platforms': [{
                                    'platform': 'instagram',
                                    'accountId': account_id
                                }],
                                'scheduledFor': scheduled_for,
                                'timezone': timezone,
                                'isDraft': False  # Explicitly set to not draft
                            }

                            current_app.logger.info(f"Instagram caption update - using scheduledFor: {scheduled_for}")

                            response = requests.put(
                                f"https://getlate.dev/api/v1/posts/{instagram_post_id}",
                                headers=headers,
                                json=update_post_data,
                                timeout=30
                            )

                            if response.status_code in [200, 201]:
                                current_app.logger.info(f"Updated Instagram post {instagram_post_id} caption")
                            else:
                                current_app.logger.error(f"Failed to update Instagram caption: {response.status_code} - {response.text}")
                    except Exception as e:
                        current_app.logger.error(f"Error updating Instagram caption: {e}")

                # Update TikTok caption
                if tiktok_post_id:
                    try:
                        import requests
                        import os
                        from app.scripts.instagram_upload_studio.latedev_oauth_service import LateDevOAuthService

                        account_id = LateDevOAuthService.get_account_id(user_id, 'tiktok')
                        if account_id:
                            # Extract caption from description
                            description = data.get('description', event.get('description', ''))
                            caption = description.replace('Caption: ', '') if description.startswith('Caption: ') else description

                            headers = {
                                'Authorization': f'Bearer {os.environ.get("LATEDEV_API_KEY")}',
                                'Content-Type': 'application/json'
                            }

                            # Use user's timezone if provided, otherwise default to event's timezone or UTC
                            timezone = data.get('timezone') or event.get('timezone') or 'UTC'

                            # Use new publish_date if provided, otherwise keep existing
                            scheduled_for = data.get('publish_date') or event.get('publish_date')

                            update_post_data = {
                                'content': caption,
                                'platforms': [{
                                    'platform': 'tiktok',
                                    'accountId': account_id
                                }],
                                'scheduledFor': scheduled_for,
                                'timezone': timezone,
                                'isDraft': False  # Explicitly set to not draft
                            }

                            current_app.logger.info(f"TikTok caption update - using scheduledFor: {scheduled_for}")

                            response = requests.put(
                                f"https://getlate.dev/api/v1/posts/{tiktok_post_id}",
                                headers=headers,
                                json=update_post_data,
                                timeout=30
                            )

                            if response.status_code in [200, 201]:
                                current_app.logger.info(f"Updated TikTok post {tiktok_post_id} caption")
                            else:
                                current_app.logger.error(f"Failed to update TikTok caption: {response.status_code} - {response.text}")
                    except Exception as e:
                        current_app.logger.error(f"Error updating TikTok caption: {e}")

                # Note: X post text is not editable from calendar - edit in X Post Editor instead
                # The link to X Post Editor is provided in the UI

                # Update YouTube video metadata (title, description, tags)
                current_app.logger.info(f"Checking YouTube update - youtube_video_id: {youtube_video_id}")
                if youtube_video_id:
                    current_app.logger.info(f"YouTube video ID found, proceeding with update")
                    try:
                        import requests
                        import os
                        from app.scripts.instagram_upload_studio.latedev_oauth_service import LateDevOAuthService

                        account_id = LateDevOAuthService.get_account_id(user_id, 'youtube')
                        if account_id:
                            # Use user's timezone if provided, otherwise default to event's timezone or UTC
                            timezone = data.get('timezone') or event.get('timezone') or 'UTC'

                            # Initialize YouTube title/description variables
                            youtube_title = None
                            youtube_description = None

                            # Extract YouTube title and description from the combined description field
                            # Frontend sends: "Title: <title>\nDescription: <description>"
                            if 'description' in data:
                                description_raw = data.get('description', '')

                                # Parse the combined format
                                if 'Title: ' in description_raw and 'Description: ' in description_raw:
                                    parts = description_raw.split('\n')
                                    for part in parts:
                                        if part.startswith('Title: '):
                                            youtube_title = part.replace('Title: ', '').strip()
                                        elif part.startswith('Description: '):
                                            youtube_description = part.replace('Description: ', '').strip()

                            # Build platformSpecificData with title and description
                            platform_specific_data = {}
                            if youtube_title:
                                platform_specific_data['title'] = youtube_title
                                current_app.logger.info(f"Setting YouTube title to: {youtube_title}")
                            if youtube_description:
                                platform_specific_data['description'] = youtube_description
                                current_app.logger.info(f"Setting YouTube description to: {youtube_description[:100]}...")

                            # Use new publish_date if provided, otherwise keep existing
                            scheduled_for = data.get('publish_date') or event.get('publish_date')

                            update_post_data = {
                                'platforms': [{
                                    'platform': 'youtube',
                                    'accountId': account_id,
                                    'platformSpecificData': platform_specific_data
                                }],
                                'scheduledFor': scheduled_for,
                                'timezone': timezone,
                                'isDraft': False  # Explicitly set to not draft
                            }

                            current_app.logger.info(f"YouTube metadata update - using scheduledFor: {scheduled_for}")

                            # Also set content at root level as fallback
                            if youtube_description:
                                update_post_data['content'] = youtube_description

                            # Add tags if changed
                            if 'tags' in data:
                                tags = data.get('tags', '').split(',')
                                tags = [tag.strip() for tag in tags if tag.strip()]
                                update_post_data['tags'] = tags
                                current_app.logger.info(f"Setting YouTube tags to: {tags}")

                            headers = {
                                'Authorization': f'Bearer {os.environ.get("LATEDEV_API_KEY")}',
                                'Content-Type': 'application/json'
                            }

                            response = requests.put(
                                f"https://getlate.dev/api/v1/posts/{youtube_video_id}",
                                headers=headers,
                                json=update_post_data,
                                timeout=30
                            )

                            if response.status_code in [200, 201]:
                                current_app.logger.info(f"Updated YouTube video {youtube_video_id} metadata")

                                # Also update the calendar event title with the YouTube title
                                if youtube_title and 'title' not in update_data:
                                    update_data['title'] = youtube_title
                                    current_app.logger.info(f"Updating calendar event title to: {youtube_title}")
                            else:
                                current_app.logger.error(f"Failed to update YouTube metadata: {response.status_code} - {response.text}")
                    except Exception as e:
                        current_app.logger.error(f"Error updating YouTube metadata: {e}")

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

        # If this event has a YouTube post, delete it from Late.dev
        youtube_video_id = event.get('youtube_video_id')
        if youtube_video_id:
            try:
                import requests
                import os

                headers = {
                    'Authorization': f'Bearer {os.environ.get("LATEDEV_API_KEY")}',
                    'Content-Type': 'application/json'
                }

                response = requests.delete(
                    f"https://getlate.dev/api/v1/posts/{youtube_video_id}",
                    headers=headers,
                    timeout=30
                )

                if response.status_code in [200, 201, 204]:
                    current_app.logger.info(f"Deleted YouTube post {youtube_video_id}")
                else:
                    current_app.logger.error(f"Failed to delete YouTube post {youtube_video_id}: {response.status_code}")
            except Exception as e:
                current_app.logger.error(f"Error deleting YouTube post {youtube_video_id}: {e}")
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
                    if notes and 'Draft ID:' in str(notes):
                        # Use regex to extract draft ID
                        import re
                        draft_id_match = re.search(r'Draft ID:\s*(\S+)', str(notes))
                        if draft_id_match:
                            draft_id = draft_id_match.group(1)
                            current_app.logger.info(f"Found draft ID in notes: {draft_id}")
                        else:
                            current_app.logger.warning(f"Could not extract draft ID from notes: {notes}")
                    else:
                        current_app.logger.warning(f"No Draft ID found in notes: {notes}")

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

        # Update content library - remove this platform from the content
        content_id = event.get('content_id')
        if content_id:
            try:
                from app.system.services.content_library_service import ContentLibraryManager

                # Get the platform from the event
                platform = event.get('platform', '').lower()

                # Normalize platform names (Twitter/X can be stored as either 'x' or 'twitter')
                platform_mapping = {
                    'twitter': 'x',
                    'x': 'x',
                    'youtube': 'youtube',
                    'tiktok': 'tiktok',
                    'instagram': 'instagram'
                }
                platform = platform_mapping.get(platform, platform)

                # Get content to check remaining platforms
                content = ContentLibraryManager.get_content_by_id(user_id, content_id)

                if content:
                    # Remove this platform from platforms_posted
                    platforms_posted = content.get('platforms_posted', {})

                    if platform in platforms_posted:
                        from app.system.services.firebase_service import db
                        content_ref = db.collection('users').document(user_id).collection('repost').document(content_id)

                        # Delete the platform field
                        from firebase_admin import firestore
                        content_ref.update({
                            f'platforms_posted.{platform}': firestore.DELETE_FIELD
                        })

                        # Remove platform from dict for checking
                        del platforms_posted[platform]

                        current_app.logger.info(f"Removed {platform} from content library {content_id}")

                        # If no platforms left, delete the entire content
                        if not platforms_posted:
                            ContentLibraryManager.delete_content(user_id, content_id)
                            current_app.logger.info(f"Deleted content library {content_id} - no platforms remaining")

            except Exception as e:
                current_app.logger.error(f"Error updating content library on delete: {e}")

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

@bp.route('/content-calendar/api/upload-comment-image', methods=['POST'])
@auth_required
@require_permission('content_calendar')
def upload_comment_image():
    """Upload an image for a calendar comment"""
    try:
        user_id = get_workspace_user_id()

        # Check if image file is present
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image file provided'}), 400

        image_file = request.files['image']
        if not image_file or image_file.filename == '':
            return jsonify({'success': False, 'error': 'No image file selected'}), 400

        # Validate file type
        if not image_file.content_type.startswith('image/'):
            return jsonify({'success': False, 'error': 'File must be an image'}), 400

        # Validate file size (5MB limit)
        image_file.seek(0, 2)  # Seek to end
        file_size = image_file.tell()
        image_file.seek(0)  # Seek back to beginning

        if file_size > 5 * 1024 * 1024:
            return jsonify({'success': False, 'error': 'Image must be smaller than 5MB'}), 400

        # Generate unique filename
        import os
        file_ext = os.path.splitext(image_file.filename)[1].lower()
        unique_filename = f"comment_{uuid.uuid4().hex}{file_ext}"

        # Upload to Firebase Storage
        from app.system.services.firebase_service import StorageService
        result = StorageService.upload_file(
            user_id,
            'calendar_comments',  # Directory for calendar comment images
            unique_filename,
            image_file,
            make_public=True  # Public URL for viewing
        )

        if result:
            # Extract URL from result
            if isinstance(result, dict):
                image_url = result.get('url')
            else:
                image_url = result

            current_app.logger.info(f"Comment image uploaded: {image_url}")

            return jsonify({
                'success': True,
                'image_url': image_url
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to upload to storage'}), 500

    except Exception as e:
        current_app.logger.error(f"Error uploading comment image: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500