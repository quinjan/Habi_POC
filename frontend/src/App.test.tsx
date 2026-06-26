import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import App from "./App";

describe("Project Workspace app shell", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/");

    let nextProjectId = 2;
    const projectList = [{ id: 1, project_name: "Arnaiz Residence Renovation" }];

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
          return jsonResponse(createdProject, 201);
        }

        if (
          url === "/api/project-workspaces/2/purchase-lines" &&
          method === "GET"
        ) {
          return jsonResponse({
            project_workspace: {
              id: 2,
              project_name: "Ortigas Office Fit-Out"
            },
            items: []
          });
        }

        return jsonResponse({ detail: "Not found" }, 404);
      })
    );
  });

  afterEach(() => {
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
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}
