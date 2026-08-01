export type ApplicationStatus =
  | 'wishlist'
  | 'applied'
  | 'screen'
  | 'onsite'
  | 'offer'
  | 'rejected'
  | 'withdrawn';

export interface Application {
  id: string;
  owner_id: string;
  company: string;
  role: string;
  status: ApplicationStatus;
  source_url: string | null;
  note: string | null;
  applied_at: string;
  created_at: string;
}

export interface PaginatedApplications {
  items: Application[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApplicationStats {
  total: number;
  most_common_status: ApplicationStatus | null;
  status_counts: Record<string, number>;
}

export type ReminderStatus =
  | 'pending'
  | 'queued'
  | 'delivered'
  | 'failed'
  | 'cancelled';

export interface Reminder {
  id: string;
  content: string;
  /** UTC ISO string with an offset — format it in local time before showing it. */
  remind_at: string;
  status: ReminderStatus;
}

export interface PaginatedReminders {
  items: Reminder[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface User {
  name: string;
  email: string;
}

export interface ApplicationStatusHistory {
  id: string;
  application_id: string;
  status: ApplicationStatus;
  changed_at: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterCredentials {
  name: string;
  email: string;
  password: string;
}
