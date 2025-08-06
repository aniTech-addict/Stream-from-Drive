# backend/app.py

import os
from flask import Flask, redirect, url_for, session, request, jsonify
from flask_cors import CORS
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- Configuration ---
app = Flask(__name__)
app.secret_key = 'your-super-secret-key-change-me'
CORS(app, supports_credentials=True)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid',
    'https://www.googleapis.com/auth/drive.readonly'
]
REDIRECT_URI = 'http://localhost:5000/oauth2callback'


# --- NEW: Helper Function ---
def credentials_to_dict(credentials):
    """
    A helper function to safely convert the credentials object to a dictionary.
    This is the format that we can store in the Flask session.
    """
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}


# --- Routes ---
@app.route('/api/albums')
def get_albums():
    if 'credentials' not in session:
        return jsonify({"error": "User not authenticated"}), 401

    # Recreate the credentials object from the dictionary stored in the session.
    creds = Credentials(**session['credentials'])
    drive_service = build('drive', 'v3', credentials=creds)
    results = drive_service.files().list(
        q="'root' in parents and mimeType='application/vnd.google-apps.folder'",
        pageSize=30,
        fields="files(id, name)"
    ).execute()
    items = results.get('files', [])
    return jsonify({"albums": items})


@app.route('/api/albums/<album_id>/songs')
def get_songs(album_id):
    if 'credentials' not in session:
        return jsonify({"error": "User not authenticated"}), 401
    creds = Credentials(**session['credentials'])
    drive_service = build('drive', 'v3', credentials=creds)

    # List files (songs) inside the specific folder (album_id)
    # We are looking for audio files. You can be more specific with mimeTypes
    # e.g. "mimeType='audio/mpeg' or mimeType='audio/wav'"
    q = f"'{album_id}' in parents and (mimeType contains 'audio/') "

    results = drive_service.files().list(
        q=q,
        pageSize=100,  # Get up to 100 songs
        fields="files(id, name)"
    ).execute()
    items = results.get('files', [])
    return jsonify({"songs": items})


@app.route('/api/stream/<song_id>')
def stream_song(song_id):
    if 'credentials' not in session:
        return jsonify({"error": "User not authenticated"}), 401
    creds = Credentials(**session['credentials'])
    drive_service = build('drive', 'v3', credentials=creds)

    request = drive_service.files().get_media(fileId=song_id)
    
    import io
    from flask import Response
    fh = io.BytesIO()
    downloader = request
    downloader.stream(fh)

    return Response(fh.getvalue(), mimetype="audio/mpeg")
    

@app.route('/')
def index():
    return "Backend is running!"


@app.route('/login')
def login():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    # This is important! It tells Google we want a refresh_token (Permanent ID).
    authorization_url, state = flow.authorization_url(
        include_granted_scopes='true'
    )
    session['state'] = state
    return redirect(authorization_url)


# --- UPDATED: /oauth2callback Route ---
@app.route('/oauth2callback')
def oauth2callback():
    state = session['state']
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state, redirect_uri=REDIRECT_URI
    )

    # This line exchanges the temporary code for credentials.
    flow.fetch_token(authorization_response=request.url)

    # Store the credentials in the session using our new helper function.
    session['credentials'] = credentials_to_dict(flow.credentials)

    return redirect("http://localhost:3000/")


@app.route('/logout')
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)