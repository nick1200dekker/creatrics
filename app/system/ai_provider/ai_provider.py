"""
AI Provider Manager - Centralized management for multiple LLM providers
Simplified version with one model per provider
Updated with Google Gemini 2.5 Pro Preview and latest models and pricing as of June 2025
"""
import os
import logging
import requests
import base64
from typing import Optional, Dict, Any, List
from enum import Enum

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
    # Pricing updated as of June 2025
    PROVIDER_CONFIGS = {
        AIProvider.OPENAI: {
            'model_name': 'gpt-4.1',  # Latest GPT-4.1 model
            'display_name': 'gpt-4.1',
            'input_cost_per_token': 0.0002,    # $2.00 / 1M tokens
            'output_cost_per_token': 0.0008,   # $8.00 / 1M tokens
            'context_window': 1000000,  # 1M tokens
            'supports_vision': True,
            'supports_functions': True
        },
        AIProvider.DEEPSEEK: {
            'model_name': 'deepseek-chat',  # Points to DeepSeek-V3
            'display_name': 'deepseek-chat',
            'input_cost_per_token': 0.000027,   # $0.27 / 1M tokens (cache miss)
            'output_cost_per_token': 0.00011,   # $1.10 / 1M tokens
            'input_cost_cached': 0.000007,      # $0.07 / 1M tokens (cache hit)
            'context_window': 64000,  # 64K tokens
            'supports_vision': False,
            'supports_functions': True
        },
        AIProvider.CLAUDE: {
            'model_name': 'claude-sonnet-4-20250514', 
            'display_name': 'claude-4-sonnet',
            'input_cost_per_token': 0.0003,    # $3.00 / 1M tokens
            'output_cost_per_token': 0.0015,   # $15.00 / 1M tokens
            'context_window': 200000,  # 200K tokens
            'supports_vision': True,
            'supports_functions': False,  # Claude doesn't support function calling same way
            'supports_extended_thinking': True  # Hybrid reasoning model
        },
        AIProvider.GOOGLE: {  # Google Gemini 2.5 Pro Preview configuration - FINAL CORRECT PRICING
            'model_name': 'gemini-2.5-pro-preview-05-06',  # Latest preview version
            'display_name': 'gemini-2.5-pro-preview',
            # FINAL CORRECT PRICING: Based on official Google pricing where 1 credit = $0.01
            'input_cost_per_token': 0.000125,      # $1.25/1M tokens ÷ $0.01 = 0.125 credits per 1K tokens
            'output_cost_per_token': 0.001,        # $10.00/1M tokens ÷ $0.01 = 1 credit per 1K tokens  
            'input_cost_long_context': 0.00025,    # $2.50/1M tokens ÷ $0.01 = 0.25 credits per 1K tokens
            'output_cost_long_context': 0.0015,    # $15.00/1M tokens ÷ $0.01 = 1.5 credits per 1K tokens
            'long_context_threshold': 200000,   # 200K tokens threshold
            'context_window': 1000000,  # 1M tokens (2M coming soon)
            'supports_vision': True,
            'supports_functions': True,
            'supports_thinking': True,  # Thinking model with reasoning capabilities
            'supports_multimodal': True  # Text, images, audio, video
        }
    }
    
    def __init__(self):
        self.provider = self._get_provider()
        self.config = self.PROVIDER_CONFIGS[self.provider]
        self._client = None
        
    def _get_provider(self) -> AIProvider:
        """Get the configured AI provider from environment"""
        provider_str = os.environ.get('AI_PROVIDER', 'openai').lower()
        
        # Map string to enum
        provider_map = {
            'openai': AIProvider.OPENAI,
            'deepseek': AIProvider.DEEPSEEK,
            'claude': AIProvider.CLAUDE,
            'google': AIProvider.GOOGLE,  # NEW: Added Google mapping
            'gemini': AIProvider.GOOGLE,  # Alternative name for Google
        }
        
        if provider_str not in provider_map:
            logger.warning(f"Unknown AI provider: {provider_str}, defaulting to OpenAI")
            return AIProvider.OPENAI
            
        return provider_map[provider_str]
    
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
        Create a completion using the configured provider
        Returns unified response format regardless of provider
        """
        client = self.get_client()
        if not client:
            raise ValueError(f"Failed to initialize client for provider: {self.provider}")
            
        try:
            if self.provider in [AIProvider.OPENAI, AIProvider.DEEPSEEK]:
                # OpenAI-compatible API
                response = client.chat.completions.create(
                    model=self.api_model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                
                # Return unified format
                return {
                    'content': response.choices[0].message.content,
                    'model': self.default_model,
                    'usage': {
                        'input_tokens': response.usage.prompt_tokens if hasattr(response, 'usage') else 0,
                        'output_tokens': response.usage.completion_tokens if hasattr(response, 'usage') else 0,
                        'total_tokens': response.usage.total_tokens if hasattr(response, 'usage') else 0
                    },
                    'provider': self.provider.value,
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
                
                response = client.messages.create(
                    model=self.api_model_name,
                    messages=claude_messages,
                    system=system_message,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                # Return unified format
                return {
                    'content': response.content[0].text if response.content else '',
                    'model': self.default_model,
                    'usage': {
                        'input_tokens': response.usage.input_tokens if hasattr(response, 'usage') else 0,
                        'output_tokens': response.usage.output_tokens if hasattr(response, 'usage') else 0,
                        'total_tokens': (response.usage.input_tokens + response.usage.output_tokens) if hasattr(response, 'usage') else 0
                    },
                    'provider': self.provider.value,
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
                        formatted_messages.append(msg['content'])
                    elif msg['role'] == 'assistant':
                        # For chat history, we need to track both user and assistant messages
                        # For now, we'll concatenate them as context
                        formatted_messages.append(f"Assistant: {msg['content']}")
                
                # Combine all messages into a single prompt for simplicity
                # In production, you'd want to use the chat interface for proper conversation handling
                combined_content = '\n'.join(formatted_messages)
                
                # Create generation config
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
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
                
                # Extract usage information if available
                usage_metadata = getattr(response, 'usage_metadata', None)
                input_tokens = usage_metadata.prompt_token_count if usage_metadata else 0
                output_tokens = usage_metadata.candidates_token_count if usage_metadata else 0
                total_tokens = usage_metadata.total_token_count if usage_metadata else 0
                
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
        Create a completion with image inputs
        Only works with providers that support vision
        """
        if not self.config['supports_vision']:
            raise ValueError(f"Provider {self.provider.value} does not support vision inputs")
            
        # For vision, we need to format messages differently based on provider
        if self.provider == AIProvider.OPENAI:
            # OpenAI format is already correct
            return self.create_completion(messages_with_images, **kwargs)
            
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
            response = client.messages.create(
                model=self.api_model_name,
                messages=formatted_messages,
                system=system_message,
                **kwargs
            )
            
            return {
                'content': response.content[0].text if response.content else '',
                'model': self.default_model,
                'usage': {
                    'input_tokens': response.usage.input_tokens if hasattr(response, 'usage') else 0,
                    'output_tokens': response.usage.output_tokens if hasattr(response, 'usage') else 0,
                    'total_tokens': (response.usage.input_tokens + response.usage.output_tokens) if hasattr(response, 'usage') else 0
                },
                'provider': self.provider.value,
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
                                content_parts.append(types.Part.from_text(part['text']))
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
                        content_parts.append(types.Part.from_text(msg['content']))
            
            # Create generation config
            config = types.GenerateContentConfig(
                system_instruction=system_instruction if system_instruction else None,
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
                'raw_response': response
            }
        else:
            raise ValueError(f"Vision not implemented for provider {self.provider.value}")
    
    def estimate_tokens(self, text: str) -> int:
        """Rough estimate of tokens in text (provider-agnostic)"""
        # Simple estimation: 1 token ≈ 4 characters
        return max(1, len(text) // 4)
    
    def calculate_cost(self, input_tokens: int, output_tokens: int, use_cached_rate: bool = False) -> float:
        """Calculate cost in credits for given token usage"""
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
            
            return round(input_cost + output_cost, 4)
        else:
            input_cost = input_tokens * self.config['input_cost_per_token']
            
        output_cost = output_tokens * self.config['output_cost_per_token']
        
        return round(input_cost + output_cost, 4)
    
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

# Singleton instance
_ai_provider_manager = None

def get_ai_provider() -> AIProviderManager:
    """Get the singleton AI provider manager instance"""
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