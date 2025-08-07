// frontend/src/App.js
import React, { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  // State to hold the list of albums
  const [albums, setAlbums] = useState([]);
  // State to check if user is logged in
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [selectedAlbum, setSelectedAlbum] = useState(null);
  const [songs, setSongs] = useState([]);
  const [currentSong, setCurrentSong] = useState(null);

  // NEW: State for metadata
  const [playCounts, setPlayCounts] = useState({ albums: {}, songs: {} });
  const [favorites, setFavorites] = useState({ albums: [], songs: [] });
  const [lastPlayedAlbumId, setLastPlayedAlbumId] = useState(null);

  // This ref will hold the latest metadata for the save-on-exit functionality
  const metadataRef = useRef();

  useEffect(() => {
    // Update the ref whenever the metadata state changes
    metadataRef.current = {
      playCounts,
      favorites,
      lastPlayedAlbumId,
    };
  }, [playCounts, favorites, lastPlayedAlbumId]);


  // This effect runs once when the component loads
  useEffect(() => {
    // --- 1. Check Login Status & Fetch Albums ---
    fetch('http://localhost:5000/api/albums', {credentials: 'include'})
      .then(res => {
        if (res.ok) {
          setIsLoggedIn(true);
          return res.json();
        }
        throw new Error("Not logged in");
      })
      .then(data => {
        setAlbums(data.albums);
        // --- 2. After getting albums, fetch the metadata ---
        return fetch('http://localhost:5000/api/metadata', {credentials: 'include'});
      })
      .then(res => res.json())
      .then(metadata => {
        setPlayCounts(metadata.playCounts || { albums: {}, songs: {} });
        setFavorites(metadata.favorites || { albums: [], songs: [] });
        setLastPlayedAlbumId(metadata.lastPlayedAlbumId);
      })
      .catch(error => {
        console.error(error.message);
        if (error.message === "Not logged in") {
          setIsLoggedIn(false);
        }
      });

    // --- 3. Setup Save-on-Exit ---
    const handleBeforeUnload = (event) => {
      // Use the ref to get the latest metadata
      const metadata = metadataRef.current;
      
      // Use navigator.sendBeacon to send a POST request with the data
      const blob = new Blob([JSON.stringify(metadata)], { type: 'application/json' });
      navigator.sendBeacon('http://localhost:5000/api/metadata', blob);
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    // Cleanup function to remove the event listener
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, []);

  // Function to handle the login button click
  const handleLogin = () => {
    // Redirect the user to our backend's login route
    window.location.href = 'http://localhost:5000/login';
  };

  // Function to handle clicking on an album
  const handleAlbumClick = (albumId) => {
    setSelectedAlbum(albumId);
    fetch(`http://localhost:5000/api/albums/${albumId}/songs`, {credentials: 'include'})
      .then(res => res.json())
      .then(data => setSongs(data.songs || [])) // Ensure songs is an array
      .catch(error => {
        console.error("Error fetching songs:", error);
        setSongs([]); // Clear songs on error
      });
  };

  // ----  Function to handle song playback and update counts ---
  const handleSongPlay = (song) => {
    setCurrentSong(song);
    // Update play count for the song
    setPlayCounts(prevCounts => ({
      ...prevCounts,
      songs: {
        ...prevCounts.songs,
        [song.id]: (prevCounts.songs[song.id] || 0) + 1
      }
    }));
    // Update play count for the album
    setPlayCounts(prevCounts => ({
      ...prevCounts,
      albums: {
        ...prevCounts.albums,
        [selectedAlbum]: (prevCounts.albums[selectedAlbum] || 0) + 1
      }
    }));
    setLastPlayedAlbumId(selectedAlbum);
  };

  // Login screen (if not logged in)
  if (!isLoggedIn) {
    return (
      <div className="app-container">
        <div className="login-container">
          <h1>Welcome to Your Music Sanctuary</h1>
          <p>Please log in with Google to continue</p>
          <button className="login-button" onClick={handleLogin}>
            Login with Google
          </button>
        </div>
      </div>
    );
  }

  // Logged in user
  return (
    <div className="app-container">
      <div className="player-panel">
        <h2>Album Player</h2>
        {currentSong && (
          <div>
            <h3>Now Playing</h3>
            <p>{currentSong.name}</p>
            <audio controls autoPlay src={`http://localhost:5000/api/stream/${currentSong.id}`} />
          </div>
        )}
        {selectedAlbum && !currentSong && (
          <p>Select a song to play.</p>
        )}
        {!selectedAlbum && (
           <p>Click an album on the right to play.</p>
        )}
        {songs.length > 0 && (
          <div>
            <h3>Songs</h3>
            <ul>
              {songs.map(song => (
                 <li key={song.id} onClick={() => handleSongPlay(song)}>
                  {song.name} - (Plays: {playCounts.songs[song.id] || 0})
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <div className="grid-panel">
        <h2>Your Library</h2>
        <div className="album-grid">
          {albums.map(album => (
            <div key={album.id} className="album-card" onClick={() => handleAlbumClick(album.id)}>
              <p>{album.name}</p>
              <p className="play-count">Plays: {playCounts.albums[album.id] || 0}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default App;