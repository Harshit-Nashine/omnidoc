// ================================================================
// frontend/src/api.ts
// ================================================================
// Axios client configured to talk to OmniDoc API.
// All API calls go through this file — base URL and auth headers
// are set once here, not scattered across components.
// ================================================================

import axios from 'axios';

const API_BASE = 'http://localhost:8000';

// Create axios instance with base URL
const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach JWT token to every request automatically
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Redirect to login on 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ── Auth ────────────────────────────────────────────────────────

export const login = async (email: string, password: string) => {
  const response = await api.post('/auth/login', { email, password });
  return response.data;
};

export const register = async (data: {
  tenant_name: string;
  tenant_slug: string;
  email: string;
  password: string;
  full_name?: string;
}) => {
  const response = await api.post('/auth/register', data);
  return response.data;
};

export const getMe = async () => {
  const response = await api.get('/auth/me');
  return response.data;
};

// ── Documents ───────────────────────────────────────────────────

export const getDocuments = async () => {
  const response = await api.get('/documents/');
  return response.data;
};

export const uploadDocument = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const getDocument = async (id: string) => {
  const response = await api.get(`/documents/${id}`);
  return response.data;
};

export const approveDocument = async (id: string) => {
  const response = await api.post(`/documents/${id}/approve`);
  return response.data;
};

// ── Query ───────────────────────────────────────────────────────

export const queryDocuments = async (question: string, nResults = 5) => {
  const response = await api.post('/query/', { question, n_results: nResults });
  return response.data;
};

// ── Audit ───────────────────────────────────────────────────────

export const getAuditLog = async () => {
  const response = await api.get('/audit/');
  return response.data;
};

// ── Health ──────────────────────────────────────────────────────

export const getHealth = async () => {
  const response = await api.get('/health');
  return response.data;
};

export default api;