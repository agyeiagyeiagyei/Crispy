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
};
