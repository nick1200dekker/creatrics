/**
 * Auth.js - Centralized authentication utilities for CreatorPal
 * 
 * This module provides shared authentication functionality using Firebase SDK and HTTP cookies
 * for more secure and maintainable authentication management.
 */

const Auth = {
    // Firebase auth instance
    firebaseAuth: null,
    firebaseApp: null,
    
    /**
     * Initialize Firebase with configuration
     * @param {object} config - Firebase configuration object
     */
    initFirebase: function(config) {
        if (!config || !config.apiKey || !config.authDomain) {
            console.error("Firebase configuration not provided");
            return false;
        }

        try {
            // Initialize Firebase
            this.firebaseApp = firebase.initializeApp(config);
            this.firebaseAuth = firebase.auth();
            
            // Set persistence to LOCAL (survives browser restarts)
            this.firebaseAuth.setPersistence(firebase.auth.Auth.Persistence.LOCAL);
            
            console.log("Firebase initialized successfully");
            return true;
        } catch (error) {
            console.error("Failed to initialize Firebase:", error);
            return false;
        }
    },
    
    /**
     * Check if the user is authenticated by validating the cookie-based session
     * @returns {Promise<boolean>} Promise resolving to authentication status
     */
    isAuthenticated: function() {
        return fetch('/api/check-auth', {
            method: 'GET',
            credentials: 'include' // Important: Include cookies with request
        })
        .then(async response => {
            console.log("Auth check response status:", response.status);
            
            if (response.ok) {
                return true;
            } else {
                // Try to parse response for potential redirect info
                try {
                    const responseData = await response.json();
                    console.log("Auth check error response:", responseData);
                    
                    // If the response contains redirect information, handle it
                    if (responseData.redirect) {
                        console.log("Session expired, redirecting to:", responseData.redirect);
                        
                        // Clear cookies if specified
                        if (responseData.clearCookies && Array.isArray(responseData.clearCookies)) {
                            responseData.clearCookies.forEach(cookie => {
                                if (cookie.name) {
                                    document.cookie = `${cookie.name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=${cookie.path || '/'}; domain=${cookie.domain || ''}; SameSite=Lax`;
                                }
                            });
                        }
                        
                        // Execute redirect after a brief delay to allow cookie clearing
                        setTimeout(() => {
                            window.location.href = responseData.redirect;
                        }, 100);
                    }
                } catch (e) {
                    console.error("Failed to parse auth check response:", e);
                }
                return false;
            }
        })
        .catch(error => {
            console.error("Authentication check failed:", error);
            return false;
        });
    },
    
    /**
     * Sign in with email and password
     * @param {string} email - User email
     * @param {string} password - User password
     * @returns {Promise} Auth response promise
     */
    signIn: async function(email, password) {
        if (!this.firebaseAuth) {
            console.error("Firebase not initialized");
            return Promise.reject(new Error("Auth not initialized"));
        }
        
        try {
            const userCredential = await this.firebaseAuth.signInWithEmailAndPassword(email, password);
            
            // Get the ID token
            const idToken = await userCredential.user.getIdToken();
            
            // Send token to server to establish cookie session
            return this.createServerSession(idToken);
        } catch (error) {
            console.error("Sign in failed:", error);
            return Promise.reject(error);
        }
    },
    
    /**
     * Sign in with OAuth provider (e.g., Google)
     * @param {string} provider - Provider name (google, github, etc.)
     */
    signInWithOAuth: async function(provider) {
        if (!this.firebaseAuth) {
            console.error("Firebase not initialized");
            return Promise.reject(new Error("Auth not initialized"));
        }
        
        try {
            let authProvider;
            
            switch(provider.toLowerCase()) {
                case 'google':
                    authProvider = new firebase.auth.GoogleAuthProvider();
                    break;
                case 'github':
                    authProvider = new firebase.auth.GithubAuthProvider();
                    break;
                case 'facebook':
                    authProvider = new firebase.auth.FacebookAuthProvider();
                    break;
                default:
                    throw new Error(`Unsupported provider: ${provider}`);
            }
            
            const result = await this.firebaseAuth.signInWithPopup(authProvider);
            
            // Get the ID token
            const idToken = await result.user.getIdToken();
            
            // Send token to server to establish cookie session
            return this.createServerSession(idToken);
        } catch (error) {
            console.error(`${provider} sign in failed:`, error);
            return Promise.reject(error);
        }
    },
    
    /**
     * Sign up a new user with email and password
     * @param {string} email - User email
     * @param {string} password - User password
     * @param {Object} metadata - Additional user metadata (e.g., displayName)
     * @returns {Promise} Auth response promise
     */
    signUp: async function(email, password, metadata = {}) {
        if (!this.firebaseAuth) {
            console.error("Firebase not initialized");
            return Promise.reject(new Error("Auth not initialized"));
        }
        
        try {
            const userCredential = await this.firebaseAuth.createUserWithEmailAndPassword(email, password);
            
            // Update profile if displayName provided
            if (metadata.displayName) {
                await userCredential.user.updateProfile({
                    displayName: metadata.displayName
                });
            }
            
            // Get the ID token
            const idToken = await userCredential.user.getIdToken();
            
            // Send token to server to establish cookie session
            return this.createServerSession(idToken);
        } catch (error) {
            console.error("Sign up failed:", error);
            return Promise.reject(error);
        }
    },
    
    /**
     * Handle Firebase auth state changes and redirect
     * Firebase handles OAuth callbacks automatically
     */
    handleAuthCallback: async function() {
        if (!this.firebaseAuth) {
            console.error("Firebase not initialized");
            return Promise.reject(new Error("Auth not initialized"));
        }
        
        try {
            // Wait for auth state to be ready
            return new Promise((resolve, reject) => {
                const unsubscribe = this.firebaseAuth.onAuthStateChanged(async (user) => {
                    unsubscribe();
                    
                    if (user) {
                        // Get the ID token
                        const idToken = await user.getIdToken();
                        
                        // Create server session
                        await this.createServerSession(idToken);
                        resolve(user);
                    } else {
                        reject(new Error("No user found after auth callback"));
                    }
                });
            });
        } catch (error) {
            console.error("Auth callback handling failed:", error);
            return Promise.reject(error);
        }
    },
    
    /**
     * Create server-side session with the access token (sets HTTP cookie)
     * @param {string} token - JWT access token from Supabase
     * @returns {Promise} Server response promise
     */
    createServerSession: function(token) {
        // Check for pending referral code in localStorage
        const referralCode = localStorage.getItem('pendingReferralCode');
        const payload = { token };

        // Include referral code if available
        if (referralCode) {
            payload.referral_code = referralCode;
            console.log('Including referral code in session creation:', referralCode);
        }

        return fetch('/auth/session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload),
            credentials: 'include' // Important: Include cookies with request
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server session creation failed: ${response.status}`);
            }

            return response.json();
        })
        .then(data => {
            console.log("Server session created successfully");

            // Clear referral code after successful session creation
            if (referralCode) {
                localStorage.removeItem('pendingReferralCode');
                console.log('Referral code processed and cleared');
            }

            return data;
        });
    },
    
    /**
     * Log the user out by clearing the session cookie and Firebase session
     * @returns {Promise} Logout promise
     */
    logout: async function() {
        try {
            // Sign out from Firebase
            if (this.firebaseAuth) {
                await this.firebaseAuth.signOut();
            }
            
            // Clear server-side session
            await fetch('/auth/logout', {
                method: 'POST',
                credentials: 'include' // Important: Include cookies with request
            });
            
            console.log("User logged out");
            
            // Redirect to home page
            window.location.href = '/';
            
            return true;
        } catch (error) {
            console.error("Logout failed:", error);
            
            // Still redirect to home page on error
            window.location.href = '/';
            
            return false;
        }
    },
    
    /**
     * Redirect to login page with an optional reason parameter
     * @param {string} reason - Reason for the redirect (expired, unauthorized, etc)
     */
    redirectToLogin: function(reason) {
        console.log(`Redirecting to login with reason: ${reason}`);
        window.location.href = `/auth/login?${reason ? 'reason=' + reason : ''}`;
    },
    
    /**
     * Get current user from Firebase
     * @returns {Promise} User promise
     */
    getCurrentUser: async function() {
        if (!this.firebaseAuth) {
            console.error("Firebase not initialized");
            return null;
        }

        try {
            return new Promise((resolve) => {
                const unsubscribe = this.firebaseAuth.onAuthStateChanged((user) => {
                    unsubscribe();
                    resolve(user);
                });
            });
        } catch (error) {
            console.error("Get current user failed:", error);
            return null;
        }
    },

    /**
     * Refresh the ID token from Firebase
     * @returns {Promise} Refreshed token promise
     */
    refreshToken: async function() {
        if (!this.firebaseAuth) {
            console.error("Firebase not initialized");
            return null;
        }

        try {
            const user = this.firebaseAuth.currentUser;
            
            if (!user) {
                console.warn("No user logged in, redirecting to login");
                window.location.href = '/auth/login?reason=session_expired';
                return null;
            }

            // Force refresh the ID token
            const idToken = await user.getIdToken(true);
            
            console.log("Token refreshed successfully");
            
            // Update server session with new token
            try {
                await this.createServerSession(idToken);
            } catch (sessionError) {
                console.error("Failed to update server session after token refresh:", sessionError);
            }
            
            return idToken;
        } catch (error) {
            console.error("Token refresh failed:", error);
            return null;
        }
    },

    /**
     * Start automatic token refresh for Firebase
     * Firebase tokens expire after 1 hour
     */
    startTokenRefresh: function() {
        if (!this.firebaseAuth) {
            console.error("Firebase not initialized");
            return;
        }

        // Listen to auth state changes
        this.firebaseAuth.onAuthStateChanged(async (user) => {
            if (user) {
                console.log('User authenticated, setting up token refresh');
                
                // Get token result to check expiration
                const tokenResult = await user.getIdTokenResult();
                const expirationTime = new Date(tokenResult.expirationTime).getTime();
                const now = Date.now();
                const timeUntilExpiry = expirationTime - now;
                
                console.log(`Token expires in ${Math.floor(timeUntilExpiry / 1000 / 60)} minutes`);
                
                // Refresh token 5 minutes before expiry (55 minutes after creation)
                const refreshTime = Math.max(timeUntilExpiry - (5 * 60 * 1000), 0);
                
                setTimeout(async () => {
                    console.log('Refreshing token proactively');
                    await this.refreshToken();
                    // Restart the refresh cycle
                    this.startTokenRefresh();
                }, refreshTime);
            } else {
                console.log('User signed out');
            }
        });

        console.log("Automatic token refresh started (Firebase manages token lifecycle)");
    },
    
    /**
     * Perform auth check and fetch user profile data
     * @returns {Promise} User profile promise
     */
    getUserProfile: function() {
        return fetch('/users/profile', {
            method: 'GET',
            credentials: 'include' // Important: Include cookies with request
        })
        .then(response => {
            if (!response.ok) {
                throw new Error("Failed to fetch user profile");
            }
            
            return response.json();
        });
    }
};

// Export Auth object
console.log("Auth.js loaded");