import type { components } from "./generated";

export type ProjectWorkspaceCreate = components["schemas"]["ProjectWorkspaceCreate"];
export type ProjectWorkspaceList = components["schemas"]["ProjectWorkspaceList"];
export type ProjectWorkspaceListItem = components["schemas"]["ProjectWorkspaceListItem"];
export type ProjectWorkspacePurchaseLinesView =
  components["schemas"]["ProjectWorkspacePurchaseLinesView"];
export type ProjectWorkspaceRead = components["schemas"]["ProjectWorkspaceRead"];
export type PurchaseLineDetail = components["schemas"]["PurchaseLineDetail"];
export type SourceSubmissionDetail = components["schemas"]["SourceSubmissionDetail"];
export type EntityMemoryListView = components["schemas"]["EntityMemoryListView"];
export type ProviderMemoryListView = components["schemas"]["ProviderMemoryListView"];
export type CandidateDecisionRequest = components["schemas"]["CandidateDecisionRequest"];
export type ExtractedCandidateRead = components["schemas"]["ExtractedCandidateRead"];
export type ImportReviewBatchResponse = components["schemas"]["ImportReviewBatchResponse"];
export type ManualSourceEntryCreate = components["schemas"]["ManualSourceEntryCreate"];
export type ManualSourceEntryQueuedSubmission =
  components["schemas"]["ManualSourceEntryQueuedSubmission"];
export type SourceFileQueuedSubmission = components["schemas"]["SourceFileQueuedSubmission"];
export type ProcessingJobList = components["schemas"]["ProcessingJobList"];
export type ProcessingJobListItem = components["schemas"]["ProcessingJobListItem"];
export type ReviewBatchDraftSaveRequest =
  components["schemas"]["ReviewBatchDraftSaveRequest"];
export type ReviewBatchDetail = components["schemas"]["ReviewBatchDetail"];
export type ReviewBatchTaxonomyMappingRequest =
  components["schemas"]["ReviewBatchTaxonomyMappingRequest"];
export type ReviewedPurchaseLinePayload = components["schemas"]["ReviewedPurchaseLinePayload"];
export type ReviewedAnnotationProposal = components["schemas"]["ReviewedAnnotationProposal"];
export type StructuredEvidenceAnnotationInput =
  components["schemas"]["StructuredEvidenceAnnotationInput"];
export type TaxonomyDecisionCreate = components["schemas"]["TaxonomyDecisionCreate"];
export type TaxonomyNodeListRead = components["schemas"]["TaxonomyNodeListRead"];
export type TaxonomyGateReviewerDraftSaveRequest =
  components["schemas"]["TaxonomyGateReviewerDraftSaveRequest"];
export type TaxonomyGateReviewerDraftSaveResponse =
  components["schemas"]["TaxonomyGateReviewerDraftSaveResponse"];
export type TaxonomyGateSelectionRequest =
  components["schemas"]["TaxonomyGateSelectionRequest"];

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

export async function getPurchaseLineDetail(
  projectWorkspaceId: number,
  purchaseLineId: number
): Promise<PurchaseLineDetail> {
  return request<PurchaseLineDetail>(
    `/api/project-workspaces/${projectWorkspaceId}/purchase-lines/${purchaseLineId}`
  );
}

export async function getSourceSubmissionDetail(
  projectWorkspaceId: number,
  sourceSubmissionId: number
): Promise<SourceSubmissionDetail> {
  return request<SourceSubmissionDetail>(
    `/api/project-workspaces/${projectWorkspaceId}/source-submissions/${sourceSubmissionId}`
  );
}

export function originalSourceFileUrl(
  projectWorkspaceId: number,
  sourceSubmissionId: number,
  sourceFileId: number
): string {
  return `${API_BASE_URL}/api/project-workspaces/${projectWorkspaceId}/source-submissions/${sourceSubmissionId}/source-files/${sourceFileId}/original`;
}

export async function getProjectWorkspaceMaterials(
  projectWorkspaceId: number
): Promise<EntityMemoryListView> {
  return request<EntityMemoryListView>(
    `/api/project-workspaces/${projectWorkspaceId}/materials`
  );
}

export async function getProjectWorkspaceServices(
  projectWorkspaceId: number
): Promise<EntityMemoryListView> {
  return request<EntityMemoryListView>(
    `/api/project-workspaces/${projectWorkspaceId}/services`
  );
}

export async function getProjectWorkspaceProviders(
  projectWorkspaceId: number,
  roles: string[] = []
): Promise<ProviderMemoryListView> {
  const query = new URLSearchParams();
  roles.forEach((role) => query.append("roles", role));
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return request<ProviderMemoryListView>(
    `/api/project-workspaces/${projectWorkspaceId}/providers${suffix}`
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

export async function createSourceFile(
  projectWorkspaceId: number,
  file: File
): Promise<SourceFileQueuedSubmission> {
  const formData = new FormData();
  formData.append("files", file);
  return request<SourceFileQueuedSubmission>(
    `/api/project-workspaces/${projectWorkspaceId}/source-files`,
    {
      method: "POST",
      body: formData
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

export async function resetCandidate(
  projectWorkspaceId: number,
  reviewBatchId: number,
  candidateId: number
): Promise<ExtractedCandidateRead> {
  return request<ExtractedCandidateRead>(
    `/api/project-workspaces/${projectWorkspaceId}/review-batches/${reviewBatchId}/candidates/${candidateId}/reset`,
    { method: "POST" }
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

export async function saveTaxonomyGateReviewerDraft(
  projectWorkspaceId: number,
  reviewBatchId: number,
  taxonomyGateId: number,
  payload: TaxonomyGateReviewerDraftSaveRequest
): Promise<TaxonomyGateReviewerDraftSaveResponse> {
  return request<TaxonomyGateReviewerDraftSaveResponse>(
    `/api/project-workspaces/${projectWorkspaceId}/review-batches/${reviewBatchId}/taxonomy-gates/${taxonomyGateId}/reviewer-draft`,
    { method: "PUT", body: JSON.stringify(payload) }
  );
}

export async function selectTaxonomyGateProposal(
  projectWorkspaceId: number,
  reviewBatchId: number,
  taxonomyGateId: number,
  payload: TaxonomyGateSelectionRequest
): Promise<ReviewBatchDetail> {
  return request<ReviewBatchDetail>(
    `/api/project-workspaces/${projectWorkspaceId}/review-batches/${reviewBatchId}/taxonomy-gates/${taxonomyGateId}/selection`,
    { method: "PUT", body: JSON.stringify(payload) }
  );
}

export async function acceptTaxonomyGate(
  projectWorkspaceId: number,
  reviewBatchId: number,
  taxonomyGateId: number
): Promise<ReviewBatchDetail> {
  return request<ReviewBatchDetail>(
    `/api/project-workspaces/${projectWorkspaceId}/review-batches/${reviewBatchId}/taxonomy-gates/${taxonomyGateId}/accept`,
    { method: "POST" }
  );
}

export async function editAcceptedTaxonomyGate(
  projectWorkspaceId: number,
  reviewBatchId: number,
  taxonomyGateId: number
): Promise<ReviewBatchDetail> {
  return request<ReviewBatchDetail>(
    `/api/project-workspaces/${projectWorkspaceId}/review-batches/${reviewBatchId}/taxonomy-gates/${taxonomyGateId}/edit`,
    { method: "POST" }
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
  const headers =
    init.body instanceof FormData
      ? init.headers
      : {
          "Content-Type": "application/json",
          ...init.headers
        };
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers
  });

  if (!response.ok) {
    throw new Error(`Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}
