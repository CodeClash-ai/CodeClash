import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../utils/api';
import type { GameData } from '../types';
import { Overview } from './Overview';
import { Analysis } from './Analysis';
import { RoundsList } from './RoundsList';
import './GameViewer.css';

export function GameViewer() {
  const params = useParams();
  const navigate = useNavigate();
  const [gameData, setGameData] = useState<GameData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Extract folder path from wildcard route parameter
  const folderPath = params['*'] || '';

  useEffect(() => {
    if (folderPath) {
      loadGame();
    }
  }, [folderPath]);

  const loadGame = async () => {
    if (!folderPath) return;

    try {
      setLoading(true);
      setError(null);
      console.log('Loading game data for:', folderPath);
      const data = await api.getGame(folderPath);
      console.log('Game data loaded:', data);
      setGameData(data);
    } catch (err: any) {
      console.error('Error loading game:', err);
      const errorMessage = err.response?.data?.error || err.message || 'Failed to load game data';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleBackToPicker = () => {
    navigate('/');
  };

  if (loading) {
    return <div className="loading">Loading game data...</div>;
  }

  if (error) {
    return (
      <div className="container">
        <div className="error">
          <p>Error: {error}</p>
          <button onClick={loadGame}>Retry</button>
          <button onClick={handleBackToPicker} className="secondary">Back to Picker</button>
        </div>
      </div>
    );
  }

  if (!gameData) {
    return (
      <div className="container">
        <div className="error">
          <p>No game data available</p>
          <button onClick={handleBackToPicker}>Back to Picker</button>
        </div>
      </div>
    );
  }

  return (
    <div className="game-viewer">
      <div className="game-header">
        <button onClick={handleBackToPicker} className="back-button">
          ← Back to Games
        </button>
        <h2>{folderPath}</h2>
      </div>

      <Overview gameData={gameData} folderPath={folderPath} />
      <Analysis folderPath={folderPath} />
      <RoundsList gameData={gameData} folderPath={folderPath} />
    </div>
  );
}
