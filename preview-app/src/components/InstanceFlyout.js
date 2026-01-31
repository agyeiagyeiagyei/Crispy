import React, { useEffect, useRef } from 'react';
import './InstanceFlyout.css';

function InstanceFlyout({ isOpen, onClose, onUpdateInstance, instanceName, position }) {
  const flyoutRef = useRef(null);

  // Close flyout when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (flyoutRef.current && !flyoutRef.current.contains(event.target)) {
        onClose();
      }
    };

    // Close on Escape key
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleEscape);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const style = position ? {
    position: 'absolute',
    top: `${position.top}px`,
    ...(position.right !== undefined && position.right !== null 
      ? { right: `${position.right}px`, left: 'auto' } 
      : { left: `${position.left || 0}px`, right: 'auto' }),
    zIndex: 1000,
  } : {};

  return (
    <div
      ref={flyoutRef}
      className="instance-flyout"
      style={style}
      onClick={(e) => e.stopPropagation()}
    >
      <button
        className="flyout-item"
        onClick={() => {
          onUpdateInstance();
          onClose();
        }}
      >
        Update Instance
      </button>
    </div>
  );
}

export default InstanceFlyout;
