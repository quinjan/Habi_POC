import { FormEvent, useEffect, useMemo, useState } from "react";
import { Check, FolderOpen, GitBranch, Plus, Upload, X } from "lucide-react";

import {
  createProjectWorkspace,
  createTaxonomyDecision,
  createManualSourceEntry,
  decideCandidate,
  getReviewBatch,
  getProjectWorkspacePurchaseLines,
  importReviewBatch,
  listProcessingJobs,
  listTaxonomyLeafPaths,
  listProjectWorkspaces,
  saveReviewBatchDraft,
  saveReviewBatchTaxonomyMapping,
  type ExtractedCandidateRead,
  type ManualSourceEntryCreate,
  type ProcessingJobListItem,
  type ProjectWorkspaceCreate,
  type ProjectWorkspaceListItem,
  type ProjectWorkspacePurchaseLinesView,
  type ReviewBatchDetail,
  type ReviewedPurchaseLinePayload
} from "./api/client";

type ProjectWorkspaceForm = {
  projectName: string;
  projectType: string;
  location: string;
  completionDate: string;
  completionYear: string;
  floorArea: string;
  tradeScopes: string;
  clientOrOwner: string;
  notes: string;
};

const emptyForm: ProjectWorkspaceForm = {
  projectName: "",
  projectType: "",
  location: "",
  completionDate: "",
  completionYear: "",
  floorArea: "",
  tradeScopes: "",
  clientOrOwner: "",
  notes: ""
};

type ManualSourceForm = {
  lineType: "material" | "service";
  name: string;
  quantity: string;
  unit: string;
  price: string;
  currency: string;
  providerName: string;
  purchaseDate: string;
  remarksOrTerms: string;
};

type ManualEntryMode = "structured_row" | "free_form_text";

const emptyManualSourceForm: ManualSourceForm = {
  lineType: "material",
  name: "",
  quantity: "",
  unit: "",
  price: "",
  currency: "PHP",
  providerName: "",
  purchaseDate: "",
  remarksOrTerms: ""
};

type ReviewForm = ManualSourceForm & {
  topLevelCategory: string;
  subcategory: string;
};

type WorkspaceRoute =
  | { name: "purchase_lines" }
  | { name: "upload_review" }
  | { name: "review_batch"; reviewBatchId: number };

type CandidateDraft = {
  included: boolean;
  reviewedPayload: ReviewedPurchaseLinePayload | null;
};

type TaxonomyForm = {
  topLevelCategory: string;
  subcategory: string;
  applyToSimilar: boolean;
};

