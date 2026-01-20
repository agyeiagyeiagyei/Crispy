import React, { useState, useMemo } from 'react';
import './Sidebar.css';
import AxisControl from './AxisControl';
import UpdateButton from './UpdateButton';
import DuplicateModal from './DuplicateModal';

const DEFAULT_SAMPLE_TEXT = "The Quick Brown Fox Jumps Over The Lazy Dog 0123456789 &!";

function Sidebar({ axes, coordinates, onAxisChange, disabled, sampleText, onSampleTextChange, selectedInstance, onUpdateInstance, onResetCoordinates, originalCoordinates, fontSize, onFontSizeChange, onDuplicateInstance, avar2Mode, avar2Instances, avar2Axes }) {
  // Map axis tags to names for avar2 display
  const axisNames = {
    wght: 'Weight',
    wdth: 'Width',
    opsz: 'Optical Size',
    cntr: 'Contrast'
  };
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
      
      {avar2Mode && selectedInstance && avar2Instances.length > 0 && (
        <div className="avar2-traditional-axes">
          <h3 className="avar2-section-title">AVAR2 MAPPINGS</h3>
          {(() => {
            const mapping = avar2Instances.find(
              inst => inst.instance_name === selectedInstance.name
            );
            if (mapping && mapping.avar2_mapping && mapping.avar2_mapping.in) {
              const traditionalAxes = mapping.avar2_mapping.in;
              const axisNames = {
                wght: 'Weight',
                wdth: 'Width',
                opsz: 'Optical Size',
                cntr: 'Contrast'
              };
              // Find axis metadata from axes array to get min/max
              const getAxisMetadata = (tag) => {
                return axes.find(ax => ax.tag === tag) || { min: 0, max: 1000 };
              };
              return (
                <div className="traditional-axes-list">
                  {Object.entries(traditionalAxes).map(([tag, value]) => {
                    return (
                      <div key={tag} className="traditional-axis-item">
                        <div className="traditional-axis-tag">{tag}</div>
                        <div className="traditional-axis-value">
                          {value.toFixed(1)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
            }
            return (
              <div className="avar2-no-mapping">
                No mapping available for this instance
              </div>
            );
          })()}
        </div>
      )}
      
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
