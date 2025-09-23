"""
Credit costs configuration for creator tools app
Only LLM and Fal AI models
"""

# CENTRALIZED MARGIN CONFIGURATION - Single source of truth
DEFAULT_MARGIN = 0.2  # 20% margin applied to all cost calculations

# Fal AI - Nano Banana Edit costs
FAL_NANO_BANANA = {
    'COST': 5,                       # Final cost: 5 credits per generation
    'BASE_COST': 4.17,              # Base cost (before margin)
    'SERVICE': 'fal.ai',
    'MODEL': 'fal-ai/nano-banana/edit',
    'DESCRIPTION': 'Image editing using Nano Banana model',
    'MAX_IMAGES': 4                 # Maximum input images
}

# Fal AI - ByteDance SeedDream V4 Edit costs
FAL_SEEDDREAM = {
    'COST': 4,                      # Final cost: 4 credits per generation
    'BASE_COST': 3.33,             # Base cost (before margin)
    'SERVICE': 'fal.ai',
    'MODEL': 'fal-ai/bytedance/seedream/v4/edit',
    'DESCRIPTION': 'Image editing using ByteDance SeedDream V4',
    'MAX_IMAGES': 4                # Maximum input images
}

# Fal AI - Topaz Upscale costs
FAL_TOPAZ_UPSCALE = {
    'COST': 10,                     # Final cost: 10 credits per upscale
    'BASE_COST': 8.33,             # Base cost (before margin)
    'SERVICE': 'fal.ai',
    'MODEL': 'fal-ai/topaz/upscale/image',
    'DESCRIPTION': 'Image upscaling using Topaz AI model',
    'SCALE_FACTOR': 4               # Upscale factor (up to 4x)
}

# Helper function to get Nano Banana cost
def get_nano_banana_cost():
    """Get the cost of Nano Banana edit (5 credits)"""
    return FAL_NANO_BANANA['COST']

# Helper function to get base Nano Banana cost (without margin)
def get_base_nano_banana_cost():
    """Get the base cost of Nano Banana edit (without margin)"""
    return FAL_NANO_BANANA['BASE_COST']

# Helper function to get SeedDream cost
def get_seeddream_cost():
    """Get the cost of SeedDream edit (4 credits)"""
    return FAL_SEEDDREAM['COST']

# Helper function to get base SeedDream cost (without margin)
def get_base_seeddream_cost():
    """Get the base cost of SeedDream edit (without margin)"""
    return FAL_SEEDDREAM['BASE_COST']

# Helper function to get Topaz upscale cost
def get_topaz_upscale_cost():
    """Get the cost of Topaz upscale (10 credits)"""
    return FAL_TOPAZ_UPSCALE['COST']

# Helper function to get base Topaz upscale cost (without margin)
def get_base_topaz_upscale_cost():
    """Get the base cost of Topaz upscale (without margin)"""
    return FAL_TOPAZ_UPSCALE['BASE_COST']

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