function App() {
  const [projects, setProjects] = useState<ProjectWorkspaceListItem[]>([]);
  const [selectedPurchaseLines, setSelectedPurchaseLines] =
    useState<ProjectWorkspacePurchaseLinesView | null>(null);
  const [form, setForm] = useState<ProjectWorkspaceForm>(emptyForm);
  const [manualSourceForm, setManualSourceForm] =
    useState<ManualSourceForm>(emptyManualSourceForm);
  const [manualEntryMode, setManualEntryMode] = useState<ManualEntryMode>("structured_row");
  const [freeFormText, setFreeFormText] = useState("");
  const [processingJobs, setProcessingJobs] = useState<ProcessingJobListItem[]>([]);
  const [activeReviewBatch, setActiveReviewBatch] = useState<ReviewBatchDetail | null>(null);
  const [workspaceRoute, setWorkspaceRoute] = useState<WorkspaceRoute>({
    name: "purchase_lines"
  });
  const [candidateDrafts, setCandidateDrafts] = useState<Record<number, CandidateDraft>>({});
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [detailCandidateId, setDetailCandidateId] = useState<number | null>(null);
  const [taxonomyCandidateId, setTaxonomyCandidateId] = useState<number | null>(null);
  const [taxonomyForm, setTaxonomyForm] = useState<TaxonomyForm>({
    topLevelCategory: "",
    subcategory: "",
    applyToSimilar: false
  });
  const [reviewForm, setReviewForm] = useState<ReviewForm | null>(null);
  const [isLoadingProjects, setIsLoadingProjects] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isSubmittingManualSource, setIsSubmittingManualSource] = useState(false);
  const [isApprovingCandidate, setIsApprovingCandidate] = useState(false);
  const [isImportingBatch, setIsImportingBatch] = useState(false);
  const [isCandidateApproved, setIsCandidateApproved] = useState(false);
  const [taxonomyLeafPaths, setTaxonomyLeafPaths] = useState<
    { id: number; path: string }[]
  >([]);
  const [selectedTaxonomyNodeId, setSelectedTaxonomyNodeId] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadProjects() {
      try {
        const response = await listProjectWorkspaces();
        if (isMounted) {
          setProjects(response.items);
        }
      } catch {
        if (isMounted) {
          setErrorMessage("Project Workspaces could not be loaded.");
        }
      } finally {
        if (isMounted) {
          setIsLoadingProjects(false);
        }
      }
    }

    void loadProjects();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (selectedPurchaseLines === null) {
      setProcessingJobs([]);
      return;
    }

    let isMounted = true;
    const projectId = selectedPurchaseLines.project_workspace.id;

    async function refreshJobs() {
      try {
        const response = await listProcessingJobs(projectId);
        if (isMounted) {
          setProcessingJobs(response.items);
        }
      } catch {
        if (isMounted) {
          setErrorMessage("Processing Jobs could not be loaded.");
        }
      }
    }

    void refreshJobs();
    const intervalId = window.setInterval(() => void refreshJobs(), 2000);

    return () => {
      isMounted = false;
      window.clearInterval(intervalId);
    };
  }, [selectedPurchaseLines?.project_workspace.id]);

  const selectedProjectName = useMemo(
    () => selectedPurchaseLines?.project_workspace.project_name ?? null,
    [selectedPurchaseLines]
  );
  const detailCandidate =
    activeReviewBatch?.candidates.find((candidate) => candidate.id === detailCandidateId) ?? null;
  const taxonomyCandidate =
    activeReviewBatch?.candidates.find((candidate) => candidate.id === taxonomyCandidateId) ??
    null;

  async function handleCreateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setErrorMessage(null);

    try {
      const payload = buildCreatePayload(form);
      const createdProject = await createProjectWorkspace(payload);
      setProjects((currentProjects) => [
        ...currentProjects,
        { id: createdProject.id, project_name: createdProject.project_name }
      ]);
      setForm(emptyForm);
    } catch {
      setErrorMessage("Project Workspace could not be created.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSelectProject(project: ProjectWorkspaceListItem) {
    setErrorMessage(null);

    try {
      const response = await getProjectWorkspacePurchaseLines(project.id);
      setSelectedPurchaseLines(response);
      await refreshTaxonomyLeafPaths(project.id);
      setActiveReviewBatch(null);
      setCandidateDrafts({});
      setDetailCandidateId(null);
      setTaxonomyCandidateId(null);
      setReviewForm(null);
      setFreeFormText("");
      setManualEntryMode("structured_row");
      setIsCandidateApproved(false);
      navigateWorkspace(project.id, { name: "purchase_lines" });
    } catch {
      setErrorMessage("Purchase Lines could not be loaded.");
    }
  }

  function navigateWorkspace(projectId: number, route: WorkspaceRoute) {
    setWorkspaceRoute(route);
    const path =
      route.name === "purchase_lines"
        ? `/projects/${projectId}/purchase-lines`
        : route.name === "upload_review"
          ? `/projects/${projectId}/upload-review`
          : `/projects/${projectId}/review-batches/${route.reviewBatchId}`;
    window.history.pushState({}, "", path);
  }

  async function refreshTaxonomyLeafPaths(projectWorkspaceId: number) {
    const taxonomyNodes = await listTaxonomyLeafPaths(projectWorkspaceId);
    setTaxonomyLeafPaths(taxonomyNodes.items.map((item) => ({ id: item.id, path: item.path })));
  }

  async function refreshProcessingJobs(projectWorkspaceId: number) {
    const response = await listProcessingJobs(projectWorkspaceId);
    setProcessingJobs(response.items);
  }

  function updateForm(field: keyof ProjectWorkspaceForm, value: string) {
    setForm((currentForm) => ({ ...currentForm, [field]: value }));
  }

  async function handleCreateManualSourceEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedPurchaseLines === null) {
      return;
    }

    setIsSubmittingManualSource(true);
    setErrorMessage(null);

    try {
      await createManualSourceEntry(
        selectedPurchaseLines.project_workspace.id,
        buildManualSourcePayload(manualSourceForm, manualEntryMode, freeFormText)
      );
      await refreshProcessingJobs(selectedPurchaseLines.project_workspace.id);
      setActiveReviewBatch(null);
      setCandidateDrafts({});
      setDetailCandidateId(null);
      setTaxonomyCandidateId(null);
      setReviewForm(null);
      setSelectedTaxonomyNodeId("");
      setIsCandidateApproved(false);
      if (manualEntryMode === "structured_row") {
        setManualSourceForm(emptyManualSourceForm);
      } else {
        setFreeFormText("");
      }
    } catch {
      setErrorMessage("Manual Source Entry could not be created.");
    } finally {
      setIsSubmittingManualSource(false);
    }
  }

  async function handleOpenReviewBatch(reviewBatchId: number) {
    if (selectedPurchaseLines === null) {
      return;
    }

    setErrorMessage(null);

    try {
      const detail = await getReviewBatch(selectedPurchaseLines.project_workspace.id, reviewBatchId);
      setActiveReviewBatch(detail);
      setCandidateDrafts(initialDraftsForCandidates(detail.candidates));
      setDetailCandidateId(null);
      setTaxonomyCandidateId(null);
      setReviewForm(buildReviewForm(detail, manualSourceForm));
      setSelectedTaxonomyNodeId("");
      setIsCandidateApproved(false);
      setToastMessage(null);
      navigateWorkspace(selectedPurchaseLines.project_workspace.id, {
        name: "review_batch",
        reviewBatchId
      });
    } catch {
      setErrorMessage("Review Batch could not be loaded.");
    }
  }

  function updateCandidateIncluded(candidate: ExtractedCandidateRead, included: boolean) {
    setCandidateDrafts((currentDrafts) => ({
      ...currentDrafts,
      [candidate.id]: {
        included,
        reviewedPayload: included ? reviewedPayloadForCandidate(candidate) : null
      }
    }));
  }

  async function handleSaveReviewDraft() {
    if (selectedPurchaseLines === null || activeReviewBatch === null) {
      return null;
    }
    setErrorMessage(null);
    const detail = await saveReviewBatchDraft(
      selectedPurchaseLines.project_workspace.id,
      activeReviewBatch.review_batch.id,
      {
        candidates: activeReviewBatch.candidates.map((candidate) => {
          const draft = candidateDrafts[candidate.id] ?? {
            included: true,
            reviewedPayload: reviewedPayloadForCandidate(candidate)
          };
          return {
            candidate_id: candidate.id,
            included: draft.included,
            reviewed_payload: draft.included ? draft.reviewedPayload : null
          };
        })
      }
    );
    setActiveReviewBatch(detail);
    setCandidateDrafts(initialDraftsForCandidates(detail.candidates));
    setToastMessage("Review draft saved.");
    return detail;
  }

  function openTaxonomyDialog(candidate: ExtractedCandidateRead) {
    const reviewedPayload =
      candidateDrafts[candidate.id]?.reviewedPayload ?? reviewedPayloadForCandidate(candidate);
    setTaxonomyForm({
      topLevelCategory: reviewedPayload.top_level_category ?? "",
      subcategory: reviewedPayload.subcategory ?? "",
      applyToSimilar: false
    });
    setTaxonomyCandidateId(candidate.id);
  }

  function updateTaxonomyForm(field: keyof TaxonomyForm, value: string | boolean) {
    setTaxonomyForm((currentForm) => ({ ...currentForm, [field]: value }));
  }

  async function handleSaveTaxonomyMapping(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      selectedPurchaseLines === null ||
      activeReviewBatch === null ||
      taxonomyCandidate === null
    ) {
      return;
    }

    setIsApprovingCandidate(true);
    setErrorMessage(null);

    try {
      const previousDrafts = candidateDrafts;
      const detail = await saveReviewBatchTaxonomyMapping(
        selectedPurchaseLines.project_workspace.id,
        activeReviewBatch.review_batch.id,
        {
          candidate_id: taxonomyCandidate.id,
          top_level_category: taxonomyForm.topLevelCategory,
          subcategory: taxonomyForm.subcategory,
          apply_to_similar: taxonomyForm.applyToSimilar
        }
      );
      const refreshedDrafts = initialDraftsForCandidates(detail.candidates);
      setActiveReviewBatch(detail);
      setCandidateDrafts(
        Object.fromEntries(
          detail.candidates.map((candidate) => {
            const previousDraft = previousDrafts[candidate.id];
            const refreshedDraft = refreshedDrafts[candidate.id];
            return [
              candidate.id,
              {
                ...refreshedDraft,
                included: previousDraft?.included ?? refreshedDraft.included
              }
            ];
          })
        )
      );
      setDetailCandidateId(null);
      setTaxonomyCandidateId(null);
      setToastMessage("Taxonomy mapping saved.");
    } catch {
      setErrorMessage("Taxonomy mapping could not be saved.");
    } finally {
      setIsApprovingCandidate(false);
    }
  }

  async function handleApproveCandidate() {
    const candidate = activeReviewBatch?.candidates[0] ?? null;
    if (
      selectedPurchaseLines === null ||
      activeReviewBatch === null ||
      candidate === null ||
      reviewForm === null
    ) {
      return;
    }

    setIsApprovingCandidate(true);
    setErrorMessage(null);

    try {
      const updatedCandidate = await decideCandidate(
        selectedPurchaseLines.project_workspace.id,
        activeReviewBatch.review_batch.id,
        candidate.id,
        {
          decision: "approved",
          reviewed_payload: buildReviewedPayload(reviewForm)
        }
      );
      setActiveReviewBatch({
        ...activeReviewBatch,
        candidates: activeReviewBatch.candidates.map((existingCandidate) =>
          existingCandidate.id === updatedCandidate.id ? updatedCandidate : existingCandidate
        )
      });
      setIsCandidateApproved(true);
    } catch {
      setErrorMessage("Candidate could not be approved.");
    } finally {
      setIsApprovingCandidate(false);
    }
  }

  async function handleRejectCandidate() {
    const candidate = activeReviewBatch?.candidates[0] ?? null;
    if (
      selectedPurchaseLines === null ||
      activeReviewBatch === null ||
      candidate === null
    ) {
      return;
    }

    setIsApprovingCandidate(true);
    setErrorMessage(null);

    try {
      const updatedCandidate = await decideCandidate(
        selectedPurchaseLines.project_workspace.id,
        activeReviewBatch.review_batch.id,
        candidate.id,
        {
          decision: "rejected",
          reviewed_payload: null
        }
      );
      setActiveReviewBatch({
        ...activeReviewBatch,
        candidates: [updatedCandidate]
      });
      setReviewForm(null);
      setIsCandidateApproved(false);
    } catch {
      setErrorMessage("Candidate could not be removed from import.");
    } finally {
      setIsApprovingCandidate(false);
    }
  }

  async function handleTaxonomyDecision(decision: "approved" | "mapped" | "rejected") {
    const candidate = activeReviewBatch?.candidates[0] ?? null;
    const suggestion = taxonomySuggestion(candidate);
    if (
      selectedPurchaseLines === null ||
      activeReviewBatch === null ||
      candidate === null ||
      suggestion === null
    ) {
      return;
    }

    const resolvedTaxonomyNodeId =
      decision === "mapped" && selectedTaxonomyNodeId
        ? Number(selectedTaxonomyNodeId)
        : undefined;
    if (decision === "mapped" && !resolvedTaxonomyNodeId) {
      setErrorMessage("Choose an existing taxonomy path before mapping.");
      return;
    }

    setIsApprovingCandidate(true);
    setErrorMessage(null);

    try {
      const detail = await createTaxonomyDecision(
        selectedPurchaseLines.project_workspace.id,
        activeReviewBatch.review_batch.id,
        {
          decision,
          suggested_top_level_category: suggestion.topLevelCategory,
          suggested_subcategory: suggestion.subcategory,
          resolved_taxonomy_node_id: resolvedTaxonomyNodeId ?? null
        }
      );
      applyReviewBatchDetail(detail);
      await refreshTaxonomyLeafPaths(selectedPurchaseLines.project_workspace.id);
    } catch {
      setErrorMessage("Taxonomy decision could not be saved.");
    } finally {
      setIsApprovingCandidate(false);
    }
  }

  function applyReviewBatchDetail(detail: ReviewBatchDetail) {
    setActiveReviewBatch(detail);
    setReviewForm(buildReviewForm(detail, manualSourceForm));
    setSelectedTaxonomyNodeId("");
    setIsCandidateApproved(false);
  }

  async function handleImportBatch() {
    if (
      selectedPurchaseLines === null ||
      activeReviewBatch === null
    ) {
      return;
    }

    setIsImportingBatch(true);
    setErrorMessage(null);

    try {
      await importReviewBatch(
        selectedPurchaseLines.project_workspace.id,
        activeReviewBatch.review_batch.id
      );
      const refreshedPurchaseLines = await getProjectWorkspacePurchaseLines(
        selectedPurchaseLines.project_workspace.id
      );
      setSelectedPurchaseLines(refreshedPurchaseLines);
      setActiveReviewBatch(null);
      setReviewForm(null);
      setCandidateDrafts({});
      setIsCandidateApproved(false);
      navigateWorkspace(selectedPurchaseLines.project_workspace.id, { name: "purchase_lines" });
    } catch {
      setErrorMessage("Review Batch could not be imported.");
    } finally {
      setIsImportingBatch(false);
    }
  }

  async function handleImportIncludedCandidates() {
    if (selectedPurchaseLines === null || activeReviewBatch === null) {
      return;
    }

    setIsImportingBatch(true);
    setErrorMessage(null);

    try {
      await handleSaveReviewDraft();
      await importReviewBatch(
        selectedPurchaseLines.project_workspace.id,
        activeReviewBatch.review_batch.id
      );
      const refreshedPurchaseLines = await getProjectWorkspacePurchaseLines(
        selectedPurchaseLines.project_workspace.id
      );
      setSelectedPurchaseLines(refreshedPurchaseLines);
      setActiveReviewBatch(null);
      setCandidateDrafts({});
      setReviewForm(null);
      navigateWorkspace(selectedPurchaseLines.project_workspace.id, { name: "purchase_lines" });
    } catch {
      setErrorMessage("Review Batch could not be imported.");
    } finally {
      setIsImportingBatch(false);
    }
  }

  function updateManualSourceForm(field: keyof ManualSourceForm, value: string) {
    setManualSourceForm((currentForm) => ({ ...currentForm, [field]: value }));
  }

  function updateReviewForm(field: keyof ReviewForm, value: string) {
    setReviewForm((currentForm) =>
      currentForm === null ? currentForm : { ...currentForm, [field]: value }
    );
    setIsCandidateApproved(false);
  }

  return (
    <main className="app-shell">
      <aside className="workspace-panel">
        <div className="panel-heading">
          <p className="eyebrow">Per-Project Memory Lab</p>
          <h1>Project Workspaces</h1>
        </div>

        {errorMessage ? <p className="status-message error">{errorMessage}</p> : null}

        <nav aria-label="Project Workspace selector" className="workspace-list">
          {isLoadingProjects ? <p className="status-message">Loading workspaces...</p> : null}
          {!isLoadingProjects && projects.length === 0 ? (
            <p className="status-message">No Project Workspaces yet</p>
          ) : null}
          {projects.map((project) => (
            <button
              className={
                selectedProjectName === project.project_name
                  ? "workspace-list-item active"
                  : "workspace-list-item"
              }
              key={project.id}
              onClick={() => void handleSelectProject(project)}
              type="button"
            >
              <FolderOpen aria-hidden="true" size={18} />
              <span>{project.project_name}</span>
            </button>
          ))}
        </nav>

        <form className="project-form" onSubmit={(event) => void handleCreateProject(event)}>
          <h2>Create Project Workspace</h2>
          <label>
            Project name
            <input
              required
              value={form.projectName}
              onChange={(event) => updateForm("projectName", event.target.value)}
            />
          </label>
          <label>
            Project type
            <input
              required
              value={form.projectType}
              onChange={(event) => updateForm("projectType", event.target.value)}
            />
          </label>
          <label>
            Location
            <input
              required
              value={form.location}
              onChange={(event) => updateForm("location", event.target.value)}
            />
          </label>
          <div className="form-grid">
            <label>
              Completion date
              <input
                type="date"
                value={form.completionDate}
                onChange={(event) => updateForm("completionDate", event.target.value)}
              />
            </label>
            <label>
              Completion year
              <input
                inputMode="numeric"
                pattern="[0-9]{4}"
                value={form.completionYear}
                onChange={(event) => updateForm("completionYear", event.target.value)}
              />
            </label>
          </div>
          <label>
            Floor area
            <input
              value={form.floorArea}
              onChange={(event) => updateForm("floorArea", event.target.value)}
            />
          </label>
          <label>
            Trade scopes
            <input
              value={form.tradeScopes}
              onChange={(event) => updateForm("tradeScopes", event.target.value)}
            />
          </label>
          <label>
            Client or owner
            <input
              value={form.clientOrOwner}
              onChange={(event) => updateForm("clientOrOwner", event.target.value)}
            />
          </label>
          <label>
            Notes
            <textarea
              rows={3}
              value={form.notes}
              onChange={(event) => updateForm("notes", event.target.value)}
            />
          </label>
          <button className="primary-action" disabled={isSaving} type="submit">
            <Plus aria-hidden="true" size={18} />
            Create Project Workspace
          </button>
        </form>
      </aside>

      <section
        aria-label="Selected Project Workspace"
        aria-live="polite"
        className="workspace-view"
      >
        {selectedPurchaseLines ? (
          <>
            <div className="view-heading">
              <p className="eyebrow">{selectedPurchaseLines.project_workspace.project_name}</p>
              {workspaceRoute.name === "purchase_lines" ? <h2>Purchase Lines</h2> : null}
              {workspaceRoute.name === "upload_review" ? <h2>Upload / Review</h2> : null}
            </div>
            <div className="workspace-tabs" role="tablist" aria-label="Project Workspace sections">
              <button
                role="tab"
                aria-selected={workspaceRoute.name === "purchase_lines"}
                onClick={() =>
                  navigateWorkspace(selectedPurchaseLines.project_workspace.id, {
                    name: "purchase_lines"
                  })
                }
                type="button"
              >
                Purchase Lines
              </button>
              <button
                role="tab"
                aria-selected={workspaceRoute.name === "upload_review"}
                onClick={() =>
                  navigateWorkspace(selectedPurchaseLines.project_workspace.id, {
                    name: "upload_review"
                  })
                }
                type="button"
              >
                Upload / Review
              </button>
            </div>

            {workspaceRoute.name === "upload_review" ? (
              <>
                <form
                  className="manual-source-form"
                  onSubmit={(event) => void handleCreateManualSourceEntry(event)}
                >
              <h3>Create Manual Source Entry</h3>
              <div className="segmented-control" aria-label="Manual Source Entry mode">
                <button
                  aria-pressed={manualEntryMode === "structured_row"}
                  className={manualEntryMode === "structured_row" ? "active" : ""}
                  onClick={() => setManualEntryMode("structured_row")}
                  type="button"
                >
                  Structured Row
                </button>
                <button
                  aria-pressed={manualEntryMode === "free_form_text"}
                  className={manualEntryMode === "free_form_text" ? "active" : ""}
                  onClick={() => setManualEntryMode("free_form_text")}
                  type="button"
                >
                  Free-Form Text
                </button>
              </div>

              {manualEntryMode === "structured_row" ? (
                <>
                  <div className="form-grid three-columns">
                    <label>
                      Line type
                      <select
                        value={manualSourceForm.lineType}
                        onChange={(event) =>
                          updateManualSourceForm(
                            "lineType",
                            event.target.value as ManualSourceForm["lineType"]
                          )
                        }
                      >
                        <option value="material">Material</option>
                        <option value="service">Service</option>
                      </select>
                    </label>
                    <label>
                      Item or service name
                      <input
                        required
                        value={manualSourceForm.name}
                        onChange={(event) => updateManualSourceForm("name", event.target.value)}
                      />
                    </label>
                    <label>
                      Quantity
                      <input
                        value={manualSourceForm.quantity}
                        onChange={(event) => updateManualSourceForm("quantity", event.target.value)}
                      />
                    </label>
                  </div>
                  <div className="form-grid three-columns">
                    <label>
                      Unit
                      <input
                        value={manualSourceForm.unit}
                        onChange={(event) => updateManualSourceForm("unit", event.target.value)}
                      />
                    </label>
                    <label>
                      Price
                      <input
                        value={manualSourceForm.price}
                        onChange={(event) => updateManualSourceForm("price", event.target.value)}
                      />
                    </label>
                    <label>
                      Provider
                      <input
                        value={manualSourceForm.providerName}
                        onChange={(event) =>
                          updateManualSourceForm("providerName", event.target.value)
                        }
                      />
                    </label>
                  </div>
                  <div className="form-grid">
                    <label>
                      Purchase date
                      <input
                        type="date"
                        value={manualSourceForm.purchaseDate}
                        onChange={(event) =>
                          updateManualSourceForm("purchaseDate", event.target.value)
                        }
                      />
                    </label>
                    <label>
                      Remarks or terms
                      <input
                        value={manualSourceForm.remarksOrTerms}
                        onChange={(event) =>
                          updateManualSourceForm("remarksOrTerms", event.target.value)
                        }
                      />
                    </label>
                  </div>
                </>
              ) : (
                <label>
                  Free-form source text
                  <textarea
                    required
                    rows={5}
                    value={freeFormText}
                    onChange={(event) => setFreeFormText(event.target.value)}
                  />
                </label>
              )}
              <button
                className="primary-action compact-action"
                disabled={isSubmittingManualSource}
                type="submit"
              >
                <Upload aria-hidden="true" size={18} />
                Create Manual Source Entry
              </button>
            </form>

            <section className="processing-job-queue" aria-label="Processing Job queue">
              <div className="view-heading">
                <p className="eyebrow">Processing Jobs</p>
                <h3>Job / Review Queue</h3>
              </div>
              {processingJobs.length === 0 ? (
                <p className="status-message">No Processing Jobs yet</p>
              ) : (
                <ul className="job-queue-list">
                  {processingJobs.map((item) => (
                    <li className="job-queue-item" key={item.processing_job.id}>
                      <div>
                        <p className="eyebrow">{item.processing_job.status}</p>
                        <h4>{formatSourceType(item.processing_job.source_type)}</h4>
                        <p>
                          Candidates: {item.processing_job.candidate_count} | Review Batch:{" "}
                          {item.review_batch_id ?? "Not ready"}
                        </p>
                        {item.processing_job.error_message ? (
                          <p className="status-message error">
                            {item.processing_job.error_message}
                          </p>
                        ) : null}
                      </div>
                      {item.processing_job.status === "review_ready" && item.review_batch_id ? (
                        <button
                          className="secondary-action"
                          onClick={() => {
                            if (item.review_batch_id !== null) {
                              void handleOpenReviewBatch(item.review_batch_id);
                            }
                          }}
                          type="button"
                        >
                          Open Review Batch
                        </button>
                      ) : null}
                    </li>
                  ))}
                </ul>
                )}
              </section>
              </>
            ) : null}

            {workspaceRoute.name === "review_batch" && activeReviewBatch ? (
              <section className="review-batch-page" aria-label="Review Batch">
                <button
                  className="secondary-action"
                  onClick={() =>
                    navigateWorkspace(selectedPurchaseLines.project_workspace.id, {
                      name: "upload_review"
                    })
                  }
                  type="button"
                >
                  Back to Upload / Review
                </button>
                <div className="view-heading">
                  <p className="eyebrow">{activeReviewBatch.review_batch.status}</p>
                  <h3>Review Batch #{activeReviewBatch.review_batch.id}</h3>
                </div>
                {toastMessage ? <p className="toast-message">{toastMessage}</p> : null}
                <div className="review-batch-actions">
                  <button
                    className="secondary-action"
                    onClick={() => void handleSaveReviewDraft()}
                    type="button"
                  >
                    Save
                  </button>
                  <button
                    className="primary-action compact-action"
                    disabled={isImportingBatch}
                    onClick={() => void handleImportIncludedCandidates()}
                    type="button"
                  >
                    Import Included Candidates
                  </button>
                </div>
                <table className="candidate-table">
                  <thead>
                    <tr>
                      <th>Include</th>
                      <th>Candidate</th>
                      <th>Type</th>
                      <th>Category</th>
                      <th>Status</th>
                      <th>Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeReviewBatch.candidates.map((candidate) => {
                      const draft = candidateDrafts[candidate.id] ?? {
                        included: true,
                        reviewedPayload: reviewedPayloadForCandidate(candidate)
                      };
                      const reviewedPayload =
                        draft.reviewedPayload ?? reviewedPayloadForCandidate(candidate);
                      const candidateName =
                        reviewedPayload.name ??
                        displayText(candidate.proposed_payload.name, "candidate");
                      const candidateType =
                        reviewedPayload.line_type ??
                        displayText(candidate.proposed_payload.line_type, "");
                      return (
                        <tr key={candidate.id}>
                          <td>
                            <input
                              aria-label={`Include ${candidateName}`}
                              checked={draft.included}
                              onChange={(event) =>
                                updateCandidateIncluded(candidate, event.target.checked)
                              }
                              type="checkbox"
                            />
                          </td>
                          <td>{candidateName}</td>
                          <td>{candidateType}</td>
                          <td>
                            {reviewedPayload.top_level_category && reviewedPayload.subcategory
                              ? `${reviewedPayload.top_level_category} / ${reviewedPayload.subcategory}`
                              : "Needs taxonomy"}
                          </td>
                          <td>{draft.included ? "Included draft" : "Excluded draft"}</td>
                          <td>
                            <button
                              className="secondary-action"
                              onClick={() => setDetailCandidateId(candidate.id)}
                              type="button"
                            >
                              Details
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </section>
            ) : null}

            {workspaceRoute.name === "review_batch" && detailCandidate ? (
              <div
                aria-label="Candidate Detail"
                aria-modal="true"
                className="modal-backdrop"
                role="dialog"
              >
                <section className="modal-panel">
                  {(() => {
                    const draft = candidateDrafts[detailCandidate.id] ?? {
                      included: true,
                      reviewedPayload: reviewedPayloadForCandidate(detailCandidate)
                    };
                    const reviewedPayload =
                      draft.reviewedPayload ?? reviewedPayloadForCandidate(detailCandidate);
                    const candidateName =
                      reviewedPayload.name ??
                      displayText(detailCandidate.proposed_payload.name, "candidate");
                    const candidateType =
                      reviewedPayload.line_type ??
                      displayText(detailCandidate.proposed_payload.line_type, "");
                    const providerName =
                      reviewedPayload.provider_name ??
                      displayText(
                        detailCandidate.proposed_payload.provider_name,
                        "Unknown provider"
                      );
                    const suggestion = taxonomySuggestion(detailCandidate);
                    const proposedCategory =
                      suggestion?.topLevelCategory && suggestion.subcategory
                        ? `${suggestion.topLevelCategory} / ${suggestion.subcategory}`
                        : "No complete taxonomy suggestion";
                    const reviewedCategory =
                      reviewedPayload.top_level_category && reviewedPayload.subcategory
                        ? `${reviewedPayload.top_level_category} / ${reviewedPayload.subcategory}`
                        : "Needs taxonomy";
                    return (
                      <>
                        <div className="view-heading">
                          <p className="eyebrow">{detailCandidate.status}</p>
                          <h3>Candidate Detail</h3>
                        </div>
                        <dl className="candidate-detail-list">
                          <div>
                            <dt>Inclusion</dt>
                            <dd>{draft.included ? "Included draft" : "Excluded draft"}</dd>
                          </div>
                          <div>
                            <dt>Source Evidence</dt>
                            <dd>Source Submission #{detailCandidate.source_submission_id}</dd>
                          </div>
                          <div>
                            <dt>Taxonomy Status</dt>
                            <dd>
                              {reviewedPayload.top_level_category && reviewedPayload.subcategory
                                ? "AI suggested default"
                                : "Needs taxonomy"}
                            </dd>
                          </div>
                          <div>
                            <dt>Name</dt>
                            <dd>{candidateName}</dd>
                          </div>
                          <div>
                            <dt>Type</dt>
                            <dd>{candidateType}</dd>
                          </div>
                          <div>
                            <dt>Category</dt>
                            <dd>{reviewedCategory}</dd>
                          </div>
                          <div>
                            <dt>Provider</dt>
                            <dd>{providerName}</dd>
                          </div>
                        </dl>
                        <div className="candidate-detail-sections">
                          <section>
                            <h4>Proposed Fields</h4>
                            <p>{displayText(detailCandidate.proposed_payload.name, "candidate")}</p>
                            <p>{proposedCategory}</p>
                          </section>
                          <section>
                            <h4>Reviewed Fields</h4>
                            <p>{candidateName}</p>
                            <p>{reviewedCategory}</p>
                          </section>
                        </div>
                        <div className="review-actions">
                          <button
                            className="secondary-action"
                            onClick={() => openTaxonomyDialog(detailCandidate)}
                            type="button"
                          >
                            Change Taxonomy
                          </button>
                          <button
                            className="secondary-action"
                            onClick={() => setDetailCandidateId(null)}
                            type="button"
                          >
                            Close
                          </button>
                        </div>
                      </>
                    );
                  })()}
                </section>
              </div>
            ) : null}

            {workspaceRoute.name === "review_batch" && taxonomyCandidate ? (
              <div
                aria-label="Resolve Taxonomy"
                aria-modal="true"
                className="modal-backdrop"
                role="dialog"
              >
                <form
                  className="modal-panel"
                  onSubmit={(event) => void handleSaveTaxonomyMapping(event)}
                >
                  <div className="view-heading">
                    <p className="eyebrow">
                      {displayText(taxonomyCandidate.proposed_payload.name, "candidate")}
                    </p>
                    <h3>Resolve Taxonomy</h3>
                  </div>
                  <label>
                    Top-Level Category
                    <input
                      required
                      value={taxonomyForm.topLevelCategory}
                      onChange={(event) =>
                        updateTaxonomyForm("topLevelCategory", event.target.value)
                      }
                    />
                  </label>
                  <label>
                    Subcategory
                    <input
                      required
                      value={taxonomyForm.subcategory}
                      onChange={(event) =>
                        updateTaxonomyForm("subcategory", event.target.value)
                      }
                    />
                  </label>
                  <label className="checkbox-label">
                    <input
                      checked={taxonomyForm.applyToSimilar}
                      onChange={(event) =>
                        updateTaxonomyForm("applyToSimilar", event.target.checked)
                      }
                      type="checkbox"
                    />
                    Apply to similar taxonomy in this Review Batch
                  </label>
                  <div className="review-actions">
                    <button
                      className="primary-action compact-action"
                      disabled={isApprovingCandidate}
                      type="submit"
                    >
                      Save Mapping
                    </button>
                    <button
                      className="secondary-action"
                      onClick={() => setTaxonomyCandidateId(null)}
                      type="button"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </div>
            ) : null}

            {workspaceRoute.name === "purchase_lines" ? (
              selectedPurchaseLines.items.length === 0 ? (
                <div className="empty-state">
                  <h3>No Purchase Lines yet</h3>
                </div>
              ) : (
                <div className="purchase-lines-table-wrap">
                  <table className="purchase-lines-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Type</th>
                        <th>Provider</th>
                        <th>Quantity</th>
                        <th>Price</th>
                        <th>Date</th>
                        <th>Category</th>
                        <th>Evidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedPurchaseLines.items.map((purchaseLine) => (
                        <tr key={purchaseLine.id}>
                          <td>{purchaseLine.item_or_service_name}</td>
                          <td>{purchaseLine.line_type}</td>
                          <td>{purchaseLine.provider_name ?? "Unknown provider"}</td>
                          <td>
                            {purchaseLine.quantity ?? "Unknown"} {purchaseLine.unit ?? ""}
                            {purchaseLine.unit_state === "unknown" ? " Unknown unit" : ""}
                          </td>
                          <td>
                            {purchaseLine.price
                              ? `${purchaseLine.currency ?? ""} ${purchaseLine.price}`.trim()
                              : "Unknown price"}
                          </td>
                          <td>{purchaseLine.purchase_date ?? "Unknown date"}</td>
                          <td>{purchaseLine.category_path}</td>
                          <td>
                            {purchaseLine.has_evidence ? purchaseLine.source_label : "No evidence"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            ) : null}
          </>
        ) : (
          <div className="empty-state">
            <h2>Select a Project Workspace</h2>
          </div>
        )}
      </section>
    </main>
  );
}

function buildCreatePayload(form: ProjectWorkspaceForm): ProjectWorkspaceCreate {
  return {
    project_name: form.projectName.trim(),
    project_type: form.projectType.trim(),
    location: form.location.trim(),
    completion_date: form.completionDate || null,
    completion_year: form.completionYear ? Number(form.completionYear) : null,
    floor_area: optionalText(form.floorArea),
    trade_scopes: form.tradeScopes
      .split(",")
      .map((scope) => scope.trim())
      .filter(Boolean),
    client_or_owner: optionalText(form.clientOrOwner),
    notes: optionalText(form.notes)
  };
}

function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function displayText(value: unknown, fallback: string): string {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : fallback;
  }
  return value === null || value === undefined ? fallback : String(value);
}

function buildManualSourcePayload(
  form: ManualSourceForm,
  mode: ManualEntryMode,
  originalText: string
): ManualSourceEntryCreate {
  if (mode === "free_form_text") {
    return {
      entry_type: "free_form_text",
      original_text: originalText
    };
  }

  return {
    entry_type: "structured_row",
    structured_payload: {
      line_type: form.lineType,
      name: form.name.trim(),
      quantity: optionalText(form.quantity),
      unit: optionalText(form.unit),
      price: optionalText(form.price),
      currency: optionalText(form.currency),
      provider_name: optionalText(form.providerName),
      purchase_date: form.purchaseDate || null,
      remarks_or_terms: optionalText(form.remarksOrTerms)
    }
  };
}

function buildReviewForm(
  reviewBatchDetail: ReviewBatchDetail,
  fallbackForm: ManualSourceForm
): ReviewForm | null {
  const proposedPayload = reviewBatchDetail.candidates[0]?.proposed_payload;
  const taxonomyDefault = reviewBatchDetail.candidates[0]?.taxonomy_default;
  if (!proposedPayload) {
    return null;
  }
  const defaultPath = splitCategoryPath(taxonomyDefault?.resolved_category_path ?? null);

  return {
    lineType:
      proposedPayload.line_type === "service" || proposedPayload.line_type === "material"
        ? proposedPayload.line_type
        : fallbackForm.lineType,
    name: String(proposedPayload.name ?? fallbackForm.name),
    quantity: String(proposedPayload.quantity ?? fallbackForm.quantity ?? ""),
    unit: String(proposedPayload.unit ?? fallbackForm.unit ?? ""),
    price: String(proposedPayload.price ?? fallbackForm.price ?? ""),
    currency: String(proposedPayload.currency ?? fallbackForm.currency ?? ""),
    providerName: String(proposedPayload.provider_name ?? fallbackForm.providerName ?? ""),
    purchaseDate: String(proposedPayload.purchase_date ?? fallbackForm.purchaseDate ?? ""),
    remarksOrTerms: String(proposedPayload.remarks_or_terms ?? fallbackForm.remarksOrTerms ?? ""),
    topLevelCategory: defaultPath?.topLevelCategory ?? "",
    subcategory: defaultPath?.subcategory ?? ""
  };
}

function formatSourceType(sourceType: string): string {
  return sourceType
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function buildReviewedPayload(form: ReviewForm): ReviewedPurchaseLinePayload {
  return {
    line_type: form.lineType,
    name: form.name.trim(),
    top_level_category: optionalText(form.topLevelCategory),
    subcategory: optionalText(form.subcategory),
    quantity: optionalText(form.quantity),
    unit: optionalText(form.unit),
    price: optionalText(form.price),
    currency: optionalText(form.currency),
    provider_name: optionalText(form.providerName),
    purchase_date: form.purchaseDate || null,
    remarks_or_terms: optionalText(form.remarksOrTerms)
  };
}

function reviewedPayloadForCandidate(candidate: ExtractedCandidateRead): ReviewedPurchaseLinePayload {
  const reviewedPayload = candidate.reviewed_payload as ReviewedPurchaseLinePayload | null;
  if (reviewedPayload) {
    return reviewedPayload;
  }
  const proposedPayload = candidate.proposed_payload;
  const suggestion = taxonomySuggestion(candidate);
  return {
    line_type:
      proposedPayload.line_type === "service" || proposedPayload.line_type === "material"
        ? proposedPayload.line_type
        : "material",
    name: String(proposedPayload.name ?? ""),
    top_level_category: suggestion?.topLevelCategory ?? null,
    subcategory: suggestion?.subcategory ?? null,
    quantity: optionalText(String(proposedPayload.quantity ?? "")),
    unit: optionalText(String(proposedPayload.unit ?? "")),
    price: optionalText(String(proposedPayload.price ?? "")),
    currency: optionalText(String(proposedPayload.currency ?? "")),
    provider_name: optionalText(String(proposedPayload.provider_name ?? "")),
    purchase_date:
      typeof proposedPayload.purchase_date === "string" ? proposedPayload.purchase_date : null,
    remarks_or_terms: optionalText(String(proposedPayload.remarks_or_terms ?? ""))
  };
}

function initialDraftsForCandidates(
  candidates: ExtractedCandidateRead[]
): Record<number, CandidateDraft> {
  return Object.fromEntries(
    candidates.map((candidate) => [
      candidate.id,
      {
        included: candidate.decision !== "rejected",
        reviewedPayload:
          candidate.decision === "rejected" ? null : reviewedPayloadForCandidate(candidate)
      }
    ])
  );
}

function taxonomySuggestion(candidate: ExtractedCandidateRead | null):
  | { topLevelCategory: string; subcategory: string | null }
  | null {
  const suggestion = candidate?.proposed_payload?.category_suggestion;
  if (!suggestion || typeof suggestion !== "object") {
    return null;
  }
  const topLevelCategory = (suggestion as { top_level_category?: unknown }).top_level_category;
  const subcategory = (suggestion as { subcategory?: unknown }).subcategory;
  if (typeof topLevelCategory !== "string" || topLevelCategory.trim() === "") {
    return null;
  }
  return {
    topLevelCategory,
    subcategory: typeof subcategory === "string" ? subcategory : null
  };
}

function splitCategoryPath(
  categoryPath: string | null
): { topLevelCategory: string; subcategory: string } | null {
  if (!categoryPath) {
    return null;
  }
  const [topLevelCategory, subcategory] = categoryPath.split(" / ");
  if (!topLevelCategory || !subcategory) {
    return null;
  }
  return { topLevelCategory, subcategory };
}

export default App;
