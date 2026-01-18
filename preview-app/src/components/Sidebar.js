import React, { useState } from 'react';
import './Sidebar.css';
import AxisControl from './AxisControl';
import UpdateButton from './UpdateButton';

const DEFAULT_SAMPLE_TEXT = "The Quick Brown Fox Jumps Over The Lazy Dog 0123456789 &!";

function Sidebar({ axes, coordinates, onAxisChange, disabled, sampleText, onSampleTextChange, selectedInstance, onUpdateInstance, onResetCoordinates, originalCoordinates, fontSize, onFontSizeChange }) {
  return (
    <aside className="sidebar">
      {selectedInstance ? (
        <h2>{selectedInstance.name}</h2>
      ) : (
        <h2>Select a style on the right</h2>
      )}
      
      <div className="sample-text-section">
        <textarea
          value={sampleText}
          onChange={(e) => onSampleTextChange(e.target.value)}
          className="sample-text-input"
          placeholder="Enter sample text..."
          rows={3}
        />
      </div>
      
      {disabled && (
        <p className="sidebar-hint">Select an instance to edit</p>
      )}
      <div className="axis-controls">
        {axes.map(axis => (
          <AxisControl
            key={axis.tag}
            axis={axis}
            value={coordinates[axis.tag] ?? axis.default}
            onChange={(value) => onAxisChange(axis.tag, value)}
            disabled={disabled}
          />
        ))}
      </div>
      
      <div className="font-size-control">
        <label className="font-size-label">
          Font Size: {fontSize.toFixed(1)}rem
        </label>
        <input
          type="range"
          min="0.5"
          max="7"
          step="0.1"
          value={fontSize}
          onChange={(e) => onFontSizeChange(parseFloat(e.target.value))}
          className="font-size-slider"
        />
      </div>
      
      {!disabled && (
        <div className="reset-button-section">
          <button
            onClick={onResetCoordinates}
            className="btn btn-reset"
            disabled={!selectedInstance}
          >
            Reset to Original
          </button>
        </div>
      )}
      
      {selectedInstance && (
        <div className="update-button-section">
          <UpdateButton
            onClick={onUpdateInstance}
            instanceName={selectedInstance.name}
          />
        </div>
      )}
    </aside>
  );
}

export default Sidebar;
