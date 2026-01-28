import React from 'react';
import './UpdateButton.css';

function UpdateButton({ onClick, instanceName, disabled, title }) {
  return (
    <div className="update-button-container">
      <button
        onClick={onClick}
        className="btn btn-update"
        disabled={disabled}
        title={title}
      >
        Update Instance
      </button>
    </div>
  );
}

export default UpdateButton;
