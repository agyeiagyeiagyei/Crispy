import React, { useState, useRef, useEffect } from 'react';
import './InstanceRow.css';
import InstanceFlyout from './InstanceFlyout';

function InstanceRow({ instance, isSelected, onSelect, editingCoordinates, instanceEditingCoordinates, sampleText, fontLoaded, fontSize, onDelete, onMove, allInstances, spacMode, spacAxisExists, syncStatus = 'green', onRename, onUpdateInstance }) {
  const [showMoveControls, setShowMoveControls] = useState(false);
  const [movePosition, setMovePosition] = useState('before');
  const [targetInstance, setTargetInstance] = useState(null);
  const [isEditingName, setIsEditingName] = useState(false);
  const [editingName, setEditingName] = useState(instance.name);
  const [showFlyout, setShowFlyout] = useState(false);
  const dotRef = useRef(null);
  const rowRef = useRef(null);
  
  // Build font-variation-settings CSS from coordinates
  // If this row is selected, use editing coordinates (from sliders)
  // Otherwise, use persisted editing coordinates if they exist, or instance coordinates
  const activeCoordinates = isSelected && Object.keys(editingCoordinates).length > 0
    ? editingCoordinates
    : (instanceEditingCoordinates[instance.name] || instance.coordinates);
  
  // Build font-variation-settings string
  // SPAC is now included in activeCoordinates if spacMode is enabled
  let fontVariationSettings = Object.entries(activeCoordinates)
    .map(([tag, value]) => `"${tag}" ${value}`)
    .join(', ');

  return (
    <div
      ref={rowRef}
      className={`instance-row ${isSelected ? 'selected' : ''}`}
      onClick={(e) => {
        // Don't select if clicking on the dot wrapper
        if (e.target.closest('.sync-status-dot-wrapper')) {
          return;
        }
        onSelect();
      }}
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
            {spacMode && spacAxisExists && activeCoordinates.SPAC !== undefined && (
              <span className="coordinate">
                SPAC: {activeCoordinates.SPAC.toFixed(1)}
              </span>
            )}
          </div>
          <div 
            className="sync-status-dot-wrapper"
            onClick={(e) => {
              e.stopPropagation();
              e.preventDefault();
              e.nativeEvent?.stopImmediatePropagation();
              if (syncStatus === 'orange' && onUpdateInstance) {
                setShowFlyout(true);
              }
            }}
            onMouseDown={(e) => {
              // Prevent row selection when clicking dot
              e.stopPropagation();
              e.preventDefault();
            }}
            onMouseUp={(e) => {
              // Also prevent on mouseup
              e.stopPropagation();
              e.preventDefault();
            }}
            style={{
              cursor: syncStatus === 'orange' && onUpdateInstance ? 'pointer' : 'default',
              display: 'inline-flex',
              alignItems: 'center',
              position: 'relative',
              zIndex: 10,
              userSelect: 'none'
            }}
          >
            <span
              ref={dotRef}
              className={`sync-status-dot sync-status-${syncStatus}`}
              title={
                syncStatus === 'green' ? 'Synced with Glyphs file' :
                syncStatus === 'orange' ? 'Edited but not saved - Click to update' :
                'Unknown status'
              }
              style={{
                pointerEvents: 'auto'
              }}
            ></span>
            {showFlyout && syncStatus === 'orange' && onUpdateInstance && dotRef.current && rowRef.current && (() => {
              // Calculate position relative to instance row bounds
              const dotRect = dotRef.current.getBoundingClientRect();
              const rowRect = rowRef.current.getBoundingClientRect();
              const wrapperRect = dotRef.current.closest('.sync-status-dot-wrapper')?.getBoundingClientRect();
              
              if (!wrapperRect) return null;
              
              const flyoutWidth = 150; // Approximate flyout width
              const flyoutHeight = 40; // Approximate flyout height
              const spacing = 4;
              
              // Calculate positions relative to instance row
              const wrapperTopInRow = wrapperRect.top - rowRect.top;
              const wrapperRightInRow = wrapperRect.right - rowRect.left;
              const dotHeight = dotRect.height;
              
              // Calculate available space within instance row
              const rowHeight = rowRect.height;
              
              // Calculate where flyout would be positioned relative to wrapper
              // Use RIGHT positioning - align flyout's right edge with wrapper's right edge (where dot is)
              // Default: below the dot, right edge aligned (right: 0px)
              let flyoutRightInWrapper = 0; // Align right edge with wrapper's right edge (where dot is)
              let flyoutTopInWrapper = dotHeight + spacing;
              
              // Calculate where flyout would be relative to row using right positioning
              // With right: 0, flyout's right edge aligns with wrapper's right edge
              const flyoutRightEdgeInRow = wrapperRightInRow; // Right edge of flyout in row (aligned with wrapper)
              const flyoutLeftEdgeInRow = flyoutRightEdgeInRow - flyoutWidth; // Left edge of flyout in row
              let flyoutTopInRow = wrapperTopInRow + flyoutTopInWrapper;
              let flyoutBottomInRow = flyoutTopInRow + flyoutHeight;
              
              // Check if flyout would overflow left edge of row
              // If so, we need to move the right edge inward (increase flyoutRightInWrapper)
              if (flyoutLeftEdgeInRow < 0) {
                // Would overflow left edge, move right edge inward
                // Calculate how much we need to move: the overflow amount
                const overflow = -flyoutLeftEdgeInRow;
                flyoutRightInWrapper = overflow + spacing; // Move right edge inward by overflow amount
              }
              
              // Adjust vertical position to stay within row bounds
              flyoutTopInRow = wrapperTopInRow + flyoutTopInWrapper;
              flyoutBottomInRow = flyoutTopInRow + flyoutHeight;
              
              if (flyoutBottomInRow > rowHeight) {
                // Would overflow bottom edge
                const spaceAbove = wrapperTopInRow;
                if (spaceAbove >= flyoutHeight) {
                  // Enough space above, position above wrapper
                  flyoutTopInWrapper = -flyoutHeight - spacing;
                } else {
                  // Not enough space, align to bottom edge of row
                  flyoutTopInWrapper = rowHeight - wrapperTopInRow - flyoutHeight - spacing;
                }
              }
              
              const minTop = -wrapperTopInRow; // Can't go past top edge of row
              const maxTop = rowHeight - wrapperTopInRow; // Can't go past bottom edge of row
              flyoutTopInWrapper = Math.max(minTop, Math.min(maxTop, flyoutTopInWrapper));
              
              const positionObj = {
                top: flyoutTopInWrapper,
                right: flyoutRightInWrapper
              };
              
              return (
                <InstanceFlyout
                  isOpen={showFlyout}
                  onClose={() => {
                    setShowFlyout(false);
                  }}
                  onUpdateInstance={() => {
                    // Update this specific instance by name
                    onUpdateInstance(instance.name);
                  }}
                  instanceName={instance.name}
                  position={positionObj}
                />
              );
            })()}
          </div>
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
