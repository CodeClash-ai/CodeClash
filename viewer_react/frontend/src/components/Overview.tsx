import { useState } from 'react';
import type { GameData } from '../types';
import './Overview.css';

interface OverviewProps {
  gameData: GameData;
  folderPath: string;
}

export function Overview({ gameData }: OverviewProps) {
  const [showRawMetadata, setShowRawMetadata] = useState(false);

  const scrollToRound = (roundNum: number) => {
    const roundElement = document.querySelector(`[data-round="${roundNum}"]`);
    if (roundElement) {
      roundElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <div className="card overview-section" id="overview">
      <h2>📊 Overview</h2>

      <div className="overview-summary">
        <table className="results-table">
          <thead>
            <tr>
              <th>ROUND</th>
              <th>WINNER</th>
              <th>RESULTS</th>
              {gameData.agents.map((agent) => (
                <th key={agent.name}>{agent.name.toUpperCase()}</th>
              ))}
              <th>ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            {gameData.rounds.map((round) => {
              const results = round.results;
              const scores = results.scores || {};
              const sortedScores = Object.entries(scores)
                .filter(([player]) => player !== 'Tie')
                .sort((a, b) => b[1] - a[1]);

              return (
                <tr key={round.round_num}>
                  <td>{round.round_num}</td>
                  <td>
                    {results.winner ? (
                      <div className="winner-breakdown">
                        <span className="winner-badge">{results.winner}</span>
                        {results.winner_percentage !== null && results.winner_percentage !== undefined && (
                          <span className="score-item">{results.winner_percentage}%</span>
                        )}
                        {results.p_value !== null && results.p_value !== undefined && (
                          <span className="score-item">p={results.p_value.toFixed(2)}</span>
                        )}
                      </div>
                    ) : (
                      <span className="no-result">-</span>
                    )}
                  </td>
                  <td>
                    {sortedScores.length > 0 ? (
                      <div className="score-breakdown">
                        {sortedScores.map(([player, score]) => (
                          <span key={player} className="score-item">
                            {player}: {score}
                          </span>
                        ))}
                        {scores.Tie && scores.Tie > 0 && (
                          <span className="score-item">Tie: {scores.Tie}</span>
                        )}
                      </div>
                    ) : (
                      <span className="no-result">-</span>
                    )}
                  </td>
                  {gameData.agents.map((agent) => {
                    const playerStats = round.player_stats?.[agent.name];
                    return (
                      <td key={agent.name}>
                        {playerStats ? (
                          <div className="overview-cell-content">
                            <span className="steps-price">
                              {playerStats.api_calls}/${playerStats.cost.toFixed(2)}
                            </span>
                            {playerStats.exit_status ? (
                              <span className={`exit-status-small status-${playerStats.exit_status.toLowerCase()}`}>
                                {playerStats.exit_status}
                              </span>
                            ) : (
                              <span className="no-result">-</span>
                            )}
                          </div>
                        ) : (
                          <span className="no-result">-</span>
                        )}
                      </td>
                    );
                  })}
                  <td>
                    <button
                      className="nav-to-round-btn"
                      onClick={() => scrollToRound(round.round_num)}
                      title={`Jump to Round ${round.round_num} details`}
                    >
                      <span className="nav-arrow">↓</span>
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

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
