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
      setReviewForm(null);
      setFreeFormText("");
      setManualEntryMode("structured_row");
      setIsCandidateApproved(false);
      window.history.pushState({}, "", `/projects/${project.id}/purchase-lines`);
    } catch {
      setErrorMessage("Purchase Lines could not be loaded.");
    }
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
      setReviewForm(buildReviewForm(detail, manualSourceForm));
      setSelectedTaxonomyNodeId("");
      setIsCandidateApproved(false);
    } catch {
      setErrorMessage("Review Batch could not be loaded.");
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
      setIsCandidateApproved(false);
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
              <h2>Purchase Lines</h2>
            </div>
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

            {activeReviewBatch && activeReviewBatch.candidates[0] && reviewForm ? (
              <section className="review-panel" aria-label="Review Candidate panel">
                <div className="view-heading">
                  <p className="eyebrow">{activeReviewBatch.review_batch.status}</p>
                  <h3>Review Candidate</h3>
                </div>
                <div className="form-grid three-columns">
                  <label>
                    Item or service name
                    <input
                      value={reviewForm.name}
                      onChange={(event) => updateReviewForm("name", event.target.value)}
                    />
                  </label>
                  <label>
                    Top-level category
                    <input
                      value={reviewForm.topLevelCategory}
                      onChange={(event) =>
                        updateReviewForm("topLevelCategory", event.target.value)
                      }
                    />
                  </label>
                  <label>
                    Subcategory
                    <input
                      value={reviewForm.subcategory}
                      onChange={(event) => updateReviewForm("subcategory", event.target.value)}
                    />
                  </label>
                </div>
                {activeReviewBatch.candidates[0].taxonomy_default ? (
                  <p className="taxonomy-note">
                    {activeReviewBatch.candidates[0].taxonomy_default.provenance_text}
                  </p>
                ) : null}
                {activeReviewBatch.candidates[0].taxonomy_gate ? (
                  <div className="taxonomy-gate" aria-label="Taxonomy Gate" role="group">
                    <p className="eyebrow">{activeReviewBatch.candidates[0].taxonomy_gate.status}</p>
                    <p>
                      {activeReviewBatch.candidates[0].taxonomy_gate.suggested_category_path}
                    </p>
                    {activeReviewBatch.candidates[0].taxonomy_gate.prior_rejection ? (
                      <p className="taxonomy-warning">
                        Previously rejected for this Project Workspace.
                      </p>
                    ) : null}
                    {activeReviewBatch.candidates[0].taxonomy_gate.resolved_category_path ? (
                      <p>
                        Resolved to{" "}
                        {activeReviewBatch.candidates[0].taxonomy_gate.resolved_category_path}
                      </p>
                    ) : null}
                    <div className="taxonomy-actions">
                      <button
                        className="secondary-action"
                        disabled={isApprovingCandidate}
                        onClick={() => void handleTaxonomyDecision("approved")}
                        type="button"
                      >
                        <Check aria-hidden="true" size={18} />
                        Approve Taxonomy
                      </button>
                      <label>
                        Map to existing path
                        <select
                          value={selectedTaxonomyNodeId}
                          onChange={(event) => setSelectedTaxonomyNodeId(event.target.value)}
                        >
                          <option value="">Choose path</option>
                          {taxonomyLeafPaths.map((path) => (
                            <option key={path.id} value={path.id}>
                              {path.path}
                            </option>
                          ))}
                        </select>
                      </label>
                      <button
                        className="secondary-action"
                        disabled={isApprovingCandidate}
                        onClick={() => void handleTaxonomyDecision("mapped")}
                        type="button"
                      >
                        <GitBranch aria-hidden="true" size={18} />
                        Map Taxonomy
                      </button>
                      <button
                        className="secondary-action"
                        disabled={isApprovingCandidate}
                        onClick={() => void handleTaxonomyDecision("rejected")}
                        type="button"
                      >
                        <X aria-hidden="true" size={18} />
                        Reject Taxonomy
                      </button>
                    </div>
                  </div>
                ) : null}
                <div className="review-actions">
                  <button
                    className="primary-action compact-action"
                    disabled={isApprovingCandidate}
                    onClick={() => void handleApproveCandidate()}
                    type="button"
                  >
                    <Check aria-hidden="true" size={18} />
                    Approve Candidate
                  </button>
                  <button
                    className="secondary-action"
                    disabled={isApprovingCandidate}
                    onClick={() => void handleRejectCandidate()}
                    type="button"
                  >
                    <X aria-hidden="true" size={18} />
                    Remove from Import
                  </button>
                  <button
                    className="secondary-action"
                    disabled={!isCandidateApproved || isImportingBatch}
                    onClick={() => void handleImportBatch()}
                    type="button"
                  >
                    Import Approved Batch
                  </button>
                </div>
              </section>
            ) : null}

            {selectedPurchaseLines.items.length === 0 ? (
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
                        <td>{purchaseLine.has_evidence ? purchaseLine.source_label : "No evidence"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
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
