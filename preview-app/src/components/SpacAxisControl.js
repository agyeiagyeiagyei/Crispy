import React from 'react';
import './SpacAxisControl.css';

function SpacAxisControl({ axis, value, originalValue = 0, onChange, onApply, disabled, building }) {
  const handleSliderChange = (e) => {
    const newValue = parseFloat(e.target.value);
    onChange(newValue);
  };

  // Enable Apply button only if value has changed from original
  const hasChanged = Math.abs(value - originalValue) > 0.01; // Use small threshold for floating point comparison

  return (
    <div className="axis-control spac-axis-control">
      <div className="axis-header">
        <label className="axis-name">{axis.name}</label>
        <span className="axis-tag">{axis.tag}</span>
      </div>
      <div className="axis-slider-container">
        <div className="spac-slider-row">
          <input
            type="range"
            min={axis.min}
            max={axis.max}
            step={0.1}
            value={value}
            onChange={handleSliderChange}
            disabled={disabled || building}
            className="axis-slider"
          />
          <button
            onClick={onApply}
            disabled={disabled || building || !hasChanged}
            className="btn btn-apply-spac-inline"
          >
            {building ? 'Applying...' : 'Apply'}
          </button>
        </div>
        <div className="spac-axis-values">
          <span className="axis-min">{axis.min}</span>
          <span className="axis-current">{value.toFixed(1)}</span>
          <span className="axis-max">{axis.max}</span>
        </div>
      </div>
    </div>
  );
}

export default SpacAxisControl;
