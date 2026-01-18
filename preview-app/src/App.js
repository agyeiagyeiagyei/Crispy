import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import { api } from './api';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import InstanceRows from './components/InstanceRows';
import UpdateButton from './components/UpdateButton';

const DEFAULT_SAMPLE_TEXT = "the quick brown fox jumps over the lazy dog 0123456789 &!";

function App() {
  const [instances, setInstances] = useState([]);
  const [axes, setAxes] = useState([]);
  const [selectedInstance, setSelectedInstance] = useState(null);
  const [editingCoordinates, setEditingCoordinates] = useState({});
  const [fontLoaded, setFontLoaded] = useState(false);
  const [fontUrl, setFontUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [building, setBuilding] = useState(false);
  const [sampleText, setSampleText] = useState(DEFAULT_SAMPLE_TEXT);
  const [fontSize, setFontSize] = useState(2); // Default 2rem
  const [familyName, setFamilyName] = useState(null);
  const [lastBuildTime, setLastBuildTime] = useState(null);

  // Load initial data
  useEffect(() => {
    loadData();
  }, []);

  // Poll for font rebuilds (check every 2 seconds)
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const health = await api.health();
        setBuilding(health.building || false);
        
        // If font was rebuilt (new build time), reload
        if (health.font_built && health.last_build_time && health.last_build_time !== lastBuildTime) {
          setLastBuildTime(health.last_build_time);
          setFontLoaded(true);
          setFontUrl(api.getFontUrl());
          // Reload instances and axes in case they changed
          const [instancesData, axesData] = await Promise.all([
            api.getInstances(),
            api.getAxes(),
          ]);
          setInstances(instancesData.instances);
          setAxes(axesData.axes);
        }
      } catch (err) {
        // Silently fail polling errors
        console.debug('Polling error:', err);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(interval);
  }, [lastBuildTime]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Check health and font status
      const health = await api.health();
      
      // Load instances and axes
      const [instancesData, axesData] = await Promise.all([
        api.getInstances(),
        api.getAxes(),
      ]);

      setInstances(instancesData.instances);
      setAxes(axesData.axes);
      setFontLoaded(health.font_built);
      setFamilyName(health.family_name || null);
      setLastBuildTime(health.last_build_time || null);
      setBuilding(health.building || false);

      // If font was rebuilt (new build time), reload the font
      if (health.font_built && health.last_build_time && health.last_build_time !== lastBuildTime) {
        setFontUrl(api.getFontUrl()); // This is synchronous, returns string
        // Force font reload by updating fontLoaded state
        setFontLoaded(true);
      } else if (health.font_built && !fontUrl) {
        setFontUrl(api.getFontUrl());
      }
    } catch (err) {
      setError(err.message);
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleBuildFont = async () => {
    try {
      setBuilding(true);
      setError(null);
      await api.buildFont();
      setFontLoaded(true);
      setFontUrl(api.getFontUrl()); // This is synchronous, returns string
      // Reload axes from built font
      const axesData = await api.getAxes();
      setAxes(axesData.axes);
    } catch (err) {
      setError(err.message);
      console.error('Build failed:', err);
    } finally {
      setBuilding(false);
    }
  };

  const [originalCoordinates, setOriginalCoordinates] = useState({});

  const handleSelectInstance = useCallback((instance) => {
    setSelectedInstance(instance);
    // Initialize editing coordinates with instance coordinates
    setEditingCoordinates({ ...instance.coordinates });
    // Store original coordinates for reset
    setOriginalCoordinates({ ...instance.coordinates });
  }, []);

  const handleAxisChange = useCallback((tag, value) => {
    setEditingCoordinates(prev => ({
      ...prev,
      [tag]: value,
    }));
  }, []);

  const handleUpdateInstance = async () => {
    if (!selectedInstance) return;

    // Show confirmation dialog
    const confirmed = window.confirm(
      `Update instance "${selectedInstance.name}" with new coordinates?\n\n` +
      `This will modify the Glyphs file.`
    );

    if (!confirmed) return;

    try {
      setError(null);
      await api.updateInstance(selectedInstance.name, editingCoordinates);
      
      // Reload instances to get updated data
      const instancesData = await api.getInstances();
      setInstances(instancesData.instances);
      
      // Update selected instance
      const updated = instancesData.instances.find(
        inst => inst.name === selectedInstance.name
      );
      if (updated) {
        setSelectedInstance(updated);
        setEditingCoordinates({ ...updated.coordinates });
        setOriginalCoordinates({ ...updated.coordinates });
      }

      // Auto-rebuild font after update
      await handleBuildFont();
    } catch (err) {
      setError(err.message);
      console.error('Update failed:', err);
    }
  };

  const handleResetCoordinates = useCallback(() => {
    if (!selectedInstance) return;
    setEditingCoordinates({ ...originalCoordinates });
  }, [selectedInstance, originalCoordinates]);

  const handleDeleteInstance = useCallback((instanceToDelete) => {
    // Show confirmation dialog
    const confirmed = window.confirm(
      `Remove instance "${instanceToDelete.name}" from preview?\n\n` +
      `This will only remove it from the preview. Refresh the page to restore it.`
    );

    if (!confirmed) return;

    // Remove from instances list
    setInstances(prev => prev.filter(inst => inst.name !== instanceToDelete.name));
    
    // Clear selection if the deleted instance was selected
    if (selectedInstance && selectedInstance.name === instanceToDelete.name) {
      setSelectedInstance(null);
      setEditingCoordinates({});
      setOriginalCoordinates({});
    }
  }, [selectedInstance]);

  const handleMoveInstance = useCallback((instanceToMove, targetInstance, position) => {
    if (!instanceToMove || !targetInstance) return;
    
    // Find current indices
    const currentIndex = instances.findIndex(inst => inst.name === instanceToMove.name);
    const targetIndex = instances.findIndex(inst => inst.name === targetInstance.name);
    
    // If already in the correct position, silently ignore
    if (currentIndex === targetIndex || 
        (position === 'before' && currentIndex === targetIndex - 1) ||
        (position === 'after' && currentIndex === targetIndex + 1)) {
      return;
    }
    
    // Calculate new index
    let newIndex;
    if (position === 'before') {
      newIndex = targetIndex;
    } else {
      newIndex = targetIndex + 1;
    }
    
    // Adjust if moving from before the target position
    if (currentIndex < newIndex) {
      newIndex--;
    }
    
    // Perform move
    const newInstances = [...instances];
    const [movedItem] = newInstances.splice(currentIndex, 1);
    newInstances.splice(newIndex, 0, movedItem);
    
    setInstances(newInstances);
  }, [instances]);

  if (loading) {
    return (
      <div className="App">
        <div className="loading">Loading...</div>
      </div>
    );
  }

  return (
    <div className="App">
      <Header
        onBuildFont={handleBuildFont}
        onRefresh={loadData}
        building={building}
        fontLoaded={fontLoaded}
        familyName={familyName}
      />
      
      {error && (
        <div className="error-banner">
          Error: {error}
        </div>
      )}

      <div className="main-content">
        <Sidebar
          axes={axes}
          coordinates={editingCoordinates}
          onAxisChange={handleAxisChange}
          disabled={!selectedInstance}
          sampleText={sampleText}
          onSampleTextChange={setSampleText}
          selectedInstance={selectedInstance}
          onUpdateInstance={handleUpdateInstance}
          onResetCoordinates={handleResetCoordinates}
          originalCoordinates={originalCoordinates}
          fontSize={fontSize}
          onFontSizeChange={setFontSize}
        />
        
        <div className="content-area">
          <InstanceRows
            instances={instances}
            selectedInstance={selectedInstance}
            onSelectInstance={handleSelectInstance}
            editingCoordinates={editingCoordinates}
            sampleText={sampleText}
            fontUrl={fontUrl}
            fontLoaded={fontLoaded}
            onReorderInstances={setInstances}
            fontSize={fontSize}
            onDeleteInstance={handleDeleteInstance}
            onMoveInstance={handleMoveInstance}
          />
        </div>
      </div>
    </div>
  );
}

export default App;
