import React from 'react';
import './Header.css';

function Header({ onBuildFont, onRefresh, building, fontLoaded }) {
  return (
    <header className="header">
      <h1>Glyphs Preview Tool</h1>
      <div className="header-actions">
        {!fontLoaded && (
          <button
            onClick={onBuildFont}
            disabled={building}
            className="btn btn-primary"
          >
            {building ? 'Building...' : 'Build Font'}
          </button>
        )}
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
