import React, { useState } from 'react';
import './DeleteInstanceModal.css';

function DeleteInstanceModal({ isOpen, onClose, instanceName, onConfirm, glyphsFileHasUnsavedChanges }) {
  const [deleteFromGlyphs, setDeleteFromGlyphs] = useState(false);

  if (!isOpen) return null;

  const handleConfirm = () => {
    onConfirm(deleteFromGlyphs);
    setDeleteFromGlyphs(false); // Reset for next time
  };

  const handleCancel = () => {
    setDeleteFromGlyphs(false); // Reset
    onClose();
  };

  const isDisabled = deleteFromGlyphs && glyphsFileHasUnsavedChanges;

  return (
    <div className="modal-overlay" onClick={handleCancel}>
      <div className="delete-instance-modal" onClick={(e) => e.stopPropagation()}>
        <h3>Delete Instance</h3>
        <p className="delete-instance-message">
          {deleteFromGlyphs
            ? `Permanently delete instance "${instanceName}" from the Glyphs file and preview?`
            : `Remove instance "${instanceName}" from preview?`}
        </p>
        {deleteFromGlyphs && (
          <p className="delete-instance-warning">
            ⚠️ This action cannot be undone. The instance will be permanently removed from the font file.
          </p>
        )}
        {isDisabled && (
          <p className="delete-instance-error">
            ⚠️ Cannot delete from Glyphs file: The file has unsaved changes. Please save the file first.
          </p>
        )}
        <div className="delete-instance-checkbox">
          <label>
            <input
              type="checkbox"
              checked={deleteFromGlyphs}
              onChange={(e) => setDeleteFromGlyphs(e.target.checked)}
              disabled={glyphsFileHasUnsavedChanges}
            />
            <span>Also delete from Glyphs file</span>
          </label>
        </div>
        <div className="delete-instance-buttons">
          <button
            className="delete-instance-cancel"
            onClick={handleCancel}
          >
            Cancel
          </button>
          <button
            className="delete-instance-confirm"
            onClick={handleConfirm}
            disabled={isDisabled}
          >
            {deleteFromGlyphs ? 'Delete Permanently' : 'Remove from Preview'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default DeleteInstanceModal;
