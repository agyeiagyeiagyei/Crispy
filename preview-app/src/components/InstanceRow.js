import React, { useState } from 'react';
import './InstanceRow.css';

function InstanceRow({ instance, isSelected, onSelect, editingCoordinates, instanceEditingCoordinates, sampleText, fontLoaded, fontSize, onDelete, onMove, allInstances, spacMode, spacAxisExists, spacValue }) {
  const [showMoveControls, setShowMoveControls] = useState(false);
  const [movePosition, setMovePosition] = useState('before');
  const [targetInstance, setTargetInstance] = useState(null);
  // Build font-variation-settings CSS from coordinates
  // If this row is selected, use editing coordinates (from sliders)
  // Otherwise, use persisted editing coordinates if they exist, or instance coordinates
  const activeCoordinates = isSelected && Object.keys(editingCoordinates).length > 0
    ? editingCoordinates
    : (instanceEditingCoordinates[instance.name] || instance.coordinates);
  
  // Build font-variation-settings string
  let fontVariationSettings = Object.entries(activeCoordinates)
    .map(([tag, value]) => `"${tag}" ${value}`)
    .join(', ');
  
  // Add SPAC axis if SPAC mode is enabled and axis exists
  if (spacMode && spacAxisExists) {
    const spacSetting = `"SPAC" ${spacValue}`;
    fontVariationSettings = fontVariationSettings 
      ? `${fontVariationSettings}, ${spacSetting}`
      : spacSetting;
  }

  return (
    <div
      className={`instance-row ${isSelected ? 'selected' : ''}`}
      onClick={onSelect}
      data-instance-name={instance.name}
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
          {/* Always render icons but hide when not selected to prevent layout shift */}
          {onMove && (
            <button
              className="move-instance-btn"
              onClick={(e) => {
                e.stopPropagation();
                if (isSelected) {
                  setShowMoveControls(!showMoveControls);
                  if (!showMoveControls) {
                    setTargetInstance(null);
                    setMovePosition('before');
                  }
                }
              }}
              title="Move this instance"
              style={{ visibility: isSelected ? 'visible' : 'hidden' }}
            >
              ⇅
            </button>
          )}
          {onDelete && (
            <button
              className="delete-instance-btn"
              onClick={(e) => {
                e.stopPropagation();
                if (isSelected) {
                  onDelete(instance);
                }
              }}
              title="Remove this instance"
              style={{ visibility: isSelected ? 'visible' : 'hidden' }}
            >
              🗑️
            </button>
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
          }}
        >
          {sampleText}
        </div>
      </div>
    </div>
  );
}

export default InstanceRow;
