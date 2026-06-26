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
          return jsonResponse(
            {
              manual_source_entry: {
                id: 30,
                project_workspace_id: 1,
                structured_payload: body
              },
              review_batch: {
                id: 10,
                project_workspace_id: 1,
                manual_source_entry_id: 30,
                status: "review_pending"
              },
              candidate: {
                id: 20,
                project_workspace_id: 1,
                review_batch_id: 10,
                manual_source_entry_id: 30,
                status: "pending_review",
                proposed_payload: body,
                decision: null,
                reviewed_payload: null
              }
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
            manual_source_entry_id: 30,
            status: "approved_for_import",
            proposed_payload: body.reviewed_payload,
            decision: body.decision,
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
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}
