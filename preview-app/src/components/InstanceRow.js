import React, { useState } from 'react';
import './InstanceRow.css';

function InstanceRow({ instance, isSelected, onSelect, editingCoordinates, instanceEditingCoordinates, sampleText, fontLoaded, fontSize, onDelete, onMove, allInstances, spacMode, spacAxisExists, spacValue, syncStatus = 'green', onRename }) {
  const [showMoveControls, setShowMoveControls] = useState(false);
  const [movePosition, setMovePosition] = useState('before');
  const [targetInstance, setTargetInstance] = useState(null);
  const [isEditingName, setIsEditingName] = useState(false);
  const [editingName, setEditingName] = useState(instance.name);
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
  
  // Calculate CSS letter-spacing approximation for SPAC
  // Only apply if spacMode is enabled
  // SPAC ranges from -100 to +100
  // Map to letter-spacing: SPAC 100 = 0.1em, SPAC -100 = -0.1em
  // This is an approximation - actual font rebuild happens on "Apply"
  let letterSpacing = undefined;
  if (spacMode && spacAxisExists && spacValue !== undefined && spacValue !== 0) {
    // Convert SPAC value to em units (SPAC 100 = 0.1em)
    letterSpacing = `${(spacValue / 1000)}em`;
  }

  return (
    <div
      className={`instance-row ${isSelected ? 'selected' : ''}`}
      onClick={onSelect}
      data-instance-name={instance.name}
    >
      <div className="instance-row-header">
        <div className="instance-name-wrapper">
          {isEditingName ? (
            <input
              type="text"
              value={editingName}
              onChange={(e) => setEditingName(e.target.value)}
              onBlur={async () => {
                if (editingName.trim() && editingName.trim() !== instance.name && onRename) {
                  try {
                    await onRename(instance.name, editingName.trim());
                  } catch (err) {
                    // Revert on error
                    setEditingName(instance.name);
                    alert(err.message || 'Failed to rename instance');
                  }
                } else {
                  // Revert if empty or unchanged
                  setEditingName(instance.name);
                }
                setIsEditingName(false);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.target.blur();
                } else if (e.key === 'Escape') {
                  setEditingName(instance.name);
                  setIsEditingName(false);
                }
              }}
              onClick={(e) => e.stopPropagation()}
              className="instance-name-input"
              autoFocus
            />
          ) : (
            <h3 
              className="instance-name clickable"
              onClick={(e) => {
                e.stopPropagation();
                if (isSelected && onRename) {
                  setIsEditingName(true);
                  setEditingName(instance.name);
                }
              }}
              title={isSelected && onRename ? "Click to edit name" : ""}
            >
              {instance.name}
            </h3>
          )}
        </div>
        <div className="instance-header-right">
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
          <div className="instance-coordinates">
            {Object.entries(instance.coordinates).map(([tag, value]) => (
              <span key={tag} className="coordinate">
                {tag}: {value.toFixed(1)}
              </span>
            ))}
            {/* Show SPAC coordinate when SPAC mode is enabled */}
            {spacMode && spacAxisExists && spacValue !== undefined && (
              <span className="coordinate">
                SPAC: {spacValue.toFixed(1)}
              </span>
            )}
          </div>
          <span className={`sync-status-dot sync-status-${syncStatus}`} title={
            syncStatus === 'green' ? 'Synced with Glyphs file' :
            syncStatus === 'orange' ? 'Edited but not saved' :
            'Unknown status'
          }></span>
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
            letterSpacing: letterSpacing, // CSS approximation for SPAC
          }}
        >
          {sampleText}
        </div>
      </div>
    </div>
  );
}

export default InstanceRow;
