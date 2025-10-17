/**
 * Auth.js - Centralized authentication utilities for CreatorPal
 * 
 * This module provides shared authentication functionality using Supabase SDK and HTTP cookies
 * for more secure and maintainable authentication management.
 */

const Auth = {
    // Supabase client instance
    supabaseClient: null,
    
    /**
     * Initialize the Supabase client with credentials
     * @param {string} url - Supabase project URL
     * @param {string} key - Supabase anon key
     */
    initSupabase: function(url, key) {
        if (!url || !key) {
            console.error("Supabase credentials not provided");
            return false;
        }
        
        try {
            this.supabaseClient = supabase.createClient(url, key);
            console.log("Supabase client initialized");
            return true;
        } catch (error) {
            console.error("Failed to initialize Supabase client:", error);
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
        if (!this.supabaseClient) {
            console.error("Supabase client not initialized");
            return Promise.reject(new Error("Auth not initialized"));
        }
        
        try {
            const { data, error } = await this.supabaseClient.auth.signInWithPassword({
                email,
                password
            });
            
            if (error) throw error;
            
            // After successful Supabase auth, send token to server to establish cookie session
            return this.createServerSession(data.session.access_token);
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
        if (!this.supabaseClient) {
            console.error("Supabase client not initialized");
            return Promise.reject(new Error("Auth not initialized"));
        }
        
        try {
            const { data, error } = await this.supabaseClient.auth.signInWithOAuth({
                provider,
                options: {
                    redirectTo: window.location.origin + "/auth/callback"
                }
            });
            
            if (error) throw error;
            
            // OAuth redirect will happen automatically
            return data;
        } catch (error) {
            console.error(`${provider} sign in failed:`, error);
            return Promise.reject(error);
        }
    },
    
    /**
     * Sign up a new user with email and password
     * @param {string} email - User email
     * @param {string} password - User password
     * @param {Object} metadata - Additional user metadata
     * @returns {Promise} Auth response promise
     */
    signUp: async function(email, password, metadata = {}) {
        if (!this.supabaseClient) {
            console.error("Supabase client not initialized");
            return Promise.reject(new Error("Auth not initialized"));
        }
        
        try {
            const { data, error } = await this.supabaseClient.auth.signUp({
                email,
                password,
                options: {
                    data: metadata,
                    emailRedirectTo: window.location.origin + "/auth/callback"
                }
            });
            
            if (error) throw error;
            
            return data;
        } catch (error) {
            console.error("Sign up failed:", error);
            return Promise.reject(error);
        }
    },
    
    /**
     * Process OAuth callback with token and establish server session
     * @param {string} hash - URL hash containing the access token
     * @returns {Promise} Session creation promise
     */
    handleAuthCallback: async function(hash) {
        if (!hash) {
            console.error("No hash provided for auth callback");
            return Promise.reject(new Error("Invalid auth callback"));
        }
        
        try {
            // Extract access token from URL hash
            const hashParams = {};
            const hashParts = hash.substring(1).split('&');
            
            for (const part of hashParts) {
                const [key, value] = part.split('=');
                hashParams[key] = decodeURIComponent(value || '');
            }
            
            const accessToken = hashParams.access_token;
            
            if (!accessToken) {
                throw new Error("No access token found in callback URL");
            }
            
            console.log("Access token found in URL hash");
            
            // Create server session with the token
            return this.createServerSession(accessToken);
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
        return fetch('/auth/session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ token }),
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
            return data;
        });
    },
    
    /**
     * Log the user out by clearing the session cookie and Supabase session
     * @returns {Promise} Logout promise
     */
    logout: async function() {
        try {
            // Sign out from Supabase
            if (this.supabaseClient) {
                await this.supabaseClient.auth.signOut();
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
     * Get current user session from Supabase
     * @returns {Promise} Session promise
     */
    getCurrentSession: async function() {
        if (!this.supabaseClient) {
            console.error("Supabase client not initialized");
            return null;
        }

        try {
            const { data, error } = await this.supabaseClient.auth.getSession();

            if (error) throw error;

            return data.session;
        } catch (error) {
            console.error("Get current session failed:", error);
            return null;
        }
    },

    /**
     * Refresh the access token using Supabase refresh token
     * @returns {Promise} Refreshed session promise
     */
    refreshToken: async function() {
        if (!this.supabaseClient) {
            console.error("Supabase client not initialized");
            return null;
        }

        try {
            const { data, error } = await this.supabaseClient.auth.refreshSession();

            if (error) throw error;

            if (data.session && data.session.access_token) {
                console.log("Token refreshed successfully");
                // Update server session with new token
                await this.createServerSession(data.session.access_token);
                return data.session;
            }

            return null;
        } catch (error) {
            console.error("Token refresh failed:", error);
            return null;
        }
    },

    /**
     * Start automatic token refresh (checks every 5 minutes, refreshes if < 10 minutes remaining)
     */
    startTokenRefresh: function() {
        // Check and refresh token every 5 minutes
        const CHECK_INTERVAL = 5 * 60 * 1000; // 5 minutes
        const REFRESH_THRESHOLD = 10 * 60; // Refresh if less than 10 minutes remaining

        setInterval(async () => {
            try {
                const session = await this.getCurrentSession();

                if (session && session.expires_at) {
                    const expiresAt = session.expires_at;
                    const now = Math.floor(Date.now() / 1000);
                    const timeUntilExpiry = expiresAt - now;

                    console.log(`Token expires in ${Math.floor(timeUntilExpiry / 60)} minutes`);

                    // Refresh if less than 10 minutes remaining
                    if (timeUntilExpiry < REFRESH_THRESHOLD) {
                        console.log("Token expiring soon, refreshing...");
                        await this.refreshToken();
                    }
                }
            } catch (error) {
                console.error("Token refresh check failed:", error);
            }
        }, CHECK_INTERVAL);

        console.log("Automatic token refresh started");
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