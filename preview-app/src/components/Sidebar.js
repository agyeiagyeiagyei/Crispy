import React, { useState, useMemo } from 'react';
import './Sidebar.css';
import AxisControl from './AxisControl';
import UpdateButton from './UpdateButton';
import DuplicateModal from './DuplicateModal';

const DEFAULT_SAMPLE_TEXT = "The Quick Brown Fox Jumps Over The Lazy Dog 0123456789 &!";

function Sidebar({ axes, coordinates, onAxisChange, disabled, sampleText, onSampleTextChange, selectedInstance, onUpdateInstance, onResetCoordinates, originalCoordinates, fontSize, onFontSizeChange, onDuplicateInstance }) {
  const [showDuplicateModal, setShowDuplicateModal] = useState(false);
  
  // Check if coordinates have been modified from original
  const coordinatesChanged = React.useMemo(() => {
    if (!selectedInstance || !originalCoordinates || Object.keys(originalCoordinates).length === 0) {
      return false;
    }
    // Check if any coordinate differs from original
    return Object.keys(originalCoordinates).some(
      key => {
        const current = coordinates[key] ?? 0;
        const original = originalCoordinates[key] ?? 0;
        return Math.abs(current - original) > 0.01;
      }
    );
  }, [selectedInstance, coordinates, originalCoordinates]);
  
  const duplicateButtonText = coordinatesChanged ? "Add New Instance" : "Duplicate Instance";
  
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
          max="12"
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
        <>
          <div className="duplicate-button-section">
            <button
              onClick={() => setShowDuplicateModal(true)}
              className="btn btn-duplicate"
            >
              {duplicateButtonText}
            </button>
          </div>
          <div className="update-button-section">
            <UpdateButton
              onClick={onUpdateInstance}
              instanceName={selectedInstance.name}
            />
          </div>
        </>
      )}
      
      <DuplicateModal
        isOpen={showDuplicateModal}
        onClose={() => setShowDuplicateModal(false)}
        onConfirm={(newName) => {
          setShowDuplicateModal(false);
          onDuplicateInstance(newName);
        }}
        instanceName={selectedInstance?.name || ''}
      />
    </aside>
  );
}

export default Sidebar;
