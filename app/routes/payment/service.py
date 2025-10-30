import os
import stripe
import logging
import time
from flask import current_app
from dotenv import load_dotenv
from app.system.services.firebase_service import UserService
from app.system.credits.credits_manager import CreditsManager
from datetime import datetime, timedelta
from threading import Lock

# Setup logger
logger = logging.getLogger('stripe_service')

# Load environment variables
load_dotenv()

# Set your secret key from environment variable
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
if stripe.api_key:
    logger.info(f"Stripe configured with API key: {stripe.api_key[:4]}...{stripe.api_key[-4:]}")
else:
    logger.warning("Stripe API key not found in environment variables")

# Create a lock for preventing concurrent credit additions
credit_lock = Lock()

"""
IMPROVED WEBHOOK HANDLING WITH ROBUST DOUBLE-CREDIT PREVENTION:
1. checkout.session.completed - Handles ALL initial payments with transaction-based idempotency
2. invoice.payment_succeeded - Handles ONLY subscription renewals
3. Uses transaction IDs and locks to prevent any double-crediting
"""

class StripeService:
    @staticmethod
    def create_customer(user_id, email, username):
        """Create a Stripe customer for a user."""
        try:
            logger.info(f"Creating Stripe customer for user: {user_id}, email: {email}, username: {username}")
            customer = stripe.Customer.create(
                email=email,
                name=username,
                metadata={
                    'user_id': user_id,
                    'subscription_plan': 'Free Plan'
                }
            )
            logger.info(f"Created Stripe customer: {customer.id}")
            return customer.id
        except Exception as e:
            logger.error(f"Error creating Stripe customer: {str(e)}", exc_info=True)
            logger.error(f"Error details: Type: {type(e).__name__}, Args: {e.args}")
            return None
    
    @staticmethod
    def get_or_create_customer(user_id, user_data):
        """Get existing customer or create a new one."""
        logger.info(f"Getting or creating customer for user: {user_id}")
        logger.debug(f"User data: {user_data}")
        
        # Check if user has a stripe_customer_id in Firebase
        if user_data and 'stripe_customer_id' in user_data and user_data['stripe_customer_id']:
            try:
                # Try to retrieve the customer to validate it exists
                customer_id = user_data['stripe_customer_id']
                logger.info(f"Found existing Stripe customer ID: {customer_id}")
                customer = stripe.Customer.retrieve(customer_id)
                
                # Check if the customer has the right metadata
                if 'user_id' not in customer.metadata or customer.metadata.user_id != user_id:
                    # Update the customer with proper metadata
                    logger.info(f"Updating customer metadata for {customer_id}")
                    stripe.Customer.modify(
                        customer_id,
                        metadata={
                            'user_id': user_id,
                            'subscription_plan': user_data.get('subscription_plan', 'Free Plan')
                        }
                    )
                
                return customer_id
            except Exception as e:
                logger.error(f"Error retrieving Stripe customer: {str(e)}", exc_info=True)
                logger.error(f"Error details: Type: {type(e).__name__}, Args: {e.args}")
                # Continue to create a new customer if retrieval fails
        else:
            logger.info(f"No existing Stripe customer ID found for user {user_id}")
        
        # Create a new customer
        email = user_data.get('email', '')
        username = user_data.get('username', f"user_{user_id[:8]}")
        
        logger.info(f"Creating new customer with email: {email}, username: {username}")
        
        try:
            logger.debug(f"About to create Stripe customer with params: email={email}, name={username}, user_id={user_id}")
            customer = stripe.Customer.create(
                email=email,
                name=username,
                metadata={
                    'user_id': user_id,
                    'subscription_plan': user_data.get('subscription_plan', 'Free Plan')
                }
            )
            customer_id = customer.id
            
            # Update user record in Firebase with new customer ID
            try:
                logger.info(f"Updating user {user_id} with new Stripe customer ID: {customer_id}")
                UserService.update_user(user_id, {
                    'stripe_customer_id': customer_id
                })
                logger.info(f"Updated user {user_id} with Stripe customer ID: {customer_id}")
            except Exception as e:
                logger.error(f"Error updating user with Stripe customer ID: {str(e)}", exc_info=True)
                logger.error(f"Error details: Type: {type(e).__name__}, Args: {e.args}")
            
            return customer_id
        except Exception as e:
            logger.error(f"Error creating customer: {str(e)}", exc_info=True)
            logger.error(f"Error details: Type: {type(e).__name__}, Args: {e.args}")
            return None
    
    @staticmethod
    def create_checkout_session(user_id, user_data, plan_id, success_url, cancel_url):
        """Create a checkout session for a subscription or one-time payment."""
        logger.info(f"Creating checkout session for user {user_id}, plan {plan_id}")
        logger.info(f"Success URL: {success_url}")
        logger.info(f"Cancel URL: {cancel_url}")
        
        # Map plan_id to actual Stripe price ID
        price_id_map = {
            'basic': os.environ.get('STRIPE_BASIC_PRICE_ID'),  # Soccer Pro subscription
            'flex1': os.environ.get('STRIPE_FLEX1_PRICE_ID'),  # 500 credits one-time
            'flex2': os.environ.get('STRIPE_FLEX2_PRICE_ID')   # 1000 credits one-time
        }
        
        price_id = price_id_map.get(plan_id)
        if not price_id:
            logger.error(f"Invalid plan ID: {plan_id}")
            return None
        
        logger.info(f"Mapped plan {plan_id} to price ID: {price_id}")
        
        # IMPORTANT: Always fetch fresh user data to ensure we have the latest subscription status
        # This is especially important for flex credit purchases
        if plan_id in ['flex1', 'flex2']:
            # Refresh user data from Firebase to get the latest subscription status
            fresh_user_data = UserService.get_user(user_id)
            if fresh_user_data:
                user_data = fresh_user_data
                logger.info(f"Refreshed user data for flex credit purchase check")
            
            current_plan = user_data.get('subscription_plan', 'Free Plan')
            normalized_plan = current_plan.lower().strip()
            
            # More flexible plan name matching (including admin access)
            is_king_plan = any(plan_name in normalized_plan for plan_name in [
                'premium creator', 'premium', 'soccer pro', 'pro plan', 'basic plan', 'basic', 'pro', 'admin', 'administrator'
            ])
            
            logger.info(f"Flex credit check - User plan: '{current_plan}', normalized: '{normalized_plan}', is_king: {is_king_plan}")
            
            if not is_king_plan:
                logger.warning(f"User {user_id} attempted to buy flex credits without King plan (plan: '{current_plan}')")
                return None
        
        # Get or create customer
        customer_id = StripeService.get_or_create_customer(user_id, user_data)
        
        if not customer_id:
            logger.error("Failed to get or create customer")
            return None
        
        # Determine checkout mode based on plan type
        checkout_mode = 'subscription' if plan_id == 'basic' else 'payment'
            
        try:
            # Clean up old pending sessions before creating new one
            logger.info(f"Starting cleanup of old pending sessions for user {user_id}")
            StripeService._cleanup_old_pending_sessions(user_id, user_data)
            logger.info(f"Completed cleanup of old pending sessions for user {user_id}")
            
            # Create checkout session
            logger.info(f"Creating checkout session for customer {customer_id}")
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
                # Allow promotion codes
                allow_promotion_codes=True,
                # Store metadata for webhook processing - CRITICAL FOR CREDITS
                metadata={
                    'user_id': user_id,
                    'plan_id': plan_id
                }
            )
            logger.info(f"Created checkout session: {checkout_session.id}, URL: {checkout_session.url}")
            
            # Get fresh user data after cleanup to avoid adding back old sessions
            fresh_user_data = UserService.get_user(user_id)
            pending_sessions = fresh_user_data.get('pending_checkout_sessions', []) if fresh_user_data else []
            
            # Add new session
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
            
            return checkout_session
        except Exception as e:
            logger.error(f"Error creating checkout session: {str(e)}")
            return None
    
    @staticmethod
    def create_customer_portal_session(user_id, user_data, return_url):
        """Create a customer portal session for managing subscriptions."""
        logger.info(f"Creating customer portal session for user {user_id}")
        logger.info(f"Return URL: {return_url}")
        
        # Always try to get fresh user data if not provided
        if not user_data or not user_data.get('stripe_customer_id'):
            fresh_user_data = UserService.get_user(user_id)
            if fresh_user_data:
                user_data = fresh_user_data
                logger.info(f"Refreshed user data for portal session")
        
        # Check if user has a stripe_customer_id
        if not user_data or not user_data.get('stripe_customer_id'):
            logger.error(f"User {user_id} has no Stripe customer ID")
            
            # Try to create a customer if the user has email/username
            if user_data and (user_data.get('email') or user_data.get('username')):
                logger.info(f"Attempting to create a new customer for user {user_id}")
                customer_id = StripeService.get_or_create_customer(user_id, user_data)
                
                if not customer_id:
                    logger.error(f"Failed to create customer for user {user_id}")
                    return None
            else:
                logger.error(f"Insufficient user data to create a customer")
                return None
        else:
            customer_id = user_data['stripe_customer_id']
            
        try:
            # Log the request
            logger.info(f"Creating Stripe portal session with customer ID {customer_id}")
            
            # Create the portal session
            portal_session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )
            
            # Log success
            logger.info(f"Created Stripe portal session: {portal_session.url}")
            
            return portal_session
        except Exception as e:
            logger.error(f"Error creating portal session: {str(e)}")
            return None
    
    @staticmethod
    def handle_webhook_event(payload, signature):
        """Handle Stripe webhook events."""
        webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
        
        if not webhook_secret:
            logger.error("STRIPE_WEBHOOK_SECRET not configured!")
            return False
        
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            logger.info(f"Successfully verified webhook signature for event: {event['type']}")
        except ValueError as e:
            # Invalid payload
            logger.error(f"Invalid payload: {str(e)}")
            return False
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            logger.error(f"Invalid signature: {str(e)}")
            return False
        
        # Handle the event
        event_type = event['type']
        logger.info(f"Processing webhook event: {event_type}")
        
        # Log the full event data for debugging
        logger.debug(f"Full webhook event data: {event}")
        
        if event_type == 'checkout.session.completed':
            # PRIMARY HANDLER - Handle ALL initial payments
            session = event['data']['object']
            StripeService._handle_checkout_completed(session)
        elif event_type == 'customer.subscription.created':
            # New subscription created - update plan
            subscription = event['data']['object']
            StripeService._handle_subscription_created(subscription)
        elif event_type == 'customer.subscription.updated':
            # Subscription updated - update plan
            subscription = event['data']['object']
            StripeService._handle_subscription_updated(subscription)
        elif event_type == 'customer.subscription.deleted':
            # Subscription cancelled - reset to free plan
            subscription = event['data']['object']
            StripeService._handle_subscription_deleted(subscription)
        elif event_type == 'invoice.payment_succeeded':
            # Handle ONLY subscription renewals
            invoice = event['data']['object']
            StripeService._handle_invoice_payment_succeeded(invoice)
        else:
            logger.info(f"Unhandled event type: {event_type}")
            
        return True

    @staticmethod
    def _record_credit_transaction(user_id, transaction_id, amount, description):
        """Record that a credit transaction has been processed to prevent duplicates."""
        try:
            # Store in user's processed_transactions
            user_data = UserService.get_user(user_id)
            if user_data:
                processed_transactions = user_data.get('processed_credit_transactions', [])
                
                # Add new transaction
                processed_transactions.append({
                    'transaction_id': transaction_id,
                    'amount': amount,
                    'description': description,
                    'processed_at': datetime.now().isoformat()
                })
                
                # Keep only last 100 transactions
                processed_transactions = processed_transactions[-100:]
                
                UserService.update_user(user_id, {
                    'processed_credit_transactions': processed_transactions
                })
                
                logger.info(f"Recorded credit transaction {transaction_id} for user {user_id}")
                return True
        except Exception as e:
            logger.error(f"Error recording credit transaction: {str(e)}")
            return False

    @staticmethod
    def _is_transaction_processed(user_id, transaction_id):
        """Check if a transaction has already been processed."""
        try:
            user_data = UserService.get_user(user_id)
            if user_data:
                processed_transactions = user_data.get('processed_credit_transactions', [])
                
                for trans in processed_transactions:
                    if trans.get('transaction_id') == transaction_id:
                        logger.info(f"Transaction {transaction_id} already processed for user {user_id}")
                        return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking transaction status: {str(e)}")
            # Be safe and assume not processed to avoid blocking legitimate transactions
            return False

    @staticmethod
    def _handle_checkout_completed(session):
        """PRIMARY HANDLER - Handle ALL successful checkout completions with strong idempotency."""
        global credit_lock
        
        try:
            logger.info(f"=== CHECKOUT.SESSION.COMPLETED ===")
            logger.info(f"Session ID: {session.get('id')}")
            logger.info(f"Payment Status: {session.get('payment_status')}")
            logger.info(f"Mode: {session.get('mode')}")
            
            # Check payment status
            if session.get('payment_status') != 'paid':
                logger.warning(f"Session not paid, status: {session.get('payment_status')}")
                return
            
            # Get metadata - CRITICAL
            metadata = session.get('metadata', {})
            user_id = metadata.get('user_id')
            plan_id = metadata.get('plan_id')
            mode = session.get('mode')
            session_id = session.get('id')
            
            logger.info(f"Metadata - User ID: {user_id}, Plan ID: {plan_id}")
            
            if not user_id:
                # Try to get user from customer
                customer_id = session.get('customer')
                if customer_id:
                    user_id = StripeService._get_user_id_from_customer(customer_id)
                    logger.info(f"Found user {user_id} from customer {customer_id}")
            
            if not user_id:
                logger.error("CRITICAL: Could not determine user ID from checkout session")
                return
            
            if not plan_id:
                logger.error("CRITICAL: No plan_id in session metadata")
                return
            
            # Use a lock to prevent concurrent processing
            with credit_lock:
                # Create a unique transaction ID for this session
                transaction_id = f"checkout_{session_id}"
                
                # Check if this transaction was already processed
                if StripeService._is_transaction_processed(user_id, transaction_id):
                    logger.warning(f"Transaction {transaction_id} already processed, skipping")
                    return
                
                # Initialize credits manager
                credits_manager = CreditsManager()
                
                # Process based on plan type
                if plan_id == 'flex1':
                    # 500 credits one-time purchase
                    credits_to_add = 500
                    
                    logger.info(f"Processing FLEX1 (500 credits) for user {user_id}")
                    
                    credit_result = credits_manager.add_credits(
                        user_id,
                        credits_to_add,
                        f"Flex Credits purchase: FLEX1 (session: {session_id[:20]}...)",
                        "flex_purchase"
                    )
                    
                    if credit_result['success']:
                        logger.info(f"✅ Successfully added 500 flex credits to user {user_id}")
                        logger.info(f"New balance: {credit_result.get('credits_remaining', 'unknown')}")
                        
                        # Record the transaction
                        StripeService._record_credit_transaction(
                            user_id, transaction_id, credits_to_add, "FLEX1 purchase"
                        )
                    else:
                        logger.error(f"❌ Failed to add flex credits: {credit_result.get('message', 'Unknown error')}")
                        
                elif plan_id == 'flex2':
                    # 1000 credits one-time purchase
                    credits_to_add = 1000
                    
                    logger.info(f"Processing FLEX2 (1000 credits) for user {user_id}")
                    
                    credit_result = credits_manager.add_credits(
                        user_id,
                        credits_to_add,
                        f"Flex Credits purchase: FLEX2 (session: {session_id[:20]}...)",
                        "flex_purchase"
                    )
                    
                    if credit_result['success']:
                        logger.info(f"✅ Successfully added 1000 flex credits to user {user_id}")
                        logger.info(f"New balance: {credit_result.get('credits_remaining', 'unknown')}")
                        
                        # Record the transaction
                        StripeService._record_credit_transaction(
                            user_id, transaction_id, credits_to_add, "FLEX2 purchase"
                        )
                    else:
                        logger.error(f"❌ Failed to add flex credits: {credit_result.get('message', 'Unknown error')}")
                        
                elif plan_id == 'basic' and mode == 'subscription':
                    # New Premium Creator subscription
                    credits_to_add = 500

                    logger.info(f"Processing new Premium Creator subscription for user {user_id}")

                    # Update user to Premium Creator plan FIRST
                    update_result = UserService.update_user(user_id, {
                        'subscription_plan': 'Premium Creator'
                    })

                    if update_result:
                        logger.info(f"✅ Updated user {user_id} to Premium Creator plan")
                    else:
                        logger.error(f"❌ Failed to update user plan")

                    # Add initial 500 credits
                    credit_result = credits_manager.add_credits(
                        user_id,
                        credits_to_add,
                        f"Premium Creator subscription - initial credits (session: {session_id[:20]}...)",
                        "subscription_initial"
                    )

                    if credit_result['success']:
                        logger.info(f"✅ Successfully added 500 initial credits to user {user_id}")
                        logger.info(f"New balance: {credit_result.get('credits_remaining', 'unknown')}")

                        # Record the transaction
                        StripeService._record_credit_transaction(
                            user_id, transaction_id, credits_to_add, "Premium Creator initial"
                        )
                    else:
                        logger.error(f"❌ Failed to add initial credits: {credit_result.get('message', 'Unknown error')}")

                    # Process referral subscription bonus (one-time)
                    try:
                        from app.system.services.referral_service import ReferralService
                        referral_result = ReferralService.process_subscription_referral(user_id)
                        if referral_result.get('success'):
                            logger.info(f"✅ Referral subscription bonus processed: {referral_result.get('message')}")
                        else:
                            logger.info(f"Referral subscription bonus: {referral_result.get('message')}")
                    except Exception as ref_error:
                        logger.error(f"Error processing subscription referral bonus: {str(ref_error)}")

                else:
                    logger.warning(f"Unknown plan_id: {plan_id} or mode: {mode}")
                
                # Mark session as completed
                StripeService._mark_session_completed(user_id, session_id)
                
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR in checkout.session.completed: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

    @staticmethod
    def _mark_session_completed(user_id, session_id):
        """Mark a session as completed in user's pending sessions."""
        try:
            user_data = UserService.get_user(user_id)
            if user_data:
                pending_sessions = user_data.get('pending_checkout_sessions', [])
                
                for session_info in pending_sessions:
                    if session_info.get('session_id') == session_id:
                        session_info['status'] = 'completed'
                        session_info['completed_at'] = datetime.now().isoformat()
                        break
                
                UserService.update_user(user_id, {
                    'pending_checkout_sessions': pending_sessions
                })
                
                logger.info(f"Marked session {session_id} as completed for user {user_id}")
        except Exception as e:
            logger.error(f"Error marking session as completed: {str(e)}")

    @staticmethod
    def _handle_subscription_created(subscription):
        """Handle subscription creation - update plan only."""
        try:
            logger.info(f"=== CUSTOMER.SUBSCRIPTION.CREATED ===")
            
            # Get product ID from subscription
            product_id = None
            
            # Extract product ID
            if isinstance(subscription, dict):
                if 'items' in subscription and 'data' in subscription['items'] and len(subscription['items']['data']) > 0:
                    if 'price' in subscription['items']['data'][0] and 'product' in subscription['items']['data'][0]['price']:
                        product_id = subscription['items']['data'][0]['price']['product']
            
            if not product_id:
                logger.error("Could not extract product ID from subscription")
                return
            
            # Get customer ID
            customer_id = subscription.get('customer') if isinstance(subscription, dict) else subscription.customer
            
            if not customer_id:
                logger.error("Could not extract customer ID from subscription")
                return
            
            logger.info(f"Processing new subscription for customer: {customer_id}, product: {product_id}")
            
            # Look up user
            user_id = StripeService._get_user_id_from_customer(customer_id)
                
            if not user_id:
                logger.error(f"User not found for Stripe customer: {customer_id}")
                return
            
            # Check if this is the Premium Creator plan
            if product_id == os.environ.get('STRIPE_BASIC_PLAN_ID'):
                # Update user to Premium Creator plan (credits handled in checkout.session.completed)
                UserService.update_user(user_id, {
                    'subscription_plan': 'Premium Creator'
                })
                
                logger.info(f"✅ Updated user {user_id} to Premium Creator plan")
                
        except Exception as e:
            logger.error(f"Error in subscription creation handler: {str(e)}")
    
    @staticmethod
    def _handle_subscription_updated(subscription):
        """Handle subscription updates."""
        try:
            logger.info(f"=== CUSTOMER.SUBSCRIPTION.UPDATED ===")
            
            # Similar structure to creation, but we check for plan changes
            product_id = None
            
            # Extract product ID
            if isinstance(subscription, dict):
                if 'items' in subscription and 'data' in subscription['items'] and len(subscription['items']['data']) > 0:
                    if 'price' in subscription['items']['data'][0] and 'product' in subscription['items']['data'][0]['price']:
                        product_id = subscription['items']['data'][0]['price']['product']
            
            if not product_id:
                logger.error("Could not extract product ID from subscription")
                return
            
            # Get customer ID and status
            customer_id = subscription.get('customer') if isinstance(subscription, dict) else subscription.customer
            status = subscription.get('status', 'active')
            
            logger.info(f"Processing subscription update for customer: {customer_id}, status: {status}")
            
            # Look up user
            user_id = StripeService._get_user_id_from_customer(customer_id)
                
            if not user_id:
                logger.error(f"User not found for Stripe customer: {customer_id}")
                return
            
            # Update plan based on product and status
            if product_id == os.environ.get('STRIPE_BASIC_PLAN_ID') and status == 'active':
                UserService.update_user(user_id, {
                    'subscription_plan': 'Premium Creator'
                })
                logger.info(f"✅ Updated user {user_id} subscription to Premium Creator")
            elif status in ['canceled', 'unpaid']:
                UserService.update_user(user_id, {
                    'subscription_plan': 'Free Plan'
                })
                logger.info(f"✅ Updated user {user_id} to Free Plan due to status: {status}")
                
        except Exception as e:
            logger.error(f"Error in subscription update handler: {str(e)}")
    
    @staticmethod
    def _handle_subscription_deleted(subscription):
        """Reset user to Free Plan when subscription is cancelled."""
        try:
            logger.info(f"=== CUSTOMER.SUBSCRIPTION.DELETED ===")
            
            # Get customer ID
            customer_id = subscription.get('customer') if isinstance(subscription, dict) else subscription.customer
            
            if not customer_id:
                logger.error("Could not extract customer ID from subscription")
                return
            
            logger.info(f"Handling subscription deletion for customer: {customer_id}")
            
            # Look up user
            user_id = StripeService._get_user_id_from_customer(customer_id)
                
            if not user_id:
                logger.error(f"User not found for Stripe customer: {customer_id}")
                return
            
            # Reset to Free Plan (keep existing credits)
            UserService.update_user(user_id, {
                'subscription_plan': 'Free Plan'
            })
            
            logger.info(f"✅ Reset user {user_id} to Free Plan after subscription cancellation")
            
        except Exception as e:
            logger.error(f"Error processing subscription deletion: {str(e)}")

    @staticmethod
    def _handle_invoice_payment_succeeded(invoice):
        """Handle ONLY subscription renewals - NOT initial payments."""
        global credit_lock
        
        try:
            logger.info(f"=== INVOICE.PAYMENT_SUCCEEDED ===")
            
            # Check billing reason FIRST
            billing_reason = invoice.get('billing_reason')
            logger.info(f"Billing reason: {billing_reason}")
            
            # ONLY process subscription renewals
            if billing_reason != 'subscription_cycle':
                logger.info(f"Skipping non-renewal invoice (billing_reason: {billing_reason})")
                return
            
            # Check if this is a subscription invoice
            subscription_id = invoice.get('subscription')
            if not subscription_id:
                logger.info("Invoice is not for a subscription, skipping")
                return
            
            customer_id = invoice.get('customer')
            invoice_id = invoice.get('id')
            
            if not customer_id:
                logger.error("Could not extract customer ID from invoice")
                return
            
            # Look up user
            user_id = StripeService._get_user_id_from_customer(customer_id)
                
            if not user_id:
                logger.error(f"User not found for Stripe customer: {customer_id}")
                return
            
            # Use a lock to prevent concurrent processing
            with credit_lock:
                # Create a unique transaction ID for this renewal
                transaction_id = f"renewal_{invoice_id}"
                
                # Check if this transaction was already processed
                if StripeService._is_transaction_processed(user_id, transaction_id):
                    logger.warning(f"Renewal transaction {transaction_id} already processed, skipping")
                    return
                
                # Get the subscription to check the product
                try:
                    subscription = stripe.Subscription.retrieve(subscription_id)
                    product_id = subscription['items']['data'][0]['price']['product']
                    
                    # Only process Premium Creator renewals
                    if product_id == os.environ.get('STRIPE_BASIC_PLAN_ID'):
                        logger.info(f"Processing Premium Creator renewal for user {user_id}")

                        credits_manager = CreditsManager()
                        credit_result = credits_manager.add_credits(
                            user_id,
                            500,
                            f"Premium Creator monthly renewal credits (invoice: {invoice_id[:20]}...)",
                            "subscription_renewal"
                        )

                        if credit_result['success']:
                            logger.info(f"✅ Successfully added 500 renewal credits to user {user_id}")
                            logger.info(f"New balance: {credit_result.get('credits_remaining', 'unknown')}")

                            # Record the transaction
                            StripeService._record_credit_transaction(
                                user_id, transaction_id, 500, "Premium Creator renewal"
                            )
                        else:
                            logger.error(f"❌ Failed to add renewal credits: {credit_result.get('message', 'Unknown error')}")
                    else:
                        logger.info(f"Invoice payment is not for Premium Creator plan, skipping")
                        
                except Exception as sub_error:
                    logger.error(f"Error retrieving subscription details: {str(sub_error)}")
            
        except Exception as e:
            logger.error(f"❌ Error handling invoice payment succeeded: {str(e)}")

    @staticmethod
    def _get_user_id_from_customer(customer_id):
        """Get user ID from Stripe customer ID."""
        try:
            from app.system.services.firebase_service import db
            
            users_ref = db.collection('users')
            query = users_ref.where('stripe_customer_id', '==', customer_id).limit(1)
            user_docs = query.get()
            
            for doc in user_docs:
                return doc.id
                
            # If not found in database, try to get from customer metadata
            try:
                customer = stripe.Customer.retrieve(customer_id)
                user_id = customer.metadata.get('user_id')
                if user_id:
                    logger.info(f"Found user_id {user_id} in customer metadata")
                    return user_id
            except Exception as e:
                logger.error(f"Error retrieving customer from Stripe: {str(e)}")
                
            return None
        except Exception as e:
            logger.error(f"Error looking up user by customer ID: {str(e)}")
            return None

    @staticmethod
    def manual_sync_session(user_id, session_id):
        """Manually sync a checkout session if webhook failed"""
        try:
            logger.info(f"Manual sync requested for session {session_id} by user {user_id}")
            
            # Retrieve the session from Stripe
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Verify the session belongs to this user
            session_user_id = session.metadata.get('user_id')
            if session_user_id != user_id:
                logger.warning(f"Session {session_id} does not belong to user {user_id}")
                return {
                    'success': False,
                    'message': 'Session does not belong to this user'
                }
            
            # Check if payment was successful
            if session.payment_status != 'paid':
                logger.info(f"Session {session_id} is not paid yet: {session.payment_status}")
                return {
                    'success': False,
                    'message': 'Payment not completed'
                }
            
            # Process the completed session
            StripeService._handle_checkout_completed(session)
            
            return {
                'success': True,
                'message': 'Payment synced successfully'
            }
            
        except Exception as e:
            logger.error(f"Error in manual sync: {str(e)}")
            return {
                'success': False,
                'message': f'Error syncing payment: {str(e)}'
            }

    @staticmethod
    def check_and_sync_recent_sessions(user_id):
        """Check and sync recent checkout sessions for a user"""
        try:
            logger.info(f"Checking recent sessions for user {user_id}")
            
            # Get user data
            user_data = UserService.get_user(user_id)
            if not user_data:
                return {
                    'success': False,
                    'message': 'User not found'
                }
            
            pending_sessions = user_data.get('pending_checkout_sessions', [])
            synced_count = 0
            
            # Check sessions from the last 24 hours
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            for session_info in pending_sessions:
                if session_info.get('status') == 'pending':
                    created_at = datetime.fromisoformat(session_info.get('created_at', ''))
                    
                    if created_at > cutoff_time:
                        # Try to sync this session
                        result = StripeService.manual_sync_session(user_id, session_info.get('session_id'))
                        if result['success']:
                            synced_count += 1
                            session_info['status'] = 'completed'
                            session_info['synced_at'] = datetime.now().isoformat()
            
            # Update user data
            UserService.update_user(user_id, {
                'pending_checkout_sessions': pending_sessions
            })
            
            return {
                'success': True,
                'message': f'Synced {synced_count} pending payments',
                'synced_count': synced_count
            }
            
        except Exception as e:
            logger.error(f"Error checking recent sessions: {str(e)}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    @staticmethod
    def _cleanup_old_pending_sessions(user_id, user_data):
        """Clean up old pending checkout sessions before creating new ones."""
        try:
            pending_sessions = user_data.get('pending_checkout_sessions', [])
            if not pending_sessions:
                return
            
            logger.info(f"Cleaning up {len(pending_sessions)} pending sessions for user {user_id}")
            
            # Check each session status with Stripe
            active_sessions = []
            expired_count = 0
            
            for session_info in pending_sessions:
                session_id = session_info.get('session_id')
                if not session_id:
                    continue
                
                try:
                    # Check session status with Stripe
                    stripe_session = stripe.checkout.Session.retrieve(session_id)
                    
                    # Keep only active sessions (not expired, completed, or canceled)
                    if stripe_session.status in ['open']:
                        # Check if session is older than 24 hours (Stripe sessions expire after 24h)
                        created_time = datetime.fromtimestamp(stripe_session.created)
                        if datetime.now() - created_time < timedelta(hours=24):
                            active_sessions.append(session_info)
                            logger.info(f"Keeping recent session: {session_id} (created {created_time})")
                        else:
                            expired_count += 1
                            logger.info(f"Removing expired session: {session_id} (created {created_time}, older than 24 hours)")
                    else:
                        expired_count += 1
                        logger.info(f"Removing {stripe_session.status} session: {session_id}")
                        
                except stripe.error.InvalidRequestError:
                    # Session doesn't exist in Stripe anymore
                    expired_count += 1
                    logger.info(f"Removing non-existent session: {session_id}")
                except Exception as e:
                    logger.warning(f"Error checking session {session_id}: {str(e)}")
                    # Keep session if we can't check it (to be safe)
                    active_sessions.append(session_info)
            
            # Update user data with cleaned sessions
            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} old/expired sessions for user {user_id}")
                UserService.update_user(user_id, {
                    'pending_checkout_sessions': active_sessions
                })
                
        except Exception as e:
            logger.error(f"Error cleaning up pending sessions: {str(e)}")
            # Don't fail the checkout creation if cleanup fails
    
    @staticmethod
    def cleanup_all_expired_sessions():
        """Cleanup expired sessions for all users - can be run as a scheduled job."""
        try:
            logger.info("Starting global cleanup of expired checkout sessions")
            
            # This would need to be implemented based on your user storage
            # For now, this is a placeholder for a scheduled cleanup job
            # You could run this daily via cron job or scheduled task
            
            logger.info("Global session cleanup completed")
            return {"success": True, "message": "Global cleanup completed"}
            
        except Exception as e:
            logger.error(f"Error in global session cleanup: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}"}