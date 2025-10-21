"""
AI Provider Manager - Centralized management for multiple LLM providers
Simplified version with one model per provider
Updated with latest models and pricing as of October 2025
"""
import os
import logging
import requests
import base64
import json
from typing import Optional, Dict, Any, List
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

class AIProvider(Enum):
    """Supported AI providers"""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"
    GOOGLE = "google"  # NEW: Added Google/Gemini

class AIProviderManager:
    """Manages AI provider connections and model configurations"""
    
    # One model per provider with pricing (in credits where 1 credit = 1 cent)
    # Pricing updated as of October 2025
    PROVIDER_CONFIGS = {
        AIProvider.OPENAI: {
            'model_name': 'gpt-5-chat-latest',  # GPT-5 main (non-reasoning) chat model
            'display_name': 'gpt-5-chat',
            'input_cost_per_token': 0.00000125,    # $1.25 / 1M tokens
            'output_cost_per_token': 0.00001,      # $10.00 / 1M tokens
            'input_cost_cached': 0.000000125,      # $0.125 / 1M tokens (cached)
            'context_window': 200000,  # 200K tokens
            'supports_vision': True,
            'supports_functions': True
        },
        AIProvider.DEEPSEEK: {
            'model_name': 'deepseek-chat',  # DeepSeek-V3.2-Exp (October 2025)
            'display_name': 'deepseek-v3.2-exp',
            'input_cost_per_token': 0.00000028,   # $0.28 / 1M tokens (cache miss)
            'output_cost_per_token': 0.00000042,   # $0.42 / 1M tokens
            'input_cost_cached': 0.000000028,     # $0.028 / 1M tokens (cache hit)
            'context_window': 128000,  # 128K tokens
            'max_output_tokens': 8192,  # 8K max output
            'supports_vision': False,
            'supports_functions': True,
            'supports_json_output': True,
            'supports_chat_prefix': True,  # Chat Prefix Completion (Beta)
            'supports_fim': True  # FIM Completion (Beta)
        },
        AIProvider.CLAUDE: {
            'model_name': 'claude-sonnet-4-5-20250929',
            'display_name': 'claude-sonnet-4.5',
            'input_cost_per_token': 0.000003,    # $3.00 / 1M tokens
            'output_cost_per_token': 0.000015,   # $15.00 / 1M tokens
            'context_window': 200000,  # 200K tokens
            'supports_vision': True,
            'supports_functions': False,  # Claude doesn't support function calling same way
            'supports_extended_thinking': True  # Hybrid reasoning model
        },
        AIProvider.GOOGLE: {  # Google Gemini 2.5 Pro configuration (October 2025)
            'model_name': 'gemini-2.5-pro',  # Latest stable version
            'display_name': 'gemini-2.5-pro',
            # Pricing based on official Google rates (October 2025)
            'input_cost_per_token': 0.00000125,      # $1.25/1M tokens (≤200K tokens)
            'output_cost_per_token': 0.00001,        # $10.00/1M tokens (≤200K tokens)
            'input_cost_long_context': 0.0000025,    # $2.50/1M tokens (>200K tokens)
            'output_cost_long_context': 0.000015,    # $15.00/1M tokens (>200K tokens)
            'input_cost_cached': 0.000000125,        # $0.125/1M tokens (≤200K, cached)
            'input_cost_cached_long': 0.00000025,    # $0.25/1M tokens (>200K, cached)
            'long_context_threshold': 200000,        # 200K tokens threshold
            'context_window': 1048576,               # 1,048,576 input tokens
            'max_output_tokens': 65536,              # 65,536 output tokens
            'supports_vision': True,
            'supports_functions': True,
            'supports_thinking': True,                # Thinking model with reasoning
            'supports_multimodal': True,              # Audio, images, video, text, PDF
            'supports_grounding': True,               # Google Search & Maps grounding
            'supports_caching': True,                 # Context caching support
            'supports_structured_output': True        # Structured output support
        }
    }
    
    def __init__(self, script_name: Optional[str] = None, user_subscription: Optional[str] = None):
        """
        Initialize AI Provider Manager with optional script-specific and user-specific preferences

        Args:
            script_name: Name of the script/feature requesting AI (e.g., 'video_title', 'hook_generator')
            user_subscription: User's subscription plan (e.g., 'free', 'premium', 'admin')
        """
        self.script_name = script_name
        self.user_subscription = user_subscription

        # Get the primary provider based on preferences and user plan
        primary_provider = self._get_primary_provider()

        # Define fallback chain based on primary provider
        # Always: Primary → Claude → OpenAI → Google → DeepSeek
        all_providers = [AIProvider.CLAUDE, AIProvider.OPENAI, AIProvider.GOOGLE, AIProvider.DEEPSEEK]

        # Build fallback chain with primary provider first, then others
        self.fallback_chain = [primary_provider]
        for provider in all_providers:
            if provider != primary_provider:
                self.fallback_chain.append(provider)

        self.current_provider_index = 0
        # Start with the primary provider
        self.provider = primary_provider
        self.config = self.PROVIDER_CONFIGS[self.provider]
        self._client = None
        
    def _load_preferences(self) -> Dict[str, Any]:
        """Load AI provider preferences from JSON file"""
        try:
            # Get project root (4 levels up from this file)
            config_dir = Path(__file__).parent.parent.parent.parent / 'config'
            prefs_file = config_dir / 'ai_provider_preferences.json'

            if prefs_file.exists():
                with open(prefs_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.debug(f"Could not load AI provider preferences: {e}")

        return {
            'free_users_deepseek': False,
            'script_preferences': {}
        }

    def _get_primary_provider(self) -> AIProvider:
        """
        Get the primary AI provider based on:
        1. User subscription plan (free users may be forced to DeepSeek)
        2. Script-specific preferences from admin config
        3. Environment variable
        4. Default to Claude
        """
        preferences = self._load_preferences()

        # Map string to enum
        provider_map = {
            'claude': AIProvider.CLAUDE,
            'openai': AIProvider.OPENAI,
            'deepseek': AIProvider.DEEPSEEK,
            'google': AIProvider.GOOGLE,
            'gemini': AIProvider.GOOGLE,  # Alternative name for Google
        }

        # 1. Check script-specific preferences (for premium users or when free toggle is off)
        if self.script_name:
            script_prefs = preferences.get('script_preferences', {})
            if self.script_name in script_prefs:
                preferred_provider = script_prefs[self.script_name]
                if preferred_provider in provider_map:
                    # Check if free users should be overridden to DeepSeek
                    free_users_toggle = preferences.get('free_users_deepseek', False)

                    if free_users_toggle:
                        # Check if this user is a free user
                        is_free_user = (
                            self.user_subscription is not None and
                            self.user_subscription.lower().strip() in ['free', 'free plan', '']
                        )

                        if is_free_user:
                            logger.info(f"Free user detected - using DeepSeek")
                            return AIProvider.DEEPSEEK

                    # Use the preferred provider
                    logger.debug(f"Using preferred provider for {self.script_name}: {preferred_provider}")
                    return provider_map[preferred_provider]

        # 2. Check if free users should be forced to DeepSeek (when no script preference exists)
        if preferences.get('free_users_deepseek', False):
            is_free_user = self.user_subscription and self.user_subscription.lower().strip() in ['free', 'free plan', '']
            if is_free_user:
                logger.info(f"Free user detected - forcing DeepSeek provider (no script preference)")
                return AIProvider.DEEPSEEK

        # 3. Fall back to environment variable
        provider_str = os.environ.get('AI_PROVIDER', 'claude').lower()
        if provider_str in provider_map:
            return provider_map[provider_str]

        # 4. Default to Claude
        logger.warning(f"Unknown AI provider configuration, defaulting to Claude")
        return AIProvider.CLAUDE

    def _get_provider_from_env(self) -> AIProvider:
        """Get the primary AI provider from environment variable (legacy method)"""
        provider_str = os.environ.get('AI_PROVIDER', 'claude').lower()

        # Map string to enum
        provider_map = {
            'claude': AIProvider.CLAUDE,
            'openai': AIProvider.OPENAI,
            'deepseek': AIProvider.DEEPSEEK,
            'google': AIProvider.GOOGLE,
            'gemini': AIProvider.GOOGLE,  # Alternative name for Google
        }

        if provider_str not in provider_map:
            logger.warning(f"Unknown AI provider: {provider_str}, defaulting to Claude")
            return AIProvider.CLAUDE

        return provider_map[provider_str]

    def _get_provider(self) -> AIProvider:
        """Get the current provider (kept for backward compatibility)"""
        return self.provider

    def _switch_to_next_provider(self) -> bool:
        """Switch to the next provider in the fallback chain
        Returns True if successful, False if no more providers available"""
        self.current_provider_index += 1

        if self.current_provider_index >= len(self.fallback_chain):
            logger.error("All AI providers in fallback chain have failed")
            return False

        # Switch to next provider
        self.provider = self.fallback_chain[self.current_provider_index]
        self.config = self.PROVIDER_CONFIGS[self.provider]
        self._client = None  # Reset client to force reinitialization

        logger.info(f"Switching to fallback provider: {self.provider.value}")
        return True

    def _reset_to_primary_provider(self):
        """Reset to the primary provider from environment"""
        self.current_provider_index = 0
        self.provider = self.fallback_chain[0]  # Primary from AI_PROVIDER env
        self.config = self.PROVIDER_CONFIGS[self.provider]
        self._client = None

    @property
    def default_model(self) -> str:
        """Get the display name of the current provider's model"""
        return self.config['display_name']
    
    @property
    def api_model_name(self) -> str:
        """Get the actual API model name"""
        return self.config['model_name']
    
    def get_client(self):
        """Get AI client for the current provider"""
        if self._client is not None:
            return self._client
            
        try:
            # Clear proxy environment variables
            for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
                if proxy_var in os.environ:
                    os.environ.pop(proxy_var, None)
                    
            if self.provider == AIProvider.OPENAI:
                from openai import OpenAI
                api_key = os.environ.get('OPENAI_API_KEY', '')
                if not api_key:
                    logger.error("OpenAI API key not found")
                    return None
                self._client = OpenAI(api_key=api_key)
                
            elif self.provider == AIProvider.DEEPSEEK:
                from openai import OpenAI  # DeepSeek uses OpenAI-compatible API
                api_key = os.environ.get('DEEPSEEK_API_KEY', '')
                if not api_key:
                    logger.error("DeepSeek API key not found")
                    return None
                self._client = OpenAI(
                    api_key=api_key,
                    base_url="https://api.deepseek.com/v1"
                )
                
            elif self.provider == AIProvider.CLAUDE:
                from anthropic import Anthropic
                api_key = os.environ.get('CLAUDE_API_KEY', '')
                if not api_key:
                    logger.error("Claude API key not found")
                    return None
                self._client = Anthropic(api_key=api_key)
                
            elif self.provider == AIProvider.GOOGLE:  # NEW: Google Gemini client initialization
                from google import genai
                # Support both GOOGLE_API_KEY and GEMINI_API_KEY environment variables
                api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY', '')
                if not api_key:
                    logger.error("Google/Gemini API key not found. Set GOOGLE_API_KEY or GEMINI_API_KEY")
                    return None
                self._client = genai.Client(api_key=api_key)
                
            return self._client
            
        except ImportError as e:
            logger.error(f"Required package not installed for {self.provider}: {e}")
            if self.provider == AIProvider.GOOGLE:
                logger.error("Install required package: pip install google-genai")
            else:
                logger.error("Install required package: pip install anthropic (for Claude)")
            return None
        except Exception as e:
            logger.error(f"Error initializing {self.provider} client: {e}")
            return None
    
    def create_completion(self, messages: List[Dict[str, str]],
                         temperature: float = 0.7,
                         max_tokens: int = 4096,  # INCREASED: Default was too low for Google Gemini
                         **kwargs) -> Dict[str, Any]:
        """
        Create a completion using the configured provider with automatic fallback
        Returns unified response format regardless of provider
        Fallback chain: Primary → next providers in chain
        """
        # Reset to primary provider if this is a new request after all providers failed
        if self.current_provider_index >= len(self.fallback_chain):
            self._reset_to_primary_provider()

        max_retries = len(self.fallback_chain)
        last_error = None

        for attempt in range(max_retries):
            try:
                client = self.get_client()
                if not client:
                    logger.error(f"Failed to initialize client for provider: {self.provider.value}")
                    if not self._switch_to_next_provider():
                        raise ValueError(f"All providers failed. Last error: {last_error}")
                    continue

                # Try to create completion with current provider
                return self._create_completion_internal(client, messages, temperature, max_tokens, **kwargs)

            except Exception as e:
                last_error = str(e)
                logger.error(f"Provider {self.provider.value} failed: {last_error}")

                # If this is not the last provider, try the next one
                if attempt < max_retries - 1 and self._switch_to_next_provider():
                    logger.info(f"Retrying with {self.provider.value}...")
                    continue
                else:
                    # All providers have failed
                    raise ValueError(f"All AI providers failed. Last error: {last_error}")

        # This should never be reached, but just in case
        raise ValueError(f"Failed to get response from any provider. Last error: {last_error}")

    def _create_completion_internal(self, client, messages: List[Dict[str, str]],
                                   temperature: float = 0.7,
                                   max_tokens: int = 4096,
                                   **kwargs) -> Dict[str, Any]:
        """
        Internal method to create completion with a specific client
        """
        try:
            if self.provider in [AIProvider.OPENAI, AIProvider.DEEPSEEK]:
                # OpenAI-compatible API
                api_kwargs = {
                    'model': self.api_model_name,
                    'messages': messages,
                    **kwargs
                }

                # All OpenAI models and DeepSeek use standard chat API
                api_kwargs['temperature'] = temperature
                api_kwargs['max_tokens'] = max_tokens

                logger.debug(f"OpenAI request: model={api_kwargs['model']}, params={list(api_kwargs.keys())}")
                response = client.chat.completions.create(**api_kwargs)

                # Validate response has content
                content = response.choices[0].message.content
                logger.debug(f"OpenAI response content length: {len(content) if content else 0}")

                if content is None or (isinstance(content, str) and not content.strip()):
                    # Log the full response for debugging
                    logger.error(f"Empty OpenAI response. Finish reason: {response.choices[0].finish_reason if response.choices else 'unknown'}")
                    logger.error(f"Response object: {response}")
                    raise ValueError(f"Empty response from {self.provider.value} (HTTP 200 but no content)")

                # Return unified format
                return {
                    'content': content,
                    'model': self.default_model,
                    'usage': {
                        'input_tokens': response.usage.prompt_tokens if hasattr(response, 'usage') else 0,
                        'output_tokens': response.usage.completion_tokens if hasattr(response, 'usage') else 0,
                        'total_tokens': response.usage.total_tokens if hasattr(response, 'usage') else 0
                    },
                    'provider': self.provider.value,
                    'provider_enum': self.provider,  # Add enum for cost calculation
                    'raw_response': response
                }
                
            elif self.provider == AIProvider.CLAUDE:
                # Anthropic API has different format
                # Convert messages to Claude format
                system_message = None
                claude_messages = []
                
                for msg in messages:
                    if msg['role'] == 'system':
                        system_message = msg['content']
                    else:
                        # Claude uses 'user' and 'assistant' roles
                        role = 'user' if msg['role'] == 'user' else 'assistant'
                        claude_messages.append({
                            'role': role,
                            'content': msg['content']
                        })
                
                # Claude API call with proper system message handling
                kwargs_claude = {
                    'model': self.api_model_name,
                    'messages': claude_messages,
                    'temperature': temperature,
                    'max_tokens': max_tokens
                }

                # Only add system if it exists and is a string
                if system_message and isinstance(system_message, str):
                    kwargs_claude['system'] = system_message

                response = client.messages.create(**kwargs_claude)

                # Validate response has content
                content = response.content[0].text if response.content else ''
                if not content or not content.strip():
                    raise ValueError(f"Empty response from {self.provider.value} (HTTP 200 but no content)")

                # Return unified format
                return {
                    'content': content,
                    'model': self.default_model,
                    'usage': {
                        'input_tokens': response.usage.input_tokens if hasattr(response, 'usage') else 0,
                        'output_tokens': response.usage.output_tokens if hasattr(response, 'usage') else 0,
                        'total_tokens': (response.usage.input_tokens + response.usage.output_tokens) if hasattr(response, 'usage') else 0
                    },
                    'provider': self.provider.value,
                    'provider_enum': self.provider,  # Add enum for cost calculation
                    'raw_response': response
                }
                
            elif self.provider == AIProvider.GOOGLE:  # NEW: Google Gemini API integration
                from google.genai import types
                
                # Convert messages to Gemini format
                # Gemini expects contents as a list of parts
                formatted_messages = []
                system_instruction = None
                
                for msg in messages:
                    if msg['role'] == 'system':
                        system_instruction = msg['content']
                    elif msg['role'] == 'user':
                        # Handle both string and list content (for potential image inputs)
                        if isinstance(msg['content'], list):
                            # Extract text parts from list content
                            text_parts = []
                            for part in msg['content']:
                                if isinstance(part, dict) and part.get('type') == 'text':
                                    text_parts.append(part.get('text', ''))
                                elif isinstance(part, str):
                                    text_parts.append(part)
                            formatted_messages.append(' '.join(text_parts))
                        else:
                            formatted_messages.append(msg['content'])
                    elif msg['role'] == 'assistant':
                        # For chat history, we need to track both user and assistant messages
                        # For now, we'll concatenate them as context
                        if isinstance(msg['content'], str):
                            formatted_messages.append(f"Assistant: {msg['content']}")

                # Combine all messages into a single prompt for simplicity
                # In production, you'd want to use the chat interface for proper conversation handling
                combined_content = '\n'.join(str(m) for m in formatted_messages if m)
                
                # Create generation config
                # Force higher max_output_tokens for Google Gemini to prevent truncation
                # Use requested tokens but ensure minimum of 4096 to avoid truncation
                google_max_tokens = max(max_tokens, 4096) if max_tokens else 8192
                # Don't limit by config max, let Google handle its own limits
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=google_max_tokens,
                    system_instruction=system_instruction if system_instruction else None
                )
                
                response = client.models.generate_content(
                    model=self.api_model_name,
                    contents=combined_content,
                    config=config
                )
                
                # FIXED: Properly extract text content from Google Gemini response
                response_text = ""
                finish_reason = None
                
                try:
                    # Check finish reason first
                    if hasattr(response, 'candidates') and response.candidates:
                        candidate = response.candidates[0]
                        finish_reason = getattr(candidate, 'finish_reason', None)
                        
                        # Handle MAX_TOKENS case
                        if finish_reason and str(finish_reason) == 'FinishReason.MAX_TOKENS':
                            logger.warning(f"Google Gemini hit max tokens limit. Consider increasing max_output_tokens.")
                    
                    # Google Gemini response can have different structures
                    if hasattr(response, 'text') and response.text:
                        response_text = response.text
                    elif hasattr(response, 'candidates') and response.candidates:
                        # Get first candidate
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'content') and candidate.content:
                            if hasattr(candidate.content, 'parts') and candidate.content.parts:
                                # Get text from first part
                                first_part = candidate.content.parts[0]
                                if hasattr(first_part, 'text'):
                                    response_text = first_part.text
                            else:
                                # parts is None - this is the issue we're seeing
                                logger.warning(f"Google Gemini response has no parts. Finish reason: {finish_reason}")
                    
                    # Handle empty response based on finish reason
                    if not response_text:
                        if finish_reason and str(finish_reason) == 'FinishReason.MAX_TOKENS':
                            response_text = "[Response truncated due to max tokens limit]"
                        else:
                            logger.warning(f"No text content found in Google Gemini response. Finish reason: {finish_reason}")
                            response_text = "[No response generated]"
                        
                except Exception as e:
                    logger.error(f"Error extracting text from Google Gemini response: {e}")
                    response_text = "[Error processing response]"
                
                # Validate response has actual content (not error placeholders)
                if response_text in ["[Error processing response]", "[No response generated]", "[Response truncated due to max tokens limit]"]:
                    raise ValueError(f"Invalid response from Google Gemini: {response_text}")

                if not response_text or not response_text.strip():
                    raise ValueError(f"Empty response from {self.provider.value} (HTTP 200 but no content)")

                # Extract usage information if available
                usage_metadata = getattr(response, 'usage_metadata', None)
                input_tokens = usage_metadata.prompt_token_count if usage_metadata else 0
                output_tokens = usage_metadata.candidates_token_count if usage_metadata else 0
                total_tokens = usage_metadata.total_token_count if usage_metadata else 0

                # Log token usage for debugging
                if usage_metadata:
                    logger.info(f"Google Gemini token usage - Input: {input_tokens}, Output: {output_tokens}, Total: {total_tokens}")

                # Return unified format
                return {
                    'content': response_text,  # FIXED: Now guaranteed to be a string
                    'model': self.default_model,
                    'usage': {
                        'input_tokens': input_tokens,
                        'output_tokens': output_tokens,
                        'total_tokens': total_tokens
                    },
                    'provider': self.provider.value,
                    'provider_enum': self.provider,  # Add enum for cost calculation
                    'raw_response': response
                }
                
        except Exception as e:
            logger.error(f"Error creating completion with {self.provider}: {e}")
            raise
    
    def _convert_url_to_base64(self, image_url: str) -> Dict[str, str]:
        """
        Convert an image URL to base64 format for vision APIs
        Returns dict with 'data' and 'media_type' keys
        """
        try:
            logger.info(f"Fetching image from URL: {image_url[:100]}...")
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Get content type
            content_type = response.headers.get('content-type', 'image/jpeg')
            
            # Convert to base64
            image_data = base64.b64encode(response.content).decode('utf-8')
            
            logger.info(f"Successfully converted image to base64. Size: {len(image_data)} chars, Type: {content_type}")
            
            return {
                'data': image_data,
                'media_type': content_type
            }
            
        except Exception as e:
            logger.error(f"Error converting URL to base64: {str(e)}")
            raise
    
    def create_vision_completion(self, messages_with_images: List[Dict[str, Any]],
                               **kwargs) -> Dict[str, Any]:
        """
        Create a completion with image inputs with automatic fallback
        Falls back to next vision-capable provider if current fails
        Fallback chain: Primary → next vision-capable providers
        """
        # Reset to primary provider if this is a new request after all providers failed
        if self.current_provider_index >= len(self.fallback_chain):
            self._reset_to_primary_provider()

        max_retries = len(self.fallback_chain)
        last_error = None

        for attempt in range(max_retries):
            # Skip providers that don't support vision
            while not self.config.get('supports_vision', False):
                logger.info(f"Provider {self.provider.value} doesn't support vision, skipping...")
                if not self._switch_to_next_provider():
                    raise ValueError(f"No vision-capable providers available. Last error: {last_error}")

            try:
                client = self.get_client()
                if not client:
                    logger.error(f"Failed to initialize client for provider: {self.provider.value}")
                    if not self._switch_to_next_provider():
                        raise ValueError(f"All vision providers failed. Last error: {last_error}")
                    continue

                # Try vision completion with current provider
                return self._create_vision_completion_internal(client, messages_with_images, **kwargs)

            except Exception as e:
                last_error = str(e)
                logger.error(f"Vision provider {self.provider.value} failed: {last_error}")

                # If this is not the last provider, try the next one
                if attempt < max_retries - 1 and self._switch_to_next_provider():
                    logger.info(f"Retrying vision with {self.provider.value}...")
                    continue
                else:
                    # All providers have failed
                    raise ValueError(f"All vision-capable AI providers failed. Last error: {last_error}")

        raise ValueError(f"Failed to get vision response from any provider. Last error: {last_error}")

    def _create_vision_completion_internal(self, client, messages_with_images: List[Dict[str, Any]],
                               **kwargs) -> Dict[str, Any]:
        """
        Internal method to create vision completion with a specific client
        """
        if not self.config['supports_vision']:
            raise ValueError(f"Provider {self.provider.value} does not support vision inputs")
        # For vision, we need to format messages differently based on provider
        if self.provider == AIProvider.OPENAI:
            # OpenAI format - use GPT-5 vision capabilities
            return self._create_completion_internal(client, messages_with_images, **kwargs)
            
        elif self.provider == AIProvider.CLAUDE:
            # Claude needs special handling for images
            formatted_messages = []
            system_message = None
            
            for msg in messages_with_images:
                if msg['role'] == 'system':
                    system_message = msg['content']
                elif msg['role'] == 'user':
                    if isinstance(msg['content'], list):
                        # Handle multi-part content with images
                        claude_content = []
                        for part in msg['content']:
                            if part['type'] == 'text':
                                claude_content.append({
                                    'type': 'text',
                                    'text': part['text']
                                })
                            elif part['type'] == 'image_url':
                                # Handle both base64 and regular URLs
                                image_data = part['image_url']['url']
                                
                                if image_data.startswith('data:'):
                                    # Extract mime type and base64 data from data URI
                                    header, base64_data = image_data.split(',', 1)
                                    mime_type = header.split(':')[1].split(';')[0]
                                    
                                    # Ensure proper format for JPEG images
                                    if mime_type == 'image/jpeg' and not base64_data.strip():
                                        logger.warning(f"Empty base64 data for {mime_type}")
                                        continue
                                        
                                    # Validate base64 data
                                    try:
                                        # Verify we can decode it
                                        _ = base64.b64decode(base64_data)
                                    except Exception as e:
                                        logger.error(f"Invalid base64 data: {str(e)}")
                                        continue
                                    
                                    claude_content.append({
                                        'type': 'image',
                                        'source': {
                                            'type': 'base64',
                                            'media_type': mime_type,
                                            'data': base64_data
                                        }
                                    })
                                
                                elif image_data.startswith('http'):
                                    # Convert regular URL to base64
                                    try:
                                        converted = self._convert_url_to_base64(image_data)
                                        claude_content.append({
                                            'type': 'image',
                                            'source': {
                                                'type': 'base64',
                                                'media_type': converted['media_type'],
                                                'data': converted['data']
                                            }
                                        })
                                    except Exception as e:
                                        logger.error(f"Failed to convert URL to base64: {str(e)}")
                                        continue
                                else:
                                    logger.warning(f"Unknown image format: {image_data[:50]}...")
                                    continue
                        
                        formatted_messages.append({
                            'role': 'user',
                            'content': claude_content
                        })
                    else:
                        formatted_messages.append({
                            'role': 'user',
                            'content': msg['content']
                        })
                else:
                    formatted_messages.append({
                        'role': msg['role'],
                        'content': msg['content']
                    })
            
            # Create completion with formatted messages
            client = self.get_client()

            # Prepare kwargs for the API call
            api_kwargs = {
                'model': self.api_model_name,
                'messages': formatted_messages,
                **kwargs
            }

            # Add system message if present (must be a list for newer Claude API)
            if system_message:
                if isinstance(system_message, str):
                    api_kwargs['system'] = [{'type': 'text', 'text': system_message}]
                else:
                    api_kwargs['system'] = system_message

            response = client.messages.create(**api_kwargs)
            
            return {
                'content': response.content[0].text if response.content else '',
                'model': self.default_model,
                'usage': {
                    'input_tokens': response.usage.input_tokens if hasattr(response, 'usage') else 0,
                    'output_tokens': response.usage.output_tokens if hasattr(response, 'usage') else 0,
                    'total_tokens': (response.usage.input_tokens + response.usage.output_tokens) if hasattr(response, 'usage') else 0
                },
                'provider': self.provider.value,
                'provider_enum': self.provider,  # Add enum for cost calculation
                'raw_response': response
            }
            
        elif self.provider == AIProvider.GOOGLE:  # NEW: Google Gemini vision support
            from google.genai import types
            
            client = self.get_client()
            
            # Convert messages to Gemini format with multimodal content
            content_parts = []
            system_instruction = None
            
            for msg in messages_with_images:
                if msg['role'] == 'system':
                    system_instruction = msg['content']
                elif msg['role'] == 'user':
                    if isinstance(msg['content'], list):
                        # Handle multi-part content with images
                        for part in msg['content']:
                            if part['type'] == 'text':
                                content_parts.append(part['text'])  # Just add text directly
                            elif part['type'] == 'image_url':
                                # Handle base64 image data
                                image_data = part['image_url']['url']
                                if image_data.startswith('data:'):
                                    # Extract mime type and base64 data
                                    header, base64_data = image_data.split(',', 1)
                                    mime_type = header.split(':')[1].split(';')[0]

                                    image_bytes = base64.b64decode(base64_data)
                                    content_parts.append(types.Part.from_bytes(
                                        data=image_bytes,
                                        mime_type=mime_type
                                    ))
                    else:
                        content_parts.append(msg['content'])  # Just add text directly
            
            # Create generation config
            # Extract max_tokens from kwargs and ensure proper value for Google
            max_tokens = kwargs.pop('max_tokens', 8192)
            # Force minimum of 4096 tokens to prevent truncation
            google_max_tokens = max(max_tokens, 4096)

            config = types.GenerateContentConfig(
                system_instruction=system_instruction if system_instruction else None,
                max_output_tokens=google_max_tokens,
                **kwargs
            )
            
            response = client.models.generate_content(
                model=self.api_model_name,
                contents=content_parts,
                config=config
            )
            
            # FIXED: Use same robust text extraction as regular completion
            response_text = ""
            finish_reason = None
            
            try:
                # Check finish reason first
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    finish_reason = getattr(candidate, 'finish_reason', None)
                    
                    # Handle MAX_TOKENS case
                    if finish_reason and str(finish_reason) == 'FinishReason.MAX_TOKENS':
                        logger.warning(f"Google Gemini vision hit max tokens limit. Consider increasing max_output_tokens.")
                
                # Google Gemini response can have different structures
                if hasattr(response, 'text') and response.text:
                    response_text = response.text
                elif hasattr(response, 'candidates') and response.candidates:
                    # Get first candidate
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and candidate.content:
                        if hasattr(candidate.content, 'parts') and candidate.content.parts:
                            # Get text from first part
                            first_part = candidate.content.parts[0]
                            if hasattr(first_part, 'text'):
                                response_text = first_part.text
                        else:
                            # parts is None - this is the issue we're seeing
                            logger.warning(f"Google Gemini vision response has no parts. Finish reason: {finish_reason}")
                
                # Handle empty response based on finish reason
                if not response_text:
                    if finish_reason and str(finish_reason) == 'FinishReason.MAX_TOKENS':
                        response_text = "[Response truncated due to max tokens limit]"
                    else:
                        logger.warning(f"No text content found in Google Gemini vision response. Finish reason: {finish_reason}")
                        response_text = "[No response generated]"
                    
            except Exception as e:
                logger.error(f"Error extracting text from Google Gemini vision response: {e}")
                response_text = "[Error processing response]"
            
            # Extract usage information if available
            usage_metadata = getattr(response, 'usage_metadata', None)
            input_tokens = usage_metadata.prompt_token_count if usage_metadata else 0
            output_tokens = usage_metadata.candidates_token_count if usage_metadata else 0
            total_tokens = usage_metadata.total_token_count if usage_metadata else 0
            
            return {
                'content': response_text,  # FIXED: Now guaranteed to be a string
                'model': self.default_model,
                'usage': {
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total_tokens': total_tokens
                },
                'provider': self.provider.value,
                'provider_enum': self.provider,  # Add enum for cost calculation
                'raw_response': response
            }
        else:
            raise ValueError(f"Vision not implemented for provider {self.provider.value}")
    
    def estimate_tokens(self, text: str) -> int:
        """Rough estimate of tokens in text (provider-agnostic)"""
        # Simple estimation: 1 token ≈ 4 characters
        return max(1, len(text) // 4)
    
    def calculate_cost(self, input_tokens: int, output_tokens: int, use_cached_rate: bool = False) -> float:
        """Calculate cost in credits for given token usage (1 credit = $0.01)"""
        if self.provider == AIProvider.DEEPSEEK and use_cached_rate and 'input_cost_cached' in self.config:
            # Use cached rate for DeepSeek if available
            input_cost = input_tokens * self.config['input_cost_cached']
        elif self.provider == AIProvider.GOOGLE:  # NEW: Google Gemini dynamic pricing based on context length
            # Check if this is a long context request (>200K tokens)
            long_context_threshold = self.config.get('long_context_threshold', 200000)

            if input_tokens > long_context_threshold:
                # Use long context pricing
                input_cost = input_tokens * self.config['input_cost_long_context']
                output_cost = output_tokens * self.config['output_cost_long_context']
            else:
                # Use standard pricing
                input_cost = input_tokens * self.config['input_cost_per_token']
                output_cost = output_tokens * self.config['output_cost_per_token']

            # Convert dollars to credits (1 credit = $0.01)
            total_dollars = input_cost + output_cost
            return round(total_dollars / 0.01, 4)
        else:
            input_cost = input_tokens * self.config['input_cost_per_token']

        output_cost = output_tokens * self.config['output_cost_per_token']

        # Convert dollars to credits (1 credit = $0.01)
        total_dollars = input_cost + output_cost
        return round(total_dollars / 0.01, 4)
    
    def get_model_pricing(self) -> Dict[str, Any]:
        """Get current model's pricing information"""
        pricing = {
            'model': self.default_model,
            'provider': self.provider.value,
            'input_cost_per_token': self.config['input_cost_per_token'],
            'output_cost_per_token': self.config['output_cost_per_token'],
            'context_window': self.config.get('context_window', 128000),
            'supports_vision': self.config['supports_vision'],
            'supports_functions': self.config['supports_functions']
        }
        
        # Add cached pricing for DeepSeek
        if 'input_cost_cached' in self.config:
            pricing['input_cost_cached'] = self.config['input_cost_cached']
        
        # Add long context pricing for Google
        if self.provider == AIProvider.GOOGLE:
            pricing['input_cost_long_context'] = self.config['input_cost_long_context']
            pricing['output_cost_long_context'] = self.config['output_cost_long_context']
            pricing['long_context_threshold'] = self.config['long_context_threshold']
            pricing['supports_thinking'] = self.config['supports_thinking']
            pricing['supports_multimodal'] = self.config['supports_multimodal']
            
        return pricing

# Singleton instance (kept for backward compatibility)
_ai_provider_manager = None

def get_ai_provider(script_name: Optional[str] = None, user_subscription: Optional[str] = None) -> AIProviderManager:
    """
    Get an AI provider manager instance

    Args:
        script_name: Name of the script/feature requesting AI (e.g., 'video_title', 'hook_generator')
        user_subscription: User's subscription plan (e.g., 'free', 'premium', 'admin')

    Returns:
        AIProviderManager instance configured for the specific script and user

    Note:
        If script_name or user_subscription is provided, a new instance is created.
        Otherwise, returns the singleton instance for backward compatibility.
    """
    # If specific configuration is requested, create a new instance
    if script_name is not None or user_subscription is not None:
        return AIProviderManager(script_name=script_name, user_subscription=user_subscription)

    # Otherwise use singleton for backward compatibility
    global _ai_provider_manager
    if _ai_provider_manager is None:
        _ai_provider_manager = AIProviderManager()
    return _ai_provider_manager

# Convenience functions for backward compatibility
def get_client():
    """Get the default AI client"""
    return get_ai_provider().get_client()

def get_default_model():
    """Get the default model name"""
    return get_ai_provider().default_model

def create_completion(messages, **kwargs):
    """Create a completion with the default provider"""
    return get_ai_provider().create_completion(messages, **kwargs)