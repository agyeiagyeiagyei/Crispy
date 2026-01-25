/**
 * API client for Glyphs Preview Server
 */

// Use full backend URL in production, or proxy path in development
const API_BASE = process.env.REACT_APP_API_URL || 
  (process.env.NODE_ENV === 'production' ? 'http://localhost:5001/api' : '/api');

// Helper to parse JSON response with error handling
async function parseJSON(response) {
  const text = await response.text();
  if (!text) {
    throw new Error(`Empty response from server (status: ${response.status})`);
  }
  try {
    return JSON.parse(text);
  } catch (e) {
    throw new Error(`Invalid JSON response: ${text.substring(0, 100)}`);
  }
}

export const api = {
  async health() {
    const response = await fetch(`${API_BASE}/health`);
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.status} ${response.statusText}`);
    }
    return parseJSON(response);
  },

  async getInstances() {
    const response = await fetch(`${API_BASE}/instances`);
    if (!response.ok) {
      throw new Error(`Failed to fetch instances: ${response.status} ${response.statusText}`);
    }
    return parseJSON(response);
  },

  async getAxes() {
    const response = await fetch(`${API_BASE}/axes`);
    if (!response.ok) {
      throw new Error(`Failed to fetch axes: ${response.status} ${response.statusText}`);
    }
    return parseJSON(response);
  },

  async buildFont() {
    const response = await fetch(`${API_BASE}/build`, {
      method: 'POST',
    });
    if (!response.ok) {
      try {
        const error = await parseJSON(response);
        throw new Error(error.error || 'Build failed');
      } catch (e) {
        throw new Error(`Build failed: ${response.status} ${response.statusText}`);
      }
    }
    return parseJSON(response);
  },

  getFontUrl() {
    // Add cache busting timestamp to force reload when font is rebuilt
    const timestamp = Date.now();
    return `${API_BASE}/font?t=${timestamp}`;
  },

  getPreviewFontUrl() {
    // Add cache busting timestamp to force reload when font is rebuilt
    const timestamp = Date.now();
    return `${API_BASE}/preview-font?t=${timestamp}`;
  },

  getAvar2FontUrl() {
    // Add cache busting timestamp to force reload when font is rebuilt
    const timestamp = Date.now();
    return `${API_BASE}/avar2-font?t=${timestamp}`;
  },

  async checkSyncStatus() {
    const response = await fetch(`${API_BASE}/check-sync-status`);
    if (!response.ok) {
      throw new Error('Failed to check sync status');
    }
    return parseJSON(response);
  },

  async buildAvar2Font(traditionalAxes, avar2Axes, includeSpac) {
    const response = await fetch(`${API_BASE}/build-avar2`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        traditional_axes: traditionalAxes,
        avar2_axes: avar2Axes,
        include_spac: includeSpac,
      }),
    });
    if (!response.ok) {
      const error = await parseJSON(response);
      throw new Error(error.error || 'Build failed');
    }
    return parseJSON(response);
  },

  async createInstance(instanceName, coordinates, insertAfter = null) {
    const body = { name: instanceName, coordinates };
    if (insertAfter) {
      body.insert_after = insertAfter;
    }
    const response = await fetch(`${API_BASE}/instance`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      try {
        const error = await parseJSON(response);
        throw new Error(error.error || 'Create failed');
      } catch (e) {
        throw new Error(`Create failed: ${response.status} ${response.statusText}`);
      }
    }
    return parseJSON(response);
  },

  async updateInstance(instanceName, coordinates) {
    const response = await fetch(`${API_BASE}/instance/${encodeURIComponent(instanceName)}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ coordinates }),
    });
    if (!response.ok) {
      try {
        const error = await parseJSON(response);
        throw new Error(error.error || 'Update failed');
      } catch (e) {
        throw new Error(`Update failed: ${response.status} ${response.statusText}`);
      }
    }
    return parseJSON(response);
  },

  async renameInstance(instanceName, newName) {
    const response = await fetch(`${API_BASE}/instance/${encodeURIComponent(instanceName)}/rename`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ new_name: newName }),
    });
    if (!response.ok) {
      try {
        const error = await parseJSON(response);
        throw new Error(error.error || 'Rename failed');
      } catch (e) {
        throw new Error(`Rename failed: ${response.status} ${response.statusText}`);
      }
    }
    return parseJSON(response);
  },

  async getAvar2Instances() {
    const response = await fetch(`${API_BASE}/avar2/instances`);
    if (!response.ok) {
      throw new Error(`Failed to fetch avar2 instances: ${response.status} ${response.statusText}`);
    }
    return parseJSON(response);
  },

  async getAvar2Axes() {
    const response = await fetch(`${API_BASE}/avar2/axes`);
    if (!response.ok) {
      throw new Error(`Failed to fetch avar2 axes: ${response.status} ${response.statusText}`);
    }
    return parseJSON(response);
  },

  async addAvar2Axis(axisData) {
    const response = await fetch(`${API_BASE}/avar2/axis`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(axisData),
    });
    if (!response.ok) {
      const error = await parseJSON(response).catch(() => ({ error: `Failed to add axis: ${response.status}` }));
      throw new Error(error.error || `Failed to add axis: ${response.status} ${response.statusText}`);
    }
    return parseJSON(response);
  },

  async updateAvar2Axis(axisName, axisData) {
    const response = await fetch(`${API_BASE}/avar2/axis/${encodeURIComponent(axisName)}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(axisData),
    });
    if (!response.ok) {
      const error = await parseJSON(response).catch(() => ({ error: `Failed to update axis: ${response.status}` }));
      throw new Error(error.error || `Failed to update axis: ${response.status} ${response.statusText}`);
    }
    return parseJSON(response);
  },

  async updateAvar2Mapping(instanceName, axisName, value) {
    const response = await fetch(`${API_BASE}/avar2/mapping/${encodeURIComponent(instanceName)}/${encodeURIComponent(axisName)}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ value }),
    });
    if (!response.ok) {
      const error = await parseJSON(response).catch(() => ({ error: `Failed to update mapping: ${response.status}` }));
      throw new Error(error.error || `Failed to update mapping: ${response.status} ${response.statusText}`);
    }
    return parseJSON(response);
  },

  async checkSpacAxis() {
    const response = await fetch(`${API_BASE}/spacing/check`);
    if (!response.ok) {
      throw new Error(`Failed to check SPAC axis: ${response.status} ${response.statusText}`);
    }
    return parseJSON(response);
  },

  async getSpacValues() {
    const response = await fetch(`${API_BASE}/spacing/values`);
    if (!response.ok) {
      throw new Error(`Failed to fetch SPAC values: ${response.status} ${response.statusText}`);
    }
    return parseJSON(response);
  },

  async initSpacAxis() {
    const response = await fetch(`${API_BASE}/spacing/init`, {
      method: 'POST',
    });
    if (!response.ok) {
      const error = await parseJSON(response).catch(() => ({ error: `Failed to initialize SPAC axis: ${response.status}` }));
      throw new Error(error.error || `Failed to initialize SPAC axis: ${response.status} ${response.statusText}`);
    }
    return parseJSON(response);
  },

  async updateSpacValue(instanceName, value) {
    const response = await fetch(`${API_BASE}/spacing/instance/${encodeURIComponent(instanceName)}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ value }),
    });
    if (!response.ok) {
      const error = await parseJSON(response).catch(() => ({ error: `Failed to update SPAC value: ${response.status}` }));
      throw new Error(error.error || `Failed to update SPAC value: ${response.status} ${response.statusText}`);
    }
    return parseJSON(response);
  },

  async rebuildPreviewFont() {
    const response = await fetch(`${API_BASE}/spacing/rebuild`, {
      method: 'POST',
    });
    if (!response.ok) {
      const error = await parseJSON(response).catch(() => ({ error: `Failed to rebuild preview font: ${response.status}` }));
      throw new Error(error.error || `Failed to rebuild preview font: ${response.status} ${response.statusText}`);
    }
    return parseJSON(response);
  },

  async registerEditingInstance(instanceName) {
    const response = await fetch(`${API_BASE}/instance/${encodeURIComponent(instanceName)}/editing`, {
      method: 'POST',
    });
    if (!response.ok) {
      // Silently fail - editing registration is best effort
      return;
    }
    return parseJSON(response);
  },

  async unregisterEditingInstance(instanceName) {
    const response = await fetch(`${API_BASE}/instance/${encodeURIComponent(instanceName)}/editing`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      // Silently fail - editing registration is best effort
      return;
    }
    return parseJSON(response);
  },
};
