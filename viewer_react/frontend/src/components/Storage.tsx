import { useState } from 'react';
import type { GameData } from '../types';
import { api } from '../utils/api';
import './Storage.css';

interface StorageProps {
  gameData: GameData;
  folderPath: string;
  onMoveFolder?: (newPath: string) => void;
  onDeleteFolder?: () => void;
}

export function Storage({ gameData, folderPath, onMoveFolder, onDeleteFolder }: StorageProps) {
  const [showMoveDialog, setShowMoveDialog] = useState(false);
  const [newPath, setNewPath] = useState(folderPath);
  const [isMoving, setIsMoving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);

  const awsCommand = gameData.metadata?.aws?.AWS_USER_PROVIDED_COMMAND;
  const awsJobId = gameData.metadata?.aws?.AWS_BATCH_JOB_ID;

  const handleCopyPath = () => {
    navigator.clipboard.writeText(folderPath);
    setCopyFeedback('Path copied!');
    setTimeout(() => setCopyFeedback(null), 2000);
  };

  const handleCopyAwsCommand = () => {
    if (awsCommand) {
      navigator.clipboard.writeText(`aws/run_job.py -- ${awsCommand}`);
      setCopyFeedback('AWS command copied!');
      setTimeout(() => setCopyFeedback(null), 2000);
    }
  };

  const handleMoveFolder = async () => {
    if (!newPath || newPath === folderPath) {
      setShowMoveDialog(false);
      return;
    }

    try {
      setIsMoving(true);
      await api.moveFolder(folderPath, newPath);
      setShowMoveDialog(false);
      if (onMoveFolder) {
        onMoveFolder(newPath);
      }
    } catch (err: any) {
      alert(`Failed to move folder: ${err.message}`);
    } finally {
      setIsMoving(false);
    }
  };

  const handleDeleteFolder = async () => {
    if (!confirm(`Are you sure you want to delete "${folderPath}"? This action cannot be undone.`)) {
      return;
    }

    try {
      setIsDeleting(true);
      await api.deleteFolder(folderPath);
      if (onDeleteFolder) {
        onDeleteFolder();
      }
    } catch (err: any) {
      alert(`Failed to delete folder: ${err.message}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const s3Path = encodeURIComponent(folderPath.replace(/\\/g, '/'));
  const s3Url = `https://039984708918-4ppzlrng.us-east-1.console.aws.amazon.com/s3/buckets/codeclash?region=us-east-1&bucketType=general&prefix=logs%2F${s3Path}%2F&showversions=false`;
  const awsJobUrl = awsJobId
    ? `https://039984708918-4ppzlrng.us-east-1.console.aws.amazon.com/batch/home?region=us-east-1#jobs/ec2/detail/${awsJobId}`
    : null;

  // Get folder name and parent for display
  const pathParts = folderPath.split('/');
  const folderName = pathParts[pathParts.length - 1];
  const parentFolder = pathParts.length > 1 ? pathParts[pathParts.length - 2] : null;

  return (
    <>
      <details className="card storage-section" open>
        <summary className="storage-summary">
          💾 Storage: {parentFolder ? `${parentFolder}/` : ''}<strong>{folderName}</strong>
        </summary>

        <div className="storage-content">
          {/* Current Folder Path */}
          <div className="storage-item">
            <div className="storage-label">
              📁 Current Folder:
            </div>
            <div className="storage-actions">
              <code className="folder-path">{folderPath}</code>
              <button className="btn small" onClick={handleCopyPath} title="Copy folder path">
                📋 Copy path
              </button>
              <button
                className="btn small warning"
                onClick={() => {
                  setNewPath(folderPath);
                  setShowMoveDialog(true);
                }}
                title="Move/rename this experiment"
              >
                📦 Move/Rename
              </button>
              <button
                className="btn small danger"
                onClick={handleDeleteFolder}
                disabled={isDeleting}
                title="Delete this experiment"
              >
                {isDeleting ? '⏳ Deleting...' : '🗑️ Delete'}
              </button>
            </div>
          </div>

          {/* AWS Command */}
          {awsCommand && (
            <div className="storage-item">
              <div className="storage-label">
                ☁️ AWS Command:
              </div>
              <div className="storage-actions">
                <code className="folder-path">aws/run_job.py -- {awsCommand}</code>
                <button className="btn small" onClick={handleCopyAwsCommand} title="Copy AWS command">
                  📋 Copy command
                </button>
              </div>
            </div>
          )}

          {/* External Links */}
          <div className="storage-item">
            <div className="storage-label">
              🔗 External Links:
            </div>
            <div className="storage-actions">
              <a href={s3Url} target="_blank" rel="noopener noreferrer" className="btn small">
                🪣 S3 Bucket
              </a>
              {awsJobUrl && (
                <a href={awsJobUrl} target="_blank" rel="noopener noreferrer" className="btn small">
                  ⚙️ AWS Job
                </a>
              )}
            </div>
          </div>

          {copyFeedback && (
            <div className="copy-feedback">{copyFeedback}</div>
          )}
        </div>
      </details>

      {/* Move/Rename Dialog */}
      {showMoveDialog && (
        <div className="modal-overlay" onClick={() => setShowMoveDialog(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Move/Rename Folder</h3>
              <button className="modal-close" onClick={() => setShowMoveDialog(false)}>×</button>
            </div>
            <div className="modal-body">
              <p>Edit the path to move or rename the folder:</p>
              <input
                type="text"
                className="move-path-input"
                value={newPath}
                onChange={(e) => setNewPath(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleMoveFolder();
                  if (e.key === 'Escape') setShowMoveDialog(false);
                }}
                autoFocus
              />
              <div className="modal-actions">
                <button
                  className="btn primary"
                  onClick={handleMoveFolder}
                  disabled={isMoving}
                >
                  {isMoving ? 'Moving...' : 'Move'}
                </button>
                <button
                  className="btn"
                  onClick={() => setShowMoveDialog(false)}
                  disabled={isMoving}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
