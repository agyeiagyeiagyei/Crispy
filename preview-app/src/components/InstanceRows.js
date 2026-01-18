import React, { useEffect, useState } from 'react';
import './InstanceRows.css';
import InstanceRow from './InstanceRow';

function InstanceRows({ instances, selectedInstance, onSelectInstance, editingCoordinates, sampleText, fontUrl, fontLoaded }) {
  const [fontReady, setFontReady] = useState(false);
  
  // Load font when available
  useEffect(() => {
    if (fontUrl && fontLoaded) {
      // Load font using FontFace API
      // Register with name 'Crispy-VF' so we can reference it in CSS
      const fontFace = new FontFace('Crispy-VF', `url(${fontUrl})`);
      fontFace.load()
        .then((loadedFont) => {
          document.fonts.add(loadedFont);
          setFontReady(true);
          console.log('Font loaded successfully. Registered as:', loadedFont.family);
          console.log('Font status:', document.fonts.check('12px Crispy-VF'));
        })
        .catch(err => {
          console.error('Failed to load font:', err);
          setFontReady(false);
        });
    } else {
      setFontReady(false);
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
          editingCoordinates={editingCoordinates}
          sampleText={sampleText}
          fontLoaded={fontLoaded && fontReady}
        />
      ))}
    </div>
  );
}

export default InstanceRows;
