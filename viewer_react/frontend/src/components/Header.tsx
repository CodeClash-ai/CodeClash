import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Navigation } from '../types';
import './Header.css';

interface HeaderProps {
  navigation?: Navigation;
  currentFolder?: string;
  onShowHelp: () => void;
}

export function Header({ navigation, currentFolder, onShowHelp }: HeaderProps) {
  const navigate = useNavigate();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger shortcuts if user is typing in an input field
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      // h or Left Arrow: Navigate to previous game
      if (e.key === 'h' || e.key === 'ArrowLeft') {
        e.preventDefault();
        if (navigation?.previous) {
          navigate(`/game/${navigation.previous}`);
        }
        return;
      }

      // l or Right Arrow: Navigate to next game
      if (e.key === 'l' || e.key === 'ArrowRight') {
        e.preventDefault();
        if (navigation?.next) {
          navigate(`/game/${navigation.next}`);
        }
        return;
      }

      // p: Open game picker
      if (e.key === 'p') {
        e.preventDefault();
        navigate('/');
        return;
      }

      // ?: Show help modal
      if (e.key === '?') {
        e.preventDefault();
        onShowHelp();
        return;
      }

      // Escape: Close all open details
      if (e.key === 'Escape') {
        const openDetails = document.querySelectorAll('details[open]');
        openDetails.forEach((details) => {
          details.removeAttribute('open');
        });
        return;
      }

      // Ctrl/Cmd + E: Expand all details
      if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
        e.preventDefault();
        const allDetails = document.querySelectorAll('details');
        allDetails.forEach((details) => {
          details.setAttribute('open', '');
        });
        return;
      }

      // Ctrl/Cmd + Shift + E: Collapse all details
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'E') {
        e.preventDefault();
        const allDetails = document.querySelectorAll('details');
        allDetails.forEach((details) => {
          details.removeAttribute('open');
        });
        return;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [navigation, navigate, onShowHelp]);

  return (
    <header className="viewer-header">
      <div className="header-content">
        <h1>
          🎮 CodeClash Trajectory Viewer
        </h1>

        {currentFolder && (
          <div className="controls">
            {/* Navigation Buttons */}
            <div className="control-group">
              <button
                className="btn nav-button"
                onClick={() => navigation?.previous && navigate(`/game/${navigation.previous}`)}
                disabled={!navigation?.previous}
                title="Previous Game (Press h or ←)"
              >
                <span className="btn-icon">←</span>
                <span className="kbd-hint">
                  <kbd>h</kbd> <kbd>←</kbd>
                </span>
              </button>

              <button
                className="btn nav-button"
                onClick={() => navigation?.next && navigate(`/game/${navigation.next}`)}
                disabled={!navigation?.next}
                title="Next Game (Press l or →)"
              >
                <span className="kbd-hint">
                  <kbd>l</kbd> <kbd>→</kbd>
                </span>
                <span className="btn-icon">→</span>
              </button>
            </div>

            {/* Game Selection Button */}
            <div className="control-group">
              <button
                className="btn primary pick-game-button"
                onClick={() => navigate('/')}
                title="Pick Game (Press p)"
              >
                📁 Pick Game <kbd>p</kbd>
              </button>
            </div>

            {/* Help Button */}
            <div className="control-group">
              <button
                className="btn help-button"
                onClick={onShowHelp}
                title="Show Keyboard Shortcuts (Press ?)"
              >
                ❓ <kbd>?</kbd>
              </button>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}

interface HelpModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function HelpModal({ isOpen, onClose }: HelpModalProps) {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>⌨️ Keyboard Shortcuts</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <div className="shortcut-section">
            <h4>↔️ Navigation</h4>
            <div className="shortcut-item">
              <div className="shortcut-keys">
                <kbd>h</kbd> or <kbd>←</kbd>
              </div>
              <span>Navigate to previous game</span>
            </div>
            <div className="shortcut-item">
              <div className="shortcut-keys">
                <kbd>l</kbd> or <kbd>→</kbd>
              </div>
              <span>Navigate to next game</span>
            </div>
            <div className="shortcut-item">
              <div className="shortcut-keys">
                <kbd>p</kbd>
              </div>
              <span>Open game picker</span>
            </div>
          </div>

          <div className="shortcut-section">
            <h4>⚙️ Interface</h4>
            <div className="shortcut-item">
              <div className="shortcut-keys">
                <kbd>?</kbd>
              </div>
              <span>Show this help modal</span>
            </div>
            <div className="shortcut-item">
              <div className="shortcut-keys">
                <kbd>Escape</kbd>
              </div>
              <span>Close all open sections</span>
            </div>
            <div className="shortcut-item">
              <div className="shortcut-keys">
                <kbd>Ctrl</kbd>+<kbd>E</kbd>
              </div>
              <span>Expand all sections</span>
            </div>
            <div className="shortcut-item">
              <div className="shortcut-keys">
                <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>E</kbd>
              </div>
              <span>Collapse all sections</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
