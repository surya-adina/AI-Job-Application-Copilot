import { apiGet } from './client';

export type ApplicationListItem = {
  id: string;
  notes: string | null;
  status: string;
  createdAt: string;
  job: {
    id: string;
    company: string;
    title: string;
  };
  resume: {
    id: string;
    title: string;
  };
  analysis?: {
    id: string;
    score: number;
  } | null;
};

export type ApplicationDetails = {
  id: string;
  notes: string | null;
  status: string;
  createdAt: string;
  job: {
    id: string;
    company: string;
    title: string;
    jdText: string;
    sourceUrl: string | null;
  };
  resume: {
    id: string;
    title: string;
    rawText: string;
  };
};

export async function getApplications(token: string) {
  return apiGet<ApplicationListItem[]>('/applications', { token });
}

export async function getApplication(applicationId: string, token: string) {
  return apiGet<ApplicationDetails>(`/applications/${applicationId}`, {
    token,
  });
}