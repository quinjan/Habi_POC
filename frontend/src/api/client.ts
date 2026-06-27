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
export type ManualSourceEntryQueuedSubmission =
  components["schemas"]["ManualSourceEntryQueuedSubmission"];
export type ProcessingJobList = components["schemas"]["ProcessingJobList"];
export type ProcessingJobListItem = components["schemas"]["ProcessingJobListItem"];
export type ReviewBatchDraftSaveRequest =
  components["schemas"]["ReviewBatchDraftSaveRequest"];
export type ReviewBatchDetail = components["schemas"]["ReviewBatchDetail"];
export type ReviewBatchTaxonomyMappingRequest =
  components["schemas"]["ReviewBatchTaxonomyMappingRequest"];
export type ReviewedPurchaseLinePayload = components["schemas"]["ReviewedPurchaseLinePayload"];
export type TaxonomyDecisionCreate = components["schemas"]["TaxonomyDecisionCreate"];
export type TaxonomyNodeListRead = components["schemas"]["TaxonomyNodeListRead"];

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
): Promise<ManualSourceEntryQueuedSubmission> {
  return request<ManualSourceEntryQueuedSubmission>(
    `/api/project-workspaces/${projectWorkspaceId}/manual-source-entries`,
    {
      method: "POST",
      body: JSON.stringify(payload)
    }
  );
}

export async function listProcessingJobs(
  projectWorkspaceId: number
): Promise<ProcessingJobList> {
  return request<ProcessingJobList>(
    `/api/project-workspaces/${projectWorkspaceId}/processing-jobs`
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

export async function getReviewBatch(
  projectWorkspaceId: number,
  reviewBatchId: number
): Promise<ReviewBatchDetail> {
  return request<ReviewBatchDetail>(
    `/api/project-workspaces/${projectWorkspaceId}/review-batches/${reviewBatchId}`
  );
}

export async function saveReviewBatchDraft(
  projectWorkspaceId: number,
  reviewBatchId: number,
  payload: ReviewBatchDraftSaveRequest
): Promise<ReviewBatchDetail> {
  return request<ReviewBatchDetail>(
    `/api/project-workspaces/${projectWorkspaceId}/review-batches/${reviewBatchId}/review-draft`,
    {
      method: "PUT",
      body: JSON.stringify(payload)
    }
  );
}

export async function saveReviewBatchTaxonomyMapping(
  projectWorkspaceId: number,
  reviewBatchId: number,
  payload: ReviewBatchTaxonomyMappingRequest
): Promise<ReviewBatchDetail> {
  return request<ReviewBatchDetail>(
    `/api/project-workspaces/${projectWorkspaceId}/review-batches/${reviewBatchId}/taxonomy-mappings`,
    {
      method: "POST",
      body: JSON.stringify(payload)
    }
  );
}

export async function createTaxonomyDecision(
  projectWorkspaceId: number,
  reviewBatchId: number,
  payload: TaxonomyDecisionCreate
): Promise<ReviewBatchDetail> {
  return request<ReviewBatchDetail>(
    `/api/project-workspaces/${projectWorkspaceId}/review-batches/${reviewBatchId}/taxonomy-decisions`,
    {
      method: "POST",
      body: JSON.stringify(payload)
    }
  );
}

export async function listTaxonomyLeafPaths(
  projectWorkspaceId: number
): Promise<TaxonomyNodeListRead> {
  return request<TaxonomyNodeListRead>(
    `/api/project-workspaces/${projectWorkspaceId}/taxonomy-nodes?leaf_only=true`
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
