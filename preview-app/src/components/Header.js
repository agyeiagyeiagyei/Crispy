import React from 'react';
import './Header.css';

function Header({ onBuildFont, building, fontLoaded, familyName, avar2PreviewMode, onAvar2PreviewModeChange, onBuildAvar2Font, spacMode, onSpacModeChange, spacBuilding }) {
  return (
    <header className="header">
      {familyName && <h1>{familyName}</h1>}
      <div className="header-actions">
        <div className="mode-toggle">
          <button
            className={`mode-button ${!avar2PreviewMode ? 'active' : ''}`}
            onClick={() => onAvar2PreviewModeChange(false)}
            disabled={building}
          >
            Default
          </button>
          <button
            className={`mode-button ${avar2PreviewMode ? 'active' : ''}`}
            onClick={() => onAvar2PreviewModeChange(true)}
            disabled={building}
          >
            Avar2 Preview
          </button>
        </div>
        {avar2PreviewMode && (
          <button
            onClick={onBuildAvar2Font}
            disabled={building}
            className="btn btn-primary"
          >
            Build Avar2 Font
          </button>
        )}
        <label className="spac-toggle">
          <input
            type="checkbox"
            checked={spacMode || false}
            onChange={(e) => onSpacModeChange(e.target.checked)}
            disabled={building || spacBuilding}
          />
          <span>Show Spacing{spacBuilding ? ' (Building...)' : ''}</span>
        </label>
        {!avar2PreviewMode && (
          <button
            onClick={onBuildFont}
            disabled={building}
            className="btn btn-primary"
          >
            {building ? 'Building...' : fontLoaded ? 'Rebuild Font' : 'Build Font'}
          </button>
        )}
      </div>
    </header>
  );
}

export default Header;
