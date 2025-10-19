"""
Credits management system for creator tools app
Only LLM and Fal AI models
"""
import logging
import math
from datetime import datetime
from firebase_admin import firestore
from app.system.credits.config import (
    get_nano_banana_cost,
    get_base_nano_banana_cost,
    get_seeddream_cost,
    get_base_seeddream_cost,
    calculate_llm_cost,
    get_min_llm_cost,
    DEFAULT_MARGIN,
    apply_margin
)
from app.system.ai_provider.ai_provider import get_ai_provider

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CreditsManager:
    """Clean credits manager for meme templates app - Single source of truth"""
    
    def __init__(self):
        """Initialize the credits manager"""
        self.db = firestore.client()
        self.default_margin = DEFAULT_MARGIN
    
    def get_user_credits(self, user_id):
        """Get the current credit balance for a user"""
        try:
            user_ref = self.db.collection('users').document(user_id)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                logger.warning(f"User not found: {user_id}")
                return 0
                
            user_data = user_doc.to_dict()
            credits = user_data.get('credits', 0)
            
            # Always return rounded credits to prevent precision display issues
            return round(credits, 2)
        except Exception as e:
            logger.error(f"Error getting user credits: {str(e)}")
            return 0
    
    def check_sufficient_credits(self, user_id, required_credits):
        """
        Check if user has sufficient credits
        
        Args:
            user_id (str): User ID
            required_credits (float): Required credits
            
        Returns:
            dict: Check result with current balance and sufficiency
        """
        try:
            current_credits = self.get_user_credits(user_id)
            
            return {
                'sufficient': current_credits >= required_credits,
                'current_credits': current_credits,
                'required_credits': required_credits,
                'shortfall': max(0, required_credits - current_credits)
            }
            
        except Exception as e:
            logger.error(f"Error checking sufficient credits: {str(e)}")
            return {
                'sufficient': False,
                'current_credits': 0,
                'required_credits': required_credits,
                'shortfall': required_credits,
                'error': str(e)
            }
    
    def has_sufficient_credits(self, user_id, required_credits):
        """
        Simple boolean check for sufficient credits
        
        Args:
            user_id (str): User ID
            required_credits (float): Required credits
            
        Returns:
            bool: True if user has sufficient credits, False otherwise
        """
        try:
            credit_check = self.check_sufficient_credits(user_id, required_credits)
            return credit_check.get('sufficient', False)
        except Exception as e:
            logger.error(f"Error in has_sufficient_credits: {str(e)}")
            return False
    
    def estimate_meme_upscaling_cost(self):
        """
        Estimate meme upscaling cost
        
        Returns:
            dict: Complete cost estimation with all details
        """
        try:
            final_cost = get_image_upscaling_cost()
            base_cost = get_base_image_upscaling_cost()
            
            return {
                'base_cost': base_cost,
                'final_cost': final_cost,
                'margin_applied': self.default_margin,
                'service': 'fal.ai',
                'model': 'recraft/upscale/crisp'
            }
            
        except Exception as e:
            logger.error(f"Error estimating meme upscaling cost: {str(e)}")
            return {
                'base_cost': 0.83,
                'final_cost': 1,
                'margin_applied': self.default_margin,
                'service': 'fal.ai',
                'model': 'recraft/upscale/crisp',
                'error': str(e)
            }
    
    def estimate_and_check_meme_upscaling_operation(self, user_id):
        """
        Estimate and check meme upscaling operation
        
        Args:
            user_id (str): User ID
            
        Returns:
            dict: Complete operation check with cost estimate and sufficiency
        """
        try:
            # Get cost estimate
            cost_estimate = self.estimate_meme_upscaling_cost()
            
            # Check if user has sufficient credits
            credit_check = self.check_sufficient_credits(user_id, cost_estimate['final_cost'])
            
            return {
                'success': True,
                'estimated_cost': cost_estimate['base_cost'],
                'required_credits': cost_estimate['final_cost'],
                'current_credits': credit_check['current_credits'],
                'sufficient_credits': credit_check['sufficient'],
                'margin_applied': cost_estimate['margin_applied'],
                'service': cost_estimate['service'],
                'model': cost_estimate['model']
            }
            
        except Exception as e:
            logger.error(f"Error in estimate_and_check_meme_upscaling_operation: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'estimated_cost': 0.83,
                'required_credits': 1,
                'current_credits': self.get_user_credits(user_id),
                'sufficient_credits': False
            }
    
    def estimate_meme_to_video_cost(self):
        """
        Estimate meme to video generation cost
        
        Returns:
            dict: Complete cost estimation with all details
        """
        try:
            final_cost = get_image_to_video_cost()
            base_cost = get_base_image_to_video_cost()
            
            return {
                'base_cost': base_cost,
                'final_cost': final_cost,
                'margin_applied': self.default_margin,
                'service': 'fal.ai',
                'model': 'seedance-pro',
                'duration': 5,
                'resolution': '480p'
            }
            
        except Exception as e:
            logger.error(f"Error estimating meme to video cost: {str(e)}")
            return {
                'base_cost': 16.67,
                'final_cost': 20,
                'margin_applied': self.default_margin,
                'service': 'fal.ai',
                'model': 'seedance-pro',
                'error': str(e)
            }
    
    def estimate_and_check_meme_to_video_operation(self, user_id):
        """
        Estimate and check meme to video operation
        
        Args:
            user_id (str): User ID
            
        Returns:
            dict: Complete operation check with cost estimate and sufficiency
        """
        try:
            # Get cost estimate
            cost_estimate = self.estimate_meme_to_video_cost()
            
            # Check if user has sufficient credits
            credit_check = self.check_sufficient_credits(user_id, cost_estimate['final_cost'])
            
            return {
                'success': True,
                'estimated_cost': cost_estimate['base_cost'],
                'required_credits': cost_estimate['final_cost'],
                'current_credits': credit_check['current_credits'],
                'sufficient_credits': credit_check['sufficient'],
                'margin_applied': cost_estimate['margin_applied'],
                'service': cost_estimate['service'],
                'model': cost_estimate['model'],
                'duration': cost_estimate['duration']
            }
            
        except Exception as e:
            logger.error(f"Error in estimate_and_check_meme_to_video_operation: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'estimated_cost': 16.67,
                'required_credits': 20,
                'current_credits': self.get_user_credits(user_id),
                'sufficient_credits': False
            }
    
    def estimate_llm_cost_from_text(self, text_content, model_name=None, include_margin=True):
        """
        Estimate LLM cost from text content (for Claude)
        
        Args:
            text_content (str): Text content
            model_name (str): LLM model name (None uses Claude default)
            include_margin (bool): Whether to include margin
            
        Returns:
            dict: Complete cost estimation with all details
        """
        try:
            # If no model specified, use AI provider's default (Claude)
            if model_name is None:
                ai_provider = get_ai_provider()
                model_name = ai_provider.default_model
            
            # Rough estimate: 1 token ≈ 4 characters
            total_text_length = len(text_content)
            estimated_input_tokens = max(100, total_text_length // 4)
            estimated_output_tokens = max(50, estimated_input_tokens // 2)
            
            # Calculate base cost using Claude pricing
            base_cost = calculate_llm_cost(model_name, estimated_input_tokens, estimated_output_tokens)
            
            # Apply margin
            final_cost = apply_margin(base_cost, self.default_margin) if include_margin else base_cost
            
            return {
                'base_cost': base_cost,
                'final_cost': final_cost,
                'margin_applied': self.default_margin if include_margin else 0,
                'estimated_input_tokens': estimated_input_tokens,
                'estimated_output_tokens': estimated_output_tokens,
                'model_name': model_name
            }
            
        except Exception as e:
            logger.error(f"Error estimating LLM cost: {str(e)}")
            fallback_cost = get_min_llm_cost(model_name)
            final_cost = apply_margin(fallback_cost, self.default_margin) if include_margin else fallback_cost
            
            return {
                'base_cost': fallback_cost,
                'final_cost': final_cost,
                'margin_applied': self.default_margin if include_margin else 0,
                'estimated_input_tokens': 100,
                'estimated_output_tokens': 50,
                'model_name': model_name,
                'error': str(e)
            }
    
    def deduct_credits(self, user_id, amount, description, feature_id=None):
        """Deduct credits with proper floating point precision handling"""
        try:
            # Round to 4 decimal places for better precision with small amounts
            # Minimum charge of 0.0001 credits to avoid free API calls
            amount = max(0.0001, round(amount, 4))
            current_credits = self.get_user_credits(user_id)
            
            if current_credits < amount:
                return {
                    'success': False,
                    'message': f"Insufficient credits. Required: {amount}, Available: {current_credits}",
                    'credits_remaining': current_credits
                }
            
            # Calculate new balance outside transaction to avoid precision errors
            new_credits = round(current_credits - amount, 2)
            
            transaction_id = self.db.collection('users').document(user_id).collection('transactions').document().id
            
            transaction_data = {
                'id': transaction_id,
                'amount': -amount,
                'description': description,
                'feature_id': feature_id,
                'timestamp': datetime.now().isoformat(),
                'type': 'deduction'
            }
            
            transaction = self.db.transaction()
            
            @firestore.transactional
            def update_in_transaction(transaction, user_ref, new_credits, transaction_ref, transaction_data):
                # Update credits
                transaction.update(user_ref, {'credits': new_credits})
                
                # Add transaction record
                transaction.set(transaction_ref, transaction_data)
                
                return True
            
            # Execute transaction
            user_ref = self.db.collection('users').document(user_id)
            transaction_ref = user_ref.collection('transactions').document(transaction_id)
            
            update_in_transaction(transaction, user_ref, new_credits, transaction_ref, transaction_data)
            
            logger.info(f"Credits deduction successful for user {user_id}: {amount} credits")
            
            return {
                'success': True,
                'message': f"Successfully deducted {amount} credits",
                'credits_remaining': new_credits,
                'transaction_id': transaction_id
            }
            
        except Exception as e:
            logger.error(f"Error deducting credits: {str(e)}")
            return {
                'success': False,
                'message': f"Error deducting credits: {str(e)}",
                'credits_remaining': self.get_user_credits(user_id)
            }
    
    def deduct_meme_upscaling_credits(self, user_id, description, feature_id=None):
        """
        Deduct credits for meme upscaling usage
        
        Args:
            user_id (str): User ID
            description (str): Transaction description
            feature_id (str): Optional feature ID
            
        Returns:
            dict: Transaction result
        """
        try:
            # Get cost (1 credit)
            final_cost = get_image_upscaling_cost()
            
            # Enhanced description
            detailed_description = f"Meme Upscaling - {description}"
            
            # Deduct credits
            result = self.deduct_credits(user_id, final_cost, detailed_description, feature_id)
            
            if result['success']:
                logger.info(f"Meme upscaling credits deducted: {final_cost} credit")
                result['credits_cost'] = final_cost
                result['service'] = 'fal.ai'
                result['model'] = 'recraft/upscale/crisp'
            
            return result
            
        except Exception as e:
            logger.error(f"Error deducting meme upscaling credits: {str(e)}")
            return {
                'success': False,
                'message': f"Error deducting meme upscaling credits: {str(e)}",
                'credits_remaining': self.get_user_credits(user_id)
            }
    
    def deduct_meme_to_video_credits(self, user_id, description, feature_id=None):
        """
        Deduct credits for meme to video generation
        
        Args:
            user_id (str): User ID
            description (str): Transaction description
            feature_id (str): Optional feature ID
            
        Returns:
            dict: Transaction result
        """
        try:
            # Get cost (20 credits)
            final_cost = get_image_to_video_cost()
            
            # Enhanced description
            detailed_description = f"Meme to Video - {description}"
            
            # Deduct credits
            result = self.deduct_credits(user_id, final_cost, detailed_description, feature_id)
            
            if result['success']:
                logger.info(f"Meme to video credits deducted: {final_cost} credits")
                result['credits_cost'] = final_cost
                result['service'] = 'fal.ai'
                result['model'] = 'seedance-pro'
            
            return result
            
        except Exception as e:
            logger.error(f"Error deducting meme to video credits: {str(e)}")
            return {
                'success': False,
                'message': f"Error deducting meme to video credits: {str(e)}",
                'credits_remaining': self.get_user_credits(user_id)
            }
    
    def deduct_custom_search_credits(self, user_id, description):
        """
        Deduct credits for custom meme search
        
        Args:
            user_id (str): User ID
            description (str): Transaction description
            
        Returns:
            dict: Transaction result
        """
        try:
            # Get cost (0.5 credit)
            final_cost = get_custom_template_search_cost()
            
            # Enhanced description
            detailed_description = f"Meme Template Search - {description}"
            
            # Deduct credits
            result = self.deduct_credits(user_id, final_cost, detailed_description, "custom_meme_search")
            
            if result['success']:
                logger.info(f"Custom search credits deducted: {final_cost} credit")
                result['credits_cost'] = final_cost
                result['service'] = 'imgflip'
                result['api'] = 'search_memes'
            
            return result
            
        except Exception as e:
            logger.error(f"Error deducting custom search credits: {str(e)}")
            return {
                'success': False,
                'message': f"Error deducting custom search credits: {str(e)}",
                'credits_remaining': self.get_user_credits(user_id)
            }
    
    def deduct_llm_credits(self, user_id, model_name, input_tokens, output_tokens, description, feature_id=None):
        """
        Deduct credits for Claude LLM usage
        
        Args:
            user_id (str): User ID
            model_name (str): LLM model name
            input_tokens (int): Actual input tokens
            output_tokens (int): Actual output tokens
            description (str): Transaction description
            feature_id (str): Optional feature ID
            
        Returns:
            dict: Transaction result
        """
        try:
            # Calculate actual cost using Claude pricing
            actual_cost = calculate_llm_cost(model_name, input_tokens, output_tokens)
            
            # Apply margin
            credits_to_deduct = apply_margin(actual_cost, self.default_margin)
            
            # Enhanced description
            detailed_description = f"{description} - {input_tokens}in/{output_tokens}out tokens, {model_name}"
            
            # Deduct credits
            result = self.deduct_credits(user_id, credits_to_deduct, detailed_description, feature_id)
            
            if result['success']:
                logger.info(f"LLM credits deducted: {credits_to_deduct} credits (actual: {actual_cost:.4f}, margin: {self.default_margin*100}%)")
                result['actual_cost'] = actual_cost
                result['margin_applied'] = self.default_margin
                result['tokens_used'] = {'input': input_tokens, 'output': output_tokens}
            
            return result

        except Exception as e:
            logger.error(f"Error deducting LLM credits: {str(e)}")
            return {
                'success': False,
                'message': f"Error deducting LLM credits: {str(e)}",
                'credits_remaining': self.get_user_credits(user_id)
            }

    def deduct_nano_banana_credits(self, user_id, description, feature_id=None):
        """
        Deduct credits for Nano Banana edit usage

        Args:
            user_id (str): User ID
            description (str): Transaction description
            feature_id (str): Optional feature ID

        Returns:
            dict: Transaction result
        """
        try:
            # Get cost (5 credits)
            final_cost = get_nano_banana_cost()

            # Enhanced description
            detailed_description = f"Nano Banana Edit - {description}"

            # Deduct credits
            result = self.deduct_credits(user_id, final_cost, detailed_description, feature_id)

            if result['success']:
                logger.info(f"Nano Banana credits deducted: {final_cost} credits")
                result['credits_cost'] = final_cost
                result['service'] = 'fal.ai'
                result['model'] = 'fal-ai/nano-banana/edit'

            return result

        except Exception as e:
            logger.error(f"Error deducting Nano Banana credits: {str(e)}")
            return {
                'success': False,
                'message': f"Error deducting Nano Banana credits: {str(e)}",
                'credits_remaining': self.get_user_credits(user_id)
            }

    def deduct_seeddream_credits(self, user_id, description, feature_id=None):
        """
        Deduct credits for SeedDream edit usage

        Args:
            user_id (str): User ID
            description (str): Transaction description
            feature_id (str): Optional feature ID

        Returns:
            dict: Transaction result
        """
        try:
            # Get cost (4 credits)
            final_cost = get_seeddream_cost()

            # Enhanced description
            detailed_description = f"SeedDream Edit - {description}"

            # Deduct credits
            result = self.deduct_credits(user_id, final_cost, detailed_description, feature_id)

            if result['success']:
                logger.info(f"SeedDream credits deducted: {final_cost} credits")
                result['credits_cost'] = final_cost
                result['service'] = 'fal.ai'
                result['model'] = 'fal-ai/bytedance/seedream/v4/edit'

            return result

        except Exception as e:
            logger.error(f"Error deducting SeedDream credits: {str(e)}")
            return {
                'success': False,
                'message': f"Error deducting SeedDream credits: {str(e)}",
                'credits_remaining': self.get_user_credits(user_id)
            }
    
    def add_credits(self, user_id, amount, description, source=None):
        """Add credits with proper floating point precision handling"""
        try:
            # Round to 2 decimal places
            amount = round(amount, 2)
            
            # Get current credits
            current_credits = self.get_user_credits(user_id)
            new_credits = round(current_credits + amount, 2)
            
            transaction_id = self.db.collection('users').document(user_id).collection('transactions').document().id
            
            transaction_data = {
                'id': transaction_id,
                'amount': amount,
                'description': description,
                'source': source,
                'timestamp': datetime.now().isoformat(),
                'type': 'addition'
            }
            
            transaction = self.db.transaction()
            
            @firestore.transactional
            def update_in_transaction(transaction, user_ref, new_credits, transaction_ref, transaction_data):
                # Update credits
                transaction.update(user_ref, {'credits': new_credits})
                
                # Add transaction record
                transaction.set(transaction_ref, transaction_data)
                
                return True
            
            # Execute transaction
            user_ref = self.db.collection('users').document(user_id)
            transaction_ref = user_ref.collection('transactions').document(transaction_id)
            
            update_in_transaction(transaction, user_ref, new_credits, transaction_ref, transaction_data)
            
            logger.info(f"Credits addition successful for user {user_id}: {amount} credits, new balance: {new_credits}")
            
            return {
                'success': True,
                'message': f"Successfully added {amount} credits",
                'credits_remaining': new_credits,
                'transaction_id': transaction_id
            }
            
        except Exception as e:
            logger.error(f"Error adding credits: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': f"Error adding credits: {str(e)}"
            }
    
    def get_transaction_history(self, user_id, limit=20):
        """Get credit transaction history for a user"""
        try:
            query = self.db.collection('users').document(user_id).collection('transactions') \
                .order_by('timestamp', direction=firestore.Query.DESCENDING) \
                .limit(limit)
            
            transactions = []
            for doc in query.stream():
                transaction = doc.to_dict()
                transactions.append(transaction)
            
            logger.info(f"Retrieved {len(transactions)} transactions for user {user_id}")
            return transactions
        except Exception as e:
            logger.error(f"Error getting transaction history: {str(e)}")
            return []