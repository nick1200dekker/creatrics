"""
Credit costs configuration for soccer stats app
Updated with SeedDance Pro instead of Kling
"""

# CENTRALIZED MARGIN CONFIGURATION - Single source of truth
DEFAULT_MARGIN = 0.2  # 20% margin applied to all cost calculations

# Image Upscaling costs (Recraft Upscaler)
IMAGE_UPSCALING = {
    'COST': 1,                       # Final cost (with margin): 1 credit
    'BASE_COST': 0.83,              # Base cost (before margin): ~$0.0083
    'SERVICE': 'fal.ai',
    'MODEL': 'recraft/upscale/crisp',
    'DESCRIPTION': 'Image upscaling using Recraft Crisp Upscaler',
    'UPSCALE_FACTOR': '2x',          # Recraft upscaler provides 2x upscaling
    'MAX_INPUT_SIZE': '2048x2048'    # Maximum input image size
}

# Image to Video costs (ByteDance SeedDance Pro)
IMAGE_TO_VIDEO = {
    'COST': 20,                      # Final cost (with margin): 20 credits
    'BASE_COST': 16.67,             # Base cost (before margin): ~$0.1667
    'SERVICE': 'fal.ai',
    'MODEL': 'seedance-pro',
    'DESCRIPTION': 'Image to video animation using ByteDance SeedDance Pro 480p',
    'DURATION': 5,                   # Fixed 5 seconds
    'RESOLUTION': '480p'             # 480p quality
}

# Custom Template Search costs
CUSTOM_TEMPLATE_SEARCH = {
    'COST': 0.5,                     # Final cost (with margin): 0.5 credit
    'BASE_COST': 0.42,              # Base cost (before margin): ~$0.0042
    'SERVICE': 'imgflip',
    'API': 'search_memes',
    'DESCRIPTION': 'Custom template search from imgflip',
    'MAX_RESULTS': 20               # Maximum results per search
}

# Helper function to get image upscaling cost
def get_image_upscaling_cost():
    """Get the cost of image upscaling (1 credit)"""
    return IMAGE_UPSCALING['COST']

# Helper function to get base image upscaling cost (without margin)
def get_base_image_upscaling_cost():
    """Get the base cost of image upscaling (without margin)"""
    return IMAGE_UPSCALING['BASE_COST']

# Helper function to get image to video cost
def get_image_to_video_cost():
    """Get the cost of image to video generation (20 credits)"""
    return IMAGE_TO_VIDEO['COST']

# Helper function to get base image to video cost (without margin)
def get_base_image_to_video_cost():
    """Get the base cost of image to video generation (without margin)"""
    return IMAGE_TO_VIDEO['BASE_COST']

# Helper function to get custom template search cost
def get_custom_template_search_cost():
    """Get the cost of custom template search (0.5 credit)"""
    return CUSTOM_TEMPLATE_SEARCH['COST']

# Helper function to get base custom template search cost (without margin)
def get_base_custom_template_search_cost():
    """Get the base cost of custom template search (without margin)"""
    return CUSTOM_TEMPLATE_SEARCH['BASE_COST']

# Helper function to calculate LLM costs - Uses Claude
def calculate_llm_cost(model_name, input_tokens, output_tokens, cached_tokens=0):
    """
    Calculate the cost of an LLM API call in credits
    Uses Claude pricing via AI Provider Manager
    """
    try:
        # Lazy import to avoid circular dependencies
        from app.system.ai_provider.ai_provider import get_ai_provider
        
        # Get AI provider manager
        ai_provider = get_ai_provider()
        
        # If model_name is None, use the default model (Claude)
        if model_name is None:
            model_name = ai_provider.default_model
        
        # Calculate cost using AI provider's pricing
        base_cost = ai_provider.calculate_cost(input_tokens, output_tokens)
        
        # Add cached token cost if applicable
        if cached_tokens > 0:
            cached_cost = cached_tokens * 0.00005  # Default cached rate
            base_cost += cached_cost
        
        return round(base_cost, 4)
        
    except Exception as e:
        # Fallback to Claude pricing
        input_cost = input_tokens * 0.0003  # Claude Sonnet pricing
        output_cost = output_tokens * 0.0015
        cached_cost = cached_tokens * 0.00005
        
        total_cost = input_cost + output_cost + cached_cost
        return round(total_cost, 4)

# Helper function to get minimum credit cost for estimation
def get_min_llm_cost(model_name=None):
    """
    Get the minimum cost for an LLM call (useful for pre-checks)
    Uses Claude as the default model
    """
    if model_name is None:
        try:
            from app.system.ai_provider.ai_provider import get_ai_provider
            ai_provider = get_ai_provider()
            model_name = ai_provider.default_model
        except:
            model_name = 'claude-sonnet-4'  # Fallback
    
    return calculate_llm_cost(model_name, 50, 50)  # Estimate for small requests

# Helper function to apply margin to any cost
def apply_margin(base_cost, margin=None):
    """Apply the standard margin to a base cost"""
    if margin is None:
        margin = DEFAULT_MARGIN
    
    return round(base_cost * (1 + margin), 2)