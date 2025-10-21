"""Admin routes package"""
from flask import Blueprint

# Import blueprints
from .ai_provider_routes import ai_provider_bp

# Export blueprints
__all__ = ['ai_provider_bp']
