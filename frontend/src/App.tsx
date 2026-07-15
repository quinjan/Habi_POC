import { FormEvent, useEffect, useMemo, useState } from "react";
import { Check, FolderOpen, GitBranch, Plus, Upload, X } from "lucide-react";

import {
  createProjectWorkspace,
  createSourceFile,
  createTaxonomyDecision,
  createManualSourceEntry,
  decideCandidate,
  getReviewBatch,
  getProjectWorkspaceMaterials,
  getProjectWorkspacePurchaseLines,
  getProjectWorkspaceProviders,
  getProjectWorkspaceServices,
  importReviewBatch,
  listProcessingJobs,
  listTaxonomyLeafPaths,
  listProjectWorkspaces,
  saveReviewBatchDraft,
  saveReviewBatchTaxonomyMapping,
  type ExtractedCandidateRead,
  type EntityMemoryListView,
  type ManualSourceEntryCreate,
  type ProcessingJobListItem,
  type ProjectWorkspaceCreate,
  type ProjectWorkspaceListItem,
  type ProjectWorkspacePurchaseLinesView,
  type ProviderMemoryListView,
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
  contractorAssigned: string;
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
  contractorAssigned: "",
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

type CandidateTaxonomyGate = NonNullable<ExtractedCandidateRead["taxonomy_gates"]>[number];

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

const MAX_XLSX_UPLOAD_BYTES = 25 * 1024 * 1024;

type ReviewForm = ManualSourceForm & {
  topLevelCategory: string;
  subcategory: string;
};

type WorkspaceRoute =
  | { name: "purchase_lines" }
  | { name: "materials" }
  | { name: "services" }
  | { name: "providers" }
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
  const [entityMemory, setEntityMemory] = useState<
    EntityMemoryListView | ProviderMemoryListView | null
  >(null);
  const [selectedProviderRoles, setSelectedProviderRoles] = useState<string[]>([]);
  const [form, setForm] = useState<ProjectWorkspaceForm>(emptyForm);
  const [manualSourceForm, setManualSourceForm] =
    useState<ManualSourceForm>(emptyManualSourceForm);
  const [manualEntryMode, setManualEntryMode] = useState<ManualEntryMode>("structured_row");
  const [freeFormText, setFreeFormText] = useState("");
  const [selectedXlsxFile, setSelectedXlsxFile] = useState<File | null>(null);
  const [xlsxValidationMessage, setXlsxValidationMessage] = useState<string | null>(null);
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
  const [similarMappingConfirmation, setSimilarMappingConfirmation] = useState<{
    affectedCount: number;
  } | null>(null);
  const [reviewForm, setReviewForm] = useState<ReviewForm | null>(null);
  const [isLoadingProjects, setIsLoadingProjects] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isSubmittingManualSource, setIsSubmittingManualSource] = useState(false);
  const [isUploadingXlsx, setIsUploadingXlsx] = useState(false);
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
  const selectedExistingTaxonomyPath = taxonomyLeafPaths.find(
    (path) => path.path === `${taxonomyForm.topLevelCategory} / ${taxonomyForm.subcategory}`
  )?.path ?? "";

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
      setEntityMemory(null);
      setSelectedProviderRoles([]);
      await refreshTaxonomyLeafPaths(project.id);
      setActiveReviewBatch(null);
      setCandidateDrafts({});
      setDetailCandidateId(null);
      setTaxonomyCandidateId(null);
      setSimilarMappingConfirmation(null);
      setReviewForm(null);
      setFreeFormText("");
      setSelectedXlsxFile(null);
      setXlsxValidationMessage(null);
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
        : route.name === "materials" || route.name === "services" || route.name === "providers"
          ? `/projects/${projectId}/${route.name}`
        : route.name === "upload_review"
          ? `/projects/${projectId}/upload-review`
          : `/projects/${projectId}/review-batches/${route.reviewBatchId}`;
    window.history.pushState({}, "", path);
  }

  async function handleMemoryTab(route: "materials" | "services" | "providers") {
    if (selectedPurchaseLines === null) {
      return;
    }
    const projectId = selectedPurchaseLines.project_workspace.id;
    setErrorMessage(null);
    try {
      const response =
        route === "materials"
          ? await getProjectWorkspaceMaterials(projectId)
          : route === "services"
            ? await getProjectWorkspaceServices(projectId)
            : await getProjectWorkspaceProviders(projectId, selectedProviderRoles);
      setEntityMemory(response);
      navigateWorkspace(projectId, { name: route });
    } catch {
      setErrorMessage(`${route[0].toUpperCase()}${route.slice(1)} could not be loaded.`);
    }
  }

  async function handleProviderRoleChange(role: string, checked: boolean) {
    if (selectedPurchaseLines === null) {
      return;
    }
    const roles = checked
      ? [...selectedProviderRoles, role]
      : selectedProviderRoles.filter((selectedRole) => selectedRole !== role);
    setSelectedProviderRoles(roles);
    try {
      setEntityMemory(
        await getProjectWorkspaceProviders(selectedPurchaseLines.project_workspace.id, roles)
      );
    } catch {
      setErrorMessage("Providers could not be loaded.");
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
      setCandidateDrafts({});
      setDetailCandidateId(null);
      setTaxonomyCandidateId(null);
      setSimilarMappingConfirmation(null);
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

  function handleXlsxSelection(files: FileList | null) {
    setXlsxValidationMessage(null);
    setSelectedXlsxFile(null);
    if (files === null || files.length !== 1) {
      setXlsxValidationMessage("Choose exactly one .xlsx file.");
      return;
    }
    const file = files[0];
    if (!file.name.toLowerCase().endsWith(".xlsx")) {
      setXlsxValidationMessage("Only .xlsx source files are supported.");
      return;
    }
    if (file.size > MAX_XLSX_UPLOAD_BYTES) {
      setXlsxValidationMessage("The selected workbook exceeds the 25 MiB upload limit.");
      return;
    }
    setSelectedXlsxFile(file);
  }

  async function handleXlsxUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (selectedPurchaseLines === null || selectedXlsxFile === null) {
      setXlsxValidationMessage("Choose exactly one .xlsx file.");
      return;
    }
    setIsUploadingXlsx(true);
    setErrorMessage(null);
    try {
      await createSourceFile(
        selectedPurchaseLines.project_workspace.id,
        selectedXlsxFile
      );
      await refreshProcessingJobs(selectedPurchaseLines.project_workspace.id);
      setSelectedXlsxFile(null);
      setXlsxValidationMessage(null);
      form.reset();
    } catch {
      setXlsxValidationMessage("The workbook could not be uploaded. Check the file and try again.");
    } finally {
      setIsUploadingXlsx(false);
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
      setSimilarMappingConfirmation(null);
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

  function updateCandidateReviewedPayload(
    candidate: ExtractedCandidateRead,
    update: (payload: ReviewedPurchaseLinePayload) => ReviewedPurchaseLinePayload
  ) {
    setCandidateDrafts((currentDrafts) => {
      const currentDraft = currentDrafts[candidate.id] ?? {
        included: true,
        reviewedPayload: reviewedPayloadForCandidate(candidate)
      };
      return {
        ...currentDrafts,
        [candidate.id]: {
          ...currentDraft,
          reviewedPayload: update(
            currentDraft.reviewedPayload ?? reviewedPayloadForCandidate(candidate)
          )
        }
      };
    });
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
    setSimilarMappingConfirmation(null);
    setTaxonomyCandidateId(candidate.id);
  }

  function updateTaxonomyForm(field: keyof TaxonomyForm, value: string | boolean) {
    setTaxonomyForm((currentForm) => ({ ...currentForm, [field]: value }));
    setSimilarMappingConfirmation(null);
  }

  function handleExistingTaxonomyPathChange(path: string) {
    const categoryPath = splitCategoryPath(path);
    if (categoryPath === null) {
      return;
    }
    setTaxonomyForm((currentForm) => ({
      ...currentForm,
      topLevelCategory: categoryPath.topLevelCategory,
      subcategory: categoryPath.subcategory
    }));
    setSimilarMappingConfirmation(null);
  }

  async function handleSaveTaxonomyMapping(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      activeReviewBatch !== null &&
      taxonomyCandidate !== null &&
      taxonomyForm.applyToSimilar &&
      similarMappingConfirmation === null
    ) {
      setSimilarMappingConfirmation({
        affectedCount: countSimilarTaxonomyCandidates(activeReviewBatch, taxonomyCandidate)
      });
      return;
    }

    await saveTaxonomyMapping();
  }

  async function saveTaxonomyMapping() {
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
      setSimilarMappingConfirmation(null);
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

  async function handleTaxonomyDecision(
    gate: CandidateTaxonomyGate,
    decision: "approved" | "mapped" | "rejected"
  ) {
    const suggestion = splitCategoryPath(gate.suggested_category_path);
    if (
      selectedPurchaseLines === null ||
      activeReviewBatch === null ||
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
            Contractor Assigned
            <input
              required
              value={form.contractorAssigned}
              onChange={(event) => updateForm("contractorAssigned", event.target.value)}
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
              {workspaceRoute.name === "materials" ? <h2>Materials</h2> : null}
              {workspaceRoute.name === "services" ? <h2>Services</h2> : null}
              {workspaceRoute.name === "providers" ? <h2>Providers</h2> : null}
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
                aria-selected={workspaceRoute.name === "materials"}
                onClick={() => void handleMemoryTab("materials")}
                type="button"
              >
                Materials
              </button>
              <button
                role="tab"
                aria-selected={workspaceRoute.name === "services"}
                onClick={() => void handleMemoryTab("services")}
                type="button"
              >
                Services
              </button>
              <button
                role="tab"
                aria-selected={workspaceRoute.name === "providers"}
                onClick={() => void handleMemoryTab("providers")}
                type="button"
              >
                Providers
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
                  className="xlsx-upload-panel"
                  onSubmit={(event) => void handleXlsxUpload(event)}
                >
                  <h3>Upload Source File</h3>
                  <aside className="upload-guidance">
                    <strong>Excel upload (XLSX only)</strong>
                    <p>
                      Upload one saved `.xlsx` file. Habi reads values from visible worksheet
                      cells and uses AI to propose reviewable purchase lines. It does not run
                      formulas or macros; save calculated values before uploading. Hidden sheets,
                      images, charts, comments, and attachments are not processed. Visible
                      worksheet cell values are sent to the configured AI extraction service for
                      processing. Nothing is added to Project Memory until you review and import it.
                    </p>
                  </aside>
                  <label>
                    Excel workbook
                    <input
                      accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                      onChange={(event) => handleXlsxSelection(event.currentTarget.files)}
                      type="file"
                    />
                  </label>
                  {selectedXlsxFile ? (
                    <p className="status-message">
                      {selectedXlsxFile.name} ({formatFileSize(selectedXlsxFile.size)})
                    </p>
                  ) : null}
                  {xlsxValidationMessage ? (
                    <p className="status-message error">{xlsxValidationMessage}</p>
                  ) : null}
                  <button
                    className="primary-action compact-action"
                    disabled={isUploadingXlsx || selectedXlsxFile === null}
                    type="submit"
                  >
                    <Upload aria-hidden="true" size={18} />
                    Upload and process
                  </button>
                </form>
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
                        <h4>
                          {item.source_file?.original_filename ??
                            formatSourceType(item.processing_job.source_type)}
                        </h4>
                        <p>Submitted {formatDateTime(item.source_submission.submitted_at)}</p>
                        <p>
                          Candidates: {item.processing_job.candidate_count} | Review Batch:{" "}
                          {item.review_batch_id ?? "Not ready"}
                        </p>
                        {diagnosticSummary(item.processing_job.diagnostics) ? (
                          <p className="status-message">
                            {diagnosticSummary(item.processing_job.diagnostics)}
                          </p>
                        ) : null}
                        {recoveryGuidance(item.processing_job.status) ? (
                          <p className="status-message">
                            {recoveryGuidance(item.processing_job.status)}
                          </p>
                        ) : null}
                        {item.processing_job.status === "failed" &&
                        item.processing_job.error_message ? (
                          <details>
                            <summary>Technical details</summary>
                            <p className="status-message error">
                              {item.processing_job.error_message}
                            </p>
                          </details>
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
                      const linkedConcepts = reviewedConcepts(reviewedPayload);
                      const candidateName = linkedConcepts
                        .map((concept) => concept.name)
                        .filter(Boolean)
                        .join(" + ") || "candidate";
                      const candidateType = linkedConcepts
                        .map((concept) => concept.concept_type)
                        .join(" + ");
                      const reviewedCategories = linkedConcepts
                        .map((concept) => categoryPath(concept.top_level_category, concept.subcategory))
                        .filter((category): category is string => category !== null);
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
                            {reviewedCategories.length === linkedConcepts.length
                              ? reviewedCategories.join("; ")
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
                    const linkedConcepts = reviewedConcepts(reviewedPayload);
                    const candidateName = linkedConcepts
                      .map((concept) => concept.name)
                      .filter(Boolean)
                      .join(" + ") || "candidate";
                    const candidateType = linkedConcepts
                      .map((concept) => concept.concept_type)
                      .join(" + ");
                    const providerState = reviewedPayload.provider_state ??
                      (reviewedPayload.provider_name ? "external" : "unknown");
                    const providerName = reviewedPayload.provider_name ?? "Unknown provider";
                    const suggestion = taxonomySuggestion(detailCandidate);
                    const proposedCategory =
                      suggestion?.topLevelCategory && suggestion.subcategory
                        ? `${suggestion.topLevelCategory} / ${suggestion.subcategory}`
                        : "No complete taxonomy suggestion";
                    const reviewedCategory = linkedConcepts
                      .map((concept) =>
                        categoryPath(concept.top_level_category, concept.subcategory) ??
                        "Needs taxonomy"
                      )
                      .join("; ");
                    const taxonomyStatus = taxonomyStatusLabel(detailCandidate, reviewedPayload);
                    const spreadsheetEvidence = spreadsheetCandidateEvidence(detailCandidate);
                    const existingMemoryMatches = detailCandidate.existing_memory_matches ?? [];
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
                            <dd>
                              {spreadsheetEvidence ? (
                                <span>
                                  {spreadsheetEvidence.filename} - {spreadsheetEvidence.worksheet} -{" "}
                                  {spreadsheetEvidence.rows.length === 1 ? "row" : "rows"}{" "}
                                  {spreadsheetEvidence.rows.map((row, index) => (
                                    <span key={row}>
                                      {index > 0 ? "-" : ""}
                                      {row === spreadsheetEvidence.primaryBodyRow ? (
                                        <strong aria-label="Primary evidence row">{row}</strong>
                                      ) : (
                                        row
                                      )}
                                    </span>
                                  ))}
                                </span>
                              ) : (
                                <>Source Submission #{detailCandidate.source_submission_id}</>
                              )}
                            </dd>
                          </div>
                          <div>
                            <dt>Taxonomy Status</dt>
                            <dd>{taxonomyStatus}</dd>
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
                            <h4>Linked Concepts</h4>
                            {linkedConcepts.map((concept, index) => (
                              <div key={`${concept.concept_type}-${concept.name}-${index}`}>
                                <p><strong>{concept.name || "Unnamed concept"}</strong></p>
                                <p>{formatConceptType(concept.concept_type)}</p>
                                <p>
                                  {categoryPath(
                                    concept.top_level_category,
                                    concept.subcategory
                                  ) ?? "Needs taxonomy"}
                                </p>
                                {existingMemoryMatches.find(
                                  (match) => match.subject_type === concept.concept_type
                                ) ? (
                                  <p className="status-message">
                                    Matched existing memory: {existingMemoryMatches.find(
                                      (match) => match.subject_type === concept.concept_type
                                    )?.subject_name} - existing category will be preserved.
                                  </p>
                                ) : null}
                                {(
                                  [
                                    ["name", `${formatConceptType(concept.concept_type)} name`],
                                    [
                                      "top_level_category",
                                      `${formatConceptType(concept.concept_type)} top-level category`
                                    ],
                                    [
                                      "subcategory",
                                      `${formatConceptType(concept.concept_type)} subcategory`
                                    ]
                                  ] as const
                                ).map(([field, label]) => (
                                  <label key={field}>
                                    {label}
                                    <input
                                      onChange={(event) =>
                                        updateCandidateReviewedPayload(
                                          detailCandidate,
                                          (payload) => ({
                                            ...payload,
                                            linked_concepts: reviewedConcepts(payload).map((item) =>
                                              item.concept_type === concept.concept_type
                                                ? { ...item, [field]: event.target.value || null }
                                                : item
                                            )
                                          })
                                        )
                                      }
                                      value={concept[field] ?? ""}
                                    />
                                  </label>
                                ))}
                              </div>
                            ))}
                            <div className="review-actions">
                              {(["material", "service"] as const).map((conceptType) => {
                                const isLinked = linkedConcepts.some(
                                  (concept) => concept.concept_type === conceptType
                                );
                                return (
                                  <label key={conceptType}>
                                    <input
                                      checked={isLinked}
                                      onChange={(event) =>
                                        updateCandidateReviewedPayload(
                                          detailCandidate,
                                          (payload) => ({
                                            ...payload,
                                            line_type: null,
                                            name: null,
                                            top_level_category: null,
                                            subcategory: null,
                                            linked_concepts: event.target.checked
                                              ? [
                                                  ...reviewedConcepts(payload),
                                                  {
                                                    concept_type: conceptType,
                                                    name: "",
                                                    top_level_category: null,
                                                    subcategory: null
                                                  }
                                                ]
                                              : reviewedConcepts(payload).filter(
                                                  (concept) => concept.concept_type !== conceptType
                                                )
                                          })
                                        )
                                      }
                                      type="checkbox"
                                    />
                                    Link {formatConceptType(conceptType)}
                                  </label>
                                );
                              })}
                            </div>
                          </section>
                          <section>
                            <h4>Provider</h4>
                            <p>{formatProviderState(providerState)}</p>
                            <label>
                              Provider State
                              <select
                                onChange={(event) => {
                                  const nextState = event.target.value as
                                    | "external"
                                    | "internal"
                                    | "unknown";
                                  updateCandidateReviewedPayload(detailCandidate, (payload) => ({
                                    ...payload,
                                    provider_state: nextState,
                                    provider_name:
                                      nextState === "external" ? payload.provider_name : null,
                                    provider_top_level_category:
                                      nextState === "external"
                                        ? payload.provider_top_level_category ?? "Providers"
                                        : null,
                                    provider_subcategory:
                                      nextState === "external"
                                        ? payload.provider_subcategory ?? "General"
                                        : null
                                  }));
                                }}
                                value={providerState}
                              >
                                <option value="external">External</option>
                                <option value="internal">Internal</option>
                                <option value="unknown">Unknown</option>
                              </select>
                            </label>
                            {providerState === "external" ? (
                              <>
                                <p>{providerName}</p>
                                <p>
                                  {categoryPath(
                                    reviewedPayload.provider_top_level_category,
                                    reviewedPayload.provider_subcategory
                                  ) ?? "Providers / General"}
                                </p>
                                {existingMemoryMatches.find(
                                  (match) => match.subject_type === "provider"
                                ) ? (
                                  <p className="status-message">
                                    Matched existing memory: {existingMemoryMatches.find(
                                      (match) => match.subject_type === "provider"
                                    )?.subject_name} - existing category will be preserved.
                                  </p>
                                ) : null}
                                {(
                                  [
                                    ["provider_name", "Provider name"],
                                    [
                                      "provider_top_level_category",
                                      "Provider top-level category"
                                    ],
                                    ["provider_subcategory", "Provider subcategory"]
                                  ] as const
                                ).map(([field, label]) => (
                                  <label key={field}>
                                    {label}
                                    <input
                                      onChange={(event) =>
                                        updateCandidateReviewedPayload(
                                          detailCandidate,
                                          (payload) => ({
                                            ...payload,
                                            [field]: event.target.value || null
                                          })
                                        )
                                      }
                                      value={reviewedPayload[field] ?? ""}
                                    />
                                  </label>
                                ))}
                              </>
                            ) : null}
                            {providerState === "unknown" ? <p>Provider is a data gap.</p> : null}
                          </section>
                          <section>
                            <h4>Purchase Details</h4>
                            <p>
                              {[reviewedPayload.quantity, reviewedPayload.unit]
                                .filter(Boolean)
                                .join(" ") || "Quantity not provided"}
                            </p>
                            <p>
                              {[reviewedPayload.currency, reviewedPayload.price]
                                .filter(Boolean)
                                .join(" ") || "Price not provided"}
                            </p>
                            <p>{reviewedPayload.purchase_date ?? "Date not provided"}</p>
                            {reviewedPayload.remarks_or_terms ? (
                              <p>{reviewedPayload.remarks_or_terms}</p>
                            ) : null}
                            {(
                              [
                                ["quantity", "Quantity"],
                                ["unit", "Unit"],
                                ["price", "Price"],
                                ["currency", "Currency"],
                                ["purchase_date", "Purchase date"],
                                ["remarks_or_terms", "Remarks or terms"]
                              ] as const
                            ).map(([field, label]) => (
                              <label key={field}>
                                {label}
                                <input
                                  onChange={(event) =>
                                    updateCandidateReviewedPayload(detailCandidate, (payload) => ({
                                      ...payload,
                                      [field]: event.target.value || null
                                    }))
                                  }
                                  type={field === "purchase_date" ? "date" : "text"}
                                  value={reviewedPayload[field] ?? ""}
                                />
                              </label>
                            ))}
                          </section>
                          {(detailCandidate.taxonomy_gates ?? []).length > 0 ? (
                            <section>
                              <h4>Taxonomy Gates</h4>
                              {(detailCandidate.taxonomy_gates ?? []).map((gate) => (
                                <div
                                  key={`${gate.subject_type}-${gate.subject_name}-${gate.suggested_category_path}`}
                                >
                                  <p>
                                    <strong>{formatTaxonomySubjectType(gate.subject_type)}</strong>: {" "}
                                    {gate.subject_name}
                                  </p>
                                  <p>{gate.suggested_category_path}</p>
                                  {gate.decision ? (
                                    <p className="status-message">{gate.status}</p>
                                  ) : splitCategoryPath(gate.suggested_category_path) ? (
                                    <button
                                      className="secondary-action"
                                      disabled={isApprovingCandidate}
                                      onClick={() => void handleTaxonomyDecision(gate, "approved")}
                                      type="button"
                                    >
                                      Approve {gate.subject_type} taxonomy: {gate.suggested_category_path}
                                    </button>
                                  ) : (
                                    <p className="status-message">Choose a complete category path.</p>
                                  )}
                                </div>
                              ))}
                            </section>
                          ) : null}
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
                    Existing Taxonomy Path
                    <select
                      value={selectedExistingTaxonomyPath}
                      onChange={(event) => handleExistingTaxonomyPathChange(event.target.value)}
                    >
                      <option value="">Choose an existing path</option>
                      {taxonomyLeafPaths.map((path) => (
                        <option key={path.id} value={path.path}>
                          {path.path}
                        </option>
                      ))}
                    </select>
                  </label>
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
                      onClick={() => {
                        setTaxonomyCandidateId(null);
                        setSimilarMappingConfirmation(null);
                      }}
                      type="button"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </div>
            ) : null}

            {workspaceRoute.name === "review_batch" && similarMappingConfirmation ? (
              <div
                aria-label="Confirm Similar Taxonomy Mapping"
                aria-modal="true"
                className="modal-backdrop"
                role="dialog"
              >
                <section className="modal-panel compact-modal">
                  <div className="view-heading">
                    <p className="eyebrow">Apply to similar</p>
                    <h3>Confirm Similar Taxonomy Mapping</h3>
                  </div>
                  <p>
                    This mapping will affect {similarMappingConfirmation.affectedCount} candidates
                    in this Review Batch.
                  </p>
                  <div className="review-actions">
                    <button
                      className="primary-action compact-action"
                      disabled={isApprovingCandidate}
                      onClick={() => void saveTaxonomyMapping()}
                      type="button"
                    >
                      Confirm Mapping
                    </button>
                    <button
                      className="secondary-action"
                      onClick={() => setSimilarMappingConfirmation(null)}
                      type="button"
                    >
                      Cancel
                    </button>
                  </div>
                </section>
              </div>
            ) : null}

            {workspaceRoute.name === "providers" ? (
              <fieldset className="provider-role-filters">
                <legend>Provider roles</legend>
                {[
                  ["material_supplier", "Material supplier"],
                  ["service_provider", "Service provider"],
                  ["supply_and_install_provider", "Supply & install"]
                ].map(([role, label]) => (
                  <label key={role}>
                    <input
                      checked={selectedProviderRoles.includes(role)}
                      onChange={(event) =>
                        void handleProviderRoleChange(role, event.target.checked)
                      }
                      type="checkbox"
                    />
                    {label}
                  </label>
                ))}
              </fieldset>
            ) : null}

            {workspaceRoute.name === "materials" ||
            workspaceRoute.name === "services" ||
            workspaceRoute.name === "providers" ? (
              entityMemory === null || entityMemory.items.length === 0 ? (
                <div className="empty-state">
                  <h3>No active {workspaceRoute.name} yet</h3>
                </div>
              ) : (
                <div className="purchase-lines-table-wrap">
                  <table className="purchase-lines-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Category</th>
                        {workspaceRoute.name === "providers" ? <th>Roles</th> : null}
                        <th>Purchase Lines</th>
                        <th>Sources</th>
                      </tr>
                    </thead>
                    <tbody>
                      {entityMemory.items.map((item) => (
                        <tr key={item.memory_record_id}>
                          <td>{item.name}</td>
                          <td>{item.category_path}</td>
                          {workspaceRoute.name === "providers" ? (
                            <td>
                              {"roles" in item
                                ? item.roles.map(formatProviderRole).join(", ")
                                : ""}
                            </td>
                          ) : null}
                          <td>{item.linked_purchase_line_count}</td>
                          <td>{item.source_submission_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
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
                          <td>
                            {purchaseLine.linked_concepts.map((concept) => (
                              <div key={concept.memory_record_id}>{concept.name}</div>
                            ))}
                          </td>
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
                          <td>
                            {purchaseLine.linked_concepts.map((concept) => (
                              <div key={concept.memory_record_id}>{concept.category_path}</div>
                            ))}
                          </td>
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
    contractor_assigned: form.contractorAssigned.trim(),
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

function formatProviderRole(role: string): string {
  const labels: Record<string, string> = {
    material_supplier: "Material supplier",
    service_provider: "Service provider",
    supply_and_install_provider: "Supply & install"
  };
  return labels[role] ?? role;
}

function formatFileSize(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toFixed(2)} MiB`;
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString();
}

function diagnosticSummary(diagnostics: unknown): string | null {
  if (!diagnostics || typeof diagnostics !== "object") {
    return null;
  }
  const values = diagnostics as Record<string, unknown>;
  for (const key of ["warning_summary", "outcome_summary"]) {
    if (typeof values[key] === "string" && values[key].trim() !== "") {
      return values[key];
    }
  }
  return null;
}

function recoveryGuidance(status: string): string | null {
  if (status === "failed") {
    return "Processing failed. Check the workbook, save calculated values, and submit it as a new Source Submission.";
  }
  if (status === "no_candidates_found") {
    return "No candidates found. Check visible worksheet content or submit a new Source Submission.";
  }
  return null;
}

function spreadsheetCandidateEvidence(candidate: ExtractedCandidateRead):
  | {
      filename: string;
      worksheet: string;
      primaryBodyRow: number;
      rows: number[];
    }
  | null {
  if (!candidate.source_file) {
    return null;
  }
  const evidence = candidate.proposed_payload.evidence;
  if (!evidence || typeof evidence !== "object") {
    return null;
  }
  const values = evidence as Record<string, unknown>;
  const worksheet = values.worksheet;
  const primaryBodyRow = values.primary_body_row;
  const locators = values.locators;
  if (
    typeof worksheet !== "string" ||
    typeof primaryBodyRow !== "number" ||
    !Array.isArray(locators)
  ) {
    return null;
  }
  const rows = Array.from(
    new Set(
      locators.flatMap((locator) => {
        if (!locator || typeof locator !== "object") {
          return [];
        }
        const row = (locator as Record<string, unknown>).row;
        return typeof row === "number" ? [row] : [];
      })
    )
  ).sort((left, right) => left - right);
  if (!rows.includes(primaryBodyRow)) {
    return null;
  }
  return {
    filename: candidate.source_file.original_filename,
    worksheet,
    primaryBodyRow,
    rows
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

function reviewedPayloadForCandidate(candidate: ExtractedCandidateRead): ReviewedPurchaseLinePayload {
  const reviewedPayload = candidate.reviewed_payload as ReviewedPurchaseLinePayload | null;
  if (reviewedPayload) {
    return reviewedPayload;
  }
  const proposedPayload = candidate.proposed_payload;
  const suggestion = taxonomySuggestion(candidate);
  const proposedLinkedConcepts = Array.isArray(proposedPayload.linked_concepts)
    ? proposedPayload.linked_concepts
        .map((concept) => proposedConcept(concept))
        .filter((concept): concept is NonNullable<typeof concept> => concept !== null)
    : [];
  const providerState =
    proposedPayload.provider_state === "external" ||
    proposedPayload.provider_state === "internal" ||
    proposedPayload.provider_state === "unknown"
      ? proposedPayload.provider_state
      : proposedPayload.provider_name
        ? "external"
        : "unknown";
  const providerCategory = proposedPayload.provider_category_suggestion;
  const providerTopLevelCategory = objectString(providerCategory, "top_level_category");
  const providerSubcategory = objectString(providerCategory, "subcategory");
  return {
    linked_concepts:
      proposedLinkedConcepts.length > 0
        ? proposedLinkedConcepts
        : [
            {
              concept_type:
                proposedPayload.line_type === "service" ? "service" : "material",
              name: String(proposedPayload.name ?? ""),
              top_level_category: suggestion?.topLevelCategory ?? null,
              subcategory: suggestion?.subcategory ?? null
            }
          ],
    provider_state: providerState,
    provider_top_level_category:
      providerState === "external" ? providerTopLevelCategory ?? "Providers" : null,
    provider_subcategory:
      providerState === "external" ? providerSubcategory ?? "General" : null,
    line_type:
      proposedPayload.line_type === "service" || proposedPayload.line_type === "material"
        ? proposedPayload.line_type
        : null,
    name: proposedLinkedConcepts.length > 0 ? null : String(proposedPayload.name ?? ""),
    top_level_category: suggestion?.topLevelCategory ?? null,
    subcategory: suggestion?.subcategory ?? null,
    quantity: optionalText(String(proposedPayload.quantity ?? "")),
    unit: optionalText(String(proposedPayload.unit ?? "")),
    price: optionalText(String(proposedPayload.price ?? "")),
    currency: optionalText(String(proposedPayload.currency ?? "")),
    provider_name:
      providerState === "external"
        ? optionalText(String(proposedPayload.provider_name ?? ""))
        : null,
    purchase_date:
      typeof proposedPayload.purchase_date === "string" ? proposedPayload.purchase_date : null,
    remarks_or_terms: optionalText(String(proposedPayload.remarks_or_terms ?? ""))
  };
}

type ReviewedConcept = {
  concept_type: "material" | "service";
  name: string;
  top_level_category: string | null;
  subcategory: string | null;
};

function reviewedConcepts(payload: ReviewedPurchaseLinePayload): ReviewedConcept[] {
  if (payload.linked_concepts && payload.linked_concepts.length > 0) {
    return payload.linked_concepts.map((concept) => ({
      concept_type: concept.concept_type,
      name: concept.name ?? "",
      top_level_category: concept.top_level_category ?? null,
      subcategory: concept.subcategory ?? null
    }));
  }

  return [
    {
      concept_type: payload.line_type === "service" ? "service" : "material",
      name: payload.name ?? "",
      top_level_category: payload.top_level_category ?? null,
      subcategory: payload.subcategory ?? null
    }
  ];
}

function proposedConcept(value: unknown): ReviewedConcept | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const conceptType = objectString(value, "concept_type");
  if (conceptType !== "material" && conceptType !== "service") {
    return null;
  }
  const categorySuggestion = (value as Record<string, unknown>).category_suggestion;
  return {
    concept_type: conceptType,
    name: objectString(value, "name") ?? "",
    top_level_category: objectString(categorySuggestion, "top_level_category"),
    subcategory: objectString(categorySuggestion, "subcategory")
  };
}

function objectString(value: unknown, key: string): string | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const field = (value as Record<string, unknown>)[key];
  return typeof field === "string" && field.trim() !== "" ? field : null;
}

function categoryPath(
  topLevelCategory: string | null | undefined,
  subcategory: string | null | undefined
): string | null {
  return topLevelCategory && subcategory ? `${topLevelCategory} / ${subcategory}` : null;
}

function formatConceptType(conceptType: "material" | "service"): string {
  return conceptType === "material" ? "Material" : "Service";
}

function formatProviderState(providerState: "external" | "internal" | "unknown"): string {
  if (providerState === "external") {
    return "External";
  }
  if (providerState === "internal") {
    return "Internal";
  }
  return "Unknown";
}

function formatTaxonomySubjectType(subjectType: string): string {
  if (subjectType === "provider") {
    return "Provider";
  }
  return formatConceptType(subjectType === "service" ? "service" : "material");
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

function countSimilarTaxonomyCandidates(
  reviewBatchDetail: ReviewBatchDetail,
  selectedCandidate: ExtractedCandidateRead
): number {
  const selectedKey = normalizedTaxonomySuggestionKey(selectedCandidate);
  if (selectedKey === null) {
    return 1;
  }
  return reviewBatchDetail.candidates.filter(
    (candidate) => normalizedTaxonomySuggestionKey(candidate) === selectedKey
  ).length;
}

function normalizedTaxonomySuggestionKey(candidate: ExtractedCandidateRead): string | null {
  const suggestion = taxonomySuggestion(candidate);
  if (suggestion?.topLevelCategory && suggestion.subcategory) {
    return `${normalizeTaxonomyPart(suggestion.topLevelCategory)} / ${normalizeTaxonomyPart(
      suggestion.subcategory
    )}`;
  }
  return null;
}

function taxonomyStatusLabel(
  candidate: ExtractedCandidateRead,
  reviewedPayload: ReviewedPurchaseLinePayload
): string {
  if (!reviewedPayload.top_level_category || !reviewedPayload.subcategory) {
    return "Needs taxonomy";
  }

  const reviewedKey = `${normalizeTaxonomyPart(
    reviewedPayload.top_level_category
  )} / ${normalizeTaxonomyPart(reviewedPayload.subcategory)}`;
  const suggestedKey = normalizedTaxonomySuggestionKey(candidate);
  return suggestedKey === reviewedKey ? "AI suggested default" : "Reviewer mapped taxonomy";
}

function normalizeTaxonomyPart(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
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
