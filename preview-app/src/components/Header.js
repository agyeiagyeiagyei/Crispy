import React from 'react';
import './Header.css';

function Header({ onBuildFont, onRefresh, building, fontLoaded, familyName, avar2Mode, onAvar2ModeChange, avar2PreviewMode, onAvar2PreviewModeChange, onBuildAvar2Font, spacMode, onSpacModeChange, spacBuilding }) {
  return (
    <header className="header">
      {familyName && <h1>{familyName}</h1>}
      <div className="header-actions">
        <label className="avar2-toggle">
          <input
            type="checkbox"
            checked={avar2Mode || false}
            onChange={(e) => onAvar2ModeChange(e.target.checked)}
            disabled={building}
          />
          <span>Show Avar2</span>
        </label>
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
          <>
            <button
              onClick={onBuildFont}
              disabled={building}
              className="btn btn-primary"
            >
              {building ? 'Building...' : fontLoaded ? 'Rebuild Font' : 'Build Font'}
            </button>
            <button
              onClick={onRefresh}
              disabled={building}
              className="btn btn-secondary"
            >
              Refresh
            </button>
          </>
        )}
      </div>
    </header>
  );
}

export default Header;
