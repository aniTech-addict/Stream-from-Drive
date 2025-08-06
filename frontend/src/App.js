// frontend/src/App.js
import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  // State to hold the list of albums
  const [albums, setAlbums] = useState([]);
  // State to check if user is logged in
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  // This effect runs once when the component loads
  useEffect(() => {
    // Fetch albums from our Flask API
    fetch('http://localhost:5000/api/albums',{credentials: 'include'})
      .then(res => {
        if (res.ok) {
          setIsLoggedIn(true);
          return res.json();
        }
        throw new Error("Not logged in");
      })
      .then(data => {
        setAlbums(data.albums);
      })
      .catch(error => {
        console.error(error);
        setIsLoggedIn(false);
      });
  }, []);

  // Function to handle the login button click
  const handleLogin = () => {
    // Redirect the user to our backend's login route
    window.location.href = 'http://localhost:5000/login';
  };

  // If the user is not logged in, show the login screen
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

  // If the user is logged in, show the main app
  return (
    <div className="app-container">
      <div className="player-panel">
        <h2>Album Player</h2>
        <p>Click an album on the right to play.</p>
      </div>
      <div className="grid-panel">
        <h2>Your Library</h2>
        <div className="album-grid">
          {albums.map(album => (
            <div key={album.id} className="album-card">
              <p>{album.name}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default App;