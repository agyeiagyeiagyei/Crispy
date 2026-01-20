import React from 'react';
import './Header.css';

function Header({ onBuildFont, onRefresh, building, fontLoaded, familyName, avar2Mode, onAvar2ModeChange }) {
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
      </div>
    </header>
  );
}

export default Header;
