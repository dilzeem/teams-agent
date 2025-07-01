import os
import uuid
from flask import Flask, redirect, url_for, session, request, render_template, jsonify
import msal # Ensure msal is imported to access __version__
from dotenv import load_dotenv
import requests # For making Graph API calls

load_dotenv() # Load environment variables from .env file

# Basic Flask App Setup
app = Flask(__name__, template_folder='../templates') # Correct template folder path
app.secret_key = os.urandom(24) # Necessary for session management

# Configuration from environment variables
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID = os.getenv("TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

# Ensure REDIRECT_PATH is correctly read from env or defaults
REDIRECT_PATH = os.getenv("APP_REDIRECT_PATH", "/getAToken")

# Read scopes from environment variable, split string into list
GRAPH_SCOPES_STRING = os.getenv("GRAPH_SCOPES", "User.Read Chat.ReadWrite")
GRAPH_SCOPES = GRAPH_SCOPES_STRING.split()


# MSAL Confidential Client Application
# Ensure CLIENT_ID, AUTHORITY, and CLIENT_SECRET are not None
if not all([CLIENT_ID, AUTHORITY, CLIENT_SECRET]):
    raise ValueError("CLIENT_ID, TENANT_ID (for AUTHORITY), and CLIENT_SECRET must be set as environment variables.")

msal_app = ConfidentialClientApplication(
    CLIENT_ID, authority=AUTHORITY,
    client_credential=CLIENT_SECRET
)

@app.route("/")
def index():
    user = session.get("user")
    # Pass msal.__version__ to the template, ensuring msal is imported
    return render_template("index.html", user=user, version=msal.__version__ if 'msal' in globals() else "N/A")

@app.route("/login")
def login():
    session["state"] = str(uuid.uuid4())
    # Use the GRAPH_SCOPES list read from environment variables
    auth_url = msal_app.get_authorization_request_url(
        GRAPH_SCOPES,  # Use the dynamically loaded scopes
        state=session["state"],
        redirect_uri=url_for("authorized", _external=True)
    )
    return redirect(auth_url)

@app.route(REDIRECT_PATH) # Azure AD redirects here
def authorized():
    if request.args.get('state') != session.get("state"):
        return redirect(url_for("index")) # State mismatch, redirect to home
    if "error" in request.args: # Authentication error
        return render_template("auth_error.html", result=request.args)

    if request.args.get('code'):
        cache = msal.SerializableTokenCache() # Initialize a cache for this session
        if session.get("token_cache"):
            cache.deserialize(session["token_cache"])

        result = msal_app.acquire_token_by_authorization_code(
            request.args['code'],
            scopes=GRAPH_SCOPES,
            redirect_uri=url_for("authorized", _external=True),
            token_cache=cache
        )

        if "error" in result:
            return render_template("auth_error.html", result=result)

        session["user"] = result.get("id_token_claims")
        session["token_cache"] = cache.serialize()

    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()  # Wipe out user and token cache from session
    # Also need to redirect to Microsoft's logout page
    return redirect(
        AUTHORITY + "/oauth2/v2.0/logout" +
        "?post_logout_redirect_uri=" + url_for("index", _external=True))

@app.route("/teams_agent/message", methods=["POST"])
def teams_message():
    # Placeholder for Teams agent message handling
    # This would typically be called by a Teams bot registration or a Graph API subscription
    if not session.get("user"):
        return jsonify({"error": "Unauthorized", "message": "User not logged in."}), 401

    input_message = request.json
    print(f"Received message for agent: {input_message}")

    # Get token for Graph API
    token_result = get_token_from_cache(GRAPH_SCOPES)
    if not token_result or "access_token" not in token_result:
        # This could happen if scopes were not consented or token expired and silent refresh failed.
        # For a real app, you might redirect to login or provide a more specific error.
        return jsonify({"error": "Token unavailable", "message": "Could not retrieve access token."}), 401

    access_token = token_result['access_token']

    # Example Graph API call: Get current user's profile (/me)
    # This demonstrates using the token to act on behalf of the user.
    graph_url_me = "https://graph.microsoft.com/v1.0/me"
    headers = {'Authorization': f'Bearer {access_token}'}

    try:
        graph_response = requests.get(graph_url_me, headers=headers)
        graph_response.raise_for_status() # Raises an exception for 4XX/5XX errors
        user_profile = graph_response.json()

        # Agent logic: Combine input message with user profile info for a response
        agent_response = {
            "status": "message processed",
            "received_message": input_message,
            "user_display_name": user_profile.get("displayName", "N/A"),
            "user_principal_name": user_profile.get("userPrincipalName", "N/A"),
            "message": f"Hello {user_profile.get('displayName', 'User')}, your message '{input_message.get('text', '')}' was received."
        }
        return jsonify(agent_response), 200

    except requests.exceptions.RequestException as e:
        print(f"Graph API call failed: {e}")
        return jsonify({"error": "Graph API call failed", "message": str(e)}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": "Unexpected error", "message": str(e)}), 500


# Helper to get token from cache
def get_token_from_cache(scopes=None): # Renamed 'scope' to 'scopes' for clarity
    if scopes is None:
        scopes = GRAPH_SCOPES # Default to global GRAPH_SCOPES if none provided

    cache = msal.SerializableTokenCache()
    if session.get("token_cache"):
        cache.deserialize(session["token_cache"])
    else: # No token cache in session
        return None

    accounts = msal_app.get_accounts()
    if not accounts: # No accounts in MSAL's cache for this app
        return None

    # Attempt to acquire token silently
    # MSAL will handle checking expiry and refreshing if possible
    result = msal_app.acquire_token_silent(scopes, account=accounts[0], token_cache=cache)

    if result and "access_token" in result:
        # If a token was acquired (or refreshed), the cache in MSAL object is updated.
        # Serialize it back to session if it has changed.
        if cache.has_changed:
            session["token_cache"] = cache.serialize()
        return result
    else:
        # Silent acquisition failed. Could be due to expired refresh token,
        # revoked permissions, or conditional access policies.
        # In a real app, might trigger re-authentication.
        print(f"Silent token acquisition failed. Result: {result}")
        return None

# Basic HTML templates (in-line for simplicity, ideally use separate files) - These routes are for testing UI, not part of core agent logic
@app.route("/render_auth_error") # Helper for displaying auth errors
def auth_error_page():
    return render_template("auth_error.html", result={"error":"Sample Error", "error_description":"This is a sample error description."})

@app.route("/render_index") # Helper for displaying index
def index_page():
    user_data = {"name": "Test User"} if not session.get("user") else session.get("user")
    return render_template("index.html", user=user_data)

if __name__ == "__main__":
    # Important: For local development without HTTPS, you might need to set an environment variable:
    # OAUTHLIB_INSECURE_TRANSPORT='1'
    # However, production MUST use HTTPS.
    app.run(debug=True, port=5000)

# Create templates folder and basic HTML files
# This is not ideal for flask structure but will do for now.
# Will create separate files later if needed.

# templates/index.html
# <!DOCTYPE html>
# <html>
# <head>
#     <title>Teams Agent</title>
# </head>
# <body>
#     <h1>Welcome, {{ user.name }}!</h1>
#     <p><a href="{{ url_for('logout') }}">Logout</a></p>
#     <p>MSAL Python Version: {{ version }}</p>
#     <h2>Agent Actions:</h2>
#     <p>Send a test message to the agent (requires user to be logged in):</p>
#     <form id="messageForm">
#         <label for="message">Message:</label>
#         <input type="text" id="message" name="message" value="Hello Agent"><br><br>
#         <button type="button" onclick="sendMessage()">Send to Agent</button>
#     </form>
#     <p id="response"></p>
#     <script>
#         async function sendMessage() {
#             const message = document.getElementById('message').value;
#             const responseElement = document.getElementById('response');
#             try {
#                 const response = await fetch("{{ url_for('teams_message') }}", {
#                     method: 'POST',
#                     headers: {
#                         'Content-Type': 'application/json'
#                     },
#                     body: JSON.stringify({ text: message })
#                 });
#                 const result = await response.json();
#                 responseElement.textContent = 'Server response: ' + JSON.stringify(result);
#             } catch (error) {
#                 responseElement.textContent = 'Error sending message: ' + error;
#             }
#         }
#     </script>
# </body>
# </html>

# templates/auth_error.html
# <!DOCTYPE html>
# <html>
# <head>
#     <title>Login Error</title>
# </head>
# <body>
#     <h1>Authentication Error</h1>
#     <p><strong>Error:</strong> {{ result.error }}</p>
#     <p><strong>Description:</strong> {{ result.error_description | default(result.message, true) }}</p>
#     <p><a href="{{ url_for('index') }}">Go to Home Page</a></p>
# </body>
# </html>
