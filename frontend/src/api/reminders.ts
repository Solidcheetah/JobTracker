import { api } from './axios';
import type { PaginatedReminders, Reminder, ReminderStatus } from '../types';

export interface CreateReminderData {
  content: string;
  /** Must be in the future and carry a timezone offset — send `Date.toISOString()`. */
  remind_at: string;
}

export interface UpdateReminderData {
  content?: string;
  remind_at?: string;
}

export interface ReminderFilters {
  status?: ReminderStatus[];
  due_before?: string;
}

export const getUpcomingReminders = (limit = 5) =>
  api.get<Reminder[]>('/reminder/upcoming', { params: { limit } });

export const getReminders = (page = 1, pageSize = 20, filters: ReminderFilters = {}) =>
  api.get<PaginatedReminders>('/reminder/all', {
    params: { page, page_size: pageSize, ...filters },
  });

export const getReminder = (id: string) =>
  api.get<Reminder>('/reminder/', { params: { id } });

export const createReminder = (data: CreateReminderData) =>
  api.post<Reminder>('/reminder/', data);

export const updateReminder = (id: string, data: UpdateReminderData) =>
  api.patch<Reminder>('/reminder/', data, { params: { id } });

/** Soft delete — the reminder ends up `cancelled` rather than being removed. */
export const cancelReminder = (id: string) =>
  api.delete<Reminder>('/reminder/', { params: { id } });
