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
};
