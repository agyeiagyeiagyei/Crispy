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

  // Load initial data
  useEffect(() => {
    loadData();
  }, []);

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

      if (health.font_built) {
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
      setFontUrl(api.getFontUrl());
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

  const handleSelectInstance = useCallback((instance) => {
    setSelectedInstance(instance);
    // Initialize editing coordinates with instance coordinates
    setEditingCoordinates({ ...instance.coordinates });
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
      }

      // Auto-rebuild font after update
      await handleBuildFont();
    } catch (err) {
      setError(err.message);
      console.error('Update failed:', err);
    }
  };

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
          />
          
          {selectedInstance && (
            <UpdateButton
              onClick={handleUpdateInstance}
              instanceName={selectedInstance.name}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
