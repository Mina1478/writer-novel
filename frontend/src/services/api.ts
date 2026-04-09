const API_BASE_URL = 'http://127.0.0.1:8000';

export interface ProjectCreateReq {
  title: string;
  genre: string;
  sub_genres: string[];
  character_setting?: string;
  world_setting?: string;
  plot_idea?: string;
}

export interface OutlineReq {
  title: string;
  genre: string;
  sub_genres: string[];
  total_chapters: number;
  character_setting: string;
  world_setting: string;
  plot_idea: string;
  custom_outline_prompt?: string;
}

export const api = {
  // Check health
  async checkHealth() {
    const res = await fetch(`${API_BASE_URL}/health`);
    if (!res.ok) throw new Error('Network error');
    return res.json();
  },

  // Projects
  async listProjects() {
    const res = await fetch(`${API_BASE_URL}/projects`);
    if (!res.ok) throw new Error('Failed to fetch projects');
    return res.json();
  },

  async getProject(id: string) {
    const res = await fetch(`${API_BASE_URL}/projects/${id}`);
    if (!res.ok) throw new Error('Failed to fetch project');
    return res.json();
  },

  // Get genres
  async getGenres() {
    const res = await fetch(`${API_BASE_URL}/genres`);
    if (!res.ok) throw new Error('Failed to fetch genres');
    return res.json();
  },

  // Generate outline
  async generateOutline(data: OutlineReq) {
    const res = await fetch(`${API_BASE_URL}/generate-outline`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Outline generation failed');
    return res.json();
  },

  // Create project
  async createProject(data: ProjectCreateReq) {
    const res = await fetch(`${API_BASE_URL}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Create project failed');
    return res.json();
  },

  // Get generic config
  async getGenerationConfig() {
    const res = await fetch(`${API_BASE_URL}/config/generation`);
    if (!res.ok) throw new Error('Failed to fetch config');
    return res.json();
  },

  // Get backends
  async getBackends() {
    const res = await fetch(`${API_BASE_URL}/config/backends`);
    if (!res.ok) throw new Error('Failed to fetch backends');
    return res.json();
  },

  // Task Management
  async listTasks() {
    const res = await fetch(`${API_BASE_URL}/tasks`);
    if (!res.ok) throw new Error('Failed to fetch tasks');
    return res.json();
  },

  async startBulkGen(data: { project_id: string, chapter_nums: number[], use_reflection?: boolean }) {
    const res = await fetch(`${API_BASE_URL}/tasks/generate-bulk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to start bulk generation');
    return res.json();
  },

  async cancelTask(taskId: string) {
    const res = await fetch(`${API_BASE_URL}/tasks/${taskId}`, {
      method: 'DELETE',
    });
    return res.json();
  }
};
