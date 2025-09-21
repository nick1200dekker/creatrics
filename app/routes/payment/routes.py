from flask import Blueprint, render_template, jsonify, redirect, request, url_for, g
from app.system.auth.middleware import auth_required
from app.system.services.firebase_service import UserService
import logging
import os
from app.routes.payment.service import StripeService
import stripe
from flask import current_app
from datetime import datetime, timedelta

# Setup logger
logger = logging.getLogger('payment_routes')

# Create payment blueprint
bp = Blueprint('payment', __name__, url_prefix='/payment')

@bp.route('/')
@auth_required
def index():
    """Render payment plans page"""
    if hasattr(g, 'user') and g.user:
        current_user = g.user.get('data', {})
    else:
        # For direct navigation, return basic template
        current_user = {}
    
    logger.info(f"Payment page accessed, authenticated user: {hasattr(g, 'user')}")
    
    # Return the template with potentially limited data
    return render_template(
        'payment/index.html',
        current_user=current_user
    )

@bp.route('/api/create-checkout/<plan_id>', methods=['GET'])
@auth_required
def api_create_checkout(plan_id):
    """API endpoint to get a checkout URL without redirecting"""
    try:
        user_id = g.user.get('id')
        
        logger.info(f"API checkout requested for user {user_id}, plan: {plan_id}")
        
        # Validate plan_id - includes subscription and flex plans
        valid_plans = ['basic', 'flex1', 'flex2']
        if plan_id not in valid_plans:
            logger.warning(f"Invalid plan ID: {plan_id}")
            return jsonify({"success": False, "error": "Invalid plan ID"}), 400
        
        # Map plan_id to actual Stripe price ID
        price_id_map = {
            'basic': os.environ.get('STRIPE_BASIC_PRICE_ID'),  # Soccer Pro subscription
            'flex1': os.environ.get('STRIPE_FLEX1_PRICE_ID'),  # 500 credits one-time
            'flex2': os.environ.get('STRIPE_FLEX2_PRICE_ID')   # 1000 credits one-time
        }
        
        price_id = price_id_map.get(plan_id)
        if not price_id:
            logger.error(f"Invalid plan ID or missing price ID for: {plan_id}")
            return jsonify({"success": False, "error": "Missing price configuration"}), 400
        
        # IMPORTANT: Fetch fresh user data from Firebase instead of using g.user
        # This ensures we have the most up-to-date subscription status
        user_data = UserService.get_user(user_id)
        if not user_data:
            logger.error(f"Failed to fetch user data for {user_id}")
            return jsonify({"success": False, "error": "Failed to fetch user data"}), 500
        
        logger.info(f"Fetched fresh user data for {user_id}, plan: {user_data.get('subscription_plan')}")
        
        # Check if user is allowed to buy flex credits
        if plan_id in ['flex1', 'flex2']:
            current_plan = user_data.get('subscription_plan', 'Free Plan')
            normalized_plan = current_plan.lower().strip()
            
            # More flexible plan name matching
            is_king_plan = any(plan_name in normalized_plan for plan_name in [
                'soccer pro', 'pro plan', 'basic plan', 'basic', 'pro'
            ])
            
            logger.info(f"Flex credit check - User plan: '{current_plan}', normalized: '{normalized_plan}', is_king: {is_king_plan}")
            
            if not is_king_plan:
                logger.warning(f"User {user_id} attempted to buy flex credits without King plan (plan: '{current_plan}')")
                return jsonify({"success": False, "error": "Flex Credits are only available to Soccer Pro subscribers"}), 403
            
        # Get or create customer ID
        customer_id = user_data.get('stripe_customer_id')
        if not customer_id:
            email = user_data.get('email')
            username = user_data.get('username')
            
            if not email or not username:
                logger.error(f"Missing email or username for user {user_id}")
                return jsonify({"success": False, "error": "Missing user information"}), 400
                
            customer_id = StripeService.create_customer(user_id, email, username)
            
            if not customer_id:
                logger.error(f"Failed to create customer for user {user_id}")
                return jsonify({"success": False, "error": "Failed to create customer"}), 500
                
            # Update user data with new customer ID
            UserService.update_user(user_id, {'stripe_customer_id': customer_id})
        
        # Set success and cancel URLs - include session ID for manual sync
        success_url = url_for('payment.success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}'
        cancel_url = url_for('payment.cancel', _external=True)
        
        # Determine checkout mode based on plan type
        checkout_mode = 'subscription' if plan_id == 'basic' else 'payment'
        
        # Create checkout session directly using stripe-python library
        try:
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode=checkout_mode,
                success_url=success_url,
                cancel_url=cancel_url,
                allow_promotion_codes=True,
                metadata={
                    'user_id': user_id,
                    'plan_id': plan_id
                }
            )
            
            logger.info(f"Created API checkout URL for {plan_id}: {checkout_session.url}")
            
            # Store session ID in user's pending_sessions for manual sync if needed
            pending_sessions = user_data.get('pending_checkout_sessions', [])
            pending_sessions.append({
                'session_id': checkout_session.id,
                'plan_id': plan_id,
                'created_at': datetime.now().isoformat(),
                'status': 'pending'
            })
            
            # Keep only last 10 sessions
            pending_sessions = pending_sessions[-10:]
            
            UserService.update_user(user_id, {
                'pending_checkout_sessions': pending_sessions
            })
            
            # Return the URL instead of redirecting
            return jsonify({
                "success": True,
                "checkout_url": checkout_session.url,
                "session_id": checkout_session.id
            })
            
        except Exception as e:
            logger.error(f"Error creating checkout session: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500
            
    except Exception as e:
        logger.error(f"Error in API checkout route: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/checkout/<plan_id>')
@auth_required
def checkout(plan_id):
    """Handle checkout for a specific plan"""
    try:
        user_id = g.user.get('id')
        
        logger.info(f"Checkout initiated for user {user_id}, plan: {plan_id}")
        
        # Validate plan_id
        valid_plans = ['basic', 'flex1', 'flex2']
        if plan_id not in valid_plans:
            logger.warning(f"Invalid plan ID: {plan_id}")
            return redirect(url_for('payment.index'))
        
        # IMPORTANT: Fetch fresh user data from Firebase
        user_data = UserService.get_user(user_id)
        if not user_data:
            logger.error(f"Failed to fetch user data for {user_id}")
            return redirect(url_for('payment.index', payment_status='error'))
        
        # Set success and cancel URLs with session ID
        success_url = url_for('payment.success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}'
        cancel_url = url_for('payment.cancel', _external=True)
        
        # Create Stripe checkout session
        session = StripeService.create_checkout_session(
            user_id, 
            user_data, 
            plan_id, 
            success_url, 
            cancel_url
        )
        
        if session:
            logger.info(f"Redirecting to Stripe checkout: {session.url}")
            return redirect(session.url)
        else:
            logger.error("Failed to create checkout session")
            return redirect(url_for('payment.index', payment_status='error'))
    except Exception as e:
        logger.error(f"Error during checkout: {str(e)}")
        return redirect(url_for('payment.index', payment_status='error'))

@bp.route('/success')
@auth_required
def success():
    """Handle successful payment with manual sync fallback"""
    logger.info("Payment success page accessed")
    
    # Get session ID from URL
    session_id = request.args.get('session_id')
    
    if session_id and hasattr(g, 'user') and g.user:
        user_id = g.user.get('id')
        logger.info(f"Attempting manual sync for session {session_id}")
        
        # Attempt manual sync
        try:
            result = StripeService.manual_sync_session(user_id, session_id)
            if result['success']:
                logger.info(f"Manual sync successful: {result['message']}")
            else:
                logger.warning(f"Manual sync failed: {result['message']}")
        except Exception as e:
            logger.error(f"Error during manual sync: {str(e)}")
    
    # Redirect to the payment page with a success parameter
    return redirect(url_for('payment.index', payment_status='success'))

@bp.route('/cancel')
def cancel():
    """Handle cancelled payment"""
    logger.info("Payment cancelled by user")
    
    # Redirect to the payment page with a cancelled parameter
    return redirect(url_for('payment.index', payment_status='cancelled'))

@bp.route('/direct-portal', methods=['GET'])
@auth_required
def direct_portal():
    """Direct portal route that handles existing stripe customers correctly"""
    try:
        user_id = g.user.get('id')
        logger.info(f"Direct portal access authenticated for user {user_id}")
        
        # Get the complete user data from Firebase directly
        user_data = UserService.get_user(user_id)
        if not user_data:
            logger.error(f"Failed to fetch user data for {user_id}")
            user_data = {}
        
        # Determine if this is an API request
        wants_json = False
        if (request.headers.get('Accept') == 'application/json' or 
            request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
            request.args.get('format') == 'json'):
            wants_json = True
            logger.info(f"Client requested JSON response")
        
        # Check if user has a Stripe customer ID
        stripe_customer_id = user_data.get('stripe_customer_id')
        
        if not stripe_customer_id:
            logger.warning(f"User {user_id} does not have a Stripe customer ID")
            
            # Try to create a customer for the user
            email = user_data.get('email')
            username = user_data.get('username')
            
            if email and username:
                # Create customer and update user data
                customer_id = StripeService.create_customer(user_id, email, username)
                if customer_id:
                    logger.info(f"Created new Stripe customer {customer_id} for user {user_id}")
                    # Update user data
                    UserService.update_user(user_id, {'stripe_customer_id': customer_id})
                    stripe_customer_id = customer_id
                else:
                    logger.error(f"Failed to create Stripe customer for user {user_id}")
                    if wants_json:
                        return jsonify({"success": False, "error": "Failed to create Stripe customer"}), 500
                    return redirect(url_for('payment.index', payment_status='error'))
            else:
                logger.error(f"Insufficient user data to create Stripe customer for user {user_id}")
                if wants_json:
                    return jsonify({"success": False, "error": "Insufficient user data"}), 400
                return redirect(url_for('payment.index', payment_status='error'))
        else:
            logger.info(f"Using existing Stripe customer ID: {stripe_customer_id}")
        
        # Create return URL
        return_url = url_for('payment.index', _external=True)
        
        # Create portal session
        try:
            logger.info(f"Creating portal session for customer {stripe_customer_id} with return URL {return_url}")
            
            portal_session = stripe.billing_portal.Session.create(
                customer=stripe_customer_id,
                return_url=return_url
            )
            
            portal_url = portal_session.url
            logger.info(f"Created direct portal URL: {portal_url}")
            
            # Return JSON if client requested it
            if wants_json:
                return jsonify({
                    "success": True,
                    "url": portal_url
                })
            
            # Otherwise redirect directly to the portal URL
            return redirect(portal_url)
            
        except Exception as e:
            logger.error(f"Error creating direct portal session: {str(e)}")
            if wants_json:
                return jsonify({"success": False, "error": str(e)}), 500
            return redirect(url_for('payment.index', payment_status='error'))
            
    except Exception as e:
        logger.error(f"Error in direct portal route: {str(e)}")
        if request.headers.get('Accept') == 'application/json':
            return jsonify({"success": False, "error": str(e)}), 500
        return redirect(url_for('payment.index', payment_status='error'))

@bp.route('/webhook', methods=['POST'])
def webhook():
    """Handle Stripe webhooks"""
    # IMPORTANT: Webhooks from Stripe don't include auth headers
    # so we need to bypass the normal auth check
    
    payload = request.data
    signature = request.headers.get('Stripe-Signature')
    
    # Log webhook receipt
    logger.info(f"=== WEBHOOK RECEIVED ===")
    logger.info(f"Signature present: {bool(signature)}")
    logger.info(f"Payload size: {len(payload) if payload else 0} bytes")
    
    if not payload or not signature:
        logger.warning("Missing webhook payload or signature")
        return jsonify({'error': 'Missing payload or signature'}), 400
    
    logger.info("Processing Stripe webhook...")
    success = StripeService.handle_webhook_event(payload, signature)
    
    if success:
        logger.info("✅ Webhook processed successfully")
        return jsonify({'status': 'success'}), 200
    else:
        logger.error("❌ Failed to process webhook")
        return jsonify({'error': 'Failed to process webhook'}), 400

@bp.route('/webhook/test', methods=['GET'])
@auth_required
def test_webhook():
    """Test webhook configuration"""
    try:
        # Check if webhook secret is configured
        webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
        
        result = {
            'webhook_secret_configured': bool(webhook_secret),
            'webhook_url': url_for('payment.webhook', _external=True),
            'stripe_api_key_configured': bool(os.environ.get('STRIPE_SECRET_KEY')),
            'required_env_vars': {
                'STRIPE_SECRET_KEY': bool(os.environ.get('STRIPE_SECRET_KEY')),
                'STRIPE_WEBHOOK_SECRET': bool(os.environ.get('STRIPE_WEBHOOK_SECRET')),
                'STRIPE_BASIC_PRICE_ID': bool(os.environ.get('STRIPE_BASIC_PRICE_ID')),
                'STRIPE_BASIC_PLAN_ID': bool(os.environ.get('STRIPE_BASIC_PLAN_ID')),
                'STRIPE_FLEX1_PRICE_ID': bool(os.environ.get('STRIPE_FLEX1_PRICE_ID')),
                'STRIPE_FLEX2_PRICE_ID': bool(os.environ.get('STRIPE_FLEX2_PRICE_ID')),
            }
        }
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in webhook test: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/manual-sync', methods=['POST'])
@auth_required
def manual_sync():
    """Manually sync payment status if webhooks fail"""
    try:
        user_id = g.user.get('id')
        
        logger.info(f"Manual sync requested by user {user_id}")
        
        # Check recent sessions
        result = StripeService.check_and_sync_recent_sessions(user_id)
        
        logger.info(f"Manual sync result: {result}")
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in manual sync: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500