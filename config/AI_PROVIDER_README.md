# AI Provider Preferences System

This system allows you to configure which AI model is used for each script/feature in your application.

## Admin Interface

Access the AI Provider Manager at: `/admin/ai-provider`

**Features:**
- Set preferred AI model for each script (DeepSeek, Claude, OpenAI, Google)
- Toggle to force all free users to use DeepSeek (most cost-effective)
- Visual grid showing all AI-powered scripts
- Real-time preference updates

## How It Works

### Fallback Chain
The system uses a fallback chain for reliability. If the preferred model fails, it automatically tries the next available provider:

**Default Chain:** Preferred → Claude → OpenAI → Google → DeepSeek

This ensures your application continues working even if one provider has issues.

### Priority Order

When determining which AI provider to use, the system checks in this order:

1. **Free User Setting**: If enabled and user is on free plan → Force DeepSeek
2. **Script Preference**: Check admin-configured preference for this specific script
3. **Environment Variable**: Fall back to `AI_PROVIDER` env var
4. **Default**: Use Claude as ultimate fallback

## Usage in Scripts

### Basic Usage (Legacy - Still Works)
```python
from app.system.ai_provider.ai_provider import get_ai_provider

# Uses default/environment provider
ai_provider = get_ai_provider()
response = ai_provider.create_completion(messages)
```

### Recommended Usage (With Preferences)
```python
from app.system.ai_provider.ai_provider import get_ai_provider
from flask import g

# Get user subscription from Flask g object
user_subscription = g.user.get('subscription_plan') if hasattr(g, 'user') and g.user else None

# Create AI provider with script name and user subscription
ai_provider = get_ai_provider(
    script_name='video_title',  # Name of your script folder
    user_subscription=user_subscription
)

response = ai_provider.create_completion(messages)
```

### Script Names

Use the folder name from `/app/scripts/` as the script name:

- `video_title` - Video Title Generator
- `hook_generator` - TikTok Hook Generator
- `video_script` - Video Script Writer
- `keyword_research` - Keyword Research
- `competitors` - Competitor Analysis
- etc.

## Configuration File

Preferences are stored in: `/config/ai_provider_preferences.json`

**Example:**
```json
{
  "free_users_deepseek": true,
  "script_preferences": {
    "video_title": "claude",
    "hook_generator": "deepseek",
    "keyword_research": "openai",
    "video_script": "google"
  }
}
```

## Benefits

1. **Cost Optimization**: Route expensive tasks to cheaper models
2. **Performance Tuning**: Use faster models for time-sensitive features
3. **Quality Control**: Use best models for critical features
4. **Free User Management**: Control costs by routing free users to DeepSeek
5. **Reliability**: Automatic fallback ensures continuous operation

## Best Practices

### For Scripts
- Always pass `script_name` when calling `get_ai_provider()`
- Pass `user_subscription` to enable free user filtering
- Use descriptive script names matching your folder structure

### For Admins
- Test each model with your specific prompts
- Monitor costs and adjust preferences accordingly
- Consider model strengths:
  - **DeepSeek**: Most cost-effective, good general performance
  - **Claude**: Best for creative writing and long-form content
  - **OpenAI**: Fast, reliable, good all-rounder
  - **Google**: Best for multimodal tasks, large context windows

## Monitoring

Check logs for AI provider selection:
```
INFO: Using preferred provider for video_title: claude
INFO: Free user detected - forcing DeepSeek provider
INFO: Switching to fallback provider: openai
```

## Example Migration

### Before (Old Way)
```python
def generate_titles(self, user_input: str, user_id: str = None) -> Dict:
    ai_provider = get_ai_provider()
    response = ai_provider.create_completion(messages)
```

### After (New Way)
```python
def generate_titles(self, user_input: str, user_id: str = None, user_subscription: str = None) -> Dict:
    ai_provider = get_ai_provider(
        script_name='video_title',
        user_subscription=user_subscription
    )
    response = ai_provider.create_completion(messages)
```

## Troubleshooting

**Preferences not applying?**
- Check `/config/ai_provider_preferences.json` exists and is valid JSON
- Verify script name matches folder name exactly
- Check logs for "Using preferred provider" messages

**All providers failing?**
- Verify API keys are set in environment variables
- Check network connectivity
- Review error logs for specific failures

**Free users not using DeepSeek?**
- Verify toggle is enabled in admin panel
- Check user subscription plan is correctly set to 'free' or 'Free Plan'
- Review logs for "Free user detected" messages
