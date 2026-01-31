import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import { api } from './api';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import InstanceRows from './components/InstanceRows';
import BuildAvar2Modal from './components/BuildAvar2Modal';
import Avar2Preview from './components/Avar2Preview';

const DEFAULT_SAMPLE_TEXT = "The Quick Brown Fox Jumps Over The Lazy Dog 0123456789 &!";

function App() {
  const [instances, setInstances] = useState([]);
  const [axes, setAxes] = useState([]);
  const [selectedInstance, setSelectedInstance] = useState(null);
  const [editingCoordinates, setEditingCoordinates] = useState({});
  // Store editing coordinates per instance to persist when deselected
  const [instanceEditingCoordinates, setInstanceEditingCoordinates] = useState({});
  // Store original coordinates per instance for sync status comparison
  const [instanceOriginalCoordinates, setInstanceOriginalCoordinates] = useState({});
  const [fontLoaded, setFontLoaded] = useState(false);
  const [fontUrl, setFontUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [building, setBuilding] = useState(false);
  const [sampleText, setSampleText] = useState(DEFAULT_SAMPLE_TEXT);
  const [fontSize, setFontSize] = useState(2); // Default 2rem
  const [familyName, setFamilyName] = useState(null);
  const [lastBuildTime, setLastBuildTime] = useState(null);
  // avar2Mode is now always true when avar2 data exists (no toggle needed)
  const [avar2Mode] = useState(true);
  const [avar2Instances, setAvar2Instances] = useState([]);
  const [avar2Axes, setAvar2Axes] = useState(null);
  const [spacMode, setSpacMode] = useState(false);
  const [spacAxisExists, setSpacAxisExists] = useState(false);
  const [spacValues, setSpacValues] = useState({}); // { instanceName: SPAC_value } - kept for loading from CSV
  const [spacBuilding, setSpacBuilding] = useState(false);
  const [glyphsFileHasUnsavedChanges, setGlyphsFileHasUnsavedChanges] = useState(false);
  const [avar2PreviewMode, setAvar2PreviewMode] = useState(false); // New mode: Default vs Avar2 Preview
  const [syncStatus, setSyncStatus] = useState(null);
  const [showBuildAvar2Modal, setShowBuildAvar2Modal] = useState(false);
  const [avar2FontUrl, setAvar2FontUrl] = useState(null);
  const [avar2FontLoaded, setAvar2FontLoaded] = useState(false);

  // Load initial data
  useEffect(() => {
    loadData();
    // Preload avar2 data so it's ready when toggled
    loadAvar2Data().catch(() => {
      // Silently fail - avar2 is optional
    });
    // Check sync status
    checkSyncStatus();
    // Check SPAC axis status and enable mode if axis exists
    checkSpacAxisStatus().then((exists) => {
      if (exists) {
        // SPAC axis exists - enable mode by default and load values
        setSpacMode(true);
        // checkSpacAxisStatus already adds the axis to the axes array
        loadSpacValues();
        // Use main font URL (serves designspace font from preview-fonts/spac)
        setFontUrl(api.getFontUrl());
        setFontLoaded(true);
      }
    }).catch(() => {
      // Silently fail - SPAC is optional
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Intentionally empty - only run on mount
  
  // Unregister instance when deselected or component unmounts
  useEffect(() => {
    const currentInstance = selectedInstance;
    return () => {
      // Cleanup: unregister instance when deselected or component unmounts
      if (currentInstance) {
        api.unregisterEditingInstance(currentInstance.name).catch(() => {});
      }
    };
  }, [selectedInstance]);

  // Load avar2 data on mount (always enabled now)
  useEffect(() => {
    // Load avar2 data if not already loaded
    if (avar2Instances.length === 0 && !avar2Axes) {
      loadAvar2Data();
    }
  }, [avar2Instances.length, avar2Axes]); // eslint-disable-line react-hooks/exhaustive-deps

  // Ensure selected instance is in CSV when avar2 data exists (avar2Mode always enabled now)
  useEffect(() => {
    if (selectedInstance && avar2Instances.length > 0) {
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
  }, [selectedInstance, avar2Instances]); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll for font rebuilds and Glyphs file unsaved changes (check every 2 seconds)
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const [health, glyphsStatus] = await Promise.all([
          api.health(),
          api.glyphsFileStatus().catch(() => ({ has_unsaved_changes: false }))
        ]);
        
        setBuilding(health.building || false);
        setGlyphsFileHasUnsavedChanges(glyphsStatus.has_unsaved_changes || false);
        
        // If font was rebuilt (new build time), reload
        if (health.font_built && health.last_build_time && health.last_build_time !== lastBuildTime) {
          // Store scroll position before reloading
          const scrollY = window.scrollY;
          const selectedInstanceName = selectedInstance?.name;
          
          setLastBuildTime(health.last_build_time);
          // Force font reload by generating new URL with timestamp
          setFontLoaded(false); // Reset first to trigger reload
          setTimeout(() => {
            setFontUrl(api.getFontUrl()); // New URL with fresh timestamp
            setFontLoaded(true);
          }, 100);
          // Reload instances and axes in case they changed
          const [instancesData, axesData, spacExists] = await Promise.all([
            api.getInstances(),
            api.getAxes(),
            checkSpacAxisStatus().catch(() => false),
          ]);
          setInstances(instancesData.instances);
          
          // Add SPAC to axes if it exists and spacMode is enabled
          let axesList = axesData.axes || [];
          if (spacExists && spacMode) {
            const hasSpac = axesList.some(axis => axis.tag === 'SPAC' || axis.tag === 'spac');
            if (!hasSpac) {
              axesList = [...axesList, {
                tag: 'SPAC',
                name: 'Spacing',
                min: 0,
                max: 100,
                default: 0
              }];
            }
          }
          setAxes(axesList);
          
          // Restore scroll position after a brief delay
          if (selectedInstanceName) {
            setTimeout(() => {
              const element = document.querySelector(`[data-instance-name="${selectedInstanceName}"]`);
              if (element) {
                element.scrollIntoView({ behavior: 'auto', block: 'nearest' });
              } else {
                // Fallback to stored scroll position
                window.scrollTo(0, scrollY);
              }
            }, 200);
          }
        }
      } catch (err) {
        // Silently fail polling errors
        console.debug('Polling error:', err);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(interval);
  }, [lastBuildTime, selectedInstance?.name, spacMode]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Check health and font status
      const health = await api.health();
      
      // If font is not built, trigger auto-build on hard reset
      if (!health.font_built && !health.building) {
        console.log('Font not built, triggering auto-build...');
        try {
          await api.buildFont();
          // Reload health to get updated status
          const updatedHealth = await api.health();
          setFontLoaded(updatedHealth.font_built);
          setLastBuildTime(updatedHealth.last_build_time || null);
        } catch (err) {
          console.error('Auto-build on load failed:', err);
          // Continue loading even if build fails
        }
      }
      
      // Load instances and axes, and check SPAC status in parallel
      const [instancesData, axesData, spacExists] = await Promise.all([
        api.getInstances(),
        api.getAxes(),
        checkSpacAxisStatus().catch(() => false), // Don't fail if SPAC check fails
      ]);

      setInstances(instancesData.instances);
      
      // Check if SPAC axis exists and add it to axes if present
      let axesList = axesData.axes || [];
      if (spacExists) {
        // Enable SPAC mode by default when axis exists
        setSpacMode(true);
        // Load SPAC values
        loadSpacValues();
        // Use main font URL (serves designspace font from preview-fonts/spac)
        setFontUrl(api.getFontUrl());
        setFontLoaded(true);
        
        // SPAC axis will be added with correct range from checkSpacAxisStatus
        // But ensure it's added here if not already present with correct range (0-100)
        const hasSpac = axesList.some(axis => axis.tag === 'SPAC' || axis.tag === 'spac');
        if (!hasSpac) {
          // Add SPAC axis temporarily - checkSpacAxisStatus will update with correct range
          // Use correct range (0-100) to match designspace, not -100 to 100
          axesList = [...axesList, {
            tag: 'SPAC',
            name: 'Spacing',
            min: 0,
            max: 100,
            default: 0
          }];
        }
      }
      
      setAxes(axesList);
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
      
      // avar2Mode is always enabled, no need to set it
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
      const exists = result.exists || false;
      setSpacAxisExists(exists);
      
      // Always add/update SPAC axis in axes array when axis exists OR when spacMode is enabled
      // This ensures the slider appears when the axis exists or when mode is enabled
      setAxes(prev => {
        const hasSpac = prev.some(axis => axis.tag === 'SPAC' || axis.tag === 'spac');
        if (exists && result.range) {
          // Update or add SPAC axis with font range
          const spacRange = result.range;
          if (hasSpac) {
            // Update existing SPAC axis with font range
            return prev.map(axis => 
              (axis.tag === 'SPAC' || axis.tag === 'spac') 
                ? { ...axis, min: spacRange.min, max: spacRange.max, default: spacRange.default }
                : axis
            );
          } else {
            // Add SPAC axis with font range
            return [...prev, {
              tag: 'SPAC',
              name: 'Spacing',
              min: spacRange.min,
              max: spacRange.max,
              default: spacRange.default || 0
            }];
          }
        } else if (exists) {
          // Axis exists but no range info - use default range (0-100)
          if (!hasSpac) {
            return [...prev, {
              tag: 'SPAC',
              name: 'Spacing',
              min: 0,
              max: 100,
              default: 0
            }];
          }
        } else if (spacMode && !hasSpac) {
          // spacMode is enabled but axis doesn't exist yet - add placeholder
          return [...prev, {
            tag: 'SPAC',
            name: 'Spacing',
            min: 0,
            max: 100,
            default: 0
          }];
        }
        return prev;
      });
      
      return exists; // Return boolean for use in initialization
    } catch (err) {
      console.error('Failed to check SPAC axis:', err);
      setSpacAxisExists(false);
      // Still add SPAC axis if spacMode is enabled
      if (spacMode) {
        setAxes(prev => {
          const hasSpac = prev.some(axis => axis.tag === 'SPAC' || axis.tag === 'spac');
          if (!hasSpac) {
            return [...prev, {
              tag: 'SPAC',
              name: 'Spacing',
              min: 0,
              max: 100,
              default: 0
            }];
          }
          return prev;
        });
      }
      return false;
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
      
      // Add SPAC values to editingCoordinates if spacMode is enabled and instance is selected
      if (spacMode && selectedInstance && valuesMap[selectedInstance.name] !== undefined) {
        const spacValue = valuesMap[selectedInstance.name] || 0;
        setEditingCoordinates(prev => ({ ...prev, SPAC: spacValue }));
        setOriginalCoordinates(prev => ({ ...prev, SPAC: spacValue }));
      }
    } catch (err) {
      console.error('Failed to load SPAC values:', err);
      // Don't show error - SPAC is optional
    }
  };

  const handleSpacModeChange = async (enabled) => {
    // Error handling now via setError
    
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
          // Use main font URL (serves designspace font from preview-fonts/spac)
          setFontUrl(api.getFontUrl());
          setFontLoaded(true);
        // SPAC axis will be added with correct range from checkSpacAxisStatus
        // No need to add here with hardcoded values
        } catch (err) {
          console.error('Failed to initialize SPAC axis:', err);
          setError(err.message || 'Failed to initialize SPAC axis');
          setSpacMode(false); // Revert toggle on error
        } finally {
          setSpacBuilding(false);
        }
      } else {
        // SPAC axis exists, enable mode and load values
        setSpacMode(true);
        await loadSpacValues();
        // Use main font URL (serves designspace font from preview-fonts/spac)
        setFontUrl(api.getFontUrl());
        setFontLoaded(true);
        // Ensure SPAC axis is added to axes array
        await checkSpacAxisStatus();
      }
    } else {
      // Disable SPAC mode - still use main font URL (which serves designspace font)
      setSpacMode(false);
      setFontUrl(api.getFontUrl());
      setFontLoaded(true);
      // Remove SPAC from axes list
      setAxes(prev => prev.filter(axis => axis.tag !== 'SPAC' && axis.tag !== 'spac'));
    }
  };

  const checkSyncStatus = async () => {
    try {
      const status = await api.checkSyncStatus();
      setSyncStatus(status);
    } catch (err) {
      console.error('Failed to check sync status:', err);
      setSyncStatus({ synced: false, message: 'Failed to check sync status' });
    }
  };

  const handleBuildAvar2Font = async ({ traditionalAxes, avar2Axes, includeSpac }) => {
    try {
      setBuilding(true);
      setError(null);
      
      const result = await api.buildAvar2Font(traditionalAxes, avar2Axes, includeSpac);
      
      // Update sync status from response
      if (result.sync_status) {
        setSyncStatus(result.sync_status);
      }
      
      // If in avar2 preview mode, load the font
      // Also auto-switch to avar2 preview mode after successful build
      if (!avar2PreviewMode) {
        setAvar2PreviewMode(true);
      }
      
      const fontUrl = api.getAvar2FontUrl();
      setAvar2FontUrl(fontUrl);
      setAvar2FontLoaded(true);
      
      // Load font using FontFace API
      try {
        // Remove old font if it exists to force reload
        const oldFont = Array.from(document.fonts).find(f => f.family === 'Crispy-VF');
        if (oldFont) {
          document.fonts.delete(oldFont);
        }
        
        const fontFace = new FontFace('Crispy-VF', `url(${fontUrl})`);
        await fontFace.load();
        document.fonts.add(fontFace);
        await document.fonts.ready;
      } catch (err) {
        console.error('Failed to load avar2 font:', err);
      }
      
      // Show success message (could be a toast notification)
      console.log('Avar2 font built successfully:', result.font_path);
      
      return result;
    } catch (err) {
      setError(err.message || 'Failed to build avar2 font');
      throw err;
    } finally {
      setBuilding(false);
    }
  };

  const handleAvar2PreviewModeChange = async (enabled) => {
    setAvar2PreviewMode(enabled);
    
    if (enabled) {
      // Switch to Avar2 Preview mode
      // Load avar2 data if not already loaded
      if (avar2Instances.length === 0 || !avar2Axes) {
        await loadAvar2Data();
      }
      
      // Load avar2 font if it exists
      try {
        const fontUrl = api.getAvar2FontUrl();
        // Try to load font to check if it exists
        const response = await fetch(fontUrl);
        if (response.ok) {
          setAvar2FontUrl(fontUrl);
          setAvar2FontLoaded(true);
          
          // Load font using FontFace API
          const fontFace = new FontFace('Crispy-VF', `url(${fontUrl})`);
          await fontFace.load();
          document.fonts.add(fontFace);
          await document.fonts.ready;
        } else {
          // Font doesn't exist yet, user needs to build it
          setAvar2FontLoaded(false);
        }
      } catch (err) {
        // Font doesn't exist yet
        setAvar2FontLoaded(false);
      }
    } else {
      // Switch back to Default mode
      // Use main font URL (serves designspace font from preview-fonts/spac)
      setFontUrl(api.getFontUrl());
      setAvar2FontUrl(null);
      setAvar2FontLoaded(false);
    }
  };

  const handleSpacRebuild = async () => {
    if (spacBuilding) return; // Prevent concurrent rebuilds
    
    setSpacBuilding(true);
    // Error handling now via setError
    try {
      await api.rebuildPreviewFont();
      // Reload font URL to get updated designspace font (with SPAC axis)
      const newFontUrl = api.getFontUrl();
      setFontUrl(newFontUrl);
      setFontLoaded(true);
      await checkSpacAxisStatus();
    } catch (err) {
      console.error('Failed to rebuild preview font:', err);
      setError(err.message || 'Failed to rebuild preview font');
      throw err; // Re-throw to allow retry
    } finally {
      setSpacBuilding(false);
    }
  };

  // handleSpacChange and handleSpacApply removed - SPAC now handled via handleAxisChange

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

  // Calculate sync status for an instance
  // Checks both parametric axes (in editingCoordinates) and SPAC (if spacMode is enabled)
  const getInstanceSyncStatus = useCallback((instance) => {
    // For selected instance, compare editingCoordinates with originalCoordinates
    if (selectedInstance && selectedInstance.name === instance.name) {
      // If originalCoordinates is empty, consider it synced (initial state)
      if (!originalCoordinates || Object.keys(originalCoordinates).length === 0) {
        return 'green';
      }
      // Compare all coordinates including SPAC if present
      const isSynced = JSON.stringify(editingCoordinates) === JSON.stringify(originalCoordinates);
      if (!isSynced) {
        return 'orange'; // Edited but not saved (either parametric axes or SPAC changed)
      }
      return 'green'; // Synced
    }
    
    // For other instances, compare instanceEditingCoordinates with saved originalCoordinates
    const savedCoordinates = instanceEditingCoordinates[instance.name];
    const savedOriginalCoords = instanceOriginalCoordinates[instance.name];
    
    if (savedCoordinates && Object.keys(savedCoordinates).length > 0) {
      // Use saved originalCoordinates if available, otherwise build from instance.coordinates
      let comparisonCoords;
      if (savedOriginalCoords && Object.keys(savedOriginalCoords).length > 0) {
        comparisonCoords = savedOriginalCoords;
      } else {
        // Build comparison object including SPAC if spacMode is enabled
        comparisonCoords = { ...instance.coordinates };
        if (spacMode && spacValues[instance.name] !== undefined) {
          comparisonCoords.SPAC = spacValues[instance.name];
        }
      }
      const isSynced = JSON.stringify(savedCoordinates) === JSON.stringify(comparisonCoords);
      if (!isSynced) {
        return 'orange'; // Edited but not saved
      }
    }
    return 'green'; // Synced (default: no edits)
  }, [selectedInstance, editingCoordinates, originalCoordinates, instanceEditingCoordinates, instanceOriginalCoordinates, spacMode, spacValues]);

  const handleSelectInstance = useCallback((instance) => {
    // If clicking the same instance, don't reset coordinates
    if (selectedInstance && selectedInstance.name === instance.name) {
      return; // Already selected, keep current editing coordinates
    }
    
    // Save current editing coordinates for the previously selected instance
    // Also save the originalCoordinates so getInstanceSyncStatus can compare correctly
    if (selectedInstance && Object.keys(editingCoordinates).length > 0) {
      setInstanceEditingCoordinates(prev => ({
        ...prev,
        [selectedInstance.name]: { ...editingCoordinates }
      }));
      // Also save originalCoordinates for this instance so sync status works correctly
      // We need to store this per-instance so getInstanceSyncStatus can compare
      setInstanceOriginalCoordinates(prev => ({
        ...prev,
        [selectedInstance.name]: { ...originalCoordinates }
      }));
    }
    
    setSelectedInstance(instance);
    
    // Restore editing coordinates for this instance if they exist, otherwise use instance coordinates
    const savedCoordinates = instanceEditingCoordinates[instance.name];
    if (savedCoordinates) {
      setEditingCoordinates({ ...savedCoordinates });
    } else {
      // Include SPAC in editingCoordinates if spacMode is enabled
      const coords = { ...instance.coordinates };
      if (spacMode) {
        const currentSpacValue = spacValues[instance.name] || 0;
        coords.SPAC = currentSpacValue;
      }
      setEditingCoordinates(coords);
    }
    
    // Store original coordinates for reset (include SPAC if spacMode is enabled)
    // Check if we have saved originalCoordinates for this instance first
    const savedOriginalCoords = instanceOriginalCoordinates[instance.name];
    if (savedOriginalCoords) {
      setOriginalCoordinates(savedOriginalCoords);
    } else {
      const originalCoords = { ...instance.coordinates };
      if (spacMode) {
        const spacValue = spacValues[instance.name] || 0;
        originalCoords.SPAC = spacValue;
      }
      setOriginalCoordinates(originalCoords);
    }
  }, [selectedInstance, editingCoordinates, instanceEditingCoordinates, instanceOriginalCoordinates, originalCoordinates, spacValues, spacMode]);

  const handleAxisChange = useCallback((tag, value) => {
    // Register instance as editing when first axis change happens
    if (selectedInstance && Object.keys(editingCoordinates).length === 0) {
      api.registerEditingInstance(selectedInstance.name).catch(() => {});
    }
    
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
      // If SPAC changed, also update spacValues for real-time preview
      if (tag === 'SPAC' && spacMode) {
        setSpacValues(prev => ({ ...prev, [selectedInstance.name]: value }));
      }
      return updated;
    });
  }, [selectedInstance, editingCoordinates, spacMode]);

  // Helper function to wait for font to be loaded and ready
  const waitForFontReady = async (maxAttempts = 50, delayMs = 100) => {
    for (let i = 0; i < maxAttempts; i++) {
      // Check if font is loaded by checking document.fonts
      if (document.fonts && document.fonts.check('12px "Crispy-VF"')) {
        // Also wait for fonts.ready to ensure font is fully ready
        await document.fonts.ready;
        return true;
      }
      await new Promise(resolve => setTimeout(resolve, delayMs));
    }
    return false; // Timeout - font might not be ready, but proceed anyway
  };

  // Helper function to update a specific instance by name
  const updateInstanceByName = async (instanceName, coordinatesToUse) => {
    // Extract SPAC from coordinates (SPAC is CSV-only, not in Glyphs)
    const spacValue = coordinatesToUse.SPAC;
    const parametricCoordinates = { ...coordinatesToUse };
    delete parametricCoordinates.SPAC; // Remove SPAC - backend handles it separately
    
    // Get the instance to check original coordinates
    const instance = instances.find(inst => inst.name === instanceName);
    if (!instance) {
      throw new Error(`Instance "${instanceName}" not found`);
    }
    
    // Build original coordinates for comparison (including SPAC if in spacValues)
    const originalCoords = { ...instance.coordinates };
    if (spacMode && spacValues[instanceName] !== undefined) {
      originalCoords.SPAC = spacValues[instanceName];
    }
    
    // Check if parametric axes changed (for Glyphs update)
    const parametricChanged = Object.keys(parametricCoordinates).some(
      key => Math.abs((parametricCoordinates[key] ?? 0) - (originalCoords[key] ?? 0)) > 0.01
    );
    
    // Send all coordinates to backend - it will handle SPAC (CSV) and parametric axes (Glyphs) separately
    await api.updateInstance(instanceName, coordinatesToUse);
    
    // Update spacValues state if SPAC was included
    if (spacMode && spacValue !== undefined) {
      setSpacValues(prev => ({ ...prev, [instanceName]: spacValue }));
    }
    
    // Reload instances to get updated data (if Glyphs was updated)
    if (parametricChanged) {
      const instancesData = await api.getInstances();
      setInstances(instancesData.instances);
      
      // Update selected instance if this was the selected one
      if (selectedInstance && selectedInstance.name === instanceName) {
        const updated = instancesData.instances.find(
          inst => inst.name === instanceName
        );
        if (updated) {
          setSelectedInstance(updated);
          // Restore editing coordinates with updated values (including SPAC)
          const updatedCoords = { ...updated.coordinates };
          if (spacMode && spacValue !== undefined) {
            updatedCoords.SPAC = spacValue;
          }
          setEditingCoordinates(updatedCoords);
          setOriginalCoordinates(updatedCoords);
        }
      }
    } else {
      // No parametric changes, update instanceEditingCoordinates
      setInstanceEditingCoordinates(prev => ({
        ...prev,
        [instanceName]: { ...coordinatesToUse }
      }));
    }
    
    // Unregister instance from editing (we're saving, so sync is OK now)
    await api.unregisterEditingInstance(instanceName).catch(() => {});
  };

  const handleUpdateInstance = async (instanceName) => {
    // If instanceName is provided, update that specific instance (for flyout)
    // Otherwise, update the selected instance (for button)
    const targetInstanceName = instanceName || (selectedInstance?.name);
    if (!targetInstanceName) return;

    let coordinatesToUse;
    
    if (instanceName && instanceName !== selectedInstance?.name) {
      // Updating a different instance - use its saved editing coordinates
      coordinatesToUse = instanceEditingCoordinates[instanceName];
      if (!coordinatesToUse) {
        // No edits for this instance, nothing to update
        return;
      }
    } else {
      // Updating selected instance - use current editingCoordinates
      if (!selectedInstance) return;
      
      // Check if anything changed
      const hasChanges = JSON.stringify(editingCoordinates) !== JSON.stringify(originalCoordinates);
      if (!hasChanges) {
        return; // Nothing to update
      }
      
      coordinatesToUse = editingCoordinates;
    }

    // Extract SPAC from coordinates (SPAC is CSV-only, not in Glyphs)
    const spacValue = coordinatesToUse.SPAC;
    const parametricCoordinates = { ...coordinatesToUse };
    delete parametricCoordinates.SPAC; // Remove SPAC - backend handles it separately
    
    // Get the instance to check original coordinates
    const instance = instances.find(inst => inst.name === targetInstanceName);
    if (!instance) {
      setError(`Instance "${targetInstanceName}" not found`);
      return;
    }
    
    // Build original coordinates for comparison (including SPAC if in spacValues)
    const originalCoords = { ...instance.coordinates };
    if (spacMode && spacValues[targetInstanceName] !== undefined) {
      originalCoords.SPAC = spacValues[targetInstanceName];
    }
    
    // Check if parametric axes changed (for Glyphs update)
    const parametricChanged = Object.keys(parametricCoordinates).some(
      key => Math.abs((parametricCoordinates[key] ?? 0) - (originalCoords[key] ?? 0)) > 0.01
    );

    // Show confirmation dialog only for selected instance updates
    if (!instanceName || instanceName === selectedInstance?.name) {
      const confirmed = window.confirm(
        `Update instance "${targetInstanceName}"?\n\n` +
        (parametricChanged ? `This will modify the Glyphs file.\n` : '') +
        (spacMode && spacValue !== undefined ? `SPAC value will be saved to CSV.\n` : '')
      );

      if (!confirmed) return;
    }

    try {
      setError(null);
      
      await updateInstanceByName(targetInstanceName, coordinatesToUse);
      
      // Store instance name before rebuild (in case it changes)
      const instanceNameToScroll = targetInstanceName;
      
      // Backend already rebuilds the font (regular or SPAC) after instance update
      // Just wait for it to complete - no need to trigger another rebuild
      // The backend will regenerate SPAC font if it exists, or rebuild regular font otherwise
      
      // Backend rebuilds automatically after instance update
      // Wait for build to complete by polling health endpoint
      let buildComplete = false;
      let attempts = 0;
      const maxAttempts = 60; // 60 seconds max wait
      
      while (!buildComplete && attempts < maxAttempts) {
        try {
          const health = await api.health();
          if (!health.building) {
            buildComplete = true;
            break;
          }
        } catch (err) {
          // Ignore polling errors, continue waiting
        }
        await new Promise(resolve => setTimeout(resolve, 1000));
        attempts++;
      }
      
      // Reload font URL to get updated font (with timestamp to force reload)
      setFontUrl(api.getFontUrl());
      setFontLoaded(false);
      await new Promise(resolve => setTimeout(resolve, 500));
      setFontLoaded(true);
      
      // Wait for font to be loaded before scrolling
      await waitForFontReady();
      
      // Additional small delay to ensure DOM is updated after font load
      await new Promise(resolve => setTimeout(resolve, 200));
      
      // Scroll to updated instance after font is ready
      const element = document.querySelector(`[data-instance-name="${instanceNameToScroll}"]`);
      if (element) {
        // Use requestAnimationFrame to ensure DOM is ready
        requestAnimationFrame(() => {
          element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        });
      }
    } catch (err) {
      setError(err.message);
      console.error('Update failed:', err);
      throw err; // Re-throw for error handling in batch update
    }
  };

  const handleUpdateAllInstances = async () => {
    // Find all instances with unsaved changes (orange status)
    const instancesToUpdate = instances.filter(instance => {
      const status = getInstanceSyncStatus(instance);
      return status === 'orange';
    });

    if (instancesToUpdate.length === 0) {
      return; // Nothing to update
    }

    // Show confirmation
    const confirmed = window.confirm(
      `Update ${instancesToUpdate.length} instance${instancesToUpdate.length > 1 ? 's' : ''}?\n\n` +
      `This will save all unsaved changes and rebuild the font.`
    );

    if (!confirmed) return;

    try {
      setError(null);
      setBuilding(true); // Show loading state
      
      // Store original state for revert
      const originalInstances = [...instances];
      const originalInstanceEditingCoordinates = { ...instanceEditingCoordinates };
      const originalEditingCoordinates = { ...editingCoordinates };
      const originalOriginalCoordinates = { ...originalCoordinates };
      const originalSpacValues = { ...spacValues };
      const originalSelectedInstance = selectedInstance;
      
      const successfulUpdates = [];
      
      // Update each instance sequentially
      for (const instance of instancesToUpdate) {
        try {
          let coordinatesToUse;
          
          if (instance.name === selectedInstance?.name) {
            // Use current editingCoordinates for selected instance
            coordinatesToUse = editingCoordinates;
          } else {
            // Use saved editing coordinates for other instances
            coordinatesToUse = instanceEditingCoordinates[instance.name];
          }
          
          if (!coordinatesToUse) {
            continue; // Skip if no edits
          }
          
          await updateInstanceByName(instance.name, coordinatesToUse);
          successfulUpdates.push(instance.name);
        } catch (err) {
          // Revert all successful updates
          setInstances(originalInstances);
          setInstanceEditingCoordinates(originalInstanceEditingCoordinates);
          setEditingCoordinates(originalEditingCoordinates);
          setOriginalCoordinates(originalOriginalCoordinates);
          setSpacValues(originalSpacValues);
          setSelectedInstance(originalSelectedInstance);
          
          setError(`Failed to update instance "${instance.name}": ${err.message}. All changes have been reverted.`);
          console.error('Batch update failed:', err);
          setBuilding(false);
          return; // Stop on first error
        }
      }
      
      // All updates successful - wait for build to complete
      let buildComplete = false;
      let attempts = 0;
      const maxAttempts = 60; // 60 seconds max wait
      
      while (!buildComplete && attempts < maxAttempts) {
        try {
          const health = await api.health();
          if (!health.building) {
            buildComplete = true;
            break;
          }
        } catch (err) {
          // Ignore polling errors, continue waiting
        }
        await new Promise(resolve => setTimeout(resolve, 1000));
        attempts++;
      }
      
      // Reload font URL to get updated font (with timestamp to force reload)
      setFontUrl(api.getFontUrl());
      setFontLoaded(false);
      await new Promise(resolve => setTimeout(resolve, 500));
      setFontLoaded(true);
      
      // Wait for font to be loaded
      await waitForFontReady();
      
      setBuilding(false);
    } catch (err) {
      setError(err.message);
      console.error('Batch update failed:', err);
      setBuilding(false);
    }
  };

  const handleResetCoordinates = useCallback(() => {
    if (!selectedInstance) return;
    // Reset all coordinates including SPAC (SPAC is now in editingCoordinates)
    setEditingCoordinates({ ...originalCoordinates });
    // Also update spacValues for real-time preview if SPAC is in originalCoordinates
    if (spacMode && originalCoordinates.SPAC !== undefined) {
      setSpacValues(prev => ({ ...prev, [selectedInstance.name]: originalCoordinates.SPAC }));
    }
  }, [selectedInstance, originalCoordinates, spacMode]);

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
      
      if (!newInstance) {
        throw new Error(`Failed to find newly created instance "${newInstanceName}"`);
      }
      
      // Store instance name before rebuild (in case it changes)
      const instanceNameToScroll = newInstanceName;
      
      // Set up coordinates for the new instance (including SPAC if spacMode is enabled)
      const newCoords = { ...newInstance.coordinates };
      if (spacMode && coordinatesToUse.SPAC !== undefined) {
        newCoords.SPAC = coordinatesToUse.SPAC;
        // Update spacValues state
        setSpacValues(prev => ({ ...prev, [newInstanceName]: coordinatesToUse.SPAC }));
      }
      
      setSelectedInstance(newInstance);
      setEditingCoordinates(newCoords);
      setOriginalCoordinates(newCoords);
      
      // Backend rebuilds the font after instance creation
      // Wait for build to complete by polling health endpoint (same as update instance)
      let buildComplete = false;
      let attempts = 0;
      const maxAttempts = 60; // 60 seconds max wait
      
      while (!buildComplete && attempts < maxAttempts) {
        try {
          const health = await api.health();
          if (!health.building) {
            buildComplete = true;
            break;
          }
        } catch (err) {
          // Ignore polling errors, continue waiting
        }
        await new Promise(resolve => setTimeout(resolve, 1000));
        attempts++;
      }
      
      // Reload font URL to get updated font (with timestamp to force reload)
      setFontUrl(api.getFontUrl());
      setFontLoaded(false);
      await new Promise(resolve => setTimeout(resolve, 500));
      setFontLoaded(true);
      
      // Wait for font to be loaded before scrolling
      await waitForFontReady();
      
      // Additional small delay to ensure DOM is updated after font load
      await new Promise(resolve => setTimeout(resolve, 200));
      
      // Scroll to new instance after font is ready
      const element = document.querySelector(`[data-instance-name="${instanceNameToScroll}"]`);
      if (element) {
        // Use requestAnimationFrame to ensure DOM is ready
        requestAnimationFrame(() => {
          element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        });
      }
    } catch (err) {
      setError(err.message);
      console.error('Duplicate failed:', err);
    }
  };

  const handleRenameInstance = async (oldName, newName) => {
    if (!oldName || !newName || oldName === newName) {
      return;
    }

    try {
      setError(null);
      await api.renameInstance(oldName, newName);
      
      // Reload instances to get updated data
      const instancesData = await api.getInstances();
      setInstances(instancesData.instances);
      
      // Update selected instance if it was renamed
      if (selectedInstance && selectedInstance.name === oldName) {
        const renamed = instancesData.instances.find(
          inst => inst.name === newName
        );
        if (renamed) {
          setSelectedInstance(renamed);
          setEditingCoordinates({ ...renamed.coordinates });
          setOriginalCoordinates({ ...renamed.coordinates });
          
          // Scroll to renamed instance
          setTimeout(() => {
            const element = document.querySelector(`[data-instance-name="${newName}"]`);
            if (element) {
              element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
          }, 100);
        }
      }
      
      // Auto-rebuild font after rename
      await handleBuildFont();
    } catch (err) {
      setError(err.message);
      console.error('Rename failed:', err);
      throw err; // Re-throw to let component handle error display
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
        building={building}
        fontLoaded={fontLoaded}
        familyName={familyName}
        avar2PreviewMode={avar2PreviewMode}
        onAvar2PreviewModeChange={handleAvar2PreviewModeChange}
        onBuildAvar2Font={() => setShowBuildAvar2Modal(true)}
        spacMode={spacMode}
        onSpacModeChange={handleSpacModeChange}
        spacBuilding={spacBuilding}
      />
      
      <BuildAvar2Modal
        isOpen={showBuildAvar2Modal}
        onClose={() => setShowBuildAvar2Modal(false)}
        onBuild={handleBuildAvar2Font}
        syncStatus={syncStatus}
        avar2Axes={avar2Axes}
      />
      
      {error && (
        <div className="error-banner">
          Error: {error}
        </div>
      )}

      <div className="main-content">
        <div className="content-area">
          {avar2PreviewMode ? (
            <Avar2Preview
              avar2Instances={avar2Instances}
              avar2Axes={avar2Axes}
              fontUrl={avar2FontUrl}
              fontLoaded={avar2FontLoaded}
              sampleText={sampleText}
              onSampleTextChange={setSampleText}
              fontSize={fontSize}
              onFontSizeChange={setFontSize}
            />
          ) : (
            <>
              <Sidebar
                axes={axes}
                coordinates={editingCoordinates}
                onAxisChange={handleAxisChange}
                disabled={!selectedInstance}
                sampleText={sampleText}
                onSampleTextChange={setSampleText}
                selectedInstance={selectedInstance}
                onUpdateInstance={handleUpdateInstance}
                onUpdateAllInstances={handleUpdateAllInstances}
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
                glyphsFileHasUnsavedChanges={glyphsFileHasUnsavedChanges}
                getInstanceSyncStatus={getInstanceSyncStatus}
                instances={instances}
                building={building}
              />
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
                fontLoaded={fontLoaded}
                onReorderInstances={setInstances}
                fontSize={fontSize}
                onDeleteInstance={handleDeleteInstance}
                getInstanceSyncStatus={getInstanceSyncStatus}
                onMoveInstance={handleMoveInstance}
                onRenameInstance={handleRenameInstance}
                onUpdateInstance={handleUpdateInstance}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
