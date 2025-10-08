import { useState, useEffect } from 'react';
import { api } from '../utils/api';
import type { Trajectory } from '../types';
import './TrajectoryViewer.css';

interface TrajectoryViewerProps {
  folderPath: string;
  playerName: string;
  roundNum: number;
}

export function TrajectoryViewer({ folderPath, playerName, roundNum }: TrajectoryViewerProps) {
  const [trajectory, setTrajectory] = useState<Trajectory | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [expandedMessages, setExpandedMessages] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (isExpanded && !trajectory && !loading) {
      loadTrajectory();
    }
  }, [isExpanded]);

  const loadTrajectory = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getTrajectory(folderPath, playerName, roundNum);
      setTrajectory(data);
    } catch (err: any) {
      console.log(`Trajectory not found for ${playerName} round ${roundNum}`);
      // Don't show error for missing trajectories - it's common for incomplete games
      const errorMsg = err.response?.status === 404
        ? `No trajectory data available for round ${roundNum}`
        : (err.message || 'Failed to load trajectory');
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const toggleMessage = (index: number) => {
    setExpandedMessages(prev => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const truncateContent = (content: string, maxLength: number = 200) => {
    if (content.length <= maxLength) return content;
    return content.substring(0, maxLength) + '...';
  };

  return (
    <div className="trajectory-viewer">
      <div className="trajectory-header" onClick={() => setIsExpanded(!isExpanded)}>
        <h5>{playerName}</h5>
        <span className="toggle-icon">{isExpanded ? '▼' : '▶'}</span>
      </div>

      {isExpanded && (
        <div className="trajectory-content">
          {loading && <div className="loading-small">Loading trajectory...</div>}

          {error && (
            <div className="error-small">
              <p>Error: {error}</p>
              <button onClick={loadTrajectory} className="small">Retry</button>
            </div>
          )}

          {trajectory && (
            <>
              {/* Stats */}
              <div className="trajectory-stats">
                <div className="stat-item">
                  <span className="stat-label">API Calls:</span>
                  <span className="stat-value">{trajectory.api_calls}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Cost:</span>
                  <span className="stat-value">${trajectory.cost.toFixed(4)}</span>
                </div>
                {trajectory.exit_status && (
                  <div className="stat-item">
                    <span className="stat-label">Exit Status:</span>
                    <span className={`stat-value ${trajectory.exit_status === 'success' ? 'text-success' : 'text-error'}`}>
                      {trajectory.exit_status}
                    </span>
                  </div>
                )}
                {trajectory.valid_submission !== null && (
                  <div className="stat-item">
                    <span className="stat-label">Valid Submission:</span>
                    <span className={`stat-value ${trajectory.valid_submission ? 'text-success' : 'text-error'}`}>
                      {trajectory.valid_submission ? 'Yes' : 'No'}
                    </span>
                  </div>
                )}
              </div>

              {/* Messages */}
              {trajectory.messages && trajectory.messages.length > 0 && (
                <details className="mt-2">
                  <summary>Messages ({trajectory.messages.length})</summary>
                  <div className="content">
                    {trajectory.messages.map((message, idx) => (
                      <div key={idx} className="message-block">
                        <div className="message-header">
                          <span className={`message-role ${message.role}`}>{message.role}</span>
                        </div>
                        <div className="message-content">
                          {expandedMessages.has(idx) ? (
                            <>
                              <pre>{message.content}</pre>
                              <button
                                onClick={() => toggleMessage(idx)}
                                className="small secondary mt-1"
                              >
                                Show Less
                              </button>
                            </>
                          ) : (
                            <>
                              <pre>{truncateContent(message.content)}</pre>
                              {message.content.length > 200 && (
                                <button
                                  onClick={() => toggleMessage(idx)}
                                  className="small secondary mt-1"
                                >
                                  Show More
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </details>
              )}

              {/* Diffs */}
              {trajectory.diff_by_files && Object.keys(trajectory.diff_by_files).length > 0 && (
                <details className="mt-2">
                  <summary>Full Diff ({Object.keys(trajectory.diff_by_files).length} files)</summary>
                  <div className="content">
                    {Object.entries(trajectory.diff_by_files).map(([filePath, diff]) => (
                      <details key={filePath} className="file-diff">
                        <summary>{filePath}</summary>
                        <div className="content">
                          <pre><code>{diff}</code></pre>
                        </div>
                      </details>
                    ))}
                  </div>
                </details>
              )}

              {trajectory.incremental_diff_by_files && Object.keys(trajectory.incremental_diff_by_files).length > 0 && (
                <details className="mt-2">
                  <summary>Incremental Diff ({Object.keys(trajectory.incremental_diff_by_files).length} files)</summary>
                  <div className="content">
                    {Object.entries(trajectory.incremental_diff_by_files).map(([filePath, diff]) => (
                      <details key={filePath} className="file-diff">
                        <summary>{filePath}</summary>
                        <div className="content">
                          <pre><code>{diff}</code></pre>
                        </div>
                      </details>
                    ))}
                  </div>
                </details>
              )}

              {/* Modified Files */}
              {trajectory.modified_files && Object.keys(trajectory.modified_files).length > 0 && (
                <details className="mt-2">
                  <summary>Modified Files ({Object.keys(trajectory.modified_files).length} files)</summary>
                  <div className="content">
                    {Object.entries(trajectory.modified_files).map(([filePath, content]) => (
                      <details key={filePath} className="file-diff">
                        <summary>{filePath}</summary>
                        <div className="content">
                          <pre><code>{content}</code></pre>
                        </div>
                      </details>
                    ))}
                  </div>
                </details>
              )}

              {/* Submission */}
              {trajectory.submission && (
                <details className="mt-2">
                  <summary>Submission</summary>
                  <div className="content">
                    <pre>{trajectory.submission}</pre>
                  </div>
                </details>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
