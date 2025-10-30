"""
Referral Service - Handles referral code generation, tracking, and rewards
"""

import random
import string
import logging
from datetime import datetime
from app.system.services.firebase_service import UserService, db
from app.system.credits.credits_manager import CreditsManager
from google.cloud.firestore_v1.base_query import FieldFilter

logger = logging.getLogger('referral_service')

class ReferralService:
    """Service for managing referral program"""

    # Reward amounts
    SIGNUP_CREDITS = 10  # Credits for both referrer and referee on signup
    SUBSCRIPTION_BONUS = 200  # One-time bonus for referrer when referee subscribes

    # Power referrer tiers
    POWER_TIER_THRESHOLD = 100  # Number of signups to become power referrer

    @staticmethod
    def generate_referral_code(user_id, username=None):
        """
        Generate a unique referral code for a user

        Args:
            user_id: User's ID
            username: Optional username to use in code

        Returns:
            str: Generated referral code (e.g., NICK2025 or REF-AB12CD)
        """
        try:
            # Try to create a code based on username if provided
            if username and len(username) >= 3:
                # Clean username (remove spaces, special chars)
                clean_username = ''.join(c for c in username if c.isalnum())[:6].upper()
                year = datetime.now().year
                base_code = f"{clean_username}{year}"

                # Check if code is unique
                code = base_code
                counter = 1
                while ReferralService._code_exists(code):
                    code = f"{clean_username}{year}{counter}"
                    counter += 1
                    if counter > 99:  # Fallback to random if too many collisions
                        break

                if not ReferralService._code_exists(code):
                    return code

            # Fallback: Generate random code
            while True:
                random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                code = f"REF-{random_part}"

                if not ReferralService._code_exists(code):
                    return code

        except Exception as e:
            logger.error(f"Error generating referral code: {str(e)}")
            # Final fallback
            return f"REF-{user_id[:8].upper()}"

    @staticmethod
    def _code_exists(code):
        """Check if a referral code already exists"""
        try:
            if not db:
                return False

            users_ref = db.collection('users')
            query = users_ref.where(filter=FieldFilter('referral_code', '==', code)).limit(1)
            results = list(query.get())

            return len(results) > 0
        except Exception as e:
            logger.error(f"Error checking code existence: {str(e)}")
            return False

    @staticmethod
    def create_referral_entry(user_id, username=None):
        """
        Initialize referral data for a new user

        Args:
            user_id: User's ID
            username: Optional username

        Returns:
            dict: Referral data including code
        """
        try:
            # Generate referral code
            referral_code = ReferralService.generate_referral_code(user_id, username)

            # Initialize referral stats
            referral_data = {
                'referral_code': referral_code,
                'referred_by': None,
                'referral_stats': {
                    'total_signups': 0,
                    'paid_conversions': 0,
                    'total_earned_credits': 0,
                    'tier': 'basic'
                },
                'referral_rewards_claimed': {
                    'signup_rewards': [],
                    'subscription_rewards': []
                }
            }

            logger.info(f"Created referral data for user {user_id}: {referral_code}")
            return referral_data

        except Exception as e:
            logger.error(f"Error creating referral entry: {str(e)}")
            return None

    @staticmethod
    def get_user_by_referral_code(code):
        """
        Find user by their referral code

        Args:
            code: Referral code to search for

        Returns:
            tuple: (user_id, user_data) or (None, None)
        """
        try:
            if not db or not code:
                return None, None

            users_ref = db.collection('users')
            query = users_ref.where(filter=FieldFilter('referral_code', '==', code.upper())).limit(1)
            results = list(query.get())

            if results:
                doc = results[0]
                return doc.id, doc.to_dict()

            return None, None

        except Exception as e:
            logger.error(f"Error finding user by referral code {code}: {str(e)}")
            return None, None

    @staticmethod
    def process_signup_referral(new_user_id, referral_code):
        """
        Process a new signup with a referral code

        Args:
            new_user_id: ID of the new user who signed up
            referral_code: Referral code used during signup

        Returns:
            dict: Result with success status and message
        """
        try:
            if not referral_code:
                return {'success': True, 'message': 'No referral code provided'}

            # Find referrer
            referrer_id, referrer_data = ReferralService.get_user_by_referral_code(referral_code)

            if not referrer_id:
                logger.warning(f"Invalid referral code: {referral_code}")
                return {'success': False, 'message': 'Invalid referral code'}

            # Prevent self-referral
            if referrer_id == new_user_id:
                logger.warning(f"Self-referral attempt by {new_user_id}")
                return {'success': False, 'message': 'Cannot refer yourself'}

            # IDEMPOTENCY CHECK: Check if this user has already been awarded signup bonus
            # Check if user is already in referrer's signup_rewards list
            rewards_claimed = referrer_data.get('referral_rewards_claimed', {})
            signup_rewards = rewards_claimed.get('signup_rewards', [])

            if new_user_id in signup_rewards:
                logger.info(f"Signup bonus already claimed for {new_user_id}")
                return {'success': True, 'message': 'Referral bonus already claimed'}

            # Link referee to referrer
            UserService.update_user(new_user_id, {
                'referred_by': referrer_id
            })

            # Award credits to BOTH users
            credits_manager = CreditsManager()

            # Award referee (new user) signup bonus
            referee_result = credits_manager.add_credits(
                new_user_id,
                ReferralService.SIGNUP_CREDITS,
                f"Referral signup bonus (used code: {referral_code})",
                "referral_signup_bonus"
            )

            # Award referrer signup bonus
            referrer_result = credits_manager.add_credits(
                referrer_id,
                ReferralService.SIGNUP_CREDITS,
                f"Referral reward - new signup",
                "referral_signup_reward"
            )

            # Update referrer stats
            stats = referrer_data.get('referral_stats', {})
            stats['total_signups'] = stats.get('total_signups', 0) + 1
            stats['total_earned_credits'] = stats.get('total_earned_credits', 0) + ReferralService.SIGNUP_CREDITS

            # Check if user qualifies for power tier
            if stats['total_signups'] >= ReferralService.POWER_TIER_THRESHOLD:
                stats['tier'] = 'power'

            # Track this signup in claimed rewards
            rewards_claimed = referrer_data.get('referral_rewards_claimed', {})
            signup_rewards = rewards_claimed.get('signup_rewards', [])
            signup_rewards.append(new_user_id)

            UserService.update_user(referrer_id, {
                'referral_stats': stats,
                'referral_rewards_claimed.signup_rewards': signup_rewards
            })

            # Create referral entry in referrals collection
            if db:
                db.collection('referrals').add({
                    'referrer_id': referrer_id,
                    'referee_id': new_user_id,
                    'referral_code': referral_code,
                    'created_at': datetime.now(),
                    'status': 'active',
                    'subscription_reward_claimed': False,
                    'conversion_date': None
                })

            logger.info(f"Processed signup referral: {new_user_id} referred by {referrer_id}")
            return {
                'success': True,
                'message': f'Referral processed! Both users received {ReferralService.SIGNUP_CREDITS} credits',
                'credits_awarded': ReferralService.SIGNUP_CREDITS
            }

        except Exception as e:
            logger.error(f"Error processing signup referral: {str(e)}")
            return {'success': False, 'message': f'Error: {str(e)}'}

    @staticmethod
    def process_subscription_referral(user_id):
        """
        Process referral bonus when a user subscribes (one-time only)

        Args:
            user_id: ID of user who just subscribed

        Returns:
            dict: Result with success status
        """
        try:
            # Get user data
            user_data = UserService.get_user(user_id)
            if not user_data:
                return {'success': False, 'message': 'User not found'}

            # Check if user was referred
            referrer_id = user_data.get('referred_by')
            if not referrer_id:
                return {'success': True, 'message': 'User was not referred'}

            # Get referrer data
            referrer_data = UserService.get_user(referrer_id)
            if not referrer_data:
                return {'success': False, 'message': 'Referrer not found'}

            # Check if bonus already claimed
            rewards_claimed = referrer_data.get('referral_rewards_claimed', {})
            subscription_rewards = rewards_claimed.get('subscription_rewards', [])

            if user_id in subscription_rewards:
                logger.info(f"Subscription bonus already claimed for {user_id}")
                return {'success': True, 'message': 'Bonus already claimed'}

            # Award referrer the subscription bonus (ONE TIME ONLY)
            credits_manager = CreditsManager()
            result = credits_manager.add_credits(
                referrer_id,
                ReferralService.SUBSCRIPTION_BONUS,
                f"Referral subscription bonus - user upgraded",
                "referral_subscription_bonus"
            )

            if result['success']:
                # Update referrer stats
                stats = referrer_data.get('referral_stats', {})
                stats['paid_conversions'] = stats.get('paid_conversions', 0) + 1
                stats['total_earned_credits'] = stats.get('total_earned_credits', 0) + ReferralService.SUBSCRIPTION_BONUS

                # Mark bonus as claimed
                subscription_rewards.append(user_id)

                UserService.update_user(referrer_id, {
                    'referral_stats': stats,
                    'referral_rewards_claimed.subscription_rewards': subscription_rewards
                })

                # Update referral entry
                if db:
                    referrals_ref = db.collection('referrals')
                    query = referrals_ref.where(filter=FieldFilter('referee_id', '==', user_id)).limit(1)
                    results = list(query.get())

                    if results:
                        doc_ref = results[0].reference
                        doc_ref.update({
                            'subscription_reward_claimed': True,
                            'conversion_date': datetime.now(),
                            'status': 'converted'
                        })

                logger.info(f"Awarded {ReferralService.SUBSCRIPTION_BONUS} subscription bonus to {referrer_id}")
                return {
                    'success': True,
                    'message': f'Referral subscription bonus awarded',
                    'credits_awarded': ReferralService.SUBSCRIPTION_BONUS
                }
            else:
                return {'success': False, 'message': 'Failed to award credits'}

        except Exception as e:
            logger.error(f"Error processing subscription referral: {str(e)}")
            return {'success': False, 'message': f'Error: {str(e)}'}

    @staticmethod
    def get_referral_stats(user_id):
        """
        Get referral statistics for a user

        Args:
            user_id: User's ID

        Returns:
            dict: Referral statistics
        """
        try:
            user_data = UserService.get_user(user_id)
            if not user_data:
                return None

            # Check if user has a referral code, if not create one (for existing users)
            code = user_data.get('referral_code', '')
            if not code:
                logger.info(f"User {user_id} missing referral code, generating one")
                username = user_data.get('username')
                referral_data = ReferralService.create_referral_entry(user_id, username)
                if referral_data:
                    code = referral_data['referral_code']
                    # Update user with new referral data
                    UserService.update_user(user_id, referral_data)
                    logger.info(f"Generated referral code {code} for existing user {user_id}")

            stats = user_data.get('referral_stats', {})

            # Get list of referred users
            if db:
                referrals_ref = db.collection('referrals')
                query = referrals_ref.where(filter=FieldFilter('referrer_id', '==', user_id))
                referrals = list(query.get())

                referred_users = []
                for ref_doc in referrals:
                    ref_data = ref_doc.to_dict()
                    referee_data = UserService.get_user(ref_data['referee_id'])

                    if referee_data:
                        referred_users.append({
                            'user_id': ref_data['referee_id'],
                            'username': referee_data.get('username', 'User'),
                            'joined_date': ref_data.get('created_at'),
                            'status': ref_data.get('status', 'active'),
                            'converted': ref_data.get('subscription_reward_claimed', False)
                        })
            else:
                referred_users = []

            return {
                'referral_code': code,
                'total_signups': stats.get('total_signups', 0),
                'paid_conversions': stats.get('paid_conversions', 0),
                'total_earned_credits': stats.get('total_earned_credits', 0),
                'tier': stats.get('tier', 'basic'),
                'is_power_referrer': stats.get('total_signups', 0) >= ReferralService.POWER_TIER_THRESHOLD,
                'referred_users': referred_users,
                'signup_bonus': ReferralService.SIGNUP_CREDITS,
                'subscription_bonus': ReferralService.SUBSCRIPTION_BONUS
            }

        except Exception as e:
            logger.error(f"Error getting referral stats: {str(e)}")
            return None
