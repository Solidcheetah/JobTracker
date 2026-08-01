import { api } from './axios';
import type { LoginCredentials, RegisterCredentials, User } from '../types';

export interface AuthResponse {
  token: string;
  type: string;
}

export const register = (data: RegisterCredentials) =>
  api.post<User>('/user/register', data);

export const login = (data: LoginCredentials) =>
  api.post<AuthResponse>('/user/login', data);

export const logout = () => api.post<{ detail: string }>('/user/logout');
