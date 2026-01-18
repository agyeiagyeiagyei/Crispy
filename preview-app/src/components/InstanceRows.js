import React, { useEffect } from 'react';
import './InstanceRows.css';
import InstanceRow from './InstanceRow';

function InstanceRows({ instances, selectedInstance, onSelectInstance, coordinates, fontUrl, fontLoaded }) {
  // Load font when available
  useEffect(() => {
    if (fontUrl && fontLoaded) {
      // Load font using FontFace API
      const font = new FontFace('Crispy-VF', `url(${fontUrl})`);
      font.load().then(() => {
        document.fonts.add(font);
      }).catch(err => {
        console.error('Failed to load font:', err);
      });
    }
  }, [fontUrl, fontLoaded]);

  if (!fontLoaded) {
    return (
      <div className="instance-rows-container">
        <div className="no-font-message">
          Build the font to see instance previews
        </div>
      </div>
    );
  }

  return (
    <div className="instance-rows-container">
      {instances.map(instance => (
        <InstanceRow
          key={instance.name}
          instance={instance}
          isSelected={selectedInstance?.name === instance.name}
          onSelect={() => onSelectInstance(instance)}
          coordinates={coordinates}
          fontLoaded={fontLoaded}
        />
      ))}
    </div>
  );
}

export default InstanceRows;
