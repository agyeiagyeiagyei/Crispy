import React, { useState, useEffect } from 'react';
import './BuildAvar2Modal.css';

function BuildAvar2Modal({ isOpen, onClose, onBuild, syncStatus, avar2Axes }) {
  // Initialize selected axes based on available axes from CSV
  const initialTraditionalAxes = React.useMemo(() => {
    if (!avar2Axes?.traditional_axes?.columns) {
      return {};
    }
    const initial = {};
    // Select all traditional axes by default
    avar2Axes.traditional_axes.columns.forEach(col => {
      const normalized = col.toLowerCase().replace(/-e$/, ''); // Remove -e suffix if present
      initial[normalized] = true;
    });
    return initial;
  }, [avar2Axes]);

  const initialParametricAxes = React.useMemo(() => {
    if (!avar2Axes?.parametric_axes) {
      return {};
    }
    const initial = {};
    // Select all parametric axes by default (excluding SPAC)
    avar2Axes.parametric_axes.forEach(axis => {
      if (axis.toUpperCase() !== 'SPAC') {
        initial[axis.toUpperCase()] = true;
      }
    });
    return initial;
  }, [avar2Axes]);

  const [selectedTraditionalAxes, setSelectedTraditionalAxes] = useState(initialTraditionalAxes);
  const [selectedAvar2Axes, setSelectedAvar2Axes] = useState(initialParametricAxes);
  const [includeSpac, setIncludeSpac] = useState(true);
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isOpen) {
      setError(null);
      setBuilding(false);
      // Reset selections when modal opens
      setSelectedTraditionalAxes(initialTraditionalAxes);
      setSelectedAvar2Axes(initialParametricAxes);
    }
  }, [isOpen, initialTraditionalAxes, initialParametricAxes]);

  const handleTraditionalAxisToggle = (axis) => {
    setSelectedTraditionalAxes(prev => ({
      ...prev,
      [axis]: !prev[axis]
    }));
  };

  const handleAvar2AxisToggle = (axis) => {
    setSelectedAvar2Axes(prev => ({
      ...prev,
      [axis]: !prev[axis]
    }));
  };

  const handleBuild = async () => {
    // Validate at least one traditional axis is selected
    const selectedTraditional = Object.entries(selectedTraditionalAxes)
      .filter(([_, selected]) => selected)
      .map(([axis, _]) => {
        // Map back to original CSV column name
        const axisObj = traditionalAxes.find(a => a.key === axis);
        return axisObj?.originalColumn || axis;
      });
    
    if (selectedTraditional.length === 0) {
      setError('At least one traditional axis must be selected');
      return;
    }

    const selectedAvar2 = Object.entries(selectedAvar2Axes)
      .filter(([_, selected]) => selected)
      .map(([axis, _]) => axis);

    setBuilding(true);
    setError(null);

    try {
      await onBuild({
        traditionalAxes: selectedTraditional,
        avar2Axes: selectedAvar2,
        includeSpac
      });
      onClose();
    } catch (err) {
      setError(err.message || 'Build failed');
    } finally {
      setBuilding(false);
    }
  };

  // Get traditional axes from avar2Axes (columns from CSV that aren't parametric)
  const traditionalAxes = React.useMemo(() => {
    if (!avar2Axes?.traditional_axes?.columns) {
      return [];
    }
    return avar2Axes.traditional_axes.columns
      .filter(col => col.toUpperCase() !== 'SPAC') // Exclude SPAC
      .map(col => {
        const normalized = col.toLowerCase().replace(/-e$/, ''); // Remove -e suffix
        const metadata = avar2Axes?.metadata?.[col];
        const displayName = metadata?.display_name || col;
        return {
          key: normalized,
          label: `${displayName} (${normalized})`,
          originalColumn: col
        };
      });
  }, [avar2Axes]);

  // Get parametric axes from avar2Axes (axes from Glyphs file, excluding SPAC)
  const parametricAxes = React.useMemo(() => {
    if (!avar2Axes?.parametric_axes) {
      return [];
    }
    return avar2Axes.parametric_axes
      .filter(axis => axis.toUpperCase() !== 'SPAC') // SPAC is handled separately
      .map(axis => {
        const upperAxis = axis.toUpperCase();
        const metadata = avar2Axes?.metadata?.[upperAxis];
        const displayName = metadata?.display_name || axis;
        return {
          key: upperAxis,
          label: `${displayName} (${upperAxis})`
        };
      });
  }, [avar2Axes]);

  if (!isOpen) return null;

  const isUnsynced = syncStatus && !syncStatus.synced;

  return (
    <div className="build-avar2-modal-overlay" onClick={onClose}>
      <div className="build-avar2-modal" onClick={(e) => e.stopPropagation()}>
        <div className="build-avar2-modal-header">
          <h2>Build Avar2 Font</h2>
          <button className="close-button" onClick={onClose} disabled={building}>×</button>
        </div>

        <div className="build-avar2-modal-content">
          {isUnsynced && (
            <div className="sync-warning">
              <strong>⚠️ CSV is not synced with Glyphs file</strong>
              <p>{syncStatus.message}</p>
              <p>You can build anyway, but the font may not match the current Glyphs file state.</p>
            </div>
          )}

          {syncStatus && syncStatus.synced && (
            <div className="sync-success">
              ✓ CSV is synced with Glyphs file
            </div>
          )}

          {traditionalAxes.length > 0 && (
            <div className="axis-selection-section">
              <h3>Traditional Axes (Input to Avar2)</h3>
              <p className="axis-description">Select which traditional axes to include in the avar2 mappings:</p>
              <div className="axis-checkboxes">
                {traditionalAxes.map(axis => (
                  <label key={axis.key} className="axis-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedTraditionalAxes[axis.key] || false}
                      onChange={() => handleTraditionalAxisToggle(axis.key)}
                      disabled={building}
                    />
                    <span>{axis.label}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {parametricAxes.length > 0 && (
            <div className="axis-selection-section">
              <h3>Parametric Axes (Output from Avar2)</h3>
              <p className="axis-description">Select which parametric axes to include:</p>
              <div className="axis-checkboxes">
                {parametricAxes.map(axis => (
                  <label key={axis.key} className="axis-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedAvar2Axes[axis.key] || false}
                      onChange={() => handleAvar2AxisToggle(axis.key)}
                      disabled={building}
                    />
                    <span>{axis.label}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          <div className="axis-selection-section">
            <label className="axis-checkbox">
              <input
                type="checkbox"
                checked={includeSpac}
                onChange={(e) => setIncludeSpac(e.target.checked)}
                disabled={building}
              />
              <span>Include SPAC axis (Spacing)</span>
            </label>
            <p className="axis-description">SPAC axis is added programmatically and is always available.</p>
          </div>

          {error && (
            <div className="error-message">
              {error}
            </div>
          )}
        </div>

        <div className="build-avar2-modal-footer">
          <button
            className="btn btn-secondary"
            onClick={onClose}
            disabled={building}
          >
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={handleBuild}
            disabled={building}
          >
            {building ? 'Building...' : isUnsynced ? 'Build Anyway' : 'Build'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default BuildAvar2Modal;
