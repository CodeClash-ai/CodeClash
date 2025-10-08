import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../utils/api';
import type { GameFolder } from '../types';
import './GamePicker.css';

interface FolderState {
  collapsed: boolean;
  selected: boolean;
}

// Helper functions defined outside component
const stripModelPrefix = (modelName: string) => {
  if (!modelName) return '';
  return modelName.split('/').pop() || modelName;
};

const formatTimestamp = (timestamp: number | null) => {
  if (!timestamp) return '';
  const date = new Date(timestamp * 1000);
  return date.toISOString().slice(0, 16).replace('T', ' ');
};

const formatDate = (timestamp: number | null) => {
  if (!timestamp) return '';
  const date = new Date(timestamp * 1000);
  return date.toISOString().slice(0, 10);
};

export function GamePicker() {
  const [folders, setFolders] = useState<GameFolder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [folderStates, setFolderStates] = useState<Map<string, FolderState>>(new Map());

  // Filters
  const [selectedGame, setSelectedGame] = useState('');
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  // Sorting
  const [sortColumn, setSortColumn] = useState<'name' | 'date' | null>(null);
  const [sortAscending, setSortAscending] = useState(true);

  // Selection
  const [selectAll, setSelectAll] = useState(false);
  const [lastClickedCheckbox, setLastClickedCheckbox] = useState<string | null>(null);

  const navigate = useNavigate();

  useEffect(() => {
    loadFolders();
  }, []);

  const loadFolders = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getFolders();
      setFolders(data);

      // Initialize folder states
      const states = new Map<string, FolderState>();
      data.forEach(folder => {
        if (!folder.is_game) {
          states.set(folder.name, { collapsed: true, selected: false });
        } else {
          states.set(folder.name, { collapsed: false, selected: false });
        }
      });
      setFolderStates(states);
    } catch (err: any) {
      setError(err.message || 'Failed to load folders');
    } finally {
      setLoading(false);
    }
  };

  // Extract unique games and models for filters
  const { uniqueGames, uniqueModels } = useMemo(() => {
    const games = new Set<string>();
    const models = new Set<string>();

    folders.forEach(folder => {
      if (folder.is_game) {
        if (folder.game_name) games.add(folder.game_name);
        if (folder.models) {
          folder.models.forEach(model => {
            const shortModel = stripModelPrefix(model);
            models.add(shortModel);
          });
        }
      }
    });

    return {
      uniqueGames: Array.from(games).sort(),
      uniqueModels: Array.from(models).sort(),
    };
  }, [folders]);

  const handleFolderClick = (folder: GameFolder, newTab = false) => {
    if (newTab) {
      window.open(`/game/${folder.name}`, '_blank');
    } else {
      navigate(`/game/${folder.name}`);
    }
  };

  const toggleFolder = (folderName: string) => {
    setFolderStates(prev => {
      const newStates = new Map(prev);
      const state = newStates.get(folderName) || { collapsed: true, selected: false };
      newStates.set(folderName, { ...state, collapsed: !state.collapsed });
      return newStates;
    });
  };

  const toggleSelection = (folderName: string, shiftKey = false) => {
    setFolderStates(prev => {
      const newStates = new Map(prev);

      if (shiftKey && lastClickedCheckbox) {
        // Range selection
        const gameFolders = folders.filter(f => f.is_game);
        const startIdx = gameFolders.findIndex(f => f.name === lastClickedCheckbox);
        const endIdx = gameFolders.findIndex(f => f.name === folderName);

        if (startIdx !== -1 && endIdx !== -1) {
          const [min, max] = [Math.min(startIdx, endIdx), Math.max(startIdx, endIdx)];
          const targetState = !(newStates.get(folderName)?.selected || false);

          for (let i = min; i <= max; i++) {
            const name = gameFolders[i].name;
            const state = newStates.get(name) || { collapsed: false, selected: false };
            newStates.set(name, { ...state, selected: targetState });
          }
        }
      } else {
        const state = newStates.get(folderName) || { collapsed: false, selected: false };
        newStates.set(folderName, { ...state, selected: !state.selected });
      }

      setLastClickedCheckbox(folderName);
      return newStates;
    });
  };

  const handleSelectAll = (checked: boolean) => {
    setSelectAll(checked);
    setFolderStates(prev => {
      const newStates = new Map(prev);
      folders.filter(f => f.is_game).forEach(folder => {
        const state = newStates.get(folder.name) || { collapsed: false, selected: false };
        newStates.set(folder.name, { ...state, selected: checked });
      });
      return newStates;
    });
  };

  const handleSort = (column: 'name' | 'date') => {
    if (sortColumn === column) {
      setSortAscending(!sortAscending);
    } else {
      setSortColumn(column);
      setSortAscending(true);
    }
  };

  const toggleModelFilter = (model: string) => {
    setSelectedModels(prev => {
      const newSet = new Set(prev);
      if (newSet.has(model)) {
        newSet.delete(model);
      } else {
        newSet.add(model);
      }
      return newSet;
    });
  };

  const clearFilters = () => {
    setSelectedGame('');
    setSelectedModels(new Set());
    setSelectedDate(null);
  };

  // Filter and sort folders
  const processedFolders = useMemo(() => {
    let result = [...folders];

    // Apply sorting
    if (sortColumn) {
      result.sort((a, b) => {
        if (sortColumn === 'name') {
          const aName = a.name.split('/').pop() || '';
          const bName = b.name.split('/').pop() || '';
          return sortAscending ? aName.localeCompare(bName) : bName.localeCompare(aName);
        } else if (sortColumn === 'date') {
          const aTime = a.created_timestamp || 0;
          const bTime = b.created_timestamp || 0;
          if (aTime === 0 && bTime === 0) return 0;
          if (aTime === 0) return 1;
          if (bTime === 0) return -1;
          return sortAscending ? aTime - bTime : bTime - aTime;
        }
        return 0;
      });
    }

    return result;
  }, [folders, sortColumn, sortAscending]);

  // Check if a folder should be visible based on filters
  const shouldShowFolder = useCallback((folder: GameFolder): boolean => {
    if (!folder.is_game) {
      // Intermediate folder - show if any child would be visible
      return folders.some(f =>
        f.is_game &&
        f.name.startsWith(folder.name + '/') &&
        shouldShowFolder(f)
      );
    }

    // Game folder - apply filters
    if (selectedGame && folder.game_name !== selectedGame) {
      return false;
    }

    if (selectedModels.size > 0) {
      if (!folder.models || folder.models.length === 0) return false;
      const folderModels = folder.models.map(m => stripModelPrefix(m));
      const hasAllModels = Array.from(selectedModels).every(model =>
        folderModels.includes(model)
      );
      if (!hasAllModels) return false;
    }

    if (selectedDate) {
      const folderDate = formatDate(folder.created_timestamp);
      if (folderDate !== selectedDate) return false;
    }

    return true;
  }, [selectedGame, selectedModels, selectedDate, folders]);

  // Check if folder should be displayed (considering parent collapsed state)
  const shouldDisplayFolder = useCallback((folder: GameFolder): boolean => {
    if (!shouldShowFolder(folder)) return false;

    // Check if any parent is collapsed
    const pathParts = folder.name.split('/');
    for (let i = 1; i < pathParts.length; i++) {
      const parentPath = pathParts.slice(0, i).join('/');
      const parentState = folderStates.get(parentPath);
      if (parentState?.collapsed) return false;
    }

    return true;
  }, [folderStates, shouldShowFolder]);

  const getSelectedPaths = () => {
    return Array.from(folderStates.entries())
      .filter(([_, state]) => state.selected)
      .map(([name, _]) => name);
  };

  const copySelectedPaths = () => {
    const paths = getSelectedPaths();
    if (paths.length === 0) {
      alert('Please select at least one game');
      return;
    }
    navigator.clipboard.writeText(paths.join(' '));
    alert(`Copied ${paths.length} path(s)`);
  };

  if (loading) {
    return <div className="loading">Loading game folders...</div>;
  }

  if (error) {
    return (
      <div className="container">
        <div className="error">
          <p>Error: {error}</p>
          <button onClick={loadFolders}>Retry</button>
        </div>
      </div>
    );
  }

  const hasActiveFilters = selectedGame || selectedModels.size > 0 || selectedDate;

  return (
    <div className="container">
      {folders.length === 0 ? (
        <div className="no-games-message">
          <h3>No Game Sessions Found</h3>
          <p>No folders containing metadata.json were found.</p>
        </div>
      ) : (
        <div className="games-table">
          <div className="table-controls">
            <div className="selection-controls">
              <input
                type="checkbox"
                id="select-all"
                checked={selectAll}
                onChange={(e) => handleSelectAll(e.target.checked)}
              />
              <label htmlFor="select-all">Select All</label>
            </div>
            <div className="right-controls">
              {hasActiveFilters && (
                <div className="filter-controls">
                  <button onClick={clearFilters} className="clear-filters-btn">
                    ✕ Clear Filters
                  </button>
                </div>
              )}
              <div className="action-controls">
                <select onChange={(e) => {
                  if (e.target.value === 'copy-paths') {
                    copySelectedPaths();
                  }
                  e.target.value = '';
                }}>
                  <option value="">Choose action...</option>
                  <option value="copy-paths">Copy paths</option>
                </select>
              </div>
            </div>
          </div>

          <div className="table-header">
            <div>☑</div>
            <div className="sortable-header" onClick={() => handleSort('name')}>
              Name {sortColumn === 'name' && (sortAscending ? '↑' : '↓')}
            </div>
            <div className="sortable-header" onClick={() => handleSort('date')}>
              📅 Date {sortColumn === 'date' && (sortAscending ? '↑' : '↓')}
            </div>
            <div>
              <select
                value={selectedGame}
                onChange={(e) => setSelectedGame(e.target.value)}
                className="game-filter"
              >
                <option value="">All Games</option>
                {uniqueGames.map(game => (
                  <option key={game} value={game}>{game}</option>
                ))}
              </select>
            </div>
            <div>🎯 Rounds</div>
            <div>
              <select
                multiple
                value={Array.from(selectedModels)}
                onChange={(e) => {
                  const selected = Array.from(e.target.selectedOptions).map(o => o.value);
                  setSelectedModels(new Set(selected));
                }}
                className="model-filter"
                size={1}
              >
                {uniqueModels.map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </div>
            <div>Action</div>
          </div>

          {processedFolders.filter(shouldDisplayFolder).map((folder) => {
            const depth = folder.name.split('/').length - 1;
            const folderName = folder.name.split('/').pop() || folder.name;
            const state = folderStates.get(folder.name);

            return (
              <div
                key={folder.name}
                className={`game-row depth-${depth} ${folder.is_game ? 'game-folder' : 'intermediate-folder'} ${state?.collapsed ? 'collapsed' : ''}`}
                onClick={() => {
                  if (!folder.is_game) {
                    toggleFolder(folder.name);
                  }
                }}
              >
                <div className="checkbox-cell">
                  {folder.is_game ? (
                    <input
                      type="checkbox"
                      checked={state?.selected || false}
                      onChange={(e) => {
                        e.stopPropagation();
                        toggleSelection(folder.name, false);
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleSelection(folder.name, e.shiftKey);
                      }}
                    />
                  ) : (
                    <span className="checkbox-placeholder" />
                  )}
                </div>

                <div className="session-name-cell">
                  <span className="folder-indent">{'  '.repeat(depth)}</span>
                  {!folder.is_game && (
                    <span className="collapse-icon">
                      {state?.collapsed ? '▶' : '▼'}
                    </span>
                  )}
                  <span
                    className="game-name"
                    onClick={(e) => {
                      if (folder.is_game) {
                        e.stopPropagation();
                        handleFolderClick(folder, e.ctrlKey || e.metaKey);
                      }
                    }}
                  >
                    {folderName}
                  </span>
                </div>

                <div className="date-cell">
                  {folder.is_game && folder.created_timestamp ? (
                    <span
                      className={`date-text ${selectedDate === formatDate(folder.created_timestamp) ? 'date-selected' : ''}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        const date = formatDate(folder.created_timestamp);
                        setSelectedDate(selectedDate === date ? null : date);
                      }}
                    >
                      {formatTimestamp(folder.created_timestamp)}
                    </span>
                  ) : (
                    <span className="date-unknown">-</span>
                  )}
                </div>

                <div className="game-name-cell">
                  {folder.is_game && folder.game_name ? (
                    <span
                      className="game-name-tag clickable-filter"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedGame(folder.game_name === selectedGame ? '' : folder.game_name);
                      }}
                    >
                      {folder.game_name}
                    </span>
                  ) : (
                    <span className="game-name-empty">-</span>
                  )}
                </div>

                <div className="rounds-cell">
                  {folder.is_game && folder.rounds_total ? (
                    <span className={`rounds-count ${(folder.rounds_completed || 0) < folder.rounds_total ? 'rounds-count-warning' : ''}`}>
                      {folder.rounds_completed || 0}/{folder.rounds_total}
                    </span>
                  ) : folder.is_game ? (
                    <span className="rounds-unknown">?</span>
                  ) : (
                    <span className="rounds-unknown">-</span>
                  )}
                </div>

                <div className="models-cell">
                  {folder.is_game && folder.models && folder.models.length > 0 ? (
                    folder.models.map(model => {
                      const shortModel = stripModelPrefix(model);
                      return (
                        <span
                          key={model}
                          className="model-tag clickable-filter"
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleModelFilter(shortModel);
                          }}
                        >
                          {shortModel}
                        </span>
                      );
                    })
                  ) : (
                    <span className="models-unknown">-</span>
                  )}
                </div>

                <div className="action-cell">
                  {folder.is_game ? (
                    <>
                      <button
                        className="open-button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleFolderClick(folder, e.ctrlKey || e.metaKey);
                        }}
                      >
                        Open
                      </button>
                      <button
                        className="open-new-tab-button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleFolderClick(folder, true);
                        }}
                        title="Open in new tab"
                      >
                        ↗
                      </button>
                    </>
                  ) : (
                    <span className="folder-indicator">Folder</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
