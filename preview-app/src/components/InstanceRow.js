import React, { useState } from 'react';
import './InstanceRow.css';

const DEFAULT_SAMPLE_TEXT = "the quick brown fox jumps over the lazy dog 0123456789 &!";

function InstanceRow({ instance, isSelected, onSelect, coordinates, fontLoaded }) {
  const [sampleText, setSampleText] = useState(DEFAULT_SAMPLE_TEXT);

  // Build font-variation-settings CSS from coordinates
  // If this row is selected, use editing coordinates (from sliders)
  // Otherwise, use the instance's own coordinates
  const activeCoordinates = isSelected && Object.keys(coordinates).length > 0
    ? coordinates
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
          {Object.entries(coordinates).map(([tag, value]) => (
            <span key={tag} className="coordinate">
              {tag}: {value.toFixed(1)}
            </span>
          ))}
        </div>
      </div>
      
      <div className="instance-row-content">
        <input
          type="text"
          value={sampleText}
          onChange={(e) => setSampleText(e.target.value)}
          onClick={(e) => e.stopPropagation()}
          className="sample-text-input"
          placeholder="Enter sample text..."
        />
        
        <div
          className="preview-text"
          style={{
            fontFamily: fontLoaded ? 'Crispy-VF' : 'sans-serif',
            fontVariationSettings: fontLoaded ? fontVariationSettings : undefined,
          }}
        >
          {sampleText || DEFAULT_SAMPLE_TEXT}
        </div>
      </div>
    </div>
  );
}

export default InstanceRow;
