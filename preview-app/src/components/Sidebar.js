import React from 'react';
import './Sidebar.css';
import AxisControl from './AxisControl';

function Sidebar({ axes, coordinates, onAxisChange, disabled }) {
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
    </aside>
  );
}

export default Sidebar;
