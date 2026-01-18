import React from 'react';
import './Header.css';

function Header({ onBuildFont, onRefresh, building, fontLoaded, familyName }) {
  return (
    <header className="header">
      {familyName && <h1>{familyName}</h1>}
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
