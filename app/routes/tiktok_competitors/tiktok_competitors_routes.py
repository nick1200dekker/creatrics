from flask import render_template, request, jsonify
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, require_permission
from app.system.credits.credits_manager import CreditsManager
from app.scripts.tiktok_competitors.tiktok_competitor_analyzer import TikTokCompetitorAnalyzer
from app.scripts.tiktok_competitors.tiktok_api import TikTokAPI
from app.system.services.firebase_service import db, bucket
from datetime import datetime, timezone
import logging
import os
import requests
import io
import hashlib
import asyncio
import httpx
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

async def download_and_store_avatar_async(avatar_url, user_id, sec_uid):
    """
    Download TikTok avatar and store permanently in Firebase Storage (async version)

    Args:
        avatar_url: Original TikTok CDN URL
        user_id: User ID for storage path
        sec_uid: TikTok account sec_uid for unique filename

    Returns:
        Public URL to stored avatar or None if failed
    """
    if not avatar_url or not bucket:
        return None

    try:
        # Download the image asynchronously
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(avatar_url)
            response.raise_for_status()

        # Create a unique filename using sec_uid hash
        filename_hash = hashlib.md5(sec_uid.encode()).hexdigest()[:12]
        file_extension = 'jpg'  # TikTok avatars are typically JPEG
        filename = f"tiktok_avatar_{filename_hash}.{file_extension}"

        # Upload to Firebase Storage (blocking operation, run in thread pool)
        blob_path = f'users/{user_id}/tiktok_avatars/{filename}'

        def upload_to_firebase():
            blob = bucket.blob(blob_path)
            blob.upload_from_string(
                response.content,
                content_type=response.headers.get('content-type', 'image/jpeg')
            )
            blob.make_public()
            return blob.public_url

        # Run blocking Firebase upload in thread pool
        loop = asyncio.get_event_loop()
        public_url = await loop.run_in_executor(None, upload_to_firebase)

        logger.info(f"Avatar stored successfully: {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"Error downloading/storing avatar: {e}")
        return None

def download_and_store_avatar(avatar_url, user_id, sec_uid):
    """
    Synchronous wrapper for download_and_store_avatar_async
    """
    try:
        return asyncio.run(download_and_store_avatar_async(avatar_url, user_id, sec_uid))
    except Exception as e:
        logger.error(f"Error in sync wrapper: {e}")
        return None

@bp.route('/')
@auth_required
@require_permission('tiktok_competitors')
def tiktok_competitors():
    """TikTok Competitor analysis page"""
    return render_template('tiktok/competitors.html')

@bp.route('/api/lists', methods=['GET'])
@auth_required
@require_permission('tiktok_competitors')
def get_niche_lists():
    """Get all TikTok niche lists"""
    try:
        user_id = get_workspace_user_id()
        lists_ref = db.collection('users').document(user_id).collection('tiktok_niche_lists')
        lists = lists_ref.order_by('created_at').stream()

        lists_data = []
        for lst in lists:
            list_dict = lst.to_dict()
            list_dict['id'] = lst.id

            if list_dict.get('created_at'):
                list_dict['created_at'] = list_dict['created_at'].isoformat()
            if list_dict.get('updated_at'):
                list_dict['updated_at'] = list_dict['updated_at'].isoformat()

            lists_data.append(list_dict)

        return jsonify({
            'success': True,
            'lists': lists_data
        })
    except Exception as e:
        logger.error(f"Error getting TikTok niche lists: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/lists', methods=['POST'])
@auth_required
@require_permission('tiktok_competitors')
def create_niche_list():
    """Create a new TikTok niche list"""
    try:
        data = request.json
        list_name = data.get('name', '').strip()

        if not list_name:
            return jsonify({'success': False, 'error': 'List name is required'}), 400

        user_id = get_workspace_user_id()
        now = datetime.now(timezone.utc)

        list_data = {
            'name': list_name,
            'created_at': now,
            'updated_at': now,
            'account_count': 0
        }

        lists_ref = db.collection('users').document(user_id).collection('tiktok_niche_lists')
        doc_ref = lists_ref.add(list_data)

        if isinstance(doc_ref, tuple):
            doc_id = doc_ref[1].id
        else:
            doc_id = doc_ref.id

        list_data['id'] = doc_id
        list_data['created_at'] = list_data['created_at'].isoformat()
        list_data['updated_at'] = list_data['updated_at'].isoformat()

        return jsonify({
            'success': True,
            'list': list_data
        })
    except Exception as e:
        logger.error(f"Error creating TikTok niche list: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/lists/<list_id>', methods=['DELETE'])
@auth_required
@require_permission('tiktok_competitors')
def delete_niche_list(list_id):
    """Delete a TikTok niche list and all its accounts"""
    try:
        user_id = get_workspace_user_id()

        # Delete all accounts in this list
        accounts_ref = db.collection('users').document(user_id).collection('tiktok_niche_lists').document(list_id).collection('accounts')
        accounts = accounts_ref.stream()
        for account in accounts:
            account.reference.delete()

        # Delete the list
        lists_ref = db.collection('users').document(user_id).collection('tiktok_niche_lists')
        lists_ref.document(list_id).delete()

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting TikTok niche list: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/search', methods=['GET'])
@auth_required
@require_permission('tiktok_competitors')
def search_accounts():
    """Search for TikTok videos and show channels"""
    try:
        query = request.args.get('query', '').strip()

        if not query:
            return jsonify({'success': False, 'error': 'Search query is required'}), 400

        # Use the TikTok general search endpoint (same as Keyword Research)
        import requests

        api_key = os.getenv('RAPIDAPI_KEY', '16c9c09b8bmsh0f0d3ec2999f27ep115961jsn5f75604e8050')
        headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": "tiktok-api23.p.rapidapi.com"
        }

        url = "https://tiktok-api23.p.rapidapi.com/api/search/general"

        # PARALLEL API CALLS - Fetch first page to get search_id, then fetch 4 more pages in parallel
        channels_dict = {}
        search_id = "0"

        # First request to get search_id
        first_params = {
            "keyword": query,
            "cursor": 0,
            "search_id": "0"
        }

        logger.info(f"Fetching first page for '{query}'")
        first_response = requests.get(url, headers=headers, params=first_params, timeout=30)
        first_response.raise_for_status()
        first_data = first_response.json()

        if first_data.get('status_code') == 0:
            # Process first page
            videos_data = first_data.get('data', [])
            for entry in videos_data:
                try:
                    item = entry.get('item', {})
                    author = item.get('author', {})
                    sec_uid = author.get('secUid')
                    if not sec_uid or sec_uid in channels_dict:
                        continue
                    author_stats = item.get('authorStats', {})
                    channels_dict[sec_uid] = {
                        'sec_uid': sec_uid,
                        'username': author.get('uniqueId'),
                        'nickname': author.get('nickname'),
                        'avatar': author.get('avatarLarger'),
                        'verified': author.get('verified', False),
                        'follower_count': author_stats.get('followerCount', 0),
                        'following_count': author_stats.get('followingCount', 0),
                        'video_count': author_stats.get('videoCount', 0),
                        'heart_count': author_stats.get('heartCount', 0)
                    }
                except Exception as e:
                    logger.error(f"Error parsing channel: {e}")
                    continue

            # Get search_id for next requests
            log_pb = first_data.get('log_pb', {})
            impr_id = log_pb.get('impr_id')
            if impr_id:
                search_id = impr_id
                logger.info(f"Got search_id: {search_id}")

            # Fetch remaining 9 pages in PARALLEL (total 10 pages)
            import asyncio
            import httpx

            async def fetch_remaining_pages():
                async with httpx.AsyncClient(timeout=30.0) as client:
                    tasks = []
                    for page_num in range(1, 10):  # Pages 1-9 (plus page 0 already fetched)
                        params = {
                            "keyword": query,
                            "cursor": page_num,
                            "search_id": search_id
                        }
                        tasks.append(client.get(url, headers=headers, params=params))
                    return await asyncio.gather(*tasks, return_exceptions=True)

            logger.info("Fetching 9 more pages in parallel (total 10 pages)")
            responses = asyncio.run(fetch_remaining_pages())

            # Process parallel responses
            for resp in responses:
                if isinstance(resp, Exception):
                    continue
                try:
                    data = resp.json()
                    if data.get('status_code') == 0:
                        videos_data = data.get('data', [])
                        for entry in videos_data:
                            try:
                                item = entry.get('item', {})
                                author = item.get('author', {})
                                sec_uid = author.get('secUid')
                                if not sec_uid or sec_uid in channels_dict:
                                    continue
                                author_stats = item.get('authorStats', {})
                                channels_dict[sec_uid] = {
                                    'sec_uid': sec_uid,
                                    'username': author.get('uniqueId'),
                                    'nickname': author.get('nickname'),
                                    'avatar': author.get('avatarLarger'),
                                    'verified': author.get('verified', False),
                                    'follower_count': author_stats.get('followerCount', 0),
                                    'following_count': author_stats.get('followingCount', 0),
                                    'video_count': author_stats.get('videoCount', 0),
                                    'heart_count': author_stats.get('heartCount', 0)
                                }
                            except Exception as e:
                                logger.error(f"Error parsing channel: {e}")
                                continue
                except:
                    continue

        channels = list(channels_dict.values())
        logger.info(f"Found {len(channels)} unique channels")

        # Sort by follower count
        channels.sort(key=lambda x: x.get('follower_count', 0), reverse=True)

        # Pre-download and store avatars in parallel for all channels
        user_id = get_workspace_user_id()

        async def download_all_avatars():
            """Download all avatars in parallel"""
            tasks = []
            for channel in channels:
                if channel.get('avatar'):
                    tasks.append(
                        download_and_store_avatar_async(
                            channel['avatar'],
                            user_id,
                            channel['sec_uid']
                        )
                    )
                else:
                    tasks.append(asyncio.sleep(0))  # Placeholder for channels without avatars

            return await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"Pre-downloading {len(channels)} avatars in parallel")
        stored_avatars = asyncio.run(download_all_avatars())

        # Update channels with stored avatar URLs
        for i, channel in enumerate(channels):
            if i < len(stored_avatars) and stored_avatars[i] and not isinstance(stored_avatars[i], Exception):
                channel['avatar'] = stored_avatars[i]
                logger.info(f"Updated avatar for {channel.get('nickname')}")

        return jsonify({
            'success': True,
            'channels': channels
        })

    except Exception as e:
        logger.error(f"Error searching TikTok videos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/add', methods=['POST'])
@auth_required
@require_permission('tiktok_competitors')
def add_competitor():
    """Add a TikTok competitor account"""
    try:
        data = request.json
        account_url = data.get('account_url', '').strip()
        account_data_from_search = data.get('account_data')
        list_id = data.get('list_id', '').strip()

        if not list_id:
            return jsonify({'success': False, 'error': 'List ID is required'}), 400

        user_id = get_workspace_user_id()
        now = datetime.now(timezone.utc)

        if account_data_from_search:
            # From search results
            sec_uid = account_data_from_search.get('sec_uid')
            if not sec_uid:
                return jsonify({'success': False, 'error': 'Account sec_uid is required'}), 400

            # Check if avatar is already a Firebase URL (pre-downloaded from search)
            original_avatar = account_data_from_search.get('avatar', '')
            if original_avatar and 'firebasestorage.googleapis.com' in original_avatar:
                # Already stored in Firebase, use as-is
                avatar_url = original_avatar
            else:
                # Download and store avatar permanently
                stored_avatar = download_and_store_avatar(original_avatar, user_id, sec_uid)
                # Fallback to original if storage fails
                avatar_url = stored_avatar if stored_avatar else original_avatar

            competitor_data = {
                'sec_uid': sec_uid,
                'username': account_data_from_search.get('username', ''),
                'nickname': account_data_from_search.get('nickname', ''),
                'bio': account_data_from_search.get('bio', ''),
                'avatar': avatar_url,
                'follower_count': account_data_from_search.get('follower_count', 0),
                'following_count': account_data_from_search.get('following_count', 0),
                'video_count': account_data_from_search.get('video_count', 0),
                'heart_count': account_data_from_search.get('heart_count', 0),
                'verified': account_data_from_search.get('verified', False),
                'added_at': now,
                'updated_at': now
            }
        else:
            # From URL
            if not account_url:
                return jsonify({'success': False, 'error': 'Account URL is required'}), 400

            tiktok_api = TikTokAPI()
            username = tiktok_api.extract_username(account_url)

            if not username:
                return jsonify({'success': False, 'error': 'Invalid TikTok account URL. Use format: tiktok.com/@username'}), 400

            account_info = tiktok_api.get_user_info(username)
            if not account_info:
                return jsonify({'success': False, 'error': 'Failed to fetch account information. Please check the URL.'}), 500

            sec_uid = account_info.get('sec_uid')
            if not sec_uid:
                return jsonify({'success': False, 'error': 'Could not get account ID from TikTok'}), 500

            # Download and store avatar permanently
            original_avatar = account_info.get('avatar', '')
            stored_avatar = download_and_store_avatar(original_avatar, user_id, sec_uid)
            # Fallback to original if storage fails
            avatar_url = stored_avatar if stored_avatar else original_avatar

            competitor_data = {
                'sec_uid': sec_uid,
                'username': account_info.get('username', ''),
                'nickname': account_info.get('nickname', ''),
                'bio': account_info.get('bio', ''),
                'avatar': avatar_url,
                'follower_count': account_info.get('follower_count', 0),
                'following_count': account_info.get('following_count', 0),
                'video_count': account_info.get('video_count', 0),
                'heart_count': account_info.get('heart_count', 0),
                'verified': account_info.get('verified', False),
                'added_at': now,
                'updated_at': now
            }

        # Check if already exists
        accounts_ref = db.collection('users').document(user_id).collection('tiktok_niche_lists').document(list_id).collection('accounts')
        existing = accounts_ref.where('sec_uid', '==', sec_uid).limit(1).get()

        if len(list(existing)) > 0:
            return jsonify({'success': False, 'error': 'This account is already in this niche list'}), 400

        # Save to Firebase
        doc_ref = accounts_ref.add(competitor_data)

        if isinstance(doc_ref, tuple):
            doc_id = doc_ref[1].id
        else:
            doc_id = doc_ref.id

        # Update account count
        lists_ref = db.collection('users').document(user_id).collection('tiktok_niche_lists')
        list_doc = lists_ref.document(list_id).get()
        if list_doc.exists:
            current_count = list_doc.to_dict().get('account_count', 0)
            lists_ref.document(list_id).update({
                'account_count': current_count + 1,
                'updated_at': now
            })

        competitor_data['id'] = doc_id
        competitor_data['added_at'] = competitor_data['added_at'].isoformat()
        competitor_data['updated_at'] = competitor_data['updated_at'].isoformat()

        return jsonify({
            'success': True,
            'account': competitor_data
        })

    except Exception as e:
        logger.error(f"Error adding TikTok competitor: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/list', methods=['GET'])
@auth_required
@require_permission('tiktok_competitors')
def list_competitors():
    """Get all saved TikTok competitors for a specific list"""
    try:
        user_id = get_workspace_user_id()
        list_id = request.args.get('list_id')

        if not list_id:
            return jsonify({'success': False, 'error': 'List ID is required'}), 400

        accounts_ref = db.collection('users').document(user_id).collection('tiktok_niche_lists').document(list_id).collection('accounts')
        accounts = accounts_ref.stream()

        accounts_list = []
        for acc in accounts:
            acc_data = acc.to_dict()
            acc_data['id'] = acc.id

            if acc_data.get('added_at'):
                acc_data['added_at'] = acc_data['added_at'].isoformat()
            if acc_data.get('updated_at'):
                acc_data['updated_at'] = acc_data['updated_at'].isoformat()

            accounts_list.append(acc_data)

        return jsonify({
            'success': True,
            'competitors': accounts_list
        })

    except Exception as e:
        logger.error(f"Error listing TikTok competitors: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/latest-analysis', methods=['GET'])
@auth_required
@require_permission('tiktok_competitors')
def get_latest_analysis():
    """Get the latest saved TikTok competitor analysis"""
    try:
        user_id = get_workspace_user_id()

        analysis_ref = db.collection('users').document(user_id).collection('tiktok_competitor_analyses').document('latest')
        analysis_doc = analysis_ref.get()

        if not analysis_doc.exists:
            return jsonify({
                'success': True,
                'has_analysis': False
            })

        analysis_data = analysis_doc.to_dict()

        if analysis_data.get('created_at'):
            analysis_data['created_at'] = analysis_data['created_at'].isoformat()

        return jsonify({
            'success': True,
            'has_analysis': True,
            'analysis': analysis_data
        })

    except Exception as e:
        logger.error(f"Error getting latest TikTok analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/analyze', methods=['POST'])
@auth_required
@require_permission('tiktok_competitors')
def analyze_competitors():
    """Analyze TikTok competitors and generate insights"""
    try:
        data = request.json
        timeframe = data.get('timeframe', '30')
        list_id = data.get('list_id', '').strip()

        if not list_id:
            return jsonify({'success': False, 'error': 'List ID is required'}), 400

        user_id = get_workspace_user_id()

        # Get all saved competitors
        accounts_ref = db.collection('users').document(user_id).collection('tiktok_niche_lists').document(list_id).collection('accounts')
        competitors = list(accounts_ref.stream())

        if not competitors:
            return jsonify({'success': False, 'error': 'No competitors added. Please add some accounts first.'}), 400

        if len(competitors) > 15:
            return jsonify({'success': False, 'error': 'Maximum 15 competitors allowed for analysis'}), 400
        
        # Extract account data
        account_data = []
        for comp in competitors:
            comp_dict = comp.to_dict()
            account_data.append({
                'sec_uid': comp_dict.get('sec_uid'),
                'username': comp_dict.get('username', ''),
                'nickname': comp_dict.get('nickname', '')
            })
        
        credits_manager = CreditsManager()
        analyzer = TikTokCompetitorAnalyzer()
        
        # Estimate cost
        estimated_cost = len(account_data) * 0.5
        
        # Check credits
        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=estimated_cost
        )
        
        if not credit_check.get('sufficient', False):
            current_credits = credits_manager.get_user_credits(user_id)
            return jsonify({
                "success": False,
                "error": f"Insufficient credits. Required: {estimated_cost:.2f}, Available: {current_credits:.2f}",
                "error_type": "insufficient_credits",
                "current_credits": current_credits,
                "required_credits": estimated_cost
            }), 402
        
        # Perform analysis
        result = analyzer.analyze_competitors(
            account_data=account_data,
            timeframe=timeframe,
            user_id=user_id
        )
        
        if not result.get('success'):
            return jsonify({
                "success": False,
                "error": result.get('error', 'Analysis failed')
            }), 500
        
        # Deduct credits if AI was used
        if result.get('used_ai', False):
            token_usage = result.get('token_usage', {})
            if token_usage.get('input_tokens', 0) > 0:
                credits_manager.deduct_llm_credits(
                    user_id=user_id,
                    model_name=token_usage.get('model', None),  # Uses current AI provider model
                    input_tokens=token_usage.get('input_tokens', 0),
                    output_tokens=token_usage.get('output_tokens', 0),
                    description="TikTok Competitor Analysis",
                    provider_enum=token_usage.get('provider_enum')
                )

        # Save as latest analysis
        try:
            analysis_data = {
                'list_id': list_id,
                'list_name': data.get('list_name', 'Unknown'),
                'timeframe': timeframe,
                'account_count': len(account_data),
                'insights': result.get('data', {}),
                'created_at': datetime.now(timezone.utc)
            }

            analysis_ref = db.collection('users').document(user_id).collection('tiktok_competitor_analyses').document('latest')
            analysis_ref.set(analysis_data)

            logger.info(f"Saved latest TikTok analysis for user {user_id}")
        except Exception as e:
            logger.error(f"Error saving TikTok analysis: {e}")

        return jsonify({
            'success': True,
            'data': result.get('data', {}),
            'used_ai': result.get('used_ai', False)
        })
        
    except Exception as e:
        logger.error(f"Error analyzing TikTok competitors: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/remove/<list_id>/<doc_id>', methods=['DELETE'])
@auth_required
@require_permission('tiktok_competitors')
def remove_competitor(list_id, doc_id):
    """Remove a TikTok competitor"""
    try:
        user_id = get_workspace_user_id()

        accounts_ref = db.collection('users').document(user_id).collection('tiktok_niche_lists').document(list_id).collection('accounts')
        accounts_ref.document(doc_id).delete()

        # Update account count
        lists_ref = db.collection('users').document(user_id).collection('tiktok_niche_lists')
        list_doc = lists_ref.document(list_id).get()
        if list_doc.exists:
            current_count = list_doc.to_dict().get('account_count', 1)
            lists_ref.document(list_id).update({
                'account_count': max(0, current_count - 1),
                'updated_at': datetime.now(timezone.utc)
            })

        return jsonify({'success': True, 'message': 'Competitor removed successfully'})

    except Exception as e:
        logger.error(f"Error removing TikTok competitor: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500