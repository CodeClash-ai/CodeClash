import { useState, useEffect } from 'react';
import type { GameData } from '../types';
import './FloatingToc.css';

interface FloatingTocProps {
  gameData: GameData;
}

export function FloatingToc({ gameData }: FloatingTocProps) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input field
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      if (e.key === 't' || e.key === 'T') {
        e.preventDefault();
        setIsVisible((prev) => !prev);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  const scrollToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    });
  };

  const scrollToSection = (selector: string) => {
    const element = document.querySelector(selector);
    if (element) {
      element.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    }
  };

  const scrollToRound = (roundNum: number) => {
    const element = document.querySelector(`[data-round="${roundNum}"]`);
    if (element) {
      element.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    }
  };

  if (!isVisible) {
    return (
      <button
        className="toc-toggle-button"
        onClick={() => setIsVisible(true)}
        title="Toggle Table of Contents (Press T)"
      >
        📑
      </button>
    );
  }

  return (
    <div className="floating-toc">
      <div className="toc-menu">
        <div className="toc-header">
          <span>Navigation</span>
          <button
            className="toc-close"
            onClick={() => setIsVisible(false)}
            title="Close (Press T)"
          >
            ×
          </button>
        </div>

        <div className="toc-content">
          <button className="toc-item toc-top" onClick={scrollToTop}>
            ↑ Go to Top
          </button>

          <button className="toc-item" onClick={() => scrollToSection('.storage-section')}>
            💾 Storage
          </button>

          <button className="toc-item" onClick={() => scrollToSection('.readme-section')}>
            📝 Notes
          </button>

          <button className="toc-item" onClick={() => scrollToSection('#overview')}>
            📊 Overview
          </button>

          <button className="toc-item" onClick={() => scrollToSection('.analysis-section')}>
            📈 Analysis
          </button>

          {gameData.rounds.length > 0 && (
            <>
              <div className="toc-divider">Rounds</div>
              {gameData.rounds.map((round) => (
                <button
                  key={round.round_num}
                  className="toc-item toc-round"
                  onClick={() => scrollToRound(round.round_num)}
                >
                  🏁 Round {round.round_num}
                </button>
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
