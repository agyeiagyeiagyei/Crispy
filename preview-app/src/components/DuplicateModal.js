import React, { useState, useEffect, useRef } from 'react';
import './DuplicateModal.css';

function DuplicateModal({ isOpen, onClose, onConfirm, instanceName }) {
  const [newName, setNewName] = useState('');
  const inputRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      // Set default name when modal opens
      setNewName(`${instanceName} Copy`);
      // Focus input after a brief delay to ensure modal is rendered
      setTimeout(() => {
        if (inputRef.current) {
          inputRef.current.focus();
          inputRef.current.select();
        }
      }, 100);
    }
  }, [isOpen, instanceName]);

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmedName = newName.trim();
    if (trimmedName) {
      onConfirm(trimmedName);
    }
  };

  const handleCancel = () => {
    setNewName('');
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={handleCancel}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h3>Duplicate Instance</h3>
        <p>Enter a name for the new instance:</p>
        <form onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Instance name"
            className="modal-input"
            autoFocus
          />
          <div className="modal-buttons">
            <button type="button" onClick={handleCancel} className="btn btn-cancel">
              Cancel
            </button>
            <button type="submit" className="btn btn-confirm" disabled={!newName.trim()}>
              Duplicate
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default DuplicateModal;
