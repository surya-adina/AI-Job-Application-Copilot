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