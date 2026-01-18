import React from 'react';
import './UpdateButton.css';

function UpdateButton({ onClick, instanceName }) {
  return (
    <div className="update-button-container">
      <button
        onClick={onClick}
        className="btn btn-update"
      >
        Update Instance: {instanceName}
      </button>
    </div>
  );
}

export default UpdateButton;
