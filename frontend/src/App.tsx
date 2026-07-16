import { FormEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Check, FolderOpen, GitBranch, Plus, Upload, X } from "lucide-react";

import {
  acceptTaxonomyGate,
  createProjectWorkspace,
  createSourceFile,
  createManualSourceEntry,
  decideCandidate,
  editAcceptedTaxonomyGate,
  getPurchaseLineDetail,
  getReviewBatch,
  getProjectWorkspaceMaterials,
  getProjectWorkspacePurchaseLines,
  getProjectWorkspaceProviders,
  getProjectWorkspaceServices,
  getSourceSubmissionDetail,
  importReviewBatch,
  listProcessingJobs,
  listTaxonomyLeafPaths,
  listProjectWorkspaces,
  originalSourceFileUrl,
  resetCandidate,
  saveReviewBatchDraft,
  saveTaxonomyGateReviewerDraft,
  selectTaxonomyGateProposal,
  type ExtractedCandidateRead,
  type EntityMemoryListView,
  type ManualSourceEntryCreate,
  type ProcessingJobListItem,
  type PurchaseLineDetail,
  type ProjectWorkspaceCreate,
  type ProjectWorkspaceListItem,
  type ProjectWorkspacePurchaseLinesView,
  type ProviderMemoryListView,
  type ReviewBatchDetail,
  type ReviewedAnnotationProposal,
  type ReviewedPurchaseLinePayload,
  type StructuredEvidenceAnnotationInput,
  type SourceSubmissionDetail
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
  annotations: StructuredEvidenceAnnotationInput[];
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
  annotations: []
};

const annotationTypes: StructuredEvidenceAnnotationInput["annotation_type"][] = [
  "delivery_terms",
  "payment_terms",
  "validity_terms",
  "warranty_terms",
  "availability_terms",
  "condition_or_exclusion",
  "general_qualifier"
];

const annotationTargets: StructuredEvidenceAnnotationInput["target"][] = [
  "purchase_line",
  "material",
  "service",
  "provider"
];

const MAX_XLSX_UPLOAD_BYTES = 25 * 1024 * 1024;

type ReviewForm = ManualSourceForm & {
  remarksOrTerms: string;
  topLevelCategory: string;
  subcategory: string;
};

type WorkspaceRoute =
  | { name: "purchase_lines" }
  | { name: "materials" }
  | { name: "services" }
  | { name: "providers" }
  | { name: "upload_review" }
  | { name: "review_batch"; reviewBatchId: number }
  | { name: "purchase_line_detail"; purchaseLineId: number }
  | { name: "source_submission_detail"; sourceSubmissionId: number };

