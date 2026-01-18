import React, { useState } from 'react';
import './InstanceRow.css';

function InstanceRow({ instance, isSelected, onSelect, editingCoordinates, sampleText, fontLoaded, fontSize, onDelete, onMove, allInstances }) {
  const [showMoveControls, setShowMoveControls] = useState(false);
  const [movePosition, setMovePosition] = useState('before');
  const [targetInstance, setTargetInstance] = useState(null);
  // Build font-variation-settings CSS from coordinates
  // If this row is selected, use editing coordinates (from sliders)
  // Otherwise, use the instance's own coordinates
  const activeCoordinates = isSelected && Object.keys(editingCoordinates).length > 0
    ? editingCoordinates
    : instance.coordinates;
  
  const fontVariationSettings = Object.entries(activeCoordinates)
    .map(([tag, value]) => `"${tag}" ${value}`)
    .join(', ');

  return (
    <div
      className={`instance-row ${isSelected ? 'selected' : ''}`}
      onClick={onSelect}
    >
      <div className="instance-row-header">
        <h3 className="instance-name">{instance.name}</h3>
        <div className="instance-header-right">
          <div className="instance-coordinates">
            {Object.entries(instance.coordinates).map(([tag, value]) => (
              <span key={tag} className="coordinate">
                {tag}: {value.toFixed(1)}
              </span>
            ))}
          </div>
          {isSelected && (
            <>
              {onMove && (
                <button
                  className="move-instance-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowMoveControls(!showMoveControls);
                    if (!showMoveControls) {
                      setTargetInstance(null);
                      setMovePosition('before');
                    }
                  }}
                  title="Move this instance"
                >
                  ⇅
                </button>
              )}
              {onDelete && (
                <button
                  className="delete-instance-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(instance);
                  }}
                  title="Remove this instance"
                >
                  🗑️
                </button>
              )}
            </>
          )}
        </div>
      </div>
      
      {isSelected && showMoveControls && onMove && (
        <div className="move-controls" onClick={(e) => e.stopPropagation()}>
          <div className="move-controls-row">
            <select
              className="move-position-select"
              value={movePosition}
              onChange={(e) => setMovePosition(e.target.value)}
            >
              <option value="before">Before</option>
              <option value="after">After</option>
            </select>
            <select
              className="move-target-select"
              value={targetInstance?.name || ''}
              onChange={(e) => {
                const selected = allInstances.find(inst => inst.name === e.target.value);
                setTargetInstance(selected || null);
              }}
            >
              <option value="">Select instance...</option>
              {allInstances
                .filter(inst => inst.name !== instance.name)
                .map(inst => (
                  <option key={inst.name} value={inst.name}>
                    {inst.name}
                  </option>
                ))}
            </select>
            <button
              className="move-apply-btn"
              onClick={(e) => {
                e.stopPropagation();
                if (targetInstance) {
                  onMove(instance, targetInstance, movePosition);
                  setShowMoveControls(false);
                  setTargetInstance(null);
                }
              }}
              disabled={!targetInstance}
            >
              Apply
            </button>
            <button
              className="move-cancel-btn"
              onClick={(e) => {
                e.stopPropagation();
                setShowMoveControls(false);
                setTargetInstance(null);
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      
      <div className="instance-row-content">
        <div
          className="preview-text"
          style={{
            fontFamily: fontLoaded ? '"Crispy-VF", sans-serif' : 'sans-serif',
            fontVariationSettings: fontLoaded ? fontVariationSettings : undefined,
            fontFeatureSettings: 'normal',
            fontSize: `${fontSize}rem`,
            textTransform: 'capitalize',
          }}
        >
          {sampleText}
        </div>
      </div>
    </div>
  );
}

export default InstanceRow;
