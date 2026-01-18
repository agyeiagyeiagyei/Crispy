import React, { useEffect, useState } from 'react';
import './InstanceRows.css';
import InstanceRow from './InstanceRow';

function InstanceRows({ instances, selectedInstance, onSelectInstance, editingCoordinates, sampleText, fontUrl, fontLoaded, onReorderInstances, fontSize, onDeleteInstance, onMoveInstance }) {
  const [draggedIndex, setDraggedIndex] = useState(null);
  const [dragOverIndex, setDragOverIndex] = useState(null);
  const [fontReady, setFontReady] = useState(false);
  
  // Load font when available
  useEffect(() => {
    if (fontUrl && fontLoaded && typeof fontUrl === 'string') {
      console.log('Loading font from:', fontUrl);
      
      // Remove old font if it exists to force reload
      const oldFont = Array.from(document.fonts).find(f => f.family === 'Crispy-VF');
      if (oldFont) {
        document.fonts.delete(oldFont);
        console.log('Removed old font to force reload');
      }
      
      // Load font using FontFace API
      // Register with name 'Crispy-VF' so we can reference it in CSS
      const fontFace = new FontFace('Crispy-VF', `url(${fontUrl})`);
      fontFace.load()
        .then((loadedFont) => {
          document.fonts.add(loadedFont);
          // Wait for font to be ready
          return document.fonts.ready.then(() => {
            setFontReady(true);
            console.log('Font loaded and ready. Registered as:', loadedFont.family);
            console.log('Font check:', document.fonts.check('12px "Crispy-VF"'));
          });
        })
        .catch(err => {
          console.error('Failed to load font:', err);
          console.error('Font URL:', fontUrl);
          setFontReady(false);
        });
    } else {
      setFontReady(false);
    }
  }, [fontUrl, fontLoaded]);

  // Handle wheel scrolling during drag
  useEffect(() => {
    if (draggedIndex === null) return;
    
    const container = document.querySelector('.instance-rows-container');
    if (!container) return;
    
    // Allow wheel scrolling on the container during drag
    const handleWheel = (e) => {
      // Don't prevent default - allow normal scrolling
    };
    
    container.addEventListener('wheel', handleWheel, { passive: true });
    return () => {
      container.removeEventListener('wheel', handleWheel);
    };
  }, [draggedIndex]);

  if (!fontLoaded) {
    return (
      <div className="instance-rows-container">
        <div className="no-font-message">
          Build the font to see instance previews
        </div>
      </div>
    );
  }

  const handleDragStart = (index) => {
    setDraggedIndex(index);
  };

  const handleDragOver = (e, index) => {
    e.preventDefault();
    setDragOverIndex(index);
    
    // Enable scrolling during drag
    const container = e.currentTarget.closest('.instance-rows-container');
    if (container) {
      const rect = container.getBoundingClientRect();
      const scrollThreshold = 50; // pixels from edge
      const scrollSpeed = 10; // pixels per scroll
      
      // Check if near top edge
      if (e.clientY - rect.top < scrollThreshold) {
        container.scrollTop -= scrollSpeed;
      }
      // Check if near bottom edge
      else if (rect.bottom - e.clientY < scrollThreshold) {
        container.scrollTop += scrollSpeed;
      }
    }
  };

  const handleDragEnd = () => {
    if (draggedIndex === null || dragOverIndex === null || draggedIndex === dragOverIndex) {
      setDraggedIndex(null);
      setDragOverIndex(null);
      return;
    }

    const newInstances = [...instances];
    const [draggedItem] = newInstances.splice(draggedIndex, 1);
    newInstances.splice(dragOverIndex, 0, draggedItem);
    
    onReorderInstances(newInstances);
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  const handleDragLeave = () => {
    setDragOverIndex(null);
  };

  return (
    <div className="instance-rows-container">
      {instances.map((instance, index) => (
        <div
          key={instance.name}
          draggable
          onDragStart={() => handleDragStart(index)}
          onDragOver={(e) => handleDragOver(e, index)}
          onDragEnd={handleDragEnd}
          onDragLeave={handleDragLeave}
          className={`instance-row-wrapper ${draggedIndex === index ? 'dragging' : ''} ${dragOverIndex === index ? 'drag-over' : ''}`}
        >
          <InstanceRow
            instance={instance}
            isSelected={selectedInstance?.name === instance.name}
            onSelect={() => onSelectInstance(instance)}
            editingCoordinates={editingCoordinates}
            sampleText={sampleText}
            fontLoaded={fontLoaded && fontReady}
            fontSize={fontSize}
            onDelete={onDeleteInstance}
            onMove={onMoveInstance}
            allInstances={instances}
          />
        </div>
      ))}
    </div>
  );
}

export default InstanceRows;
