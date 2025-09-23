# YouTube OAuth Setup - Keeping Login Separate

## The Problem
- Adding YouTube scopes triggers Google's verification requirement (can take weeks)
- You want login to keep working without YouTube scopes
- Solution: Use completely separate OAuth clients

## Setup Instructions

### 1. In Google Cloud Console

#### OAuth Client 1: Login (Keep existing)
- Name: "Creator Tools Login" (or your existing one)
- Scopes: Only email and profile
- Status: Can stay in production
- Used for: `/auth/google` login flow

#### OAuth Client 2: YouTube Access (New)
- Name: "Creator Tools YouTube"
- Scopes: YouTube Data API, YouTube Analytics API
- Status: Keep in **Testing Mode** (no verification needed!)
- Used for: `/accounts/youtube/connect` flow

### 2. Configure Testing Mode for YouTube OAuth

1. Go to **APIs & Services > OAuth consent screen**
2. Keep status as **Testing** (DON'T publish)
3. Add test users:
   - Click "ADD USERS"
   - Add your email and up to 100 test emails
   - These users can connect YouTube without verification

### 3. Enable Required APIs

In **APIs & Services > Library**, enable:
- YouTube Data API v3
- YouTube Analytics API
- YouTube Reporting API (optional)

### 4. Create YouTube OAuth Client

1. Go to **APIs & Services > Credentials**
2. Click **+ CREATE CREDENTIALS** > **OAuth client ID**
3. Configure:
   - Application type: **Web application**
   - Name: **Creator Tools YouTube**
   - Authorized redirect URIs:
     ```
     http://localhost:5001/accounts/youtube/callback
     http://localhost:8080/accounts/youtube/callback
     https://yourdomain.com/accounts/youtube/callback (if deployed)
     ```

4. Download JSON and save as `youtube_oauth_client.json`

### 5. File Structure

```
creator-tools/
├── .env                          # Has GOOGLE_CLIENT_ID for login
├── youtube_oauth_client.json    # Separate OAuth for YouTube
└── app/
    ├── routes/
    │   ├── auth/                # Login OAuth (no YouTube scopes)
    │   └── accounts/
    │       └── youtube.py       # YouTube OAuth (with YouTube scopes)
```

## How It Works

1. **User logs in**: Uses regular OAuth (no YouTube scopes) → No verification needed
2. **User connects YouTube**: Uses separate OAuth client → Works in testing mode
3. **Both work independently**: Login doesn't break when YouTube requires verification

## Testing Mode Limitations

- ✅ Up to 100 test users
- ✅ Full access to YouTube APIs
- ✅ No verification required
- ⚠️ Users see "unverified app" warning (that's OK for testing)
- ⚠️ Refresh tokens expire after 7 days of inactivity

## When Ready for Production

Only when you want to go public:
1. Submit YouTube OAuth for verification
2. During verification, testing mode still works
3. Once approved, switch to production

## Current Configuration

Your app is now configured to:
- Keep login OAuth completely separate
- Use `youtube_oauth_client.json` for YouTube only
- Request YouTube scopes only when connecting YouTube
- Work without verification in testing mode