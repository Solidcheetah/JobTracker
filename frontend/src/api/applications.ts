import { api } from './axios';
import type {
  Application,
  ApplicationStats,
  ApplicationStatus,
  ApplicationStatusHistory,
  PaginatedApplications,
} from '../types';

export interface CreateApplicationData {
  company: string;
  role: string;
  status: ApplicationStatus;
  source_url?: string | null;
  note?: string | null;
  applied_at: string;
}

export interface UpdateApplicationData {
  company?: string;
  role?: string;
  status?: ApplicationStatus;
  source_url?: string | null;
  note?: string | null;
  applied_at?: string;
}

export interface ApplicationFilters {
  status?: ApplicationStatus[];
  search?: string;
  applied_from?: string;
  applied_to?: string;
}

export const getApplications = (
  page = 1,
  pageSize = 20,
  filters: ApplicationFilters = {}
) =>
  api.get<PaginatedApplications>('/application/all', {
    params: {
      page,
      page_size: pageSize,
      ...filters,
    },
  });

export const getRecentApplications = () => api.get<Application[]>('/application/recent');

export const getApplicationStats = () =>
  api.get<ApplicationStats>('/application/stats');

export const createApplication = (data: CreateApplicationData) =>
  api.post<Application>('/application/', data);

export const updateApplication = (id: string, data: UpdateApplicationData) =>
  api.patch<Application>('/application/', data, { params: { id } });

export const updateApplicationStatus = (id: string, status: ApplicationStatus) =>
  api.patch<Application>('/application/status', { status }, { params: { id } });

export const updateApplicationNote = (id: string, note: string | null) =>
  api.patch<Application>('/application/note', { note }, { params: { id } });

export const deleteApplication = (id: string) =>
  api.delete('/application/', { params: { application_id: id } });

export const getApplicationStatusHistory = (id: string) =>
  api.get<ApplicationStatusHistory[]>('/application/history', { params: { id } });
