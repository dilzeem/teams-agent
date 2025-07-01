import os
import uuid
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware
import msal # Ensure msal is imported to access __version__
from dotenv import load_dotenv
import requests # For making Graph API calls
import uvicorn

load_dotenv() # Load environment variables from .env file

# Basic FastAPI App Setup
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.urandom(24))

# Mount static files and templates
templates = Jinja2Templates(directory="../templates")

# Configuration from environment variables
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID = os.getenv("TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

# Ensure REDIRECT_PATH is correctly read from env or defaults
REDIRECT_PATH = os.getenv("APP_REDIRECT_PATH", "/getAToken")
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000") # Needed for redirect_uri

# Read scopes from environment variable, split string into list
GRAPH_SCOPES_STRING = os.getenv("GRAPH_SCOPES", "User.Read Chat.ReadWrite")
GRAPH_SCOPES = GRAPH_SCOPES_STRING.split()


# MSAL Confidential Client Application
if not all([CLIENT_ID, AUTHORITY, CLIENT_SECRET]):
    raise ValueError("CLIENT_ID, TENANT_ID (for AUTHORITY), and CLIENT_SECRET must be set as environment variables.")

msal_app = msal.ConfidentialClientApplication(
    CLIENT_ID, authority=AUTHORITY,
    client_credential=CLIENT_SECRET
)

class Message(BaseModel):
    text: str

def get_session(request: Request):
    return request.session

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, session: dict = Depends(get_session)):
    user = session.get("user")
    return templates.TemplateResponse("index.html", {"request": request, "user": user, "version": msal.__version__ if 'msal' in globals() else "N/A"})

@app.get("/login")
async def login(request: Request, session: dict = Depends(get_session)):
    session["state"] = str(uuid.uuid4())
    auth_url = msal_app.get_authorization_request_url(
        GRAPH_SCOPES,
        state=session["state"],
        redirect_uri=f"{BASE_URL}{REDIRECT_PATH}"
    )
    return RedirectResponse(auth_url)

@app.get(REDIRECT_PATH, response_class=HTMLResponse) # Azure AD redirects here
async def authorized(request: Request, session: dict = Depends(get_session), code: str = None, state: str = None, error: str = None, error_description: str = None):
    if state != session.get("state"):
        return RedirectResponse(url="/") # State mismatch, redirect to home
    if error: # Authentication error
        return templates.TemplateResponse("auth_error.html", {"request": request, "result": {"error": error, "error_description": error_description}})

    if code:
        cache = msal.SerializableTokenCache() # Initialize a cache for this session
        if session.get("token_cache"):
            cache.deserialize(session["token_cache"])

        result = msal_app.acquire_token_by_authorization_code(
            code,
            scopes=GRAPH_SCOPES,
            redirect_uri=f"{BASE_URL}{REDIRECT_PATH}",
            token_cache=cache
        )

        if "error" in result:
            return templates.TemplateResponse("auth_error.html", {"request": request, "result": result})

        session["user"] = result.get("id_token_claims")
        session["token_cache"] = cache.serialize()

    return RedirectResponse(url="/")

@app.get("/logout")
async def logout(request: Request, session: dict = Depends(get_session)):
    session.clear()  # Wipe out user and token cache from session
    logout_url = (
        AUTHORITY + "/oauth2/v2.0/logout" +
        "?post_logout_redirect_uri=" + f"{BASE_URL}/"
    )
    return RedirectResponse(logout_url)

