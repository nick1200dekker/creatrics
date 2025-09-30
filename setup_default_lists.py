#!/usr/bin/env python3
"""
Setup script to create default lists with big creator accounts for Reply Guy
"""
import os
import sys
import json
from datetime import datetime

# Add the app directory to the path so we can import Firebase
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

# Set up Firebase
import firebase_admin
from firebase_admin import credentials, firestore

def setup_firebase():
    """Initialize Firebase if not already done"""
    if not firebase_admin._apps:
        # Use the same credentials file as the main app
        cred_path = os.path.join(os.path.dirname(__file__), 'firebase-credentials.json')
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        else:
            print("Firebase credentials not found. Using default credentials.")
            firebase_admin.initialize_app()

    return firestore.client()

def get_big_creator_accounts():
    """
    Get a list of 50 big creator accounts across different niches
    These are well-known accounts with good engagement that would be good for reply opportunities
    """
    return [
        # Tech/Business
        'elonmusk', 'sundarpichai', 'tim_cook', 'satyanadella', 'jeffweiner', 'reidhoffman',
        'naval', 'balajis', 'pmarca', 'bgurley', 'chamath', 'jason', 'garyvee', 'dan_schulman',

        # Content Creators
        'MrBeast', 'PewDiePie', 'KSI', 'LoganPaul', 'jakepaul', 'EmmaChamberlain', 'jamescharles',
        'nikocadoavocado', 'mrbeastyt', 'dualipa', 'justinbieber', 'taylorswift13', 'selenagomez',

        # News/Media
        'cnn', 'nytimes', 'washingtonpost', 'bbcnews', 'reuters', 'ap', 'nbcnews', 'abcnews',
        'foxnews', 'wsj', 'usatoday', 'latimes', 'guardianUS', 'politico',

        # Finance/Crypto
        'michael_saylor', 'cz_binance', 'SBF_FTX', 'elonmusk', 'cathiedwood', 'chamath',
        'novogratz', 'APompliano', 'naval', 'VitalikButerin', 'justinsuntron', 'brian_armstrong',

        # Sports
        'stephencurry30', 'KingJames', 'Cristiano', 'TeamMessi', 'usainbolt', 'Ronaldinho',
        'neymarjr', 'SerenaWilliams', 'tombrady', 'TheRealMikeT', 'FloydMayweather', 'espn'
    ]

def create_default_lists(db):
    """Create the default lists in Firebase"""

    # Get the big creator accounts
    accounts = get_big_creator_accounts()

    # Create the content_creators list
    content_creators_data = {
        'id': 'content_creators',
        'name': 'Content Creators',
        'description': 'Top 50 content creators and influencers across tech, entertainment, sports, and business',
        'industry': 'Content Creation',
        'accounts': accounts,
        'account_count': len(accounts),
        'created_at': datetime.now(),
        'last_updated': datetime.now(),
        'is_active': True,
        'update_frequency': 'daily'
    }

    # Save to Firebase
    try:
        doc_ref = db.collection('default_lists').document('content_creators')
        doc_ref.set(content_creators_data)
        print(f"✅ Created default list 'content_creators' with {len(accounts)} accounts")

        # Also create a document to track when this list was last analyzed
        analysis_ref = db.collection('default_list_analyses').document('content_creators')
        analysis_ref.set({
            'list_id': 'content_creators',
            'list_name': 'Content Creators',
            'last_updated': datetime.now(),
            'analyzed_accounts': len(accounts),
            'tweet_opportunities': [],
            'next_update': datetime.now()
        })
        print(f"✅ Created analysis tracking document for content_creators")

        return True

    except Exception as e:
        print(f"❌ Error creating default list: {str(e)}")
        return False

def main():
    """Main setup function"""
    print("🚀 Setting up default lists for Reply Guy...")

    try:
        # Initialize Firebase
        db = setup_firebase()
        print("✅ Firebase initialized")

        # Create default lists
        if create_default_lists(db):
            print("🎉 Setup completed successfully!")
            print("\nNext steps:")
            print("1. Set up the cron endpoint to update this list daily")
            print("2. Run the analysis on this list to populate reply opportunities")
        else:
            print("❌ Setup failed")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Setup error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()