import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import App from "./App";

describe("Project Workspace app shell", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/");

    let nextProjectId = 2;
    const projectList = [{ id: 1, project_name: "Arnaiz Residence Renovation" }];
    const purchaseLinesByProject = new Map<number, unknown[]>([[1, []]]);
    const projectNamesById = new Map<number, string>([[1, "Arnaiz Residence Renovation"]]);

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

        if (url === "/api/project-workspaces/1/manual-source-entries" && method === "POST") {
          const body = JSON.parse(String(init?.body));
          const sourceSubmission = {
            id: 30,
            project_workspace_id: 1,
            submission_type: "manual_source_entry",
            submitted_at: "2026-06-27T00:00:00Z",
            entered_by: null
          };
          const manualSourceEntry = {
            id: 31,
            project_workspace_id: 1,
            source_submission_id: 30,
            entry_type: body.entry_type,
            structured_payload: body.structured_payload ?? null,
            original_text: body.original_text ?? null
          };
          const processingJobBase = {
            id: 32,
            project_workspace_id: 1,
            source_submission_id: 30,
            source_type: "manual_source_entry",
            processor_name:
              body.entry_type === "free_form_text"
                ? "manual_free_form_stub_v1"
                : "structured_manual_row_v1",
            created_at: "2026-06-27T00:00:00Z",
            started_at: "2026-06-27T00:00:00Z",
            finished_at: "2026-06-27T00:00:00Z",
            error_message: null
          };

          if (body.entry_type === "free_form_text" && body.original_text === "Follow up with foreman") {
            return jsonResponse(
              {
                source_submission: sourceSubmission,
                manual_source_entry: manualSourceEntry,
                processing_job: {
                  ...processingJobBase,
                  status: "no_candidates_found",
                  candidate_count: 0,
                  review_batch_id: null
                },
                review_batch: null,
                candidates: []
              },
              201
            );
          }

          const proposedPayload =
            body.entry_type === "free_form_text"
              ? {
                  line_type: "material",
                  name: "PVC pipe",
                  quantity: "20",
                  unit: "pcs",
                  price: "1500",
                  currency: "PHP",
                  provider_name: "ABC Trading",
                  purchase_date: null,
                  remarks_or_terms: null,
                  raw_text: body.original_text,
                  confidence: 0.72,
                  category_suggestion: {
                    top_level_category: "Plumbing",
                    subcategory: "Pipes"
                  },
                  evidence: {
                    source_submission_id: 30,
                    snippet: body.original_text,
                    locator: "manual_source_entry.original_text"
                  }
                }
              : body.structured_payload;

          return jsonResponse(
            {
              source_submission: sourceSubmission,
              manual_source_entry: manualSourceEntry,
              processing_job: {
                ...processingJobBase,
                status: "review_ready",
                candidate_count: 1,
                review_batch_id: 10
              },
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
                  proposed_payload: proposedPayload,
                  decision: null,
                  merged_into_candidate_id: null,
                  reviewed_payload: null
                }
              ]
            },
            201
          );
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
            reviewed_payload: body.reviewed_payload
          });
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

  test("reviewer submits a manual source entry, approves it, and sees the imported purchase line", async () => {
    const user = userEvent.setup();

    render(<App />);

    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );

    await user.selectOptions(screen.getByLabelText("Line type"), "material");
    await user.type(screen.getByLabelText("Item or service name"), "PVC pipe");
    await user.type(screen.getByLabelText("Quantity"), "20");
    await user.type(screen.getByLabelText("Unit"), "pcs");
    await user.type(screen.getByLabelText("Price"), "1500");
    await user.type(screen.getByLabelText("Provider"), "ABC Trading");
    await user.type(screen.getByLabelText("Purchase date"), "2025-07-12");
    await user.type(screen.getByLabelText("Remarks or terms"), "Delivery included");
    await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));

    expect(await screen.findByRole("heading", { name: "Review Candidate" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Top-level category"), "Plumbing");
    await user.type(screen.getByLabelText("Subcategory"), "Pipes");
    await user.click(screen.getByRole("button", { name: "Approve Candidate" }));
    await user.click(await screen.findByRole("button", { name: "Import Approved Batch" }));

    const selectedWorkspace = screen.getByRole("region", {
      name: "Selected Project Workspace"
    });
    expect(await within(selectedWorkspace).findByText("PVC pipe")).toBeInTheDocument();
    expect(within(selectedWorkspace).getByText("ABC Trading")).toBeInTheDocument();
    expect(within(selectedWorkspace).getByText("Plumbing / Pipes")).toBeInTheDocument();
    expect(within(selectedWorkspace).getByText("Manual Source Entry")).toBeInTheDocument();
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

    await user.click(screen.getByRole("button", { name: "Free-Form Text" }));
    await user.type(
      screen.getByLabelText("Free-form source text"),
      "PVC pipe, 20 pcs, from ABC Trading, PHP 1,500"
    );
    await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));

    expect(await screen.findByText("review_ready")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Review Candidate" })).toBeInTheDocument();
    expect(screen.getByDisplayValue("PVC pipe")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Top-level category"), "Plumbing");
    await user.type(screen.getByLabelText("Subcategory"), "Pipes");
    await user.click(screen.getByRole("button", { name: "Approve Candidate" }));
    await user.click(await screen.findByRole("button", { name: "Import Approved Batch" }));

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

    await user.click(screen.getByRole("button", { name: "Free-Form Text" }));
    await user.type(screen.getByLabelText("Free-form source text"), "Follow up with foreman");
    await user.click(screen.getByRole("button", { name: "Create Manual Source Entry" }));

    expect(await screen.findByText("no_candidates_found")).toBeInTheDocument();
    expect(screen.getByText("No candidates found")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Review Candidate" })).not.toBeInTheDocument();
  });
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}