function parseWorkspaceLocation(
  pathname: string
): { projectId: number; route: WorkspaceRoute } | null {
  const purchaseDetail = pathname.match(/^\/projects\/(\d+)\/purchase-lines\/(\d+)$/);
  if (purchaseDetail) {
    return {
      projectId: Number(purchaseDetail[1]),
      route: { name: "purchase_line_detail", purchaseLineId: Number(purchaseDetail[2]) }
    };
  }
  const sourceDetail = pathname.match(/^\/projects\/(\d+)\/sources\/(\d+)$/);
  if (sourceDetail) {
    return {
      projectId: Number(sourceDetail[1]),
      route: {
        name: "source_submission_detail",
        sourceSubmissionId: Number(sourceDetail[2])
      }
    };
  }
  const reviewBatch = pathname.match(/^\/projects\/(\d+)\/review-batches\/(\d+)$/);
  if (reviewBatch) {
    return {
      projectId: Number(reviewBatch[1]),
      route: { name: "review_batch", reviewBatchId: Number(reviewBatch[2]) }
    };
  }
  const purchaseList = pathname.match(/^\/projects\/(\d+)\/purchase-lines$/);
  if (purchaseList) {
    return { projectId: Number(purchaseList[1]), route: { name: "purchase_lines" } };
  }
  return null;
}

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
  const [purchaseLineDetail, setPurchaseLineDetail] = useState<PurchaseLineDetail | null>(null);
  const [sourceSubmissionDetail, setSourceSubmissionDetail] =
    useState<SourceSubmissionDetail | null>(null);
  const [workspaceRoute, setWorkspaceRoute] = useState<WorkspaceRoute>({
    name: "purchase_lines"
  });
  const [candidateDrafts, setCandidateDrafts] = useState<Record<number, CandidateDraft>>({});
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [detailCandidateId, setDetailCandidateId] = useState<number | null>(null);
  const [taxonomyCandidateId, setTaxonomyCandidateId] = useState<number | null>(null);
  const [taxonomyGateId, setTaxonomyGateId] = useState<number | null>(null);
  const [taxonomyForm, setTaxonomyForm] = useState<TaxonomyForm>({
    topLevelCategory: "",
    subcategory: "",
    applyToSimilar: false
  });
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
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const pendingScrollYRef = useRef<number | null>(null);

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
    if (projects.length === 0 || selectedPurchaseLines !== null) return;
    const parsed = parseWorkspaceLocation(window.location.pathname);
    if (parsed === null) return;
    const linkedRoute = parsed;
    const project = projects.find((item) => item.id === linkedRoute.projectId);
    if (project === undefined) return;
    let isMounted = true;

    async function loadDeepLink() {
      try {
        const purchaseLines = await getProjectWorkspacePurchaseLines(linkedRoute.projectId);
        if (!isMounted) return;
        setSelectedPurchaseLines(purchaseLines);
        setWorkspaceRoute(linkedRoute.route);
        const taxonomyNodes = await listTaxonomyLeafPaths(linkedRoute.projectId);
        if (!isMounted) return;
        setTaxonomyLeafPaths(
          taxonomyNodes.items.map((item) => ({ id: item.id, path: item.path }))
        );
        if (linkedRoute.route.name === "purchase_line_detail") {
          setPurchaseLineDetail(
            await getPurchaseLineDetail(
              linkedRoute.projectId,
              linkedRoute.route.purchaseLineId
            )
          );
        } else if (linkedRoute.route.name === "source_submission_detail") {
          setSourceSubmissionDetail(
            await getSourceSubmissionDetail(
              linkedRoute.projectId,
              linkedRoute.route.sourceSubmissionId
            )
          );
        } else if (linkedRoute.route.name === "review_batch") {
          const detail = await getReviewBatch(
            linkedRoute.projectId,
            linkedRoute.route.reviewBatchId
          );
          if (!isMounted) return;
          setActiveReviewBatch(detail);
          setCandidateDrafts(initialDraftsForCandidates(detail.candidates));
          setReviewForm(buildReviewForm(detail, manualSourceForm));
        }
      } catch {
        if (isMounted) setErrorMessage("The linked Project Memory view could not be loaded.");
      }
    }

    void loadDeepLink();
    return () => {
      isMounted = false;
    };
  }, [projects, selectedPurchaseLines]);

  useEffect(() => {
    async function handlePopState(event: PopStateEvent) {
      const parsed = parseWorkspaceLocation(window.location.pathname);
      if (
        parsed === null ||
        selectedPurchaseLines === null ||
        parsed.projectId !== selectedPurchaseLines.project_workspace.id
      ) {
        return;
      }
      const scrollY = (event.state as { scrollY?: unknown } | null)?.scrollY;
      pendingScrollYRef.current = typeof scrollY === "number" ? scrollY : null;
      setWorkspaceRoute(parsed.route);
      if (parsed.route.name === "purchase_line_detail") {
        setPurchaseLineDetail(
          await getPurchaseLineDetail(parsed.projectId, parsed.route.purchaseLineId)
        );
      } else if (parsed.route.name === "source_submission_detail") {
        setSourceSubmissionDetail(
          await getSourceSubmissionDetail(parsed.projectId, parsed.route.sourceSubmissionId)
        );
      }
    }

    const listener = (event: PopStateEvent) => void handlePopState(event);
    window.addEventListener("popstate", listener);
    return () => window.removeEventListener("popstate", listener);
  }, [selectedPurchaseLines]);

  useEffect(() => {
    const top = pendingScrollYRef.current;
    if (top === null) return;
    pendingScrollYRef.current = null;
    window.scrollTo({ behavior: "auto", top });
  }, [workspaceRoute]);

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
  const taxonomyGate =
    taxonomyCandidate?.taxonomy_gates?.find((gate) => gate.id === taxonomyGateId) ?? null;
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
      setTaxonomyGateId(null);
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
    window.history.replaceState(
      { ...(window.history.state ?? {}), scrollY: window.scrollY },
      "",
      window.location.href
    );
    setWorkspaceRoute(route);
    const path =
      route.name === "purchase_lines"
        ? `/projects/${projectId}/purchase-lines`
        : route.name === "materials" || route.name === "services" || route.name === "providers"
          ? `/projects/${projectId}/${route.name}`
        : route.name === "upload_review"
          ? `/projects/${projectId}/upload-review`
          : route.name === "review_batch"
            ? `/projects/${projectId}/review-batches/${route.reviewBatchId}`
            : route.name === "purchase_line_detail"
              ? `/projects/${projectId}/purchase-lines/${route.purchaseLineId}`
              : `/projects/${projectId}/sources/${route.sourceSubmissionId}`;
    window.history.pushState({}, "", path);
  }

  async function handleOpenPurchaseLineDetail(purchaseLineId: number) {
    if (selectedPurchaseLines === null) return;
    const projectId = selectedPurchaseLines.project_workspace.id;
    setErrorMessage(null);
    try {
      const detail = await getPurchaseLineDetail(projectId, purchaseLineId);
      setPurchaseLineDetail(detail);
      setSourceSubmissionDetail(null);
      navigateWorkspace(projectId, { name: "purchase_line_detail", purchaseLineId });
    } catch {
      setErrorMessage("Purchase Line Detail could not be loaded.");
    }
  }

  async function handleOpenSourceSubmissionDetail(sourceSubmissionId: number) {
    if (selectedPurchaseLines === null) return;
    const projectId = selectedPurchaseLines.project_workspace.id;
    setErrorMessage(null);
    try {
      const detail = await getSourceSubmissionDetail(projectId, sourceSubmissionId);
      setSourceSubmissionDetail(detail);
      navigateWorkspace(projectId, {
        name: "source_submission_detail",
        sourceSubmissionId
      });
    } catch {
      setErrorMessage("Source Submission Detail could not be loaded.");
    }
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
      setTaxonomyGateId(null);
      setReviewForm(null);
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
      setTaxonomyGateId(null);
      setReviewForm(buildReviewForm(detail, manualSourceForm));
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

  function updateCandidateAnnotation(
    candidate: ExtractedCandidateRead,
    proposalId: string,
    update: Partial<ReviewedAnnotationProposal>
  ) {
    updateCandidateReviewedPayload(candidate, (payload) => ({
      ...payload,
      annotation_proposals: (payload.annotation_proposals ?? []).map((annotation) =>
        annotation.proposal_id === proposalId ? { ...annotation, ...update } : annotation
      )
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

  function openTaxonomyDialog(candidate: ExtractedCandidateRead, gate: CandidateTaxonomyGate) {
    const selectedPath = splitCategoryPath(
      gate.reviewer_draft_category_path ?? gate.selected_category_path
    );
    setTaxonomyForm({
      topLevelCategory: selectedPath?.topLevelCategory ?? "",
      subcategory: selectedPath?.subcategory ?? "",
      applyToSimilar: false
    });
    setTaxonomyCandidateId(candidate.id);
    setTaxonomyGateId(gate.id);
  }

  function updateTaxonomyForm(field: keyof TaxonomyForm, value: string | boolean) {
    setTaxonomyForm((currentForm) => ({ ...currentForm, [field]: value }));
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
  }

  async function handleSaveTaxonomyDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      selectedPurchaseLines === null ||
      activeReviewBatch === null ||
      taxonomyGate === null
    ) {
      return;
    }

    setIsApprovingCandidate(true);
    setErrorMessage(null);

    try {
      const response = await saveTaxonomyGateReviewerDraft(
        selectedPurchaseLines.project_workspace.id,
        activeReviewBatch.review_batch.id,
        taxonomyGate.id,
        {
          top_level_category: taxonomyForm.topLevelCategory,
          subcategory: taxonomyForm.subcategory,
          apply_to_similar: taxonomyForm.applyToSimilar
        }
      );
      applyReviewBatchDetail(response.review_batch);
      setTaxonomyCandidateId(null);
      setTaxonomyGateId(null);
      setToastMessage(
        response.affected_count > 0
          ? `Reviewer draft saved and copied to ${response.affected_count} similar gates.`
          : "Reviewer taxonomy draft saved."
      );
    } catch {
      setErrorMessage("Reviewer taxonomy draft could not be saved.");
    } finally {
      setIsApprovingCandidate(false);
    }
  }

  async function handleSelectTaxonomyGate(
    gate: CandidateTaxonomyGate,
    selectedProposal: "ai_suggestion" | "reviewer_draft"
  ) {
    if (selectedPurchaseLines === null || activeReviewBatch === null) return;
    try {
      const detail = await selectTaxonomyGateProposal(
        selectedPurchaseLines.project_workspace.id,
        activeReviewBatch.review_batch.id,
        gate.id,
        { selected_proposal: selectedProposal }
      );
      applyReviewBatchDetail(detail);
    } catch {
      setErrorMessage("Taxonomy proposal could not be selected.");
    }
  }

  async function handleAcceptTaxonomyGate(gate: CandidateTaxonomyGate) {
    if (selectedPurchaseLines === null || activeReviewBatch === null) return;
    setIsApprovingCandidate(true);
    try {
      const detail = await acceptTaxonomyGate(
        selectedPurchaseLines.project_workspace.id,
        activeReviewBatch.review_batch.id,
        gate.id
      );
      applyReviewBatchDetail(detail);
      await refreshTaxonomyLeafPaths(selectedPurchaseLines.project_workspace.id);
    } catch {
      setErrorMessage("Selected taxonomy category could not be accepted.");
    } finally {
      setIsApprovingCandidate(false);
    }
  }

  async function handleEditTaxonomyGate(gate: CandidateTaxonomyGate) {
    if (selectedPurchaseLines === null || activeReviewBatch === null) return;
    try {
      const detail = await editAcceptedTaxonomyGate(
        selectedPurchaseLines.project_workspace.id,
        activeReviewBatch.review_batch.id,
        gate.id
      );
      applyReviewBatchDetail(detail);
    } catch {
      setErrorMessage("Accepted taxonomy gate could not be edited.");
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

  async function handleResetCandidate(candidate: ExtractedCandidateRead) {
    if (
      selectedPurchaseLines === null ||
      activeReviewBatch === null ||
      !window.confirm("Reset this candidate to the original extraction proposal?")
    ) {
      return;
    }

    setIsApprovingCandidate(true);
    setErrorMessage(null);
    try {
      const updatedCandidate = await resetCandidate(
        selectedPurchaseLines.project_workspace.id,
        activeReviewBatch.review_batch.id,
        candidate.id
      );
      setActiveReviewBatch((currentBatch) =>
        currentBatch === null
          ? currentBatch
          : {
              ...currentBatch,
              candidates: currentBatch.candidates.map((existingCandidate) =>
                existingCandidate.id === updatedCandidate.id
                  ? updatedCandidate
                  : existingCandidate
              )
            }
      );
      setCandidateDrafts((currentDrafts) => ({
        ...currentDrafts,
        [updatedCandidate.id]: {
          included: updatedCandidate.decision !== "rejected",
          reviewedPayload: reviewedPayloadForCandidate(updatedCandidate)
        }
      }));
      setToastMessage("Candidate reset to the original extraction proposal.");
    } catch {
      setErrorMessage("Candidate could not be reset.");
    } finally {
      setIsApprovingCandidate(false);
    }
  }

  function applyReviewBatchDetail(detail: ReviewBatchDetail) {
    setActiveReviewBatch(detail);
    setReviewForm(buildReviewForm(detail, manualSourceForm));
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

  function addManualAnnotation() {
    setManualSourceForm((currentForm) => ({
      ...currentForm,
      annotations: [
        ...currentForm.annotations,
        {
          text: "",
          annotation_type: "general_qualifier",
          target: "purchase_line"
        }
      ]
    }));
  }

  function updateManualAnnotation(
    index: number,
    update: Partial<StructuredEvidenceAnnotationInput>
  ) {
    setManualSourceForm((currentForm) => ({
      ...currentForm,
      annotations: currentForm.annotations.map((annotation, annotationIndex) =>
        annotationIndex === index ? { ...annotation, ...update } : annotation
      )
    }));
  }

  function removeManualAnnotation(index: number) {
    setManualSourceForm((currentForm) => ({
      ...currentForm,
      annotations: currentForm.annotations.filter((_, annotationIndex) => annotationIndex !== index)
    }));
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
              {workspaceRoute.name === "purchase_line_detail" ? (
                <h2>Purchase Line Detail</h2>
              ) : null}
              {workspaceRoute.name === "source_submission_detail" ? (
                <h2>Source Submission Detail</h2>
              ) : null}
            </div>
            <div className="workspace-tabs" role="tablist" aria-label="Project Workspace sections">
              <button
                role="tab"
                aria-selected={
                  workspaceRoute.name === "purchase_lines" ||
                  workspaceRoute.name === "purchase_line_detail"
                }
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
                  <section className="annotation-editor" aria-label="Structured annotations">
                    <div className="evidence-heading">
                      <div>
                        <h4>Annotations</h4>
                        <p>Capture each source term separately and choose what it describes.</p>
                      </div>
                      <button
                        className="secondary-action"
                        disabled={manualSourceForm.annotations.length >= 20}
                        onClick={addManualAnnotation}
                        type="button"
                      >
                        <Plus aria-hidden="true" size={16} />
                        Add annotation
                      </button>
                    </div>
                    {manualSourceForm.annotations.map((annotation, index) => (
                      <div className="annotation-editor-row" key={index}>
                        <label>
                          Annotation text {index + 1}
                          <input
                            aria-label={`Annotation text ${index + 1}`}
                            required
                            value={annotation.text}
                            onChange={(event) =>
                              updateManualAnnotation(index, { text: event.target.value })
                            }
                          />
                        </label>
                        <label>
                          Annotation type {index + 1}
                          <select
                            aria-label={`Annotation type ${index + 1}`}
                            value={annotation.annotation_type}
                            onChange={(event) =>
                              updateManualAnnotation(index, {
                                annotation_type: event.target.value as StructuredEvidenceAnnotationInput["annotation_type"]
                              })
                            }
                          >
                            {annotationTypes.map((annotationType) => (
                              <option key={annotationType} value={annotationType}>
                                {formatLabel(annotationType)}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Annotation target {index + 1}
                          <select
                            aria-label={`Annotation target ${index + 1}`}
                            value={annotation.target}
                            onChange={(event) =>
                              updateManualAnnotation(index, {
                                target: event.target.value as StructuredEvidenceAnnotationInput["target"]
                              })
                            }
                          >
                            {annotationTargets.map((target) => (
                              <option key={target} value={target}>
                                {formatLabel(target)}
                              </option>
                            ))}
                          </select>
                        </label>
                        <button
                          aria-label={`Remove annotation ${index + 1}`}
                          className="icon-action"
                          onClick={() => removeManualAnnotation(index)}
                          type="button"
                        >
                          <X aria-hidden="true" size={16} />
                        </button>
                      </div>
                    ))}
                  </section>
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
                    const memoryOptions = detailCandidate.memory_options ?? [];
                    const originalAnnotations = proposedAnnotations(detailCandidate);
                    const reviewedAnnotations = reviewedPayload.annotation_proposals ?? [];
                    const sourceGrounding = detailCandidate.source_grounding;
                    const sourceGroundingOptions = sourceGrounding?.options ?? [];
                    const canAddGroundedAnnotation = Boolean(
                      sourceGrounding &&
                        ((sourceGrounding.kind === "free_form_text" &&
                          sourceGrounding.original_text) ||
                          sourceGroundingOptions.length > 0)
                    );
                    const availableAnnotationTargets = new Set<ReviewedAnnotationProposal["target"]>([
                      "purchase_line",
                      ...linkedConcepts.map((concept) => concept.concept_type),
                      ...(providerState === "external" ? (["provider"] as const) : [])
                    ]);
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
                          <div>
                            <dt>AI Confidence</dt>
                            <dd>{formatCandidateConfidence(detailCandidate.proposed_payload.confidence)}</dd>
                          </div>
                        </dl>
                        <div className="candidate-detail-sections">
                          <section>
                            <h4>Linked Concepts</h4>
                            {linkedConcepts.map((concept, index) => {
                              const conceptMemoryOptions = memoryOptions.filter(
                                (option) => option.subject_type === concept.concept_type
                              );
                              const matchedMemory = concept.project_memory_record_id
                                ? conceptMemoryOptions.find(
                                    (option) => option.record_id === concept.project_memory_record_id
                                  )
                                : null;
                              const originalConcept = Array.isArray(
                                detailCandidate.proposed_payload.linked_concepts
                              )
                                ? proposedConcept(
                                    detailCandidate.proposed_payload.linked_concepts[index]
                                  )
                                : null;
                              const listId = `candidate-${detailCandidate.id}-${concept.concept_id ?? index}-memory`;
                              return (
                              <div key={concept.concept_id ?? `${concept.concept_type}-${index}`}>
                                <p><strong>{concept.name || "Unnamed concept"}</strong></p>
                                <p>{formatConceptType(concept.concept_type)}</p>
                                {concept.observed_name_text ? (
                                  <p className="status-message">
                                    Observed source: {concept.observed_name_text}
                                  </p>
                                ) : null}
                                {!concept.project_memory_record_id ? (
                                  <p className="status-message">
                                    New Project Memory record — taxonomy approval required.
                                  </p>
                                ) : null}
                                <p>
                                  {categoryPath(
                                    concept.top_level_category,
                                    concept.subcategory
                                  ) ?? "Needs taxonomy"}
                                </p>
                                {matchedMemory || existingMemoryMatches.find(
                                  (match) =>
                                    match.subject_type === concept.concept_type &&
                                    match.subject_name === concept.name
                                ) ? (
                                  <p className="status-message">
                                    Matched existing memory: {matchedMemory?.subject_name ?? concept.name} - existing category will be preserved.
                                  </p>
                                ) : null}
                                <label>
                                  {formatConceptType(concept.concept_type)} name
                                  <input
                                    list={listId}
                                    onChange={(event) => {
                                      const value = event.target.value;
                                      const option = conceptMemoryOptions.find(
                                        (candidateOption) =>
                                          normalizeName(candidateOption.subject_name) === normalizeName(value)
                                      );
                                      const selectedCategory = option
                                        ? splitCategoryPath(option.category_path)
                                        : null;
                                      updateCandidateReviewedPayload(
                                        detailCandidate,
                                        (payload) => ({
                                          ...payload,
                                          linked_concepts: reviewedConcepts(payload).map((item, itemIndex) =>
                                            itemIndex === index
                                              ? {
                                                  ...item,
                                                  name: option?.subject_name ?? value,
                                                  project_memory_record_id: option?.record_id ?? null,
                                                  top_level_category:
                                                    selectedCategory?.topLevelCategory ??
                                                    originalConcept?.top_level_category ??
                                                    item.top_level_category,
                                                  subcategory:
                                                    selectedCategory?.subcategory ??
                                                    originalConcept?.subcategory ?? item.subcategory
                                                }
                                              : item
                                          )
                                        })
                                      );
                                    }}
                                    value={concept.name}
                                  />
                                  <datalist id={listId}>
                                    {conceptMemoryOptions.map((option) => (
                                      <option key={option.record_id} value={option.subject_name}>
                                        {option.category_path}
                                      </option>
                                    ))}
                                  </datalist>
                                </label>
                              </div>
                            );})}
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
                                                    concept_id: `reviewer-${conceptType}-${Date.now()}`,
                                                    name: "",
                                                    observed_name_text: null,
                                                    project_memory_record_id: null,
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
                                    provider_memory_record_id:
                                      nextState === "external"
                                        ? payload.provider_memory_record_id
                                        : null,
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
                                {reviewedPayload.observed_provider_text ? (
                                  <p className="status-message">
                                    Observed source: {reviewedPayload.observed_provider_text}
                                  </p>
                                ) : null}
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
                                <label>
                                  Provider name
                                  <input
                                    list={`candidate-${detailCandidate.id}-provider-memory`}
                                    onChange={(event) => {
                                      const value = event.target.value;
                                      const option = memoryOptions.find(
                                        (candidateOption) =>
                                          candidateOption.subject_type === "provider" &&
                                          normalizeName(candidateOption.subject_name) === normalizeName(value)
                                      );
                                      const selectedCategory = option
                                        ? splitCategoryPath(option.category_path)
                                        : null;
                                      updateCandidateReviewedPayload(
                                        detailCandidate,
                                        (payload) => ({
                                          ...payload,
                                          provider_name: option?.subject_name ?? (value || null),
                                          provider_memory_record_id: option?.record_id ?? null,
                                          provider_top_level_category:
                                            selectedCategory?.topLevelCategory ??
                                            payload.provider_top_level_category,
                                          provider_subcategory:
                                            selectedCategory?.subcategory ??
                                            payload.provider_subcategory
                                        })
                                      );
                                    }}
                                    value={reviewedPayload.provider_name ?? ""}
                                  />
                                  <datalist id={`candidate-${detailCandidate.id}-provider-memory`}>
                                    {memoryOptions
                                      .filter((option) => option.subject_type === "provider")
                                      .map((option) => (
                                        <option key={option.record_id} value={option.subject_name}>
                                          {[option.category_path, ...(option.provider_roles ?? [])]
                                            .filter(Boolean)
                                            .join(" — ")}
                                        </option>
                                      ))}
                                  </datalist>
                                </label>
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
                            {reviewedPayload.calculation ? (
                              <p className="status-message">
                                Calculated: {String(reviewedPayload.calculation.formula)} = {String(reviewedPayload.calculation.result)}
                              </p>
                            ) : null}
                            {reviewedPayload.variance_warning ? (
                              <p className="status-message error">
                                Source total {String(reviewedPayload.variance_warning.source_stated_total)} differs from calculated total {String(reviewedPayload.variance_warning.calculated_total)} by {String(reviewedPayload.variance_warning.variance)}.
                              </p>
                            ) : null}
                            <p>{reviewedPayload.purchase_date ?? "Date not provided"}</p>
                            {(
                              [
                                ["quantity", "Quantity"],
                                ["unit", "Unit"],
                                ["price", "Price"],
                                ["currency", "Currency"],
                                ["purchase_date", "Purchase date"]
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
                          <section className="annotation-editor" aria-label="Annotation review">
                            <div className="evidence-heading">
                              <div>
                                <h4>Annotations</h4>
                                <p>Review the source-grounded terms before import.</p>
                              </div>
                              <button
                                className="secondary-action"
                                disabled={
                                  !canAddGroundedAnnotation
                                }
                                onClick={() =>
                                  updateCandidateReviewedPayload(detailCandidate, (payload) => ({
                                    ...payload,
                                    annotation_proposals: [
                                      ...(payload.annotation_proposals ?? []),
                                      reviewerAddedAnnotation(
                                        detailCandidate,
                                        reviewedAnnotations.length
                                      )
                                    ]
                                  }))
                                }
                                type="button"
                              >
                                <Plus aria-hidden="true" size={16} />
                                Add annotation
                              </button>
                            </div>
                            {!canAddGroundedAnnotation ? (
                              <p className="status-message">
                                No precise source grounding is available for another annotation.
                              </p>
                            ) : null}
                            {reviewedAnnotations.length === 0 ? (
                              <p className="status-message">No annotations proposed.</p>
                            ) : null}
                            {reviewedAnnotations.map((annotation, index) => {
                              const original = originalAnnotations.find(
                                (proposal) => proposal.proposal_id === annotation.proposal_id
                              );
                              const targetIsAvailable = availableAnnotationTargets.has(annotation.target);
                              const annotationConceptOptions =
                                annotation.target === "material" || annotation.target === "service"
                                  ? linkedConcepts.filter(
                                      (concept) => concept.concept_type === annotation.target
                                    )
                                  : [];
                              return (
                                <div className="annotation-review-card" key={annotation.proposal_id}>
                                  <div className="evidence-heading">
                                    <span className="annotation-type">
                                      {formatAnnotationProvenance(annotation.provenance)}
                                    </span>
                                    <button
                                      aria-label={`Remove annotation ${index + 1}`}
                                      className="icon-action"
                                      onClick={() =>
                                        updateCandidateReviewedPayload(detailCandidate, (payload) => ({
                                          ...payload,
                                          annotation_proposals: (payload.annotation_proposals ?? []).filter(
                                            (proposal) => proposal.proposal_id !== annotation.proposal_id
                                          )
                                        }))
                                      }
                                      type="button"
                                    >
                                      <X aria-hidden="true" size={16} />
                                    </button>
                                  </div>
                                  <label>
                                    Annotation text {index + 1}
                                    <input
                                      aria-label={`Annotation text ${index + 1}`}
                                      value={annotation.text}
                                      onChange={(event) =>
                                        updateCandidateAnnotation(
                                          detailCandidate,
                                          annotation.proposal_id,
                                          { text: event.target.value }
                                        )
                                      }
                                    />
                                  </label>
                                  {annotation.provenance === "reviewer_added" &&
                                  sourceGrounding?.kind === "free_form_text" ? (
                                    <label>
                                      Source quote {index + 1}
                                      <input
                                        aria-label={`Source quote ${index + 1}`}
                                        value={annotation.source_excerpt}
                                        onChange={(event) => {
                                          const quote = event.target.value;
                                          const sourceText = sourceGrounding.original_text ?? "";
                                          const start = sourceText.indexOf(quote);
                                          updateCandidateAnnotation(
                                            detailCandidate,
                                            annotation.proposal_id,
                                            {
                                              source_excerpt: quote,
                                              source_locator: {
                                                kind: "text_span",
                                                start,
                                                end: start < 0 ? -1 : start + quote.length
                                              }
                                            }
                                          );
                                        }}
                                      />
                                    </label>
                                  ) : annotation.provenance === "reviewer_added" &&
                                    sourceGrounding &&
                                    sourceGroundingOptions.length > 0 ? (
                                    <label>
                                      Annotation source {index + 1}
                                      <select
                                        aria-label={`Annotation source ${index + 1}`}
                                        value={groundingOptionIndex(sourceGroundingOptions, annotation)}
                                        onChange={(event) => {
                                          const option = sourceGroundingOptions[Number(event.target.value)];
                                          if (option) {
                                            updateCandidateAnnotation(
                                              detailCandidate,
                                              annotation.proposal_id,
                                              option
                                            );
                                          }
                                        }}
                                      >
                                        {sourceGroundingOptions.map((option, optionIndex) => (
                                          <option key={optionIndex} value={optionIndex}>
                                            {option.source_excerpt}
                                          </option>
                                        ))}
                                      </select>
                                    </label>
                                  ) : null}
                                  <div className="form-grid">
                                    <label>
                                      Annotation type {index + 1}
                                      <select
                                        aria-label={`Annotation type ${index + 1}`}
                                        value={annotation.annotation_type}
                                        onChange={(event) =>
                                          updateCandidateAnnotation(
                                            detailCandidate,
                                            annotation.proposal_id,
                                            {
                                              annotation_type: event.target.value as ReviewedAnnotationProposal["annotation_type"]
                                            }
                                          )
                                        }
                                      >
                                        {annotationTypes.map((annotationType) => (
                                          <option key={annotationType} value={annotationType}>
                                            {formatLabel(annotationType)}
                                          </option>
                                        ))}
                                      </select>
                                    </label>
                                    <label>
                                      Annotation target {index + 1}
                                      <select
                                        aria-label={`Annotation target ${index + 1}`}
                                        value={annotation.target}
                                        onChange={(event) =>
                                          {
                                            const target = event.target.value as ReviewedAnnotationProposal["target"];
                                            const targetConcepts = linkedConcepts.filter(
                                              (concept) => concept.concept_type === target
                                            );
                                            updateCandidateAnnotation(
                                              detailCandidate,
                                              annotation.proposal_id,
                                              {
                                                target,
                                                target_concept_id:
                                                  targetConcepts.length > 1
                                                    ? targetConcepts[0].concept_id
                                                    : null
                                              }
                                            );
                                          }
                                        }
                                      >
                                        {annotationTargets.map((target) => (
                                          <option
                                            disabled={!availableAnnotationTargets.has(target)}
                                            key={target}
                                            value={target}
                                          >
                                            {formatLabel(target)}
                                          </option>
                                        ))}
                                      </select>
                                    </label>
                                  </div>
                                  {annotationConceptOptions.length > 1 ? (
                                    <label>
                                      Annotation concept {index + 1}
                                      <select
                                        aria-label={`Annotation concept ${index + 1}`}
                                        value={
                                          annotation.target_concept_id ??
                                          annotationConceptOptions[0].concept_id ??
                                          ""
                                        }
                                        onChange={(event) =>
                                          updateCandidateAnnotation(
                                            detailCandidate,
                                            annotation.proposal_id,
                                            { target_concept_id: event.target.value || null }
                                          )
                                        }
                                      >
                                        {annotationConceptOptions.map((concept, conceptIndex) => (
                                          <option
                                            key={concept.concept_id ?? conceptIndex}
                                            value={concept.concept_id ?? ""}
                                          >
                                            {concept.name || `Unnamed ${formatConceptType(concept.concept_type)}`}
                                          </option>
                                        ))}
                                      </select>
                                    </label>
                                  ) : null}
                                  {original && original.annotation_type !== annotation.annotation_type ? (
                                    <p className="status-message">
                                      Changed from {formatLabel(original.annotation_type)}
                                    </p>
                                  ) : null}
                                  {original && original.target !== annotation.target ? (
                                    <p className="status-message">
                                      Retargeted from {formatLabel(original.target)}
                                    </p>
                                  ) : null}
                                  {!targetIsAvailable ? (
                                    <p className="status-message error">
                                      Target is not available on this candidate. Retarget or remove this annotation.
                                    </p>
                                  ) : null}
                                  <blockquote>{annotation.source_excerpt}</blockquote>
                                  <p className="source-locator">
                                    Source locator: {formatLocator(annotation.source_locator)}
                                  </p>
                                  {annotation.provenance === "reviewer_added" &&
                                  !validReviewerGrounding(annotation) ? (
                                    <p className="status-message error">
                                      Select or quote exact preserved source content.
                                    </p>
                                  ) : null}
                                </div>
                              );
                            })}
                          </section>
                          {(detailCandidate.taxonomy_gates ?? []).length > 0 ? (
                            <section>
                              <h4>Taxonomy Gates</h4>
                              {(detailCandidate.taxonomy_gates ?? []).map((gate) => (
                                <div className="taxonomy-gate" key={gate.id}>
                                  <p>
                                    <strong>{formatTaxonomySubjectType(gate.subject_type)}</strong>: {" "}
                                    {gate.subject_name}
                                  </p>
                                  <p>AI suggestion: {gate.original_ai_category_path}</p>
                                  {gate.reviewer_draft_category_path ? (
                                    <p>Reviewer draft: {gate.reviewer_draft_category_path}</p>
                                  ) : null}
                                  {gate.status === "accepted" ? (
                                    <>
                                      <p className="status-message">
                                        Accepted: {gate.accepted_category_path}
                                      </p>
                                      <p>
                                        Accepted from {gate.accepted_source === "reviewer_draft"
                                          ? "reviewer draft"
                                          : "AI suggestion"}
                                      </p>
                                      <button
                                        className="secondary-action"
                                        onClick={() => void handleEditTaxonomyGate(gate)}
                                        type="button"
                                      >
                                        Edit
                                      </button>
                                    </>
                                  ) : (
                                    <>
                                      <p className="status-message">Needs decision</p>
                                      <p>Selected: {gate.selected_category_path}</p>
                                      <div className="taxonomy-actions">
                                        <button
                                          className="secondary-action"
                                          disabled={gate.selected_proposal === "ai_suggestion"}
                                          onClick={() =>
                                            void handleSelectTaxonomyGate(gate, "ai_suggestion")
                                          }
                                          type="button"
                                        >
                                          Select AI suggestion
                                        </button>
                                        {gate.reviewer_draft_category_path ? (
                                          <button
                                            className="secondary-action"
                                            disabled={gate.selected_proposal === "reviewer_draft"}
                                            onClick={() =>
                                              void handleSelectTaxonomyGate(gate, "reviewer_draft")
                                            }
                                            type="button"
                                          >
                                            Select reviewer draft
                                          </button>
                                        ) : null}
                                        <button
                                          className="secondary-action"
                                          onClick={() => openTaxonomyDialog(detailCandidate, gate)}
                                          type="button"
                                        >
                                          Adjust category
                                        </button>
                                        <button
                                          className="primary-action compact-action"
                                          disabled={isApprovingCandidate}
                                          onClick={() => void handleAcceptTaxonomyGate(gate)}
                                          type="button"
                                        >
                                          Accept selected category
                                        </button>
                                      </div>
                                    </>
                                  )}
                                </div>
                              ))}
                            </section>
                          ) : null}
                        </div>
                        <div className="review-actions">
                          <button
                            className="secondary-action"
                            disabled={isApprovingCandidate}
                            onClick={() => void handleResetCandidate(detailCandidate)}
                            type="button"
                          >
                            Reset candidate
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

            {workspaceRoute.name === "review_batch" &&
            activeReviewBatch &&
            taxonomyCandidate &&
            taxonomyGate ? (
              <div
                aria-label="Edit Taxonomy Gate"
                aria-modal="true"
                className="modal-backdrop"
                role="dialog"
              >
                <form
                  className="modal-panel"
                  onSubmit={(event) => void handleSaveTaxonomyDraft(event)}
                >
                  <div className="view-heading">
                    <p className="eyebrow">{taxonomyGate.subject_name}</p>
                    <h3>Edit Taxonomy Gate</h3>
                  </div>
                  <p>AI suggestion: {taxonomyGate.original_ai_category_path}</p>
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
                    Apply reviewer draft to similar ({countSimilarPendingTaxonomyGates(
                      activeReviewBatch,
                      taxonomyGate
                    )} gates)
                  </label>
                  <div className="review-actions">
                    <button
                      className="primary-action compact-action"
                      disabled={isApprovingCandidate}
                      type="submit"
                    >
                      Save reviewer draft
                    </button>
                    <button
                      className="secondary-action"
                      onClick={() => {
                        setTaxonomyCandidateId(null);
                        setTaxonomyGateId(null);
                      }}
                      type="button"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
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
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedPurchaseLines.items.map((purchaseLine) => (
                        <tr key={purchaseLine.id}>
                          <td>
                            {purchaseLine.linked_concepts.map((concept) => (
                              <div key={concept.memory_record_id}>
                                <a
                                  href={`/projects/${selectedPurchaseLines.project_workspace.id}/purchase-lines/${purchaseLine.id}`}
                                  onClick={(event) => {
                                    event.preventDefault();
                                    void handleOpenPurchaseLineDetail(purchaseLine.id);
                                  }}
                                >
                                  {concept.name}
                                </a>
                              </div>
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
                            {purchaseLine.has_evidence
                              ? `${purchaseLine.evidence_count} ${purchaseLine.evidence_count === 1 ? "evidence" : "evidence records"} — ${purchaseLine.source_label}`
                              : "No evidence"}
                          </td>
                          <td>
                            <a
                              href={`/projects/${selectedPurchaseLines.project_workspace.id}/purchase-lines/${purchaseLine.id}`}
                              onClick={(event) => {
                                event.preventDefault();
                                void handleOpenPurchaseLineDetail(purchaseLine.id);
                              }}
                            >
                              View details
                            </a>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            ) : null}

            {workspaceRoute.name === "purchase_line_detail" && purchaseLineDetail ? (
              <article className="detail-page" aria-label="Purchase Line Detail">
                <div className="detail-grid">
                  <section className="detail-card">
                    <p className="eyebrow">Linked concepts</p>
                    {purchaseLineDetail.linked_concepts.map((concept) => (
                      <div key={concept.memory_record_id}>
                        <strong>{concept.name}</strong>
                        <p>{formatLabel(concept.concept_type)} · {concept.category_path}</p>
                      </div>
                    ))}
                  </section>
                  <section className="detail-card">
                    <p className="eyebrow">Provider</p>
                    {purchaseLineDetail.provider.record ? (
                      <>
                        <strong>{purchaseLineDetail.provider.record.name}</strong>
                        <p>{purchaseLineDetail.provider.record.category_path}</p>
                        <p>{purchaseLineDetail.provider.roles.map(formatProviderRole).join(", ")}</p>
                      </>
                    ) : (
                      <strong>{formatLabel(purchaseLineDetail.provider.state)}</strong>
                    )}
                  </section>
                  <section className="detail-card">
                    <p className="eyebrow">Commercial values</p>
                    <dl className="detail-values">
                      <div><dt>Quantity</dt><dd>{purchaseLineDetail.quantity ?? "Unknown"}</dd></div>
                      <div><dt>Unit</dt><dd>{purchaseLineDetail.unit ?? "Unknown"} ({purchaseLineDetail.unit_state})</dd></div>
                      <div><dt>Price</dt><dd>{purchaseLineDetail.price ? `${purchaseLineDetail.currency ?? ""} ${purchaseLineDetail.price}`.trim() : "Unknown"} ({purchaseLineDetail.price_state})</dd></div>
                      <div><dt>Date</dt><dd>{purchaseLineDetail.purchase_date ?? "Unknown"} ({purchaseLineDetail.date_state})</dd></div>
                    </dl>
                  </section>
                </div>
                <section className="evidence-section">
                  <h3>Evidence Records ({purchaseLineDetail.evidence_records.length})</h3>
                  {purchaseLineDetail.evidence_records.map((evidence) => (
                    <article className="evidence-card" key={evidence.id}>
                      <div className="evidence-heading">
                        <a
                          href={evidence.source_submission_href}
                          onClick={(event) => {
                            event.preventDefault();
                            void handleOpenSourceSubmissionDetail(evidence.source_submission_id);
                          }}
                        >
                          {evidence.source_label}
                        </a>
                        <span>{formatLabel(evidence.source_type)}</span>
                      </div>
                      <EvidenceInspection
                        annotations={evidence.annotations}
                        detectedCount={evidence.annotation_detected_count}
                        locator={evidence.locator}
                        omittedCount={evidence.annotation_omitted_count}
                        supportingContent={evidence.supporting_content}
                      />
                    </article>
                  ))}
                </section>
                <section className="detail-card">
                  <h3>Value History</h3>
                  <p>No reviewed changes yet</p>
                </section>
              </article>
            ) : null}

            {workspaceRoute.name === "source_submission_detail" && sourceSubmissionDetail ? (
              <article className="detail-page" aria-label="Source Submission Detail">
                <div className="detail-grid">
                  <section className="detail-card">
                    <h3>Immutable source</h3>
                    <p>{formatLabel(sourceSubmissionDetail.source.kind)}</p>
                    {sourceSubmissionDetail.source.kind === "free_form_text" ? (
                      <HighlightedSourceText
                        annotations={sourceSubmissionDetail.imported_evidence.flatMap(
                          (evidence) => evidence.annotations
                        )}
                        text={sourceSubmissionDetail.source.original_text ?? ""}
                      />
                    ) : sourceSubmissionDetail.source.kind === "structured_manual" ? (
                      <pre className="source-content">
                        {JSON.stringify(sourceSubmissionDetail.source.structured_payload, null, 2)}
                      </pre>
                    ) : sourceSubmissionDetail.source.source_file ? (
                      <>
                        <strong>{sourceSubmissionDetail.source.source_file.original_filename}</strong>
                        <p>{formatFileSize(sourceSubmissionDetail.source.source_file.byte_size)}</p>
                        {sourceSubmissionDetail.source.source_file.available ? (
                          <a
                            href={originalSourceFileUrl(
                              sourceSubmissionDetail.project_workspace_id,
                              sourceSubmissionDetail.id,
                              sourceSubmissionDetail.source.source_file.id
                            )}
                          >
                            Open original file
                          </a>
                        ) : (
                          <p className="status-message error">Original file unavailable</p>
                        )}
                      </>
                    ) : null}
                  </section>
                  <section className="detail-card">
                    <h3>Processing outcome</h3>
                    {sourceSubmissionDetail.processing_job ? (
                      <>
                        <strong>{sourceSubmissionDetail.processing_job.status}</strong>
                        <p>{sourceSubmissionDetail.processing_job.processor_name}</p>
                        {sourceSubmissionDetail.processing_job.error_message ? (
                          <p>{sourceSubmissionDetail.processing_job.error_message}</p>
                        ) : null}
                      </>
                    ) : (
                      <p>No Processing Job</p>
                    )}
                  </section>
                  <section className="detail-card">
                    <h3>Review Batch</h3>
                    {sourceSubmissionDetail.review_batch ? (
                      <a
                        href={sourceSubmissionDetail.review_batch.href}
                        onClick={(event) => {
                          event.preventDefault();
                          void handleOpenReviewBatch(sourceSubmissionDetail.review_batch!.id);
                        }}
                      >
                        Review Batch #{sourceSubmissionDetail.review_batch.id}
                      </a>
                    ) : (
                      <p>No Review Batch</p>
                    )}
                  </section>
                </div>
                <section className="evidence-section">
                  <h3>Imported evidence</h3>
                  {sourceSubmissionDetail.empty_state ? (
                    <div className="empty-state">{sourceSubmissionDetail.empty_state}</div>
                  ) : null}
                  {sourceSubmissionDetail.imported_evidence.map((evidence) => (
                    <article className="evidence-card" key={evidence.id}>
                      <div className="evidence-heading">
                        <strong>{evidence.source_label}</strong>
                        <span>Evidence Record #{evidence.id}</span>
                      </div>
                      {evidence.purchase_lines.map((purchaseLine) => (
                        <div className="source-purchase-line" key={purchaseLine.id}>
                          <a
                            href={purchaseLine.href}
                            onClick={(event) => {
                              event.preventDefault();
                              void handleOpenPurchaseLineDetail(purchaseLine.id);
                            }}
                          >
                            Purchase Line #{purchaseLine.id}
                          </a>
                          <p>
                            {purchaseLine.linked_records
                              .map((record) => `${record.name} · ${record.category_path}`)
                              .join(", ")}
                          </p>
                        </div>
                      ))}
                      <EvidenceInspection
                        annotations={evidence.annotations}
                        detectedCount={evidence.annotation_detected_count}
                        locator={evidence.locator}
                        omittedCount={evidence.annotation_omitted_count}
                        supportingContent={evidence.supporting_content}
                      />
                    </article>
                  ))}
                </section>
              </article>
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
      annotations: form.annotations.map((annotation) => ({
        ...annotation,
        text: annotation.text.trim()
      }))
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
    annotations: fallbackForm.annotations,
    remarksOrTerms: String(proposedPayload.remarks_or_terms ?? ""),
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
    observed_provider_text: objectString(proposedPayload, "observed_provider_text"),
    provider_memory_record_id: objectNumber(proposedPayload, "provider_memory_record_id"),
    provider_top_level_category:
      providerState === "external" ? providerTopLevelCategory ?? "Providers" : null,
    provider_subcategory:
      providerState === "external" ? providerSubcategory ?? "General" : null,
    bundle_quantity: objectString(proposedPayload, "bundle_quantity"),
    bundle_unit: objectString(proposedPayload, "bundle_unit"),
    installation_relationships: Array.isArray(proposedPayload.installation_relationships)
      ? proposedPayload.installation_relationships as ReviewedPurchaseLinePayload["installation_relationships"]
      : [],
    primary_evidence_span:
      proposedPayload.primary_evidence_span &&
      typeof proposedPayload.primary_evidence_span === "object"
        ? proposedPayload.primary_evidence_span as Record<string, unknown>
        : null,
    supporting_evidence_spans: Array.isArray(proposedPayload.supporting_evidence_spans)
      ? proposedPayload.supporting_evidence_spans as Record<string, unknown>[]
      : [],
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
    price_state:
      proposedPayload.price_state === "source_stated" ||
      proposedPayload.price_state === "calculated" ||
      proposedPayload.price_state === "defaulted" ||
      proposedPayload.price_state === "unknown"
        ? proposedPayload.price_state
        : null,
    calculation:
      proposedPayload.calculation && typeof proposedPayload.calculation === "object"
        ? proposedPayload.calculation as Record<string, unknown>
        : null,
    variance_warning:
      proposedPayload.variance_warning && typeof proposedPayload.variance_warning === "object"
        ? proposedPayload.variance_warning as Record<string, unknown>
        : null,
    currency: optionalText(String(proposedPayload.currency ?? "")),
    provider_name:
      providerState === "external"
        ? optionalText(String(proposedPayload.provider_name ?? ""))
        : null,
    purchase_date:
      typeof proposedPayload.purchase_date === "string" ? proposedPayload.purchase_date : null,
    remarks_or_terms: optionalText(String(proposedPayload.remarks_or_terms ?? "")),
    annotation_proposals: proposedAnnotations(candidate)
  };
}

function proposedAnnotations(candidate: ExtractedCandidateRead): ReviewedAnnotationProposal[] {
  const proposals = candidate.proposed_payload.annotation_proposals;
  return Array.isArray(proposals)
    ? proposals.filter(isReviewedAnnotationProposal).map((proposal) => ({ ...proposal }))
    : [];
}

function isReviewedAnnotationProposal(value: unknown): value is ReviewedAnnotationProposal {
  if (!value || typeof value !== "object") {
    return false;
  }
  const proposal = value as Record<string, unknown>;
  return (
    typeof proposal.proposal_id === "string" &&
    typeof proposal.text === "string" &&
    annotationTypes.includes(
      proposal.annotation_type as ReviewedAnnotationProposal["annotation_type"]
    ) &&
    annotationTargets.includes(proposal.target as ReviewedAnnotationProposal["target"]) &&
    typeof proposal.source_excerpt === "string" &&
    !!proposal.source_locator &&
    typeof proposal.source_locator === "object" &&
    ["source_field", "ai_suggested", "legacy_default", "reviewer_added"].includes(
      String(proposal.provenance)
    )
  );
}

function reviewerAddedAnnotation(
  candidate: ExtractedCandidateRead,
  index: number
): ReviewedAnnotationProposal {
  const grounding = candidate.source_grounding;
  const option = grounding?.options?.[0];
  return {
    proposal_id: `reviewer:${candidate.id}:${Date.now()}:${index}`,
    text: "",
    annotation_type: "general_qualifier",
    target: "purchase_line",
    source_excerpt: option?.source_excerpt ?? "",
    source_locator: option?.source_locator ?? { kind: "text_span", start: -1, end: -1 },
    provenance: "reviewer_added"
  };
}

function groundingOptionIndex(
  options: NonNullable<
    NonNullable<ExtractedCandidateRead["source_grounding"]>["options"]
  >,
  annotation: ReviewedAnnotationProposal
): number {
  const index = options.findIndex(
    (option) =>
      option.source_excerpt === annotation.source_excerpt &&
      JSON.stringify(option.source_locator) === JSON.stringify(annotation.source_locator)
  );
  return index < 0 ? 0 : index;
}

function validReviewerGrounding(annotation: ReviewedAnnotationProposal): boolean {
  const locator = annotation.source_locator;
  if (!annotation.source_excerpt.trim()) return false;
  if (locator.kind === "text_span") {
    return (
      typeof locator.start === "number" &&
      typeof locator.end === "number" &&
      locator.start >= 0 &&
      locator.end > locator.start
    );
  }
  return locator.kind === "structured_field" || locator.kind === "xlsx_cell";
}

function formatCandidateConfidence(value: unknown): string {
  return typeof value === "number" && value >= 0 && value <= 1
    ? `${Math.round(value * 100)}%`
    : "Not available";
}

function formatAnnotationProvenance(
  provenance: ReviewedAnnotationProposal["provenance"]
): string {
  const labels: Record<ReviewedAnnotationProposal["provenance"], string> = {
    source_field: "Source field",
    ai_suggested: "AI suggested",
    legacy_default: "Legacy default",
    reviewer_added: "Reviewer added"
  };
  return labels[provenance];
}

type ReviewedConcept = {
  concept_id: string | null;
  concept_type: "material" | "service";
  name: string;
  observed_name_text: string | null;
  project_memory_record_id: number | null;
  top_level_category: string | null;
  subcategory: string | null;
  quantity: string | null;
  unit: string | null;
  component_unit_price: string | null;
};

function reviewedConcepts(payload: ReviewedPurchaseLinePayload): ReviewedConcept[] {
  if (payload.linked_concepts && payload.linked_concepts.length > 0) {
    return payload.linked_concepts.map((concept) => ({
      concept_id: concept.concept_id ?? null,
      concept_type: concept.concept_type,
      name: concept.name ?? "",
      observed_name_text: concept.observed_name_text ?? null,
      project_memory_record_id: concept.project_memory_record_id ?? null,
      top_level_category: concept.top_level_category ?? null,
      subcategory: concept.subcategory ?? null,
      quantity: concept.quantity ?? null,
      unit: concept.unit ?? null,
      component_unit_price: concept.component_unit_price ?? null
    }));
  }

  return [
    {
      concept_id: null,
      concept_type: payload.line_type === "service" ? "service" : "material",
      name: payload.name ?? "",
      observed_name_text: null,
      project_memory_record_id: null,
      top_level_category: payload.top_level_category ?? null,
      subcategory: payload.subcategory ?? null,
      quantity: payload.quantity ?? null,
      unit: payload.unit ?? null,
      component_unit_price: null
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
    concept_id: objectString(value, "concept_id"),
    concept_type: conceptType,
    name: objectString(value, "name") ?? "",
    observed_name_text: objectString(value, "observed_name_text"),
    project_memory_record_id: objectNumber(value, "project_memory_record_id"),
    top_level_category: objectString(categorySuggestion, "top_level_category"),
    subcategory: objectString(categorySuggestion, "subcategory"),
    quantity: objectString(value, "quantity"),
    unit: objectString(value, "unit"),
    component_unit_price: objectString(value, "component_unit_price")
  };
}

function objectString(value: unknown, key: string): string | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const field = (value as Record<string, unknown>)[key];
  return typeof field === "string" && field.trim() !== "" ? field : null;
}

function objectNumber(value: unknown, key: string): number | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const field = (value as Record<string, unknown>)[key];
  return typeof field === "number" ? field : null;
}

function normalizeName(value: string): string {
  return value.trim().toLocaleLowerCase();
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

function countSimilarPendingTaxonomyGates(
  reviewBatchDetail: ReviewBatchDetail,
  selectedGate: CandidateTaxonomyGate
): number {
  const selectedPath = normalizeTaxonomyPart(selectedGate.original_ai_category_path);
  return reviewBatchDetail.candidates.flatMap((candidate) => candidate.taxonomy_gates ?? []).filter(
    (gate) =>
      gate.id !== selectedGate.id &&
      gate.active &&
      gate.status === "needs_decision" &&
      gate.subject_type === selectedGate.subject_type &&
      normalizeTaxonomyPart(gate.original_ai_category_path) === selectedPath
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
  const activeGates = (candidate.taxonomy_gates ?? []).filter((gate) => gate.active);
  if (activeGates.length > 0) {
    return activeGates.every((gate) => gate.status === "accepted")
      ? "Accepted"
      : "Needs decision";
  }

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

function formatLabel(value: string): string {
  const text = value.replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function formatLocator(locator: Record<string, unknown> | null | undefined): string {
  if (!locator) {
    return "Precise locator unavailable";
  }
  if (locator.kind === "text_span") {
    return `Characters ${locator.start}–${locator.end}`;
  }
  if (locator.kind === "xlsx_cell") {
    return `${locator.worksheet ?? "Worksheet"} · Cell ${locator.coordinate ?? "unknown"}`;
  }
  if (locator.kind === "xlsx_rows") {
    return `${locator.worksheet ?? "Worksheet"} · Source rows`;
  }
  if (typeof locator.field_path === "string") {
    return locator.field_path;
  }
  return "Precise locator unavailable";
}

type EvidenceAnnotationView =
  PurchaseLineDetail["evidence_records"][number]["annotations"][number];

function EvidenceInspection({
  annotations,
  detectedCount,
  locator,
  omittedCount,
  supportingContent
}: {
  annotations: EvidenceAnnotationView[];
  detectedCount: number;
  locator: Record<string, unknown> | null;
  omittedCount: number;
  supportingContent: Record<string, unknown>;
}) {
  const rowSnapshot = Array.isArray(supportingContent.row_snapshot)
    ? supportingContent.row_snapshot
    : [];
  const annotationGroups = groupAnnotationsByTarget(annotations);
  return (
    <div className="evidence-inspection">
      {locator ? <code>{formatLocator(locator)}</code> : <p>Precise locator unavailable</p>}
      {rowSnapshot.length > 0 ? (
        <div className="xlsx-row-snapshot" role="table" aria-label="Source row snapshot">
          {rowSnapshot.map((rawCell, index) => {
            const cell = rawCell as Record<string, unknown>;
            return (
              <div className="xlsx-snapshot-cell" key={String(cell.coordinate ?? index)}>
                <strong>{String(cell.header ?? cell.coordinate ?? `Column ${index + 1}`)}</strong>
                {cell.annotation ? <mark>{String(cell.value ?? "")}</mark> : <span>{String(cell.value ?? "")}</span>}
              </div>
            );
          })}
        </div>
      ) : (
        <HighlightedEvidenceContent annotations={annotations} content={supportingContent} />
      )}
      {omittedCount > 0 ? (
        <p className="status-message error">
          Annotation extraction limit reached — 20 of {detectedCount} source-grounded annotation
          proposals were retained. Review the source and add any omitted qualifiers that matter.
        </p>
      ) : null}
      {annotationGroups.map((group) => (
        <section className="annotation-target-group" key={group.key}>
          <h4>{formatLabel(group.target.record_type)} · {group.target.name}</h4>
          {group.annotations.map((annotation) => (
            <div className="annotation-card" key={annotation.id}>
              <span className="annotation-type">{formatLabel(annotation.annotation_type)}</span>
              <strong>{annotation.text}</strong>
              <blockquote>{annotation.source_excerpt}</blockquote>
              <p className="source-locator">{formatLocator(annotation.source_locator)}</p>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}

function groupAnnotationsByTarget(annotations: EvidenceAnnotationView[]) {
  const groups = new Map<
    string,
    {
      key: string;
      target: EvidenceAnnotationView["target"];
      annotations: EvidenceAnnotationView[];
    }
  >();
  annotations.forEach((annotation) => {
    const key = `${annotation.target.record_type}:${annotation.target.memory_record_id}`;
    const group = groups.get(key);
    if (group) {
      group.annotations.push(annotation);
    } else {
      groups.set(key, { key, target: annotation.target, annotations: [annotation] });
    }
  });
  return Array.from(groups.values());
}

function HighlightedEvidenceContent({
  annotations,
  content
}: {
  annotations: EvidenceAnnotationView[];
  content: Record<string, unknown>;
}) {
  const serialized = JSON.stringify(content, null, 2);
  const excerpts = Array.from(
    new Set(annotations.map((annotation) => annotation.source_excerpt).filter(Boolean))
  );
  if (excerpts.length === 0) {
    return <pre className="source-content">{serialized}</pre>;
  }
  const matches = excerpts
    .flatMap((excerpt) => {
      const start = serialized.indexOf(excerpt);
      return start >= 0 ? [{ start, end: start + excerpt.length }] : [];
    })
    .sort((left, right) => left.start - right.start);
  const rendered: ReactNode[] = [];
  let cursor = 0;
  matches.forEach((match, index) => {
    if (match.start < cursor) return;
    rendered.push(serialized.slice(cursor, match.start));
    rendered.push(
      <mark key={`${match.start}:${index}`}>
        {serialized.slice(match.start, match.end)}
      </mark>
    );
    cursor = match.end;
  });
  rendered.push(serialized.slice(cursor));
  return <pre className="source-content">{rendered}</pre>;
}

function HighlightedSourceText({
  annotations,
  text
}: {
  annotations: EvidenceAnnotationView[];
  text: string;
}) {
  const firstHighlightRef = useRef<HTMLElement | null>(null);
  const spans = annotations
    .map((annotation) => annotation.source_locator)
    .filter(
      (locator): locator is { kind: string; start: number; end: number } =>
        !!locator &&
        locator.kind === "text_span" &&
        typeof locator.start === "number" &&
        typeof locator.end === "number"
    )
    .sort((left, right) => left.start - right.start);
  const spanKey = spans.map((span) => `${span.start}:${span.end}`).join("|");
  useEffect(() => {
    firstHighlightRef.current?.scrollIntoView({ block: "center" });
  }, [text, spanKey]);
  if (spans.length === 0) {
    return <pre className="source-content">{text}</pre>;
  }
  const content: ReactNode[] = [];
  let cursor = 0;
  spans.forEach((span, index) => {
    if (span.start < cursor || span.start < 0 || span.end > text.length) return;
    content.push(text.slice(cursor, span.start));
    content.push(
      <mark
        key={`${span.start}:${span.end}:${index}`}
        ref={index === 0 ? firstHighlightRef : undefined}
      >
        {text.slice(span.start, span.end)}
      </mark>
    );
    cursor = span.end;
  });
  content.push(text.slice(cursor));
  return <pre className="source-content">{content}</pre>;
}

export default App;
