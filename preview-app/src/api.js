/**
 * API client for Glyphs Preview Server
 */

const API_BASE = process.env.REACT_APP_API_URL || '/api';

export const api = {
  async health() {
    const response = await fetch(`${API_BASE}/health`);
    return response.json();
  },

  async getInstances() {
    const response = await fetch(`${API_BASE}/instances`);
    if (!response.ok) throw new Error('Failed to fetch instances');
    return response.json();
  },

  async getAxes() {
    const response = await fetch(`${API_BASE}/axes`);
    if (!response.ok) throw new Error('Failed to fetch axes');
    return response.json();
  },

  async buildFont() {
    const response = await fetch(`${API_BASE}/build`, {
      method: 'POST',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Build failed');
    }
    return response.json();
  },

  async getFontUrl() {
    return `${API_BASE}/font`;
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
      const error = await response.json();
      throw new Error(error.error || 'Update failed');
    }
    return response.json();
  },
};
