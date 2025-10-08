import { useState } from 'react';
import type { GameData } from '../types';
import { TrajectoryViewer } from './TrajectoryViewer';
import './RoundsList.css';

interface RoundsListProps {
  gameData: GameData;
  folderPath: string;
}

export function RoundsList({ gameData, folderPath }: RoundsListProps) {
  const [expandedRounds, setExpandedRounds] = useState<Set<number>>(new Set());

  const toggleRound = (roundNum: number) => {
    setExpandedRounds(prev => {
      const next = new Set(prev);
      if (next.has(roundNum)) {
        next.delete(roundNum);
      } else {
        next.add(roundNum);
      }
      return next;
    });
  };

  return (
    <div className="rounds-list">
      <h2>Rounds</h2>

      {gameData.rounds.map((round) => (
        <div key={round.round_num} className="round-card">
          <div className="round-header" onClick={() => toggleRound(round.round_num)}>
            <h3>Round {round.round_num}</h3>
            <span className="toggle-icon">{expandedRounds.has(round.round_num) ? '▼' : '▶'}</span>
          </div>

          {expandedRounds.has(round.round_num) && (
            <div className="round-content">
              {/* Round Results */}
              {round.results && (
                <div className="round-results">
                  <h4>Results</h4>

                  {round.results.winner && (
                    <div className="result-item">
                      <span className="result-label">Winner:</span>
                      <span className="result-value text-success">{round.results.winner}</span>
                    </div>
                  )}

                  {round.results.winner_percentage !== null && round.results.winner_percentage !== undefined && (
                    <div className="result-item">
                      <span className="result-label">Win Percentage:</span>
                      <span className="result-value">{round.results.winner_percentage}%</span>
                    </div>
                  )}

                  {round.results.p_value !== null && round.results.p_value !== undefined && (
                    <div className="result-item">
                      <span className="result-label">P-value:</span>
                      <span className="result-value">{round.results.p_value}</span>
                    </div>
                  )}

                  <h5 className="mt-2">Scores</h5>
                  <table>
                    <thead>
                      <tr>
                        <th>Player</th>
                        <th>Wins</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(round.results.scores)
                        .sort((a, b) => b[1] - a[1])
                        .map(([player, wins]) => (
                          <tr key={player}>
                            <td>{player}</td>
                            <td>{wins}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Trajectories for each player */}
              <div className="trajectories-section mt-3">
                <h4>Trajectories</h4>
                {gameData.agents.map((agent) => (
                  <TrajectoryViewer
                    key={agent.name}
                    folderPath={folderPath}
                    playerName={agent.name}
                    roundNum={round.round_num}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
