import type { components } from "./generated";

export type ProjectWorkspaceCreate = components["schemas"]["ProjectWorkspaceCreate"];
export type ProjectWorkspaceList = components["schemas"]["ProjectWorkspaceList"];
export type ProjectWorkspaceListItem = components["schemas"]["ProjectWorkspaceListItem"];
export type ProjectWorkspacePurchaseLinesView =
  components["schemas"]["ProjectWorkspacePurchaseLinesView"];
export type ProjectWorkspaceRead = components["schemas"]["ProjectWorkspaceRead"];
export type CandidateDecisionRequest = components["schemas"]["CandidateDecisionRequest"];
export type ExtractedCandidateRead = components["schemas"]["ExtractedCandidateRead"];
export type ImportReviewBatchResponse = components["schemas"]["ImportReviewBatchResponse"];
export type ManualSourceEntryCreate = components["schemas"]["ManualSourceEntryCreate"];
export type ManualSourceEntrySubmission = components["schemas"]["ManualSourceEntrySubmission"];
export type ReviewedPurchaseLinePayload = components["schemas"]["ReviewedPurchaseLinePayload"];

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export async function listProjectWorkspaces(): Promise<ProjectWorkspaceList> {
  return request<ProjectWorkspaceList>("/api/project-workspaces");
}

export async function createProjectWorkspace(
  payload: ProjectWorkspaceCreate
): Promise<ProjectWorkspaceRead> {
  return request<ProjectWorkspaceRead>("/api/project-workspaces", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function getProjectWorkspacePurchaseLines(
  projectWorkspaceId: number
): Promise<ProjectWorkspacePurchaseLinesView> {
  return request<ProjectWorkspacePurchaseLinesView>(
    `/api/project-workspaces/${projectWorkspaceId}/purchase-lines`
  );
}

export async function createManualSourceEntry(
  projectWorkspaceId: number,
  payload: ManualSourceEntryCreate
): Promise<ManualSourceEntrySubmission> {
  return request<ManualSourceEntrySubmission>(
    `/api/project-workspaces/${projectWorkspaceId}/manual-source-entries`,
    {
      method: "POST",
      body: JSON.stringify(payload)
    }
  );
}

export async function decideCandidate(
  projectWorkspaceId: number,
  reviewBatchId: number,
  candidateId: number,
  payload: CandidateDecisionRequest
): Promise<ExtractedCandidateRead> {
  return request<ExtractedCandidateRead>(
    `/api/project-workspaces/${projectWorkspaceId}/review-batches/${reviewBatchId}/candidates/${candidateId}/decision`,
    {
      method: "POST",
      body: JSON.stringify(payload)
    }
  );
}

export async function importReviewBatch(
  projectWorkspaceId: number,
  reviewBatchId: number
): Promise<ImportReviewBatchResponse> {
  return request<ImportReviewBatchResponse>(
    `/api/project-workspaces/${projectWorkspaceId}/review-batches/${reviewBatchId}/import`,
    { method: "POST" }
  );
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers
    }
  });

  if (!response.ok) {
    throw new Error(`Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}
