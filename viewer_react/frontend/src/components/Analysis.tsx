import { useState, useEffect } from 'react';
import { api } from '../utils/api';
import type { SimWinsData } from '../types';
import './Analysis.css';

interface AnalysisProps {
  folderPath: string;
}

export function Analysis({ folderPath }: AnalysisProps) {
  const [simWinsData, setSimWinsData] = useState<SimWinsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    if (isExpanded && !simWinsData && !loading) {
      loadAnalysis();
    }
  }, [isExpanded]);

  const loadAnalysis = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getSimWinsAnalysis(folderPath);
      setSimWinsData(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load analysis');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <div className="card-header" onClick={() => setIsExpanded(!isExpanded)} style={{ cursor: 'pointer' }}>
        <h2>
          Analysis
          <span className="toggle-icon" style={{ marginLeft: '0.5rem', fontSize: '0.9rem' }}>
            {isExpanded ? '▼' : '▶'}
          </span>
        </h2>
      </div>

      {isExpanded && (
        <div className="analysis-content">
          {loading && <div className="loading-small">Loading analysis...</div>}

          {error && (
            <div className="error-small">
              <p>Error: {error}</p>
              <button onClick={loadAnalysis} className="small">Retry</button>
            </div>
          )}

          {simWinsData && (
            <>
              <h3>Simulation Wins Per Round</h3>
              <p className="text-muted mb-2">
                Score shown as percentage: (wins + 0.5 × ties) / total games × 100
              </p>

              {/* Simple table view of scores */}
              <div className="scores-table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Round</th>
                      {simWinsData.players.map(player => (
                        <th key={player}>{player}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {simWinsData.rounds.map((round, idx) => (
                      <tr key={round}>
                        <td>Round {round}</td>
                        {simWinsData.players.map(player => {
                          const score = simWinsData.scores_by_player[player][idx];
                          return (
                            <td key={player}>
                              <span className={score > 50 ? 'text-success' : score < 50 ? 'text-warning' : ''}>
                                {score.toFixed(1)}%
                              </span>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Simple ASCII-style chart */}
              <details className="mt-3">
                <summary>ASCII Chart</summary>
                <div className="content">
                  <pre className="ascii-chart">
                    {generateAsciiChart(simWinsData)}
                  </pre>
                </div>
              </details>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function generateAsciiChart(data: SimWinsData): string {
  const width = 60;
  const height = 20;
  let chart = '';

  chart += 'Win Rate (%) vs Round\n';
  chart += '100% ┤\n';

  const maxRound = Math.max(...data.rounds);
  const minRound = Math.min(...data.rounds);

  // Generate chart lines
  for (let y = 90; y >= 10; y -= 10) {
    let line = y.toString().padStart(4, ' ') + '% ┤';

    for (let roundIdx = 0; roundIdx < data.rounds.length; roundIdx++) {
      // Check if any player has a score near this y-value
      let hasPoint = false;
      for (const player of data.players) {
        const score = data.scores_by_player[player][roundIdx];
        if (Math.abs(score - y) < 5) {
          hasPoint = true;
          break;
        }
      }
      line += hasPoint ? '●' : ' ';
    }

    chart += line + '\n';
  }

  chart += '  0% └' + '─'.repeat(data.rounds.length) + '\n';
  chart += '     ';

  // Add round numbers
  for (const round of data.rounds) {
    chart += round.toString()[0];
  }
  chart += '\n';

  // Legend
  chart += '\nPlayers: ' + data.players.join(', ') + '\n';

  return chart;
}
