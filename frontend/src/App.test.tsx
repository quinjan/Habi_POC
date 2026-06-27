import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import App from "./App";

describe("Project Workspace app shell", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/");

    let nextProjectId = 2;
    const projectList = [{ id: 1, project_name: "Arnaiz Residence Renovation" }];
    const purchaseLinesByProject = new Map<number, unknown[]>([[1, []]]);
    const processingJobsByProject = new Map<number, unknown[]>([[1, []]]);
    const projectNamesById = new Map<number, string>([[1, "Arnaiz Residence Renovation"]]);
    const taxonomyLeafPathsByProject = new Map<
      number,
      { id: number; name: string; parent_id: number; path: string }[]
    >([[1, []]]);

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = input.toString();
        const method = init?.method ?? "GET";

        if (url === "/api/project-workspaces" && method === "GET") {
          return jsonResponse({ items: projectList });
        }

        if (url === "/api/project-workspaces" && method === "POST") {
          const body = JSON.parse(String(init?.body));
          const createdProject = { id: nextProjectId++, ...body };
          projectList.push({
            id: createdProject.id,
            project_name: createdProject.project_name
          });
          projectNamesById.set(createdProject.id, createdProject.project_name);
          purchaseLinesByProject.set(createdProject.id, []);
          return jsonResponse(createdProject, 201);
        }

        const purchaseLinesMatch = url.match(
          /^\/api\/project-workspaces\/(\d+)\/purchase-lines$/
        );
        if (purchaseLinesMatch && method === "GET") {
          const projectId = Number(purchaseLinesMatch[1]);
          return jsonResponse({
            project_workspace: {
              id: projectId,
              project_name: projectNamesById.get(projectId)
            },
            items: purchaseLinesByProject.get(projectId) ?? []
          });
        }

        const taxonomyNodesMatch = url.match(
          /^\/api\/project-workspaces\/(\d+)\/taxonomy-nodes\?leaf_only=true$/
        );
        if (taxonomyNodesMatch && method === "GET") {
          const projectId = Number(taxonomyNodesMatch[1]);
          return jsonResponse({
            items: taxonomyLeafPathsByProject.get(projectId) ?? []
          });
        }

        const processingJobsMatch = url.match(
          /^\/api\/project-workspaces\/(\d+)\/processing-jobs$/
        );
        if (processingJobsMatch && method === "GET") {
          const projectId = Number(processingJobsMatch[1]);
          return jsonResponse({
            items: processingJobsByProject.get(projectId) ?? []
          });
        }

        if (url === "/api/project-workspaces/1/manual-source-entries" && method === "POST") {
          const body = JSON.parse(String(init?.body));
          const nextIndex = (processingJobsByProject.get(1)?.length ?? 0) + 1;
          const sourceSubmission = {
            id: 29 + nextIndex,
            project_workspace_id: 1,
            submission_type: "manual_source_entry",
            submitted_at: "2026-06-27T00:00:00Z",
            entered_by: null
          };
          const manualSourceEntry = {
            id: 39 + nextIndex,
            project_workspace_id: 1,
            source_submission_id: sourceSubmission.id,
            entry_type: body.entry_type,
            structured_payload: body.structured_payload ?? null,
            original_text: body.original_text ?? null
          };
          const isReviewReady =
            (body.entry_type === "structured_row" && body.structured_payload?.quantity === "20") ||
            (body.entry_type === "free_form_text" &&
              String(body.original_text).includes("PVC pipe"));
          const isNoCandidates =
            body.entry_type === "free_form_text" &&
            body.original_text === "Follow up with foreman";
          const isFailed =
            body.entry_type === "free_form_text" &&
            body.original_text === "provider unavailable";
          const listJobStatus = isReviewReady
            ? "review_ready"
            : isNoCandidates
              ? "no_candidates_found"
              : isFailed
                ? "failed"
              : "queued";
          const processingJob = {
            id: 49 + nextIndex,
            project_workspace_id: 1,
            source_submission_id: sourceSubmission.id,
            source_type: "manual_source_entry",
            processor_name:
              body.entry_type === "free_form_text"
                ? "ai_manual_free_form_v1"
                : "structured_manual_row_v1",
            created_at: "2026-06-27T00:00:00Z",
            started_at: null,
            finished_at: null,
            error_message: null,
            diagnostics: null,
            status: "queued",
            candidate_count: 0,
            review_batch_id: null
          };
          processingJobsByProject.set(1, [
            {
              processing_job: processingJob,
              source_submission: {
                id: sourceSubmission.id,
                submission_type: "manual_source_entry",
                submitted_at: sourceSubmission.submitted_at
              },
              review_batch_id: null
            },
            ...(processingJobsByProject.get(1) ?? [])
          ]);
          processingJobsByProject.set(1, [
            {
              processing_job: {
                ...processingJob,
                status: listJobStatus,
                candidate_count: isReviewReady ? 1 : 0,
                review_batch_id: isReviewReady ? 10 : null,
                error_message: isFailed ? "provider unavailable" : null
              },
              source_submission: {
                id: sourceSubmission.id,
                submission_type: "manual_source_entry",
                submitted_at: sourceSubmission.submitted_at
              },
              review_batch_id: isReviewReady ? 10 : null
            },
            ...(processingJobsByProject.get(1) ?? []).slice(1)
          ]);

          return jsonResponse(
            {
              source_submission: sourceSubmission,
              manual_source_entry: manualSourceEntry,
              processing_job: processingJob
            },
            201
          );
        }

        if (url === "/api/project-workspaces/1/review-batches/10" && method === "GET") {
          return jsonResponse({
            review_batch: {
              id: 10,
              project_workspace_id: 1,
              source_submission_id: 30,
              status: "review_pending"
            },
            candidates: [
              buildCandidate(20, "PVC pipe", "material", "Plumbing", "Pipes"),
              buildCandidate(21, "PVC elbow", "material", "Plumbing", "Pipes")
            ],
            duplicate_groups: [],
            duplicate_conflicts: [],
            taxonomy_decisions: []
          });
        }

        if (url === "/api/project-workspaces/1/review-batches/10/review-draft" && method === "PUT") {
          const body = JSON.parse(String(init?.body));
          return jsonResponse({
            review_batch: {
              id: 10,
              project_workspace_id: 1,
              source_submission_id: 30,
              status: "ready_to_import"
            },
            candidates: body.candidates.map(
              (item: { candidate_id: number; included: boolean; reviewed_payload: unknown }) => ({
                ...buildCandidate(
                  item.candidate_id,
                  item.candidate_id === 20 ? "PVC pipe" : "PVC elbow",
                  "material",
                  "Plumbing",
                  "Pipes"
                ),
                status: item.included ? "approved_for_import" : "rejected_for_import",
                decision: item.included ? "approved" : "rejected",
                reviewed_payload: item.included ? item.reviewed_payload : null
              })
            ),
            duplicate_groups: [],
            duplicate_conflicts: [],
            taxonomy_decisions: []
          });
        }

        if (
          url === "/api/project-workspaces/1/review-batches/10/taxonomy-mappings" &&
          method === "POST"
        ) {
          return jsonResponse({
            review_batch: {
              id: 10,
              project_workspace_id: 1,
              source_submission_id: 30,
              status: "review_pending"
            },
            candidates: [
              {
                ...buildCandidate(20, "PVC pipe", "material", "Mechanical", "Pipe Materials"),
                reviewed_payload: {
                  line_type: "material",
                  name: "PVC pipe",
                  top_level_category: "Plumbing",
                  subcategory: "Pipes",
                  quantity: "20",
                  unit: "pcs",
                  price: "1500",
                  currency: "PHP",
                  provider_name: "ABC Trading"
                }
              },
              {
                ...buildCandidate(21, "PVC elbow", "material", "Mechanical", "Pipe Materials"),
                reviewed_payload: {
                  line_type: "material",
                  name: "PVC elbow",
                  top_level_category: "Plumbing",
                  subcategory: "Pipes",
                  quantity: "20",
                  unit: "pcs",
                  price: "1500",
                  currency: "PHP",
                  provider_name: "ABC Trading"
                }
              }
            ],
            duplicate_groups: [],
            duplicate_conflicts: [],
            taxonomy_decisions: [
              {
                id: 70,
                project_workspace_id: 1,
                review_batch_id: 10,
                suggested_top_level_category: "Mechanical",
                suggested_subcategory: "Pipe Materials",
                normalized_suggested_path_key: "mechanical / pipe materials",
                decision: "mapped",
                resolved_taxonomy_node_id: 50
              }
            ]
          });
        }

        if (
          url === "/api/project-workspaces/1/review-batches/10/candidates/20/decision" &&
          method === "POST"
        ) {
          const body = JSON.parse(String(init?.body));
          return jsonResponse({
            id: 20,
            project_workspace_id: 1,
            review_batch_id: 10,
            source_submission_id: 30,
            status: "approved_for_import",
            proposed_payload: body.reviewed_payload,
            decision: body.decision,
            merged_into_candidate_id: null,
            reviewed_payload: body.reviewed_payload,
            taxonomy_gate: null,
            taxonomy_default: null
          });
        }

        if (
          url === "/api/project-workspaces/1/review-batches/10/taxonomy-decisions" &&
          method === "POST"
        ) {
          const body = JSON.parse(String(init?.body));
          if (body.decision === "approved") {
            taxonomyLeafPathsByProject.set(1, [
              {
                id: 50,
                name: "Pipes",
                parent_id: 49,
                path: "Plumbing / Pipes"
              }
            ]);
          }
          return jsonResponse(
            {
              review_batch: {
                id: 10,
                project_workspace_id: 1,
                source_submission_id: 30,
                status: "review_pending"
              },
              candidates: [
                {
                  id: 20,
                  project_workspace_id: 1,
                  review_batch_id: 10,
                  source_submission_id: 30,
                  status: "pending_review",
                  proposed_payload: {
                    line_type: "material",
                    name: "PVC pipe",
                    quantity: "20",
                    unit: "pcs",
                    price: "1500",
                    currency: "PHP",
                    provider_name: "ABC Trading",
                    purchase_date: null,
                    remarks_or_terms: null,
                    category_suggestion: {
                      top_level_category: "Plumbing",
                      subcategory: "Pipes"
                    }
                  },
                  decision: null,
                  merged_into_candidate_id: null,
                  reviewed_payload: null,
                  taxonomy_gate:
                    body.decision === "rejected"
                      ? {
                          status: "new_taxonomy_path",
                          reason: "new_taxonomy_path",
                          suggested_category_path: "Plumbing / Pipes",
                          resolved_category_path: null,
                          decision: null,
                          taxonomy_decision_id: null,
                          prior_rejection: {
                            taxonomy_decision_id: 70,
                            suggested_category_path: "Plumbing / Pipes"
                          }
                        }
                      : {
                          status:
                            body.decision === "mapped"
                              ? "resolved_by_mapping"
                              : "resolved_by_approval",
                          reason:
                            body.decision === "mapped"
                              ? "mapped_taxonomy_decision"
                              : "approved_taxonomy_decision",
                          suggested_category_path: "Plumbing / Pipes",
                          resolved_category_path: "Plumbing / Pipes",
                          decision: body.decision,
                          taxonomy_decision_id: 70,
                          prior_rejection: null
                        },
                  taxonomy_default:
                    body.decision === "rejected"
                      ? null
                      : {
                          resolved_category_path: "Plumbing / Pipes",
                          source:
                            body.decision === "mapped"
                              ? "mapped_taxonomy_decision"
                              : "approved_taxonomy_decision",
                          provenance_text:
                            body.decision === "mapped"
                              ? "Defaulted from a previous mapping: Plumbing / Pipes -> Plumbing / Pipes"
                              : "Defaulted from a previous approved taxonomy decision: Plumbing / Pipes",
                          taxonomy_decision_id: 70
                        }
                }
              ],
              duplicate_groups: [],
              duplicate_conflicts: [],
              taxonomy_decisions: [
                {
                  id: 70,
                  project_workspace_id: 1,
                  review_batch_id: 10,
                  suggested_top_level_category: "Plumbing",
                  suggested_subcategory: "Pipes",
                  normalized_suggested_path_key: "plumbing / pipes",
                  decision: body.decision,
                  resolved_taxonomy_node_id: body.decision === "rejected" ? null : 50
                }
              ]
            },
            201
          );
        }

        if (
          url === "/api/project-workspaces/1/review-batches/10/import" &&
          method === "POST"
        ) {
          purchaseLinesByProject.set(1, [
            {
              id: 40,
              item_or_service_name: "PVC pipe",
              line_type: "material",
              provider_name: "ABC Trading",
              provider_type: "external",
              provider_role: "material_supplier",
              quantity: "20",
              unit: "pcs",
              unit_state: "known",
              price: "1500",
              currency: "PHP",
              price_state: "known",
              purchase_date: "2025-07-12",
              date_state: "known",
              category_path: "Plumbing / Pipes",
              has_evidence: true,
              source_label: "Manual Source Entry"
            }
          ]);
          return jsonResponse({ imported_purchase_lines: [{ id: 40 }] });
        }

        return jsonResponse({ detail: "Not found" }, 404);
      })
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  test("reviewer creates a workspace, selects it, and lands on empty Purchase Lines", async () => {
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Project Workspaces" })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Arnaiz Residence Renovation" })).toBeInTheDocument();

    await user.type(screen.getByLabelText("Project name"), "Ortigas Office Fit-Out");
    await user.type(screen.getByLabelText("Project type"), "Commercial fit-out");
    await user.type(screen.getByLabelText("Location"), "Pasig City");
    await user.type(screen.getByLabelText("Completion year"), "2024");
    await user.type(screen.getByLabelText("Floor area"), "420 sqm");
    await user.type(screen.getByLabelText("Trade scopes"), "HVAC, Electrical");
    await user.type(screen.getByLabelText("Client or owner"), "Ortigas Holdings");
    await user.type(screen.getByLabelText("Notes"), "Completed fit-out purchasing records.");
    await user.click(screen.getByRole("button", { name: "Create Project Workspace" }));

    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Ortigas Office Fit-Out" })
    );

    expect(window.location.pathname).toBe("/projects/2/purchase-lines");
    expect(
      await screen.findByRole("heading", { name: "Purchase Lines" })
    ).toBeInTheDocument();
    const selectedWorkspace = screen.getByRole("region", {
      name: "Selected Project Workspace"
    });
    expect(within(selectedWorkspace).getByText("Ortigas Office Fit-Out")).toBeInTheDocument();
    expect(within(selectedWorkspace).getByText("No Purchase Lines yet")).toBeInTheDocument();
  });

  test("reviewer submits multiple manual entries and sees them in the job queue", async () => {
    const user = userEvent.setup();

    render(<App />);

    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );
    await user.click(screen.getByRole("tab", { name: "Upload / Review" }));

    await user.type(screen.getByLabelText("Item or service name"), "PVC pipe");
    await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));

    await user.click(screen.getByRole("button", { name: "Free-Form Text" }));
    await user.type(
      screen.getByLabelText("Free-form source text"),
      "Hauling service by ABC Trading"
    );
    await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));

    const queue = await screen.findByRole("region", { name: "Processing Job queue" });
    expect(within(queue).getAllByText("queued")).toHaveLength(2);
    expect(screen.queryByRole("heading", { name: "Review Candidate" })).not.toBeInTheDocument();
  });

  test("reviewer opens Upload Review tab and navigates to a dedicated Review Batch page", async () => {
    const user = userEvent.setup();

    render(<App />);

    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );

    expect(await screen.findByRole("tab", { name: "Purchase Lines" })).toHaveAttribute(
      "aria-selected",
      "true"
    );
    await user.click(screen.getByRole("tab", { name: "Upload / Review" }));
    expect(window.location.pathname).toBe("/projects/1/upload-review");
    expect(screen.getByRole("heading", { name: "Create Manual Source Entry" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Processing Job queue" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Free-Form Text" }));
    await user.type(
      screen.getByLabelText("Free-form source text"),
      "PVC pipe, 20 pcs, from ABC Trading, PHP 1,500"
    );
    await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));
    await user.click(await screen.findByRole("button", { name: "Open Review Batch" }));

    expect(window.location.pathname).toBe("/projects/1/review-batches/10");
    expect(await screen.findByRole("heading", { name: "Review Batch #10" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back to Upload / Review" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Purchase Lines" })).not.toBeInTheDocument();
  });

  test("reviewer saves multi-candidate inclusion draft from the Review Batch page", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.mocked(fetch);

    render(<App />);

    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );
    await user.click(screen.getByRole("tab", { name: "Upload / Review" }));
    await user.click(screen.getByRole("button", { name: "Free-Form Text" }));
    await user.type(
      screen.getByLabelText("Free-form source text"),
      "PVC pipe and PVC elbow, 20 pcs, from ABC Trading, PHP 1,500"
    );
    await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));
    await user.click(await screen.findByRole("button", { name: "Open Review Batch" }));

    const batch = await screen.findByRole("region", { name: "Review Batch" });
    expect(within(batch).getByText("PVC pipe")).toBeInTheDocument();
    expect(within(batch).getByText("PVC elbow")).toBeInTheDocument();
    const elbowCheckbox = within(batch).getByRole("checkbox", { name: "Include PVC elbow" });
    expect(elbowCheckbox).toBeChecked();
    await user.click(elbowCheckbox);
    expect(elbowCheckbox).not.toBeChecked();

    expect(fetchSpy).not.toHaveBeenCalledWith(
      expect.stringContaining("/review-draft"),
      expect.anything()
    );

    await user.click(within(batch).getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Review draft saved.")).toBeInTheDocument();
    const draftCall = fetchSpy.mock.calls.find(([input]) =>
      input.toString().includes("/review-draft")
    );
    expect(draftCall).toBeDefined();
    expect(JSON.parse(String(draftCall?.[1]?.body))).toEqual({
      candidates: [
        expect.objectContaining({ candidate_id: 20, included: true }),
        expect.objectContaining({ candidate_id: 21, included: false, reviewed_payload: null })
      ]
    });
  });

  test("reviewer imports included candidates after saving the latest draft", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.mocked(fetch);

    render(<App />);

    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );
    await user.click(screen.getByRole("tab", { name: "Upload / Review" }));
    await user.click(screen.getByRole("button", { name: "Free-Form Text" }));
    await user.type(screen.getByLabelText("Free-form source text"), "PVC pipe, 20 pcs");
    await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));
    await user.click(await screen.findByRole("button", { name: "Open Review Batch" }));

    await user.click(screen.getByRole("button", { name: "Import Included Candidates" }));

    await waitFor(() => {
      expect(window.location.pathname).toBe("/projects/1/purchase-lines");
    });
    expect(await screen.findByRole("heading", { name: "Purchase Lines" })).toBeInTheDocument();
    const calledPaths = fetchSpy.mock.calls.map(([input]) => input.toString());
    expect(calledPaths.findIndex((path) => path.includes("/review-draft"))).toBeLessThan(
      calledPaths.findIndex((path) => path.includes("/import"))
    );
  });

  test("reviewer saves taxonomy mapping and preserves unsaved inclusion choices", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.mocked(fetch);

    render(<App />);

    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );
    await user.click(screen.getByRole("tab", { name: "Upload / Review" }));
    await user.click(screen.getByRole("button", { name: "Free-Form Text" }));
    await user.type(
      screen.getByLabelText("Free-form source text"),
      "PVC pipe and PVC elbow, 20 pcs, from ABC Trading, PHP 1,500"
    );
    await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));
    await user.click(await screen.findByRole("button", { name: "Open Review Batch" }));

    await user.click(screen.getByRole("checkbox", { name: "Include PVC elbow" }));
    await user.click(screen.getAllByRole("button", { name: "Details" })[0]);
    const detail = await screen.findByRole("dialog", { name: "Candidate Detail" });
    await user.click(within(detail).getByRole("button", { name: "Change Taxonomy" }));

    const taxonomy = await screen.findByRole("dialog", { name: "Resolve Taxonomy" });
    await user.clear(within(taxonomy).getByLabelText("Top-Level Category"));
    await user.type(within(taxonomy).getByLabelText("Top-Level Category"), "Plumbing");
    await user.clear(within(taxonomy).getByLabelText("Subcategory"));
    await user.type(within(taxonomy).getByLabelText("Subcategory"), "Pipes");
    await user.click(
      within(taxonomy).getByLabelText("Apply to similar taxonomy in this Review Batch")
    );
    await user.click(within(taxonomy).getByRole("button", { name: "Save Mapping" }));

    expect((await screen.findAllByText("Plumbing / Pipes")).length).toBeGreaterThan(1);
    expect(screen.getByRole("checkbox", { name: "Include PVC elbow" })).not.toBeChecked();
    const mappingCall = fetchSpy.mock.calls.find(([input]) =>
      input.toString().includes("/taxonomy-mappings")
    );
    expect(JSON.parse(String(mappingCall?.[1]?.body))).toEqual({
      candidate_id: 20,
      top_level_category: "Plumbing",
      subcategory: "Pipes",
      apply_to_similar: true
    });
  });

  test("reviewer opens Candidate Detail and sees review context", async () => {
    const user = userEvent.setup();

    render(<App />);

    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );
    await user.click(screen.getByRole("tab", { name: "Upload / Review" }));
    await user.click(screen.getByRole("button", { name: "Free-Form Text" }));
    await user.type(
      screen.getByLabelText("Free-form source text"),
      "PVC pipe and PVC elbow, 20 pcs, from ABC Trading, PHP 1,500"
    );
    await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));
    await user.click(await screen.findByRole("button", { name: "Open Review Batch" }));

    await user.click(screen.getByRole("checkbox", { name: "Include PVC elbow" }));
    await user.click(screen.getAllByRole("button", { name: "Details" })[1]);

    const detail = await screen.findByRole("dialog", { name: "Candidate Detail" });
    expect(within(detail).getByText("Excluded draft")).toBeInTheDocument();
    expect(within(detail).getByText("Source Submission #30")).toBeInTheDocument();
    expect(within(detail).getByText("Taxonomy Status")).toBeInTheDocument();
    expect(within(detail).getByText("AI suggested default")).toBeInTheDocument();
    expect(within(detail).getByText("Proposed Fields")).toBeInTheDocument();
    expect(within(detail).getByText("Reviewed Fields")).toBeInTheDocument();
    expect(within(detail).getAllByText("PVC elbow").length).toBeGreaterThan(1);
  });

  test("reviewer submits a manual source entry, approves it, and sees the imported purchase line", async () => {
    const user = userEvent.setup();

    render(<App />);

    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );
    await user.click(screen.getByRole("tab", { name: "Upload / Review" }));

    await user.selectOptions(screen.getByLabelText("Line type"), "material");
    await user.type(screen.getByLabelText("Item or service name"), "PVC pipe");
    await user.type(screen.getByLabelText("Quantity"), "20");
    await user.type(screen.getByLabelText("Unit"), "pcs");
    await user.type(screen.getByLabelText("Price"), "1500");
    await user.type(screen.getByLabelText("Provider"), "ABC Trading");
    await user.type(screen.getByLabelText("Purchase date"), "2025-07-12");
    await user.type(screen.getByLabelText("Remarks or terms"), "Delivery included");
    await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));

    await user.click(await screen.findByRole("button", { name: "Open Review Batch" }));
    expect(await screen.findByRole("heading", { name: "Review Batch #10" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Import Included Candidates" }));

    const selectedWorkspace = screen.getByRole("region", {
      name: "Selected Project Workspace"
    });
    expect(await within(selectedWorkspace).findByText("PVC pipe")).toBeInTheDocument();
    expect(within(selectedWorkspace).getByText("ABC Trading")).toBeInTheDocument();
    expect(within(selectedWorkspace).getByText("Plumbing / Pipes")).toBeInTheDocument();
    expect(within(selectedWorkspace).getAllByText("Manual Source Entry").length).toBeGreaterThan(0);
  });

  test("reviewer submits free-form text, reviews the parsed candidate, and imports it", async () => {
    const user = userEvent.setup();

    render(<App />);

    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );
    await user.click(screen.getByRole("tab", { name: "Upload / Review" }));

    await user.click(screen.getByRole("button", { name: "Free-Form Text" }));
    await user.type(
      screen.getByLabelText("Free-form source text"),
      "PVC pipe, 20 pcs, from ABC Trading, PHP 1,500"
    );
    await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));

    expect(await screen.findByText("review_ready")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Open Review Batch" }));
    expect(await screen.findByRole("heading", { name: "Review Batch #10" })).toBeInTheDocument();
    expect(screen.getByText("PVC pipe")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Import Included Candidates" }));

    const selectedWorkspace = screen.getByRole("region", {
      name: "Selected Project Workspace"
    });
    expect(await within(selectedWorkspace).findByText("PVC pipe")).toBeInTheDocument();
    expect(within(selectedWorkspace).getByText("ABC Trading")).toBeInTheDocument();
  });

  test("reviewer sees no candidates found for unusable free-form text", async () => {
    const user = userEvent.setup();

    render(<App />);

    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );
    await user.click(screen.getByRole("tab", { name: "Upload / Review" }));

    await user.click(screen.getByRole("button", { name: "Free-Form Text" }));
    await user.type(screen.getByLabelText("Free-form source text"), "Follow up with foreman");
    await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));

    expect(await screen.findByText("no_candidates_found")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Review Candidate" })).not.toBeInTheDocument();
  });

  test("reviewer sees free-form job terminal states in the queue", async () => {
    const user = userEvent.setup();

    render(<App />);

    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );
    await user.click(screen.getByRole("tab", { name: "Upload / Review" }));

    await user.click(screen.getByRole("button", { name: "Free-Form Text" }));
    await user.type(
      screen.getByLabelText("Free-form source text"),
      "PVC pipe, 20 pcs, from ABC Trading, PHP 1,500"
    );
    await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));

    await user.type(screen.getByLabelText("Free-form source text"), "Follow up with foreman");
    await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));

    await user.type(screen.getByLabelText("Free-form source text"), "provider unavailable");
    await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));

    const queue = await screen.findByRole("region", { name: "Processing Job queue" });
    expect(within(queue).getByText("review_ready")).toBeInTheDocument();
    expect(within(queue).getByText("no_candidates_found")).toBeInTheDocument();
    expect(within(queue).getByText("failed")).toBeInTheDocument();
    expect(within(queue).getByText("provider unavailable")).toBeInTheDocument();
    expect(within(queue).queryByText("Unclear thing")).not.toBeInTheDocument();
  });
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

function buildCandidate(
  id: number,
  name: string,
  lineType: "material" | "service",
  topLevelCategory: string,
  subcategory: string
) {
  return {
    id,
    project_workspace_id: 1,
    review_batch_id: 10,
    source_submission_id: 30,
    status: "pending_review",
    proposed_payload: {
      line_type: lineType,
      name,
      quantity: "20",
      unit: "pcs",
      price: "1500",
      currency: "PHP",
      provider_name: "ABC Trading",
      purchase_date: null,
      remarks_or_terms: null,
      category_suggestion: {
        top_level_category: topLevelCategory,
        subcategory
      }
    },
    decision: null,
    merged_into_candidate_id: null,
    reviewed_payload: null,
    taxonomy_gate: null,
    taxonomy_default: null
  };
}
