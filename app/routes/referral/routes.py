"""
Referral Routes - Handle referral dashboard and API endpoints
"""

import logging
from flask import render_template, jsonify, request, g
from app.routes.referral import bp
from app.system.services.referral_service import ReferralService
from app.system.auth.middleware import auth_required

logger = logging.getLogger('referral_routes')


@bp.route('/', methods=['GET'])
@auth_required
def referral_dashboard():
    """Render the referral dashboard page"""
    return render_template('referral/index.html')


@bp.route('/api/stats', methods=['GET'])
@auth_required
def get_referral_stats():
    """Get referral statistics for the current user"""
    try:
        user_id = g.user.get('id')
        stats = ReferralService.get_referral_stats(user_id)

        if stats:
            return jsonify({
                'success': True,
                'stats': stats
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Could not fetch referral stats'
            }), 404

    except Exception as e:
        logger.error(f"Error fetching referral stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/update-code', methods=['POST'])
@auth_required
def update_referral_code():
    """Update user's referral code (custom code)"""
    try:
        user_id = g.user.get('id')
        data = request.json
        new_code = data.get('code', '').strip().upper()

        # Validate code format
        if not new_code:
            return jsonify({
                'success': False,
                'error': 'Please enter a referral code'
            }), 400

        if len(new_code) < 4 or len(new_code) > 20:
            return jsonify({
                'success': False,
                'error': 'Code must be between 4-20 characters'
            }), 400

        # Only allow alphanumeric and hyphens
        import re
        if not re.match(r'^[A-Z0-9-]+$', new_code):
            return jsonify({
                'success': False,
                'error': 'Code can only contain letters, numbers, and hyphens'
            }), 400

        # Check if code is already taken
        existing_user, _ = ReferralService.get_user_by_referral_code(new_code)
        if existing_user and existing_user != user_id:
            return jsonify({
                'success': False,
                'error': 'This code is already taken. Please choose another.'
            }), 400

        # Update code
        from app.system.services.firebase_service import UserService
        result = UserService.update_user(user_id, {
            'referral_code': new_code
        })

        if result:
            logger.info(f"User {user_id} updated referral code to {new_code}")
            return jsonify({
                'success': True,
                'message': 'Referral code updated successfully',
                'code': new_code
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to update code'
            }), 500

    except Exception as e:
        logger.error(f"Error updating referral code: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/validate-code', methods=['POST'])
def validate_referral_code():
    """Validate a referral code (public endpoint for registration page)"""
    try:
        data = request.json
        code = data.get('code', '').strip().upper()

        if not code:
            return jsonify({
                'success': False,
                'valid': False,
                'message': 'Please enter a referral code'
            })

        referrer_id, referrer_data = ReferralService.get_user_by_referral_code(code)

        if referrer_id:
            username = referrer_data.get('username', 'User')
            return jsonify({
                'success': True,
                'valid': True,
                'message': f'Valid code from {username}! You\'ll get {ReferralService.SIGNUP_CREDITS} bonus credits.'
            })
        else:
            return jsonify({
                'success': True,
                'valid': False,
                'message': 'Invalid referral code'
            })

    except Exception as e:
        logger.error(f"Error validating referral code: {str(e)}")
        return jsonify({
            'success': False,
            'valid': False,
            'error': str(e)
        }), 500
