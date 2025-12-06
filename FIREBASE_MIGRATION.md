# Firebase Auth Migration Guide

## ✅ Migration Complete

The creator-tools app has been successfully migrated from Supabase Auth to Firebase Auth.

## Changes Made

### Backend Changes

1. **New File: `/app/system/auth/firebase_auth.py`**
   - Replaced Supabase token verification with Firebase Admin SDK
   - Uses `auth.verify_id_token()` for token validation
   - Added helper functions for user management

2. **Updated: `/app/system/auth/middleware.py`**
   - Changed import from `supabase.py` to `firebase_auth.py`
   - Updated `verify_token()` to use Firebase verification
   - Removed JWT library dependency (Firebase handles it)

3. **Updated: `/app/config.py`**
   - Removed Supabase configuration variables
   - Added Firebase configuration variables:
     - `firebase_api_key`
     - `firebase_auth_domain`
     - `firebase_project_id`
     - `firebase_storage_bucket`

4. **Updated: `/run.py`**
   - Replaced `inject_supabase_credentials()` with `inject_firebase_config()`
   - Firebase config now passed to templates

### Frontend Changes

1. **Completely Rewritten: `/app/static/js/auth.js`**
   - Replaced Supabase JS SDK with Firebase JS SDK
   - Changed `initSupabase()` → `initFirebase()`
   - Updated all auth methods:
     - `signIn()` - Uses `signInWithEmailAndPassword()`
     - `signUp()` - Uses `createUserWithEmailAndPassword()`
     - `signInWithOAuth()` - Uses `signInWithPopup()`
     - `logout()` - Uses Firebase `signOut()`
     - `refreshToken()` - Uses `getIdToken(true)`
   - Simplified token refresh (Firebase manages lifecycle)

2. **Updated: `/app/templates/auth/login.html`**
   - Replaced Supabase SDK with Firebase SDK CDN links
   - Updated initialization code to use Firebase config
   - Changed `Auth.initSupabase()` → `Auth.initFirebase()`

3. **Updated: `/app/templates/auth/register.html`**
   - Replaced Supabase SDK with Firebase SDK CDN links
   - Updated initialization code to use Firebase config
   - Changed registration flow to use `Auth.signUp()`

## Environment Variables Required

Update your `.env` file with these Firebase variables:

```bash
# Remove these Supabase variables:
# SUPABASE_URL=
# SUPABASE_ANON_KEY=
# SUPABASE_SERVICE_KEY=
# SUPABASE_JWT_SECRET=

# Add these Firebase variables:
FIREBASE_API_KEY=your-firebase-api-key
FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_STORAGE_BUCKET=your-project.appspot.com
FIREBASE_CREDENTIALS=/path/to/firebase-credentials.json
```

## Getting Firebase Configuration

1. **Go to Firebase Console**: https://console.firebase.google.com
2. **Select your project** (or create a new one)
3. **Go to Project Settings** (gear icon)
4. **Under "Your apps"**, add a web app or select existing one
5. **Copy the Firebase config** values:
   - API Key
   - Auth Domain
   - Project ID
   - Storage Bucket

6. **For Admin SDK credentials**:
   - Go to Project Settings → Service Accounts
   - Click "Generate new private key"
   - Save the JSON file as `firebase-credentials.json`
   - Set path in `FIREBASE_CREDENTIALS` env variable

## Files to Delete (Optional Cleanup)

These files are no longer needed:

- `/app/system/auth/supabase.py` - Replaced by `firebase_auth.py`

## Dependencies

The app already has `firebase-admin==6.2.0` installed. No new dependencies needed!

You can optionally remove `PyJWT` from `requirements.txt` if it's not used elsewhere.

## Testing Checklist

Before deploying to production, test these flows:

- [ ] **Email/Password Sign Up**
  - Create new account
  - Verify user created in Firebase Console
  - Check Firestore for user profile

- [ ] **Email/Password Sign In**
  - Login with existing account
  - Verify session cookie is set
  - Check user data loads correctly

- [ ] **Google OAuth Sign In**
  - Click "Sign in with Google"
  - Complete OAuth flow
  - Verify redirect back to app

- [ ] **Session Persistence**
  - Login and close browser
  - Reopen browser and verify still logged in
  - Check token refresh works (wait 55+ minutes)

- [ ] **Logout**
  - Click logout
  - Verify redirected to home/login
  - Verify session cleared

- [ ] **Protected Routes**
  - Try accessing protected page without login
  - Verify redirect to login page
  - Login and verify access granted

## Firebase Console Setup

### Enable Authentication Methods

1. Go to **Authentication** → **Sign-in method**
2. Enable these providers:
   - ✅ Email/Password
   - ✅ Google (if using OAuth)
   - ✅ GitHub (if using OAuth)

### Configure Authorized Domains

1. Go to **Authentication** → **Settings** → **Authorized domains**
2. Add your domains:
   - `localhost` (for development)
   - Your production domain

### Firestore Security Rules

Ensure your Firestore rules allow authenticated users:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
    
    // Add other collection rules as needed
  }
}
```

## Token Differences

### Supabase Tokens
- Used HS256 (symmetric) with JWT secret
- 1 hour expiry
- Manual refresh required

### Firebase Tokens
- Uses RS256 (asymmetric) with public key verification
- 1 hour expiry
- Automatic refresh by SDK
- More secure (no shared secret)

## Migration Notes

- **No user migration needed** - Starting fresh with Firebase Auth
- **Existing Firestore data** - Already compatible, no changes needed
- **Firebase Storage** - Already in use, no changes needed
- **Session cookies** - Same cookie name and structure maintained

## Rollback Plan

If you need to rollback to Supabase:

1. Restore original files from git:
   - `app/system/auth/supabase.py`
   - `app/system/auth/middleware.py`
   - `app/config.py`
   - `run.py`
   - `app/static/js/auth.js`
   - `app/templates/auth/login.html`
   - `app/templates/auth/register.html`

2. Restore Supabase environment variables

3. Restart the application

## Support

If you encounter issues:

1. Check Firebase Console for errors
2. Check browser console for JavaScript errors
3. Check server logs for authentication errors
4. Verify all environment variables are set correctly
5. Ensure `firebase-credentials.json` path is correct

## Next Steps

1. ✅ Update `.env` with Firebase credentials
2. ✅ Test all authentication flows
3. ✅ Deploy to staging environment
4. ✅ Test in staging
5. ✅ Deploy to production
6. ✅ Monitor for any auth-related errors

---

**Migration completed on**: December 6, 2024
**Migrated by**: Cascade AI Assistant
