import { useState, useEffect, useCallback } from 'react';
import { api } from '../utils/api';
import './Readme.css';

interface ReadmeProps {
  folderPath: string;
}

export function Readme({ folderPath }: ReadmeProps) {
  const [content, setContent] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadReadme();
  }, [folderPath]);

  const loadReadme = async () => {
    try {
      const readmeContent = await api.getReadme(folderPath);
      setContent(readmeContent);
      setError(null);
    } catch (err: any) {
      console.error('Failed to load readme:', err);
      setError(err.message);
    }
  };

  const saveReadme = useCallback(
    async (text: string) => {
      try {
        setIsSaving(true);
        setError(null);
        await api.saveReadme(folderPath, text);
        setLastSaved(new Date());
      } catch (err: any) {
        console.error('Failed to save readme:', err);
        setError(err.message);
      } finally {
        setIsSaving(false);
      }
    },
    [folderPath]
  );

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (content !== undefined) {
        saveReadme(content);
      }
    }, 1000); // Auto-save after 1 second of no changes

    return () => clearTimeout(timeoutId);
  }, [content, saveReadme]);

  const formatSaveTime = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const seconds = Math.floor(diff / 1000);

    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
    return date.toLocaleTimeString();
  };

  return (
    <details className="card readme-section" open>
      <summary className="readme-summary">
        📝 Notes
        {isSaving && <span className="save-indicator saving">💾 Saving...</span>}
        {!isSaving && lastSaved && (
          <span className="save-indicator saved">✓ Saved {formatSaveTime(lastSaved)}</span>
        )}
      </summary>

      <div className="readme-content">
        {error && (
          <div className="error-banner">
            ⚠️ Error: {error}
          </div>
        )}

        <textarea
          className="readme-textarea"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Add notes about this experiment here... Changes are automatically saved."
        />

        <div className="readme-help">
          💡 Changes are automatically saved as you type
        </div>
      </div>
    </details>
  );
}
