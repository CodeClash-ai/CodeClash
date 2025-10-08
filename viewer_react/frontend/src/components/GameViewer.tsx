import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../utils/api';
import type { GameData } from '../types';
import { Header, HelpModal } from './Header';
import { Storage } from './Storage';
import { ScoresChart } from './ScoresChart';
import { Readme } from './Readme';
import { Overview } from './Overview';
import { Analysis } from './Analysis';
import { RoundsList } from './RoundsList';
import { FloatingToc } from './FloatingToc';
import './GameViewer.css';

export function GameViewer() {
  const params = useParams();
  const navigate = useNavigate();
  const [gameData, setGameData] = useState<GameData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showHelp, setShowHelp] = useState(false);

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

  const handleMoveFolder = (newPath: string) => {
    navigate(`/game/${newPath}`);
  };

  const handleDeleteFolder = () => {
    navigate('/');
  };

  if (loading) {
    return (
      <>
        <Header onShowHelp={() => setShowHelp(true)} />
        <div className="container">
          <div className="loading">Loading game data...</div>
        </div>
      </>
    );
  }

  if (error) {
    return (
      <>
        <Header onShowHelp={() => setShowHelp(true)} />
        <div className="container">
          <div className="error">
            <p>Error: {error}</p>
            <button onClick={loadGame}>Retry</button>
            <button onClick={() => navigate('/')} className="secondary">Back to Picker</button>
          </div>
        </div>
      </>
    );
  }

  if (!gameData) {
    return (
      <>
        <Header onShowHelp={() => setShowHelp(true)} />
        <div className="container">
          <div className="error">
            <p>No game data available</p>
            <button onClick={() => navigate('/')}>Back to Picker</button>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Header
        navigation={gameData.navigation}
        currentFolder={folderPath}
        onShowHelp={() => setShowHelp(true)}
      />

      <div className="container game-viewer">
        <Storage
          gameData={gameData}
          folderPath={folderPath}
          onMoveFolder={handleMoveFolder}
          onDeleteFolder={handleDeleteFolder}
        />

        <ScoresChart folderPath={folderPath} />

        <Readme folderPath={folderPath} />

        <Overview gameData={gameData} folderPath={folderPath} />

        <Analysis folderPath={folderPath} />

        <RoundsList gameData={gameData} folderPath={folderPath} />
      </div>

      <HelpModal isOpen={showHelp} onClose={() => setShowHelp(false)} />
      <FloatingToc gameData={gameData} />
    </>
  );
}
