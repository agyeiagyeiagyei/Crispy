import React, { useState, useEffect, useRef } from 'react';
import './AddAxisModal.css';

function AddAxisModal({ isOpen, onClose, onConfirm, existingAxes = [], existingMetadata = {}, parametricAxes = [] }) {
  const [axisName, setAxisName] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [defaultValue, setDefaultValue] = useState('0');
  const [minValue, setMinValue] = useState('-1000');
  const [maxValue, setMaxValue] = useState('1000');
  const [errors, setErrors] = useState({});
  const displayNameRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      // Reset form when modal opens
      setAxisName('');
      setDisplayName('');
      setDefaultValue('0');
      setMinValue('-1000');
      setMaxValue('1000');
      setErrors({});
      // Focus input after a brief delay
      setTimeout(() => {
        if (displayNameRef.current) {
          displayNameRef.current.focus();
        }
      }, 100);
    }
  }, [isOpen]);

  const validate = () => {
    const newErrors = {};
    
    if (!axisName.trim()) {
      newErrors.axisName = 'Axis name is required';
    } else if (axisName.length !== 4) {
      newErrors.axisName = 'Axis name must be exactly 4 characters';
    } else if (!axisName.match(/^[a-z0-9]{4}$/)) {
      newErrors.axisName = 'Axis name must be 4 lowercase alphanumeric characters';
    } else if (existingAxes.includes(axisName.trim().toUpperCase())) {
      newErrors.axisName = 'Axis name already exists';
    } else {
      // Check for duplicate tags - axis name IS the registered tag
      const existingTagsFromAxes = existingAxes.map(ax => {
        if (typeof ax === 'string') {
          // Existing axes are CSV column names (uppercase), convert to lowercase for comparison
          return ax.toLowerCase();
        }
        return ax.registeredTag?.toLowerCase();
      }).filter(Boolean);
      
      const existingTagsFromMetadata = Object.values(existingMetadata || {})
        .map(meta => meta?.registered_tag?.toLowerCase())
        .filter(Boolean);
      
      const allExistingTags = [...new Set([...existingTagsFromAxes, ...existingTagsFromMetadata])];
      if (allExistingTags.includes(axisName.toLowerCase())) {
        newErrors.axisName = 'Axis name (registered tag) already used';
      }
      
      // Check if tag exists in parametric axes (from Glyphs file) - cannot use same tag
      const parametricTags = parametricAxes.map(ax => ax.toLowerCase());
      if (parametricTags.includes(axisName.toLowerCase())) {
        newErrors.axisName = `Axis name '${axisName}' already exists in Glyphs file as a parametric axis. Traditional axes cannot use tags that exist in the Glyphs file.`;
      }
    }
    
    if (!displayName.trim()) {
      newErrors.displayName = 'Display name is required';
    }
    
    const min = parseFloat(minValue);
    const max = parseFloat(maxValue);
    if (isNaN(min) || min < -1000 || min > 1000) {
      newErrors.minValue = 'Min must be between -1000 and 1000';
    }
    if (isNaN(max) || max < -1000 || max > 1000) {
      newErrors.maxValue = 'Max must be between -1000 and 1000';
    }
    if (!isNaN(min) && !isNaN(max) && min >= max) {
      newErrors.maxValue = 'Max must be greater than min';
    }
    
    const defVal = parseFloat(defaultValue);
    if (isNaN(defVal)) {
      newErrors.defaultValue = 'Default value must be a number';
    } else if (defVal < min || defVal > max) {
      newErrors.defaultValue = `Default value must be between ${minValue} and ${maxValue}`;
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (validate()) {
      // Axis name (uppercase) becomes CSV column, lowercase version is registered tag
      const axisNameUpper = axisName.trim().toUpperCase();
      onConfirm({
        axis_name: axisNameUpper,
        display_name: displayName.trim(),
        registered_tag: axisName.trim().toLowerCase(),
        default_value: parseFloat(defaultValue),
        min: parseFloat(minValue),
        max: parseFloat(maxValue),
      });
    }
  };

  const handleCancel = () => {
    setAxisName('');
    setDisplayName('');
    setDefaultValue('0');
    setMinValue('-1000');
    setMaxValue('1000');
    setErrors({});
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content add-axis-modal" onClick={(e) => e.stopPropagation()}>
        <h3>Add New Axis</h3>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>
              Display Name <span className="required">*</span>
            </label>
            <input
              ref={displayNameRef}
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="e.g., Weight"
              className={errors.displayName ? 'error' : ''}
            />
            {errors.displayName && <span className="error-message">{errors.displayName}</span>}
          </div>
          
          <div className="form-group">
            <label>
              Axis Name (Registered Tag) <span className="required">*</span>
            </label>
            <input
              type="text"
              value={axisName}
              onChange={(e) => {
                const val = e.target.value.toLowerCase().slice(0, 4);
                setAxisName(val);
              }}
              placeholder="e.g., wght"
              maxLength={4}
              className={errors.axisName ? 'error' : ''}
            />
            {errors.axisName && <span className="error-message">{errors.axisName}</span>}
            <small>4 lowercase alphanumeric characters (becomes CSV column name)</small>
          </div>
          
          <div className="form-row">
            <div className="form-group">
              <label>
                Min Value <span className="required">*</span>
              </label>
              <input
                type="number"
                value={minValue}
                onChange={(e) => setMinValue(e.target.value)}
                min="-1000"
                max="1000"
                step="1"
                className={`axis-number-input ${errors.minValue ? 'error' : ''}`}
              />
              {errors.minValue && <span className="error-message">{errors.minValue}</span>}
            </div>
            
            <div className="form-group">
              <label>
                Max Value <span className="required">*</span>
              </label>
              <input
                type="number"
                value={maxValue}
                onChange={(e) => setMaxValue(e.target.value)}
                min="-1000"
                max="1000"
                step="1"
                className={`axis-number-input ${errors.maxValue ? 'error' : ''}`}
              />
              {errors.maxValue && <span className="error-message">{errors.maxValue}</span>}
            </div>
          </div>
          
          <div className="form-group">
            <label>
              Default Value <span className="required">*</span>
            </label>
            <input
              type="number"
              value={defaultValue}
              onChange={(e) => setDefaultValue(e.target.value)}
              step="0.1"
              className={errors.defaultValue ? 'error' : ''}
            />
            {errors.defaultValue && <span className="error-message">{errors.defaultValue}</span>}
            <small>Applied to all instances</small>
          </div>
          
          <div className="modal-buttons">
            <button type="button" onClick={handleCancel} className="btn btn-cancel">
              Cancel
            </button>
            <button type="submit" className="btn btn-confirm">
              Add Axis
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default AddAxisModal;
