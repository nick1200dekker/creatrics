#!/usr/bin/env python3
"""
Quick script to manually mark X setup as complete for a user
Usage: python force_complete_setup.py <user_id>
"""

import sys
import firebase_admin
from firebase_admin import firestore

def force_complete_x_setup(user_id):
    """Force mark X setup as complete"""
    try:
        # Initialize Firebase
        if not firebase_admin._apps:
            firebase_admin.initialize_app()

        db = firestore.client()

        # Update user document
        user_ref = db.collection('users').document(user_id)
        user_ref.update({
            'x_setup_complete': True
        })

        print(f"✓ Successfully marked X setup as complete for user {user_id}")
        return True

    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python force_complete_setup.py <user_id>")
        print("\nExample:")
        print("  python force_complete_setup.py 972ff96a-c73a-4560-b363-4bae43c15723")
        sys.exit(1)

    user_id = sys.argv[1]
    force_complete_x_setup(user_id)
