# backend/app.py

import os
import json
from flask import Flask, redirect, url_for, session, request, jsonify
from flask_cors import CORS
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

# --- Configuration ---
app = Flask(__name__)
app.secret_key = 'inki_pinki_ponki'
CORS(app, supports_credentials=True)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Build the absolute path to the client secrets file for robustness
_BASEDIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS_FILE = os.path.join(_BASEDIR, "client_secret.json")
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid',
    'https://www.googleapis.com/auth/drive.file'
]
REDIRECT_URI = 'http://localhost:5000/oauth2callback'


# --- Helper Functions ---
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

def get_or_create_priva_folder_and_metadata(drive_service):
    """
    Checks for the 'Priva-music' folder and 'priva_metadata.json' file.
    Creates them if they don't exist. Stores their IDs in the session.
    """
    # Check for Priva-music folder in root
    q = "name='Priva-music' and 'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    response = drive_service.files().list(q=q, spaces='drive', fields='files(id, name)').execute()
    files = response.get('files', [])

    if not files:
        # Create Priva-music folder if it doesn't exist
        file_metadata = {'name': 'Priva-music', 'mimeType': 'application/vnd.google-apps.folder'}
        priva_folder = drive_service.files().create(body=file_metadata, fields='id').execute()
        priva_folder_id = priva_folder.get('id')
    else:
        priva_folder_id = files[0].get('id')

    # Store folder ID in session
    session['priva_folder_id'] = priva_folder_id

    # Check for priva_metadata.json in the folder
    q = f"name='priva_metadata.json' and '{priva_folder_id}' in parents and trashed=false"
    response = drive_service.files().list(q=q, spaces='drive', fields='files(id)').execute()
    files = response.get('files', [])

    if not files:
        # Create priva_metadata.json with default structure
        file_metadata = {'name': 'priva_metadata.json', 'parents': [priva_folder_id]}
        default_metadata = {
            "lastPlayedAlbumId": "",
            "playCounts": {"albums": {}, "songs": {}},
            "favorites": {"albums": [], "songs": []}
        }
        fh = io.BytesIO(json.dumps(default_metadata).encode('utf-8'))
        media = MediaIoBaseUpload(fh, mimetype='application/json', resumable=True)
        metadata_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        metadata_file_id = metadata_file.get('id')
    else:
        metadata_file_id = files[0].get('id')
    
    session['metadata_file_id'] = metadata_file_id


# --- Routes ---
@app.route('/api/albums')
def get_albums():
    if 'credentials' not in session or 'priva_folder_id' not in session:
        return jsonify({"error": "User not authenticated or app not initialized"}), 401

    creds = Credentials(**session['credentials'])
    drive_service = build('drive', 'v3', credentials=creds)

    priva_folder_id = session['priva_folder_id']
    
    # List folders (albums) inside the 'Priva-music' folder
    results = drive_service.files().list(
        q=f"'{priva_folder_id}' in parents and mimeType='application/vnd.google-apps.folder'",
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
        prompt='consent',
        access_type='offline',
        include_granted_scopes='true'
    )
    session['state'] = state
    return redirect(authorization_url)


# --- OAuth Routes ---
@app.route('/oauth2callback')
def oauth2callback():
    # First, verify we have the state from the session
    if 'state' not in session:
        return "Error: Missing state parameter", 400
    
    # Create the flow object with the state
    state = session['state']
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state, redirect_uri=REDIRECT_URI
    )
    
    # Debug logging
    print(f"Full callback URL: {request.url}")
    print(f"Request args: {request.args}")
    
    # Now fetch the token (only once!)
    try:
        flow.fetch_token(authorization_response=request.url)
    except Exception as e:
        print(f"OAuth error: {e}")
        print(f"Request URL: {request.url}")
        print(f"Error args: {request.args}")
        return f"Authentication failed: {e}", 400
    
    # Store credentials in session
    session['credentials'] = credentials_to_dict(flow.credentials)

    # After login, ensure user's Drive is set up
    creds = Credentials(**session['credentials'])
    drive_service = build('drive', 'v3', credentials=creds)
    get_or_create_priva_folder_and_metadata(drive_service)

    return redirect("http://localhost:3000/")

@app.route('/logout')
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})

# --- NEW: Metadata Routes ---
@app.route('/api/metadata')
def get_metadata():
    if 'credentials' not in session or 'metadata_file_id' not in session:
        return jsonify({"error": "Metadata not available"}), 401

    creds = Credentials(**session['credentials'])
    drive_service = build('drive', 'v3', credentials=creds)
    
    metadata_file_id = session['metadata_file_id']
    
    # Download and return the metadata file content
    request = drive_service.files().get_media(fileId=metadata_file_id)
    fh = io.BytesIO()
    request.stream(fh)
    
    return jsonify(json.loads(fh.getvalue()))

@app.route('/api/metadata', methods=['POST'])
def update_metadata():
    app.logger.info(f"Metadata update request received.")
    app.logger.info(f"Request Headers: {request.headers}")
    app.logger.info(f"Request Data: {request.get_data(as_text=True)}")

    if 'credentials' not in session or 'metadata_file_id' not in session:
        app.logger.error("Credentials or metadata_file_id not in session.")
        return jsonify({"error": "Cannot update metadata, session invalid."}), 401
    
    creds = Credentials(**session['credentials'])
    drive_service = build('drive', 'v3', credentials=creds)
    
    metadata_file_id = session['metadata_file_id']
    
    # Manually parse the JSON data from the request body
    try:
        new_metadata = json.loads(request.get_data(as_text=True))
        app.logger.info(f"Successfully parsed metadata: {new_metadata}")
    except json.JSONDecodeError:
        app.logger.error("Failed to decode JSON from request body.")
        return jsonify({"error": "Bad Request: Invalid JSON"}), 400

    # Update the metadata file in Google Drive
    try:
        fh = io.BytesIO(json.dumps(new_metadata).encode('utf-8'))
        media = MediaIoBaseUpload(fh, mimetype='application/json', resumable=True)
        
        drive_service.files().update(fileId=metadata_file_id, media_body=media).execute()
        app.logger.info("Successfully updated metadata file in Google Drive.")
    except Exception as e:
        app.logger.error(f"Error updating Google Drive file: {e}")
        return jsonify({"error": "Failed to update Google Drive file"}), 500
    
    return jsonify({"success": True})


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)