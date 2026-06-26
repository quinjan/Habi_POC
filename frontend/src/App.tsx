import { FormEvent, useEffect, useMemo, useState } from "react";
import { Check, FolderOpen, Plus, Upload } from "lucide-react";

import {
  createProjectWorkspace,
  createManualSourceEntry,
  decideCandidate,
  getProjectWorkspacePurchaseLines,
  importReviewBatch,
  listProjectWorkspaces,
  type ManualSourceEntrySubmission,
  type ManualSourceEntryCreate,
  type ProjectWorkspaceCreate,
  type ProjectWorkspaceListItem,
  type ProjectWorkspacePurchaseLinesView,
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
  const [pendingSubmission, setPendingSubmission] =
    useState<ManualSourceEntrySubmission | null>(null);
  const [reviewForm, setReviewForm] = useState<ReviewForm | null>(null);
  const [isLoadingProjects, setIsLoadingProjects] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isSubmittingManualSource, setIsSubmittingManualSource] = useState(false);
  const [isApprovingCandidate, setIsApprovingCandidate] = useState(false);
  const [isImportingBatch, setIsImportingBatch] = useState(false);
  const [isCandidateApproved, setIsCandidateApproved] = useState(false);
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
      setPendingSubmission(null);
      setReviewForm(null);
      setFreeFormText("");
      setManualEntryMode("structured_row");
      setIsCandidateApproved(false);
      window.history.pushState({}, "", `/projects/${project.id}/purchase-lines`);
    } catch {
      setErrorMessage("Purchase Lines could not be loaded.");
    }
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
      const submission = await createManualSourceEntry(
        selectedPurchaseLines.project_workspace.id,
        buildManualSourcePayload(manualSourceForm, manualEntryMode, freeFormText)
      );
      setPendingSubmission(submission);
      setReviewForm(buildReviewForm(submission, manualSourceForm));
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

  async function handleApproveCandidate() {
    const candidate = pendingSubmission?.candidates[0] ?? null;
    if (
      selectedPurchaseLines === null ||
      pendingSubmission === null ||
      pendingSubmission.review_batch === null ||
      candidate === null ||
      reviewForm === null
    ) {
      return;
    }

    setIsApprovingCandidate(true);
    setErrorMessage(null);

    try {
      await decideCandidate(
        selectedPurchaseLines.project_workspace.id,
        pendingSubmission.review_batch.id,
        candidate.id,
        {
          decision: "approved",
          reviewed_payload: buildReviewedPayload(reviewForm)
        }
      );
      setIsCandidateApproved(true);
    } catch {
      setErrorMessage("Candidate could not be approved.");
    } finally {
      setIsApprovingCandidate(false);
    }
  }

  async function handleImportBatch() {
    if (
      selectedPurchaseLines === null ||
      pendingSubmission === null ||
      pendingSubmission.review_batch === null
    ) {
      return;
    }

    setIsImportingBatch(true);
    setErrorMessage(null);

    try {
      await importReviewBatch(
        selectedPurchaseLines.project_workspace.id,
        pendingSubmission.review_batch.id
      );
      const refreshedPurchaseLines = await getProjectWorkspacePurchaseLines(
        selectedPurchaseLines.project_workspace.id
      );
      setSelectedPurchaseLines(refreshedPurchaseLines);
      setPendingSubmission(null);
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

            {pendingSubmission ? (
              <section className="processing-status" aria-label="Processing Job outcome">
                <p className="eyebrow">{pendingSubmission.processing_job.status}</p>
                <h3>
                  {pendingSubmission.processing_job.status === "no_candidates_found"
                    ? "No candidates found"
                    : "Processing Job"}
                </h3>
              </section>
            ) : null}

            {pendingSubmission?.review_batch && pendingSubmission.candidates[0] && reviewForm ? (
              <section className="review-panel" aria-label="Review Candidate panel">
                <div className="view-heading">
                  <p className="eyebrow">{pendingSubmission.review_batch.status}</p>
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
  submission: ManualSourceEntrySubmission,
  fallbackForm: ManualSourceForm
): ReviewForm | null {
  const proposedPayload = submission.candidates[0]?.proposed_payload;
  if (!proposedPayload) {
    return null;
  }

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
    topLevelCategory: "",
    subcategory: ""
  };
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

export default App;
