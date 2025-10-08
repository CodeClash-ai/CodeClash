import { useState } from 'react';
import type { GameData } from '../types';
import './Overview.css';

interface OverviewProps {
  gameData: GameData;
  folderPath: string;
}

export function Overview({ gameData }: OverviewProps) {
  const [showRawMetadata, setShowRawMetadata] = useState(false);

  const gameName = gameData.metadata?.config?.game?.name || gameData.metadata?.game?.name || 'Unknown';
  const totalRounds = gameData.metadata?.config?.tournament?.rounds;
  const completedRounds = gameData.rounds.filter(r => r.round_num > 0).length;

  // Get final scores from the last round
  const finalRound = gameData.rounds[gameData.rounds.length - 1];
  const finalScores = finalRound?.results?.scores || {};

  return (
    <div className="card overview-section">
      <h2>Overview</h2>

      <div className="overview-grid">
        <div className="overview-item">
          <span className="overview-label">Game:</span>
          <span className="overview-value">{gameName}</span>
        </div>

        {totalRounds && (
          <div className="overview-item">
            <span className="overview-label">Rounds:</span>
            <span className="overview-value">{completedRounds} / {totalRounds}</span>
          </div>
        )}

        <div className="overview-item">
          <span className="overview-label">Players:</span>
          <span className="overview-value">{gameData.agents.length}</span>
        </div>
      </div>

      <h3 className="mt-3">Agents</h3>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Model</th>
            <th>Agent Class</th>
          </tr>
        </thead>
        <tbody>
          {gameData.agents.map((agent, idx) => (
            <tr key={idx}>
              <td>{agent.name}</td>
              <td>{agent.model_name || '-'}</td>
              <td>{agent.agent_class || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {Object.keys(finalScores).length > 0 && (
        <>
          <h3 className="mt-3">Final Scores</h3>
          <table>
            <thead>
              <tr>
                <th>Player</th>
                <th>Wins</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(finalScores)
                .sort((a, b) => b[1] - a[1])
                .map(([player, wins]) => (
                  <tr key={player}>
                    <td>{player}</td>
                    <td>{wins}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </>
      )}

      <details className="mt-3">
        <summary onClick={() => setShowRawMetadata(!showRawMetadata)}>
          📋 Configuration & Metadata
        </summary>
        <div className="content">
          <div className="metadata-viewer">
            <pre>
              <code>{JSON.stringify(gameData.metadata, null, 2)}</code>
            </pre>
          </div>
        </div>
      </details>
    </div>
  );
}
