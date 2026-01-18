import React from 'react';
import './InstanceRow.css';

function InstanceRow({ instance, isSelected, onSelect, editingCoordinates, sampleText, fontLoaded, fontSize }) {
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
        <div className="instance-coordinates">
          {Object.entries(instance.coordinates).map(([tag, value]) => (
            <span key={tag} className="coordinate">
              {tag}: {value.toFixed(1)}
            </span>
          ))}
        </div>
      </div>
      
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