@app.post("/teams_agent/message")
async def teams_message(message: Message, request: Request, session: dict = Depends(get_session)):
    if not session.get("user"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not logged in.")

    print(f"Received message for agent: {message.text}")

    token_result = get_token_from_cache(GRAPH_SCOPES, session)
    if not token_result or "access_token" not in token_result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not retrieve access token.")

    access_token = token_result['access_token']
    graph_url_me = "https://graph.microsoft.com/v1.0/me"
    headers = {'Authorization': f'Bearer {access_token}'}

    try:
        graph_response = requests.get(graph_url_me, headers=headers)
        graph_response.raise_for_status()
        user_profile = graph_response.json()

        agent_response = {
            "status": "message processed",
            "received_message": message.dict(),
            "user_display_name": user_profile.get("displayName", "N/A"),
            "user_principal_name": user_profile.get("userPrincipalName", "N/A"),
            "message": f"Hello {user_profile.get('displayName', 'User')}, your message '{message.text}' was received."
        }
        return agent_response

    except requests.exceptions.RequestException as e:
        print(f"Graph API call failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Graph API call failed: {str(e)}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {str(e)}")


# Helper to get token from cache
def get_token_from_cache(scopes: list = None, session: dict = None):
    if session is None: # Should not happen if called from request context
        return None
    if scopes is None:
        scopes = GRAPH_SCOPES

    cache = msal.SerializableTokenCache()
    if session.get("token_cache"):
        cache.deserialize(session["token_cache"])
    else:
        return None

    accounts = msal_app.get_accounts()
    if not accounts:
        return None

    result = msal_app.acquire_token_silent(scopes, account=accounts[0], token_cache=cache)

    if result and "access_token" in result:
        if cache.has_changed:
            session["token_cache"] = cache.serialize()
        return result
    else:
        print(f"Silent token acquisition failed. Result: {result}")
        return None

# Basic HTML templates (in-line for simplicity, ideally use separate files) - These routes are for testing UI, not part of core agent logic
@app.get("/render_auth_error", response_class=HTMLResponse)
async def auth_error_page(request: Request):
    return templates.TemplateResponse("auth_error.html", {"request": request, "result":{"error":"Sample Error", "error_description":"This is a sample error description."}})

@app.get("/render_index", response_class=HTMLResponse)
async def index_page(request: Request, session: dict = Depends(get_session)):
    user_data = {"name": "Test User"} if not session.get("user") else session.get("user")
    return templates.TemplateResponse("index.html", {"request": request, "user":user_data})

if __name__ == "__main__":
    # Important: For local development without HTTPS, you might need to set an environment variable:
    # OAUTHLIB_INSECURE_TRANSPORT='1' (though less relevant for FastAPI directly, good to be aware)
    # However, production MUST use HTTPS.
    uvicorn.run(app, host="0.0.0.0", port=5000)

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
#     <h1>Welcome, {{ user.name if user else "Guest" }}!</h1>
#     {% if user %}
#     <p><a href="/logout">Logout</a></p>
#     {% else %}
#     <p><a href="/login">Login</a></p>
#     {% endif %}
#     <p>MSAL Python Version: {{ version }}</p>
#     <h2>Agent Actions:</h2>
#     {% if user %}
#     <p>Send a test message to the agent (requires user to be logged in):</p>
#     <form id="messageForm">
#         <label for="message">Message:</label>
#         <input type="text" id="message" name="message" value="Hello Agent"><br><br>
#         <button type="button" onclick="sendMessage()">Send to Agent</button>
#     </form>
#     <p id="response"></p>
#     <script>
#         async function sendMessage() {
#             const messageText = document.getElementById('message').value;
#             const responseElement = document.getElementById('response');
#             try {
#                 const response = await fetch("/teams_agent/message", {
#                     method: 'POST',
#                     headers: {
#                         'Content-Type': 'application/json'
#                     },
#                     body: JSON.stringify({ text: messageText })
#                 });
#                 const result = await response.json();
#                 if (response.ok) {
#                     responseElement.textContent = 'Server response: ' + JSON.stringify(result);
#                 } else {
#                     responseElement.textContent = 'Error: ' + (result.detail || JSON.stringify(result));
#                 }
#             } catch (error) {
#                 responseElement.textContent = 'Error sending message: ' + error;
#             }
#         }
#     </script>
#     {% else %}
#     <p>Please login to send messages to the agent.</p>
#     {% endif %}
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
#     <p><a href="/">Go to Home Page</a></p>
# </body>
# </html>
