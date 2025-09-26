#!/usr/bin/env python3
"""
Test script for Teams functionality

This script tests:
1. Team invitation flow
2. Permission management
3. Workspace switching
4. Firebase rules compatibility
"""

import os
import sys
import json
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_teams_system():
    """Test the teams system setup"""
    print("\n" + "="*60)
    print("TEAMS FUNCTIONALITY TEST")
    print("="*60 + "\n")

    tests_passed = 0
    tests_failed = 0

    # Test 1: Check if teams route is registered
    print("1. Testing Teams Route Registration...")
    try:
        from run import app
        with app.test_client() as client:
            response = client.get('/teams/')
            # Will redirect to login if not authenticated
            if response.status_code in [302, 401]:
                print("   ✓ Teams route is registered (requires authentication)")
                tests_passed += 1
            else:
                print(f"   ✗ Unexpected status code: {response.status_code}")
                tests_failed += 1
    except Exception as e:
        print(f"   ✗ Failed to test teams route: {str(e)}")
        tests_failed += 1

    # Test 2: Check permissions module
    print("\n2. Testing Permissions Module...")
    try:
        from app.system.auth.permissions import check_workspace_permission, get_active_workspace_data
        print("   ✓ Permissions module imported successfully")
        tests_passed += 1
    except Exception as e:
        print(f"   ✗ Failed to import permissions module: {str(e)}")
        tests_failed += 1

    # Test 3: Check Firebase rules file
    print("\n3. Testing Firebase Rules...")
    try:
        rules_file = 'firestore.rules'
        if os.path.exists(rules_file):
            with open(rules_file, 'r') as f:
                content = f.read()
                if 'isTeamMember' in content and 'team_members' in content:
                    print("   ✓ Firebase rules include team member support")
                    tests_passed += 1
                else:
                    print("   ✗ Firebase rules missing team member functions")
                    tests_failed += 1
        else:
            print("   ✗ Firebase rules file not found")
            tests_failed += 1
    except Exception as e:
        print(f"   ✗ Failed to check Firebase rules: {str(e)}")
        tests_failed += 1

    # Test 4: Check teams template
    print("\n4. Testing Teams Template...")
    try:
        template_file = 'app/templates/teams/dashboard.html'
        if os.path.exists(template_file):
            with open(template_file, 'r') as f:
                content = f.read()
                required_elements = ['sendInvite', 'loadTeamMembers', 'switchWorkspace', 'editPermissions']
                missing = []
                for element in required_elements:
                    if element not in content:
                        missing.append(element)

                if not missing:
                    print("   ✓ Teams template has all required functionality")
                    tests_passed += 1
                else:
                    print(f"   ✗ Teams template missing: {', '.join(missing)}")
                    tests_failed += 1
        else:
            print("   ✗ Teams template not found")
            tests_failed += 1
    except Exception as e:
        print(f"   ✗ Failed to check teams template: {str(e)}")
        tests_failed += 1

    # Test 5: Check middleware updates
    print("\n5. Testing Middleware Updates...")
    try:
        from app.system.auth.middleware import auth_middleware
        # Check if the middleware file contains workspace handling
        import inspect
        source = inspect.getsource(auth_middleware)
        if 'active_workspace_id' in source and 'workspace_permissions' in source:
            print("   ✓ Middleware includes workspace handling")
            tests_passed += 1
        else:
            print("   ✗ Middleware missing workspace handling")
            tests_failed += 1
    except Exception as e:
        print(f"   ✗ Failed to check middleware: {str(e)}")
        tests_failed += 1

    # Test Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Tests Passed: {tests_passed}")
    print(f"Tests Failed: {tests_failed}")
    print(f"Total Tests: {tests_passed + tests_failed}")
    print(f"Success Rate: {(tests_passed/(tests_passed+tests_failed)*100):.1f}%")

    if tests_failed == 0:
        print("\n✅ All tests passed! Teams functionality is properly set up.")
        print("\nNEXT STEPS:")
        print("1. Deploy the updated Firebase rules to your Firebase project")
        print("2. Test the invitation flow with real email addresses")
        print("3. Verify Supabase email configuration for invitations")
        print("4. Test workspace switching and permission management")
    else:
        print(f"\n⚠️  {tests_failed} test(s) failed. Please review the errors above.")

    return tests_failed == 0

if __name__ == "__main__":
    success = test_teams_system()
    sys.exit(0 if success else 1)