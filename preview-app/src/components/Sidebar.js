import React, { useState } from 'react';
import './Sidebar.css';
import AxisControl from './AxisControl';

const DEFAULT_SAMPLE_TEXT = "the quick brown fox jumps over the lazy dog 0123456789 &!";

function Sidebar({ axes, coordinates, onAxisChange, disabled, sampleText, onSampleTextChange }) {
  return (
    <aside className="sidebar">
      <h2>Axes</h2>
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
      
      <div className="sample-text-section">
        <h3>Sample Text</h3>
        <textarea
          value={sampleText}
          onChange={(e) => onSampleTextChange(e.target.value)}
          className="sample-text-input"
          placeholder="Enter sample text..."
          rows={3}
        />
      </div>
    </aside>
  );
}

export default Sidebar;
