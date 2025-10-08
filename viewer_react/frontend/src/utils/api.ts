import axios from 'axios';
import type { GameFolder, GameData, Trajectory, LineCountData, SimWinsData } from '../types';

const API_BASE = '/api';

export const api = {
  async getFolders(): Promise<GameFolder[]> {
    const response = await axios.get(`${API_BASE}/folders`);
    if (!response.data.success) {
      throw new Error(response.data.error || 'Failed to fetch folders');
    }
    return response.data.folders;
  },

  async getGame(folderPath: string): Promise<GameData> {
    const response = await axios.get(`${API_BASE}/game/${folderPath}`);
    if (!response.data.success) {
      throw new Error(response.data.error || 'Failed to fetch game data');
    }
    return response.data;
  },

  async getTrajectory(folderPath: string, playerName: string, roundNum: number): Promise<Trajectory> {
    const response = await axios.get(`${API_BASE}/trajectory/${folderPath}/${playerName}/${roundNum}`);
    if (!response.data.success) {
      throw new Error(response.data.error || 'Failed to fetch trajectory');
    }
    return response.data.trajectory;
  },

  async getLineCountAnalysis(folderPath: string): Promise<LineCountData> {
    const response = await axios.get(`${API_BASE}/analysis/line-counts/${folderPath}`);
    return response.data;
  },

  async getSimWinsAnalysis(folderPath: string): Promise<SimWinsData> {
    const response = await axios.get(`${API_BASE}/analysis/sim-wins/${folderPath}`);
    return response.data;
  },

  async deleteFolder(folderPath: string): Promise<void> {
    await axios.post(`${API_BASE}/delete-folder`, { folder_path: folderPath });
  },

  async moveFolder(oldPath: string, newPath: string): Promise<{ new_path: string }> {
    const response = await axios.post(`${API_BASE}/move-folder`, { old_path: oldPath, new_path: newPath });
    if (!response.data.success) {
      throw new Error(response.data.error || 'Failed to move folder');
    }
    return response.data;
  },

  async getReadme(folderPath: string): Promise<string> {
    const response = await axios.get(`${API_BASE}/readme`, { params: { folder: folderPath } });
    if (!response.data.success) {
      throw new Error(response.data.error || 'Failed to fetch readme');
    }
    return response.data.content;
  },

  async saveReadme(folderPath: string, content: string): Promise<void> {
    const response = await axios.post(`${API_BASE}/readme`, { folder: folderPath, content });
    if (!response.data.success) {
      throw new Error(response.data.error || 'Failed to save readme');
    }
  },

  downloadFile(folderPath: string, relativePath: string): void {
    const url = `${API_BASE}/download?folder=${encodeURIComponent(folderPath)}&path=${encodeURIComponent(relativePath)}`;
    window.open(url, '_blank');
  },
};
