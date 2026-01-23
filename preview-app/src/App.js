import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import { api } from './api';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import InstanceRows from './components/InstanceRows';
import UpdateButton from './components/UpdateButton';

const DEFAULT_SAMPLE_TEXT = "The Quick Brown Fox Jumps Over The Lazy Dog 0123456789 &!";

function App() {
  const [instances, setInstances] = useState([]);
  const [axes, setAxes] = useState([]);
  const [selectedInstance, setSelectedInstance] = useState(null);
  const [editingCoordinates, setEditingCoordinates] = useState({});
  // Store editing coordinates per instance to persist when deselected
  const [instanceEditingCoordinates, setInstanceEditingCoordinates] = useState({});
  const [fontLoaded, setFontLoaded] = useState(false);
  const [fontUrl, setFontUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [building, setBuilding] = useState(false);
  const [sampleText, setSampleText] = useState(DEFAULT_SAMPLE_TEXT);
  const [fontSize, setFontSize] = useState(2); // Default 2rem
  const [familyName, setFamilyName] = useState(null);
  const [lastBuildTime, setLastBuildTime] = useState(null);
  const [avar2Mode, setAvar2Mode] = useState(false);
  const [avar2Instances, setAvar2Instances] = useState([]);
  const [avar2Axes, setAvar2Axes] = useState(null);
  const [spacMode, setSpacMode] = useState(false);
  const [spacAxisExists, setSpacAxisExists] = useState(false);
  const [spacValues, setSpacValues] = useState({}); // { instanceName: SPAC_value }
  const [spacBuilding, setSpacBuilding] = useState(false);
  const [spacError, setSpacError] = useState(null);

  // Load initial data
  useEffect(() => {
    loadData();
    // Preload avar2 data so it's ready when toggled
    loadAvar2Data().catch(() => {
      // Silently fail - avar2 is optional
    });
    // Check SPAC axis status and load values
    checkSpacAxisStatus();
    loadSpacValues();
  }, []);

  // Load avar2 data when mode is enabled (if not already loaded)
  useEffect(() => {
    if (avar2Mode) {
      // Only reload if we don't have data yet
      if (avar2Instances.length === 0 && !avar2Axes) {
        loadAvar2Data();
      }
    } else {
      // Keep data in memory but don't display it
      // This allows instant toggle back without reloading
    }
  }, [avar2Mode]);

  // Ensure selected instance is in CSV when avar2 mode is enabled
  useEffect(() => {
    if (avar2Mode && selectedInstance && avar2Instances.length > 0) {
      const mapping = avar2Instances.find(
        inst => inst.instance_name === selectedInstance.name
      );
      // If instance not in CSV, it will be added automatically by backend
      // when we fetch avar2 instances (backend handles missing instances)
      if (!mapping || mapping.match_status === 'missing_in_csv') {
        // Reload avar2 data to get updated CSV
        loadAvar2Data();
      }
    }
  }, [avar2Mode, selectedInstance, avar2Instances.length]);

  // Poll for font rebuilds (check every 2 seconds)
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const health = await api.health();
        setBuilding(health.building || false);
        
        // If font was rebuilt (new build time), reload
        if (health.font_built && health.last_build_time && health.last_build_time !== lastBuildTime) {
          setLastBuildTime(health.last_build_time);
          // Force font reload by generating new URL with timestamp
          setFontLoaded(false); // Reset first to trigger reload
          setTimeout(() => {
            setFontUrl(api.getFontUrl()); // New URL with fresh timestamp
            setFontLoaded(true);
          }, 100);
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

  const loadAvar2Data = async () => {
    try {
      // Load both in parallel, but update state as soon as each arrives
      const instancesPromise = api.getAvar2Instances().then(data => {
        setAvar2Instances(data.instances || []);
        return data;
      });
      
      const axesPromise = api.getAvar2Axes().then(data => {
        setAvar2Axes(data);
        return data;
      });
      
      // Wait for both to complete (but state updates happen immediately)
      await Promise.all([instancesPromise, axesPromise]);
    } catch (err) {
      console.error('Failed to load avar2 data:', err);
      // Don't show error to user - avar2 mode is optional
      setAvar2Instances([]);
      setAvar2Axes(null);
    }
  };

  const handleAddAvar2Axis = async (axisData) => {
    try {
      const result = await api.addAvar2Axis(axisData);
      console.log('Axis added successfully:', result);
      // Reload avar2 data to get updated axes and instances
      // Add a small delay to ensure backend has written files
      await new Promise(resolve => setTimeout(resolve, 300));
      await loadAvar2Data();
      console.log('Avar2 data reloaded after adding axis');
    } catch (err) {
      console.error('Failed to add axis:', err);
      throw err; // Re-throw to let modal handle error display
    }
  };

  const handleUpdateAvar2Axis = async (axisName, axisData) => {
    try {
      await api.updateAvar2Axis(axisName, axisData);
      // Reload avar2 data to get updated metadata
      await loadAvar2Data();
    } catch (err) {
      console.error('Failed to update axis:', err);
      throw err; // Re-throw to let component handle error display
    }
  };

  const handleUpdateAvar2Mapping = async (instanceName, axisName, value) => {
    try {
      await api.updateAvar2Mapping(instanceName, axisName, value);
      // Reload avar2 data to get updated instances
      await loadAvar2Data();
    } catch (err) {
      console.error('Failed to update mapping:', err);
      // Check if it's an external edit error
      if (err.message && err.message.includes('externally')) {
        // Reload data and show error
        await loadAvar2Data();
      }
      throw err; // Re-throw to let component handle error display
    }
  };

  const checkSpacAxisStatus = async () => {
    try {
      const result = await api.checkSpacAxis();
      setSpacAxisExists(result.exists || false);
    } catch (err) {
      console.error('Failed to check SPAC axis:', err);
      setSpacAxisExists(false);
    }
  };

  const loadSpacValues = async () => {
    try {
      const result = await api.getSpacValues();
      const valuesMap = {};
      if (result.values) {
        result.values.forEach(v => {
          valuesMap[v.instance_name] = v.spac || 0;
        });
      }
      setSpacValues(valuesMap);
    } catch (err) {
      console.error('Failed to load SPAC values:', err);
      // Don't show error - SPAC is optional
    }
  };

  const handleSpacModeChange = async (enabled) => {
    setSpacError(null);
    
    if (enabled) {
      // If SPAC axis doesn't exist, initialize and rebuild
      if (!spacAxisExists) {
        try {
          setSpacMode(true);
          setSpacBuilding(true);
          await api.initSpacAxis();
          await handleSpacRebuild();
          await checkSpacAxisStatus();
          await loadSpacValues();
          // Switch to preview font URL when SPAC mode is enabled
          setFontUrl(api.getPreviewFontUrl());
          setFontLoaded(true);
        } catch (err) {
          console.error('Failed to initialize SPAC axis:', err);
          setSpacError(err.message || 'Failed to initialize SPAC axis');
          setSpacMode(false); // Revert toggle on error
        } finally {
          setSpacBuilding(false);
        }
      } else {
        // SPAC axis exists, enable mode and load values
        setSpacMode(true);
        await loadSpacValues();
        // Switch to preview font URL when SPAC mode is enabled
        setFontUrl(api.getPreviewFontUrl());
        setFontLoaded(true);
      }
    } else {
      // Disable SPAC mode - switch back to regular font
      setSpacMode(false);
      setFontUrl(api.getFontUrl());
      setFontLoaded(true);
    }
  };

  const handleSpacRebuild = async () => {
    if (spacBuilding) return; // Prevent concurrent rebuilds
    
    setSpacBuilding(true);
    setSpacError(null);
    try {
      await api.rebuildPreviewFont();
      // Reload font URL to get updated preview font (with SPAC axis)
      const newFontUrl = api.getPreviewFontUrl();
      setFontUrl(newFontUrl);
      setFontLoaded(true);
      await checkSpacAxisStatus();
    } catch (err) {
      console.error('Failed to rebuild preview font:', err);
      setSpacError(err.message || 'Failed to rebuild preview font');
      throw err; // Re-throw to allow retry
    } finally {
      setSpacBuilding(false);
    }
  };

  const handleSpacChange = async (value) => {
    if (!selectedInstance) return;
    
    try {
      setSpacError(null);
      // Update local state immediately for responsive UI
      setSpacValues(prev => ({ ...prev, [selectedInstance.name]: value }));
      
      // Update backend
      await api.updateSpacValue(selectedInstance.name, value);
      
      // Trigger rebuild for accurate preview (if SPAC axis exists)
      if (spacAxisExists) {
        await handleSpacRebuild();
      }
    } catch (err) {
      console.error('Failed to update SPAC value:', err);
      // Revert on error
      const previousValue = spacValues[selectedInstance.name] || 0;
      setSpacValues(prev => ({ ...prev, [selectedInstance.name]: previousValue }));
      setSpacError(err.message || 'Failed to update spacing');
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
    // If clicking the same instance, don't reset coordinates
    if (selectedInstance && selectedInstance.name === instance.name) {
      return; // Already selected, keep current editing coordinates
    }
    
    // Save current editing coordinates for the previously selected instance
    if (selectedInstance) {
      setInstanceEditingCoordinates(prev => ({
        ...prev,
        [selectedInstance.name]: { ...editingCoordinates }
      }));
    }
    
    setSelectedInstance(instance);
    
    // Restore editing coordinates for this instance if they exist, otherwise use instance coordinates
    const savedCoordinates = instanceEditingCoordinates[instance.name];
    if (savedCoordinates) {
      setEditingCoordinates({ ...savedCoordinates });
    } else {
      setEditingCoordinates({ ...instance.coordinates });
    }
    
    // Store original coordinates for reset
    setOriginalCoordinates({ ...instance.coordinates });
  }, [selectedInstance, editingCoordinates, instanceEditingCoordinates]);

  const handleAxisChange = useCallback((tag, value) => {
    setEditingCoordinates(prev => {
      const updated = {
        ...prev,
        [tag]: value,
      };
      // Also update the stored coordinates for the current instance
      if (selectedInstance) {
        setInstanceEditingCoordinates(prevStored => ({
          ...prevStored,
          [selectedInstance.name]: updated
        }));
      }
      return updated;
    });
  }, [selectedInstance]);

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

  const handleDuplicateInstance = async (newInstanceName) => {
    if (!selectedInstance) return;

    try {
      setError(null);
      
      // Use current editing coordinates (if adjusted) or original instance coordinates
      const coordinatesToUse = Object.keys(editingCoordinates).length > 0 && 
        JSON.stringify(editingCoordinates) !== JSON.stringify(originalCoordinates)
        ? editingCoordinates
        : selectedInstance.coordinates;
      
      // Create new instance, inserting after the selected instance
      await api.createInstance(newInstanceName, coordinatesToUse, selectedInstance.name);
      
      // Reload instances to get the new one
      const instancesData = await api.getInstances();
      setInstances(instancesData.instances);
      
      // Find and select the new instance
      const newInstance = instancesData.instances.find(
        inst => inst.name === newInstanceName
      );
      
      if (newInstance) {
        setSelectedInstance(newInstance);
        setEditingCoordinates({ ...newInstance.coordinates });
        setOriginalCoordinates({ ...newInstance.coordinates });
        
        // Scroll to new instance after a brief delay (it should be right below the selected one)
        setTimeout(() => {
          const element = document.querySelector(`[data-instance-name="${newInstanceName}"]`);
          if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }
        }, 100);
      }
      
      // Auto-rebuild font after creation
      await handleBuildFont();
    } catch (err) {
      setError(err.message);
      console.error('Duplicate failed:', err);
    }
  };

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
        avar2Mode={avar2Mode}
        onAvar2ModeChange={setAvar2Mode}
        spacMode={spacMode}
        onSpacModeChange={handleSpacModeChange}
        spacBuilding={spacBuilding}
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
          onDuplicateInstance={handleDuplicateInstance}
          avar2Mode={avar2Mode}
          avar2Instances={avar2Instances}
          avar2Axes={avar2Axes}
          onAddAvar2Axis={handleAddAvar2Axis}
          onUpdateAvar2Axis={handleUpdateAvar2Axis}
          onUpdateAvar2Mapping={handleUpdateAvar2Mapping}
          onReloadAvar2Data={loadAvar2Data}
          spacMode={spacMode}
          spacAxisExists={spacAxisExists}
          spacValue={selectedInstance ? (spacValues[selectedInstance.name] || 0) : 0}
          onSpacChange={handleSpacChange}
          spacBuilding={spacBuilding}
          spacError={spacError}
          onSpacRetry={handleSpacRebuild}
        />
        
        <div className="content-area">
          <InstanceRows
            instances={instances}
            selectedInstance={selectedInstance}
            onSelectInstance={handleSelectInstance}
            editingCoordinates={editingCoordinates}
            instanceEditingCoordinates={instanceEditingCoordinates}
            sampleText={sampleText}
            fontUrl={fontUrl}
            spacMode={spacMode}
            spacAxisExists={spacAxisExists}
            spacValues={spacValues}
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
