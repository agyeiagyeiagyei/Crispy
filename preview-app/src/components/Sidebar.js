import React, { useState } from 'react';
import './Sidebar.css';
import AxisControl from './AxisControl';
import SpacAxisControl from './SpacAxisControl';
import DuplicateModal from './DuplicateModal';
import AddAxisModal from './AddAxisModal';
import EditAxisModal from './EditAxisModal';

function Sidebar({ axes, coordinates, onAxisChange, disabled, sampleText, onSampleTextChange, selectedInstance, onUpdateInstance, onUpdateAllInstances, onResetCoordinates, originalCoordinates, fontSize, onFontSizeChange, onDuplicateInstance, avar2Mode, avar2Instances, avar2Axes, onAddAvar2Axis, onUpdateAvar2Axis, onUpdateAvar2Mapping, onReloadAvar2Data, spacMode, spacAxisExists, glyphsFileHasUnsavedChanges, getInstanceSyncStatus, instances, building = false }) {
  const [showDuplicateModal, setShowDuplicateModal] = useState(false);
  const [showAddAxisModal, setShowAddAxisModal] = useState(false);
  const [showEditAxisModal, setShowEditAxisModal] = useState(false);
  const [editingAxisName, setEditingAxisName] = useState(null);
  const [editingValue, setEditingValue] = useState({ instance: null, axis: null, value: null });
  const [savingValue, setSavingValue] = useState(false);
  const [valueError, setValueError] = useState(null);
  
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
        <div className="axis-header">
          <label className="axis-name">Font Size: {fontSize.toFixed(1)}rem</label>
        </div>
        <div className="axis-slider-container">
          <input
            type="range"
            min="0.5"
            max="12"
            step="0.1"
            value={fontSize}
            onChange={(e) => onFontSizeChange(parseFloat(e.target.value))}
            className="axis-slider"
          />
          <div className="axis-values">
            <span className="axis-min">0.5</span>
            <span className="axis-current">{fontSize.toFixed(1)}</span>
            <span className="axis-max">12.0</span>
          </div>
        </div>
      </div>
      
      <div className="axis-controls">
        {axes.map(axis => {
          // Skip SPAC axis if spacMode is OFF
          if ((axis.tag === 'SPAC' || axis.tag === 'spac') && !spacMode) {
            return null;
          }
          
          // Render SPAC axis - now uses same pattern as other axes (no Apply button)
          // SPAC preview uses font-variation-settings (not letter-spacing) for accurate rendering
          if ((axis.tag === 'SPAC' || axis.tag === 'spac') && spacMode) {
            return (
              <SpacAxisControl
                key={axis.tag}
                axis={axis}
                value={coordinates[axis.tag] ?? axis.default}
                onChange={(value) => onAxisChange(axis.tag, value)}
                disabled={disabled}
              />
            );
          }
          // Render other axes normally
          return (
            <AxisControl
              key={axis.tag}
              axis={axis}
              value={coordinates[axis.tag] ?? axis.default}
              onChange={(value) => onAxisChange(axis.tag, value)}
              disabled={disabled}
            />
          );
        })}
        
        {/* SPAC error state - when toggle is ON but axis doesn't exist */}
        {spacMode && !spacAxisExists && (
          <div className="spac-error-state">
            <div>SPAC axis not available. Click toggle to initialize.</div>
          </div>
        )}
      </div>
      
      {avar2Mode && selectedInstance && (() => {
        // Check if there are any traditional axes in the CSV
        const hasTraditionalAxes = avar2Axes?.traditional_axes?.columns && avar2Axes.traditional_axes.columns.length > 0;
        
        return (
        <div className="avar2-traditional-axes">
          <h3 className="avar2-section-title">AVAR2 MAPPINGS</h3>
          {(() => {
            // Show loading state if data is not ready yet
            if (!avar2Axes || avar2Instances.length === 0) {
              return <div className="avar2-loading">Loading mappings...</div>;
            }
            
            // If no traditional axes exist, show "Add Axis" button
            if (!hasTraditionalAxes) {
              return (
                <div className="avar2-add-axis-section">
                  <button
                    className="btn btn-add-axis"
                    onClick={() => {
                      setShowAddAxisModal(true);
                    }}
                  >
                    + Add Axis
                  </button>
                </div>
              );
            }
            
            const mapping = avar2Instances.find(
              inst => inst.instance_name === selectedInstance.name
            );
            // Only show mappings if there are traditional axes (in:) to display
            if (mapping && mapping.avar2_mapping && mapping.avar2_mapping.in && Object.keys(mapping.avar2_mapping.in).length > 0) {
              const traditionalAxes = mapping.avar2_mapping.in;
              const metadata = avar2Axes?.metadata || {};
              
              // Get axis column names from metadata or use normalized tags
              const axisColumns = avar2Axes?.traditional_axes?.columns || [];
              
              return (
                <>
                  <div className="traditional-axes-list">
                    {Object.entries(traditionalAxes)
                      .filter(([tag]) => {
                        // Exclude SPAC from avar2 mappings
                        const normalizedTag = tag.toLowerCase();
                        return normalizedTag !== 'spac';
                      })
                      .map(([tag, value]) => {
                      // Map normalized tag (wght, wdth, etc.) to CSV column name
                      // The backend provides normalized tags in avar2_mapping.in, but we need CSV column names
                      const tagToColumnMap = {
                        'wght': 'WGHT',
                        'wdth': 'WDTH', 
                        'opsz': 'OPSZ',
                        'cntr': 'CNTR'  // CNTR is the CSV column name
                      };
                      
                      // Try to find CSV column by matching normalized tag
                      let axisColumn = tagToColumnMap[tag] || tag.toUpperCase();
                      
                      // Skip SPAC column
                      if (axisColumn === 'SPAC' || axisColumn === 'spac') {
                        return null;
                      }
                      
                      // If not found in map, try to find in columns by normalizing
                      if (!axisColumns.includes(axisColumn)) {
                        const found = axisColumns.find(col => {
                          const normalized = col.toUpperCase().replace(/-E$/, '');
                          const tagMap = { WGHT: 'wght', WDTH: 'wdth', OPSZ: 'opsz', CONTRAST: 'cntr', CNTR: 'cntr' };
                          return tagMap[normalized] === tag;
                        });
                        if (found) axisColumn = found;
                      }
                      
                      // Skip SPAC again after column lookup
                      if (axisColumn === 'SPAC' || axisColumn === 'spac') {
                        return null;
                      }
                      
                      // Use metadata from backend (which ensures all axes are in JSON)
                      // CSV column names (like "WGHT") are the keys in metadata
                      const axisMeta = metadata[axisColumn];
                      
                      // Ensure we have metadata - if not, something is wrong
                      if (!axisMeta) {
                        console.warn(`Missing metadata for axis column: ${axisColumn}`);
                      }
                      
                      // Use registered_tag for avar2 mapping labels (not display_name)
                      // Fallback to normalized tag if metadata is missing
                      const axisLabel = axisMeta?.registered_tag || tag;
                      
                      const isEditing = editingValue.instance === selectedInstance.name && editingValue.axis === axisColumn;
                      const isSaving = savingValue && editingValue.instance === selectedInstance.name && editingValue.axis === axisColumn;
                      
                      // Check if this is a parametric axis (exists in Glyphs file) - cannot edit
                      // Use is_parametric flag from metadata, fallback to checking parametric_axes array
                      const isParametricAxis = axisMeta?.is_parametric === true || avar2Axes?.parametric_axes?.includes(axisColumn) || false;
                      
                      // Get min/max from metadata or use defaults
                      const axisMin = axisMeta?.min ?? -1000;
                      const axisMax = axisMeta?.max ?? 1000;
                      
                      return (
                        <div key={tag} className="traditional-axis-item">
                          <div 
                            className={`traditional-axis-tag ${isParametricAxis ? '' : 'clickable'}`}
                            onClick={() => {
                              if (!isParametricAxis) {
                                setEditingAxisName(axisColumn);
                                setShowEditAxisModal(true);
                              }
                            }}
                            title={isParametricAxis ? "Parametric axis (from Glyphs file) - cannot edit" : "Click to edit axis metadata"}
                          >
                            {axisLabel}
                            {isParametricAxis && <span className="parametric-badge"> (Glyphs)</span>}
                          </div>
                          {isEditing && !isParametricAxis ? (
                            <input
                              type="number"
                              className="traditional-axis-value-input"
                              defaultValue={value}
                              step="0.1"
                              autoFocus
                              ref={(input) => {
                                // Select all text when input becomes focused
                                if (input) {
                                  input.select();
                                }
                              }}
                              onBlur={async (e) => {
                                const newValue = parseFloat(e.target.value);
                                if (isNaN(newValue)) {
                                  setEditingValue({ instance: null, axis: null, value: null });
                                  return;
                                }
                                
                                // Validate range
                                if (newValue < axisMin || newValue > axisMax) {
                                  setValueError(`Value must be between ${axisMin} and ${axisMax}`);
                                  setTimeout(() => setValueError(null), 3000);
                                  setEditingValue({ instance: null, axis: null, value: null });
                                  return;
                                }
                                
                                setSavingValue(true);
                                setValueError(null);
                                try {
                                  await onUpdateAvar2Mapping(selectedInstance.name, axisColumn, newValue);
                                  setEditingValue({ instance: null, axis: null, value: null });
                                } catch (err) {
                                  setValueError(err.message || 'Failed to save value');
                                  setTimeout(() => setValueError(null), 3000);
                                  // Revert to original value
                                  setEditingValue({ instance: null, axis: null, value: null });
                                } finally {
                                  setSavingValue(false);
                                }
                              }}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  e.target.blur();
                                } else if (e.key === 'Escape') {
                                  setEditingValue({ instance: null, axis: null, value: null });
                                }
                              }}
                            />
                          ) : (
                            <div 
                              className={`traditional-axis-value ${isSaving ? 'saving' : (isParametricAxis ? '' : 'clickable')}`}
                              onClick={() => {
                                if (!isSaving && !isParametricAxis) {
                                  setEditingValue({ 
                                    instance: selectedInstance.name, 
                                    axis: axisColumn, 
                                    value: value 
                                  });
                                }
                              }}
                              title={isParametricAxis ? "Parametric axis (from Glyphs file) - cannot edit" : `Click to edit (range: ${axisMeta.min} to ${axisMeta.max})`}
                            >
                              {isSaving ? '...' : value.toFixed(1)}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  {valueError && (
                    <div className="avar2-error-message">{valueError}</div>
                  )}
                  <div className="avar2-add-axis-section">
                    <button
                      className="btn btn-add-axis"
                      onClick={() => {
                        setShowAddAxisModal(true);
                      }}
                    >
                      Add Axis
                    </button>
                  </div>
                </>
              );
            }
            // No mapping for this instance, but traditional axes exist - show "Add Axis" button
            return (
              <div className="avar2-add-axis-section">
                <button
                  className="btn btn-add-axis"
                  onClick={() => {
                    setShowAddAxisModal(true);
                  }}
                >
                  + Add Axis
                </button>
              </div>
            );
          })()}
        </div>
        );
      })()}
      
      {onUpdateAllInstances && (() => {
        // Check if any instances have unsaved changes
        const hasUnsavedChanges = instances && getInstanceSyncStatus
          ? instances.some(instance => getInstanceSyncStatus(instance) === 'orange')
          : false;
        
        return (
          <div className="update-button-section">
            <button
              onClick={onUpdateAllInstances}
              className="btn btn-update"
              disabled={glyphsFileHasUnsavedChanges || !hasUnsavedChanges || building}
              title={
                glyphsFileHasUnsavedChanges
                  ? "Save Glyphs file before updating instances"
                  : !hasUnsavedChanges
                  ? "No instances have unsaved changes"
                  : building
                  ? "Updating instances..."
                  : "Update all instances with unsaved changes"
              }
            >
              {building ? "Updating..." : "Update All Instances"}
            </button>
          </div>
        );
      })()}
      
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
        <div className="duplicate-button-section">
          <button
            onClick={() => setShowDuplicateModal(true)}
            className="btn btn-duplicate"
          >
            {duplicateButtonText}
          </button>
        </div>
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
      
      <AddAxisModal
        isOpen={showAddAxisModal}
        onClose={() => setShowAddAxisModal(false)}
        onConfirm={async (axisData) => {
          try {
            await onAddAvar2Axis(axisData);
            setShowAddAxisModal(false);
            // Force reload after a brief delay to ensure backend has processed
            setTimeout(() => {
              if (onReloadAvar2Data) {
                onReloadAvar2Data();
              }
            }, 500);
          } catch (err) {
            // Error will be shown in modal or handled by parent
            console.error('Failed to add axis:', err);
            alert(err.message || 'Failed to add axis');
            // Don't close modal on error so user can see the error
          }
        }}
        existingAxes={avar2Axes?.traditional_axes?.columns || []}
        existingMetadata={avar2Axes?.metadata || {}}
        parametricAxes={avar2Axes?.parametric_axes || []}
      />
      
      <EditAxisModal
        isOpen={showEditAxisModal}
        onClose={() => {
          setShowEditAxisModal(false);
          setEditingAxisName(null);
        }}
        onConfirm={async (axisData) => {
          try {
            // Check if this is a parametric axis - should not be editable
            const axisMeta = avar2Axes?.metadata?.[editingAxisName];
            const isParametric = axisMeta?.is_parametric === true || avar2Axes?.parametric_axes?.includes(editingAxisName) || false;
            if (isParametric) {
              throw new Error("Cannot edit parametric axes - they are managed in the Glyphs file");
            }
            await onUpdateAvar2Axis(editingAxisName, axisData);
            setShowEditAxisModal(false);
            setEditingAxisName(null);
          } catch (err) {
            // Error will be shown in modal or handled by parent
            console.error('Failed to update axis:', err);
            alert(err.message || 'Failed to update axis');
          }
        }}
        axisName={editingAxisName}
        axisMetadata={editingAxisName && avar2Axes?.metadata?.[editingAxisName]}
        existingAxes={(avar2Axes?.traditional_axes?.columns || []).map(col => ({
          axisName: col,
          registeredTag: avar2Axes?.metadata?.[col]?.registered_tag || ''
        }))}
        isParametricAxis={editingAxisName && (avar2Axes?.parametric_axes?.includes(editingAxisName) || false)}
      />
    </aside>
  );
}

export default Sidebar;
