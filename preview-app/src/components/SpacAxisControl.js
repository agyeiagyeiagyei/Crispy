import React from 'react';
import './AxisControl.css'; // Use same styles as parametric axes

function SpacAxisControl({ axis, value, onChange, disabled }) {
  const handleSliderChange = (e) => {
    const newValue = parseFloat(e.target.value);
    onChange(newValue);
  }

  return (
    <div className="axis-control">
      <div className="axis-header">
        <label className="axis-name">{axis.name}</label>
        <span className="axis-tag">{axis.tag}</span>
      </div>
      <div className="axis-slider-container">
        <input
          type="range"
          min={axis.min}
          max={axis.max}
          step={0.1}
          value={value}
          onChange={handleSliderChange}
          disabled={disabled}
          className="axis-slider"
        />
        <div className="axis-values">
          <span className="axis-min">{axis.min}</span>
          <span className="axis-current">{value.toFixed(1)}</span>
          <span className="axis-max">{axis.max}</span>
        </div>
      </div>
    </div>
  );
}

export default SpacAxisControl;
