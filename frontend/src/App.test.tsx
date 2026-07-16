import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import App from "./App";

describe("Project Workspace app shell", () => {
  let purchaseLinesByProject: Map<number, unknown[]>;
  let processingJobsByProject: Map<number, unknown[]>;

  beforeEach(() => {
    window.history.pushState({}, "", "/");

    let nextProjectId = 2;
    const projectList = [{ id: 1, project_name: "Arnaiz Residence Renovation" }];
    purchaseLinesByProject = new Map<number, unknown[]>([[1, []]]);
    processingJobsByProject = new Map<number, unknown[]>([[1, []]]);
    const acceptedBatch12GateIds = new Set<number>();
    const projectNamesById = new Map<number, string>([[1, "Arnaiz Residence Renovation"]]);
    const taxonomyLeafPathsByProject = new Map<
      number,
      { id: number; name: string; parent_id: number; path: string }[]
    >([
      [
        1,
        [
          { id: 50, name: "Pipes", parent_id: 49, path: "Plumbing / Pipes" },
          { id: 52, name: "Wiring", parent_id: 51, path: "Electrical / Wiring" }
        ]
      ]
    ]);

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

        const purchaseLineDetailMatch = url.match(
          /^\/api\/project-workspaces\/(\d+)\/purchase-lines\/(\d+)$/
        );
        if (purchaseLineDetailMatch && method === "GET") {
          const projectId = Number(purchaseLineDetailMatch[1]);
          const purchaseLineId = Number(purchaseLineDetailMatch[2]);
          return jsonResponse({
            id: purchaseLineId,
            status: "active",
            line_type: "material",
            linked_concepts: [
              {
                memory_record_id: 11,
                concept_type: "material",
                name: "PVC pipe",
                category_path: "Plumbing / Pipes"
              }
            ],
            provider: {
              state: "external",
              record: {
                memory_record_id: 12,
                name: "ABC Trading",
                category_path: "Providers / General"
              },
              roles: ["material_supplier"]
            },
            quantity: "20",
            unit: "pcs",
            unit_state: "known",
            price: "1500",
            currency: "PHP",
            price_state: "known",
            purchase_date: "2025-07-12",
            date_state: "known",
            evidence_records: [
              {
                id: 21,
                source_submission_id: 31,
                source_label: "Manual Source Entry",
                source_type: "structured_row",
                source_submission_href: `/projects/${projectId}/sources/31`,
                locator: {
                  kind: "structured_field",
                  field_path: "structured_payload.annotations[0].text"
                },
                supporting_content: {
                  line_type: "material",
                  name: "PVC pipe",
                  annotations: [
                    {
                      text: "Delivery included",
                      annotation_type: "delivery_terms",
                      target: "purchase_line"
                    }
                  ]
                },
                annotations: [
                  {
                    id: 41,
                    proposal_id: "structured:annotations:0",
                    text: "Delivery included",
                    annotation_type: "delivery_terms",
                    target: {
                      memory_record_id: 10,
                      record_type: "purchase_line",
                      name: "PVC pipe"
                    },
                    source_excerpt: "Delivery included",
                    source_locator: {
                      kind: "structured_field",
                      field_path: "structured_payload.annotations[0].text"
                    },
                    provenance: "source_field"
                  },
                  {
                    id: 42,
                    proposal_id: "reviewer:material-warranty",
                    text: "Five-year warranty",
                    annotation_type: "warranty_terms",
                    target: {
                      memory_record_id: 11,
                      record_type: "material",
                      name: "PVC pipe"
                    },
                    source_excerpt: "Delivery included",
                    source_locator: {
                      kind: "structured_field",
                      field_path: "structured_payload.annotations[0].text"
                    },
                    provenance: "reviewer_added"
                  }
                ],
                annotation_omitted_count: 0,
                annotation_detected_count: 0
              }
            ],
            value_history_available: false
          });
        }

        const sourceSubmissionDetailMatch = url.match(
          /^\/api\/project-workspaces\/(\d+)\/source-submissions\/(\d+)$/
        );
        if (sourceSubmissionDetailMatch && method === "GET") {
          const projectId = Number(sourceSubmissionDetailMatch[1]);
          const sourceSubmissionId = Number(sourceSubmissionDetailMatch[2]);
          const annotation = {
            id: 41,
            proposal_id: "structured:annotations:0",
            text: "Delivery included",
            annotation_type: "delivery_terms",
            target: {
              memory_record_id: 10,
              record_type: "purchase_line",
              name: "PVC pipe"
            },
            source_excerpt: "Delivery included",
            source_locator: {
              kind: "structured_field",
              field_path: "structured_payload.annotations[0].text"
            },
            provenance: "source_field"
          };
          const freeText = "Earlier purchasing context. Delivery included in the quoted price.";
          const freeTextStart = freeText.indexOf("Delivery included");
          const sourceAnnotation =
            sourceSubmissionId === 32
              ? {
                  ...annotation,
                  proposal_id: "ai:annotation:0",
                  source_locator: {
                    kind: "text_span",
                    start: freeTextStart,
                    end: freeTextStart + "Delivery included".length
                  },
                  provenance: "ai_suggested"
                }
              : annotation;
          return jsonResponse({
            id: sourceSubmissionId,
            project_workspace_id: projectId,
            submission_type: "manual_source_entry",
            submitted_at: "2025-07-12T10:00:00Z",
            source: {
              kind: sourceSubmissionId === 32 ? "free_form_text" : "structured_manual",
              structured_payload: sourceSubmissionId === 32 ? null : {
                line_type: "material",
                name: "PVC pipe",
                annotations: [
                  {
                    text: "Delivery included",
                    annotation_type: "delivery_terms",
                    target: "purchase_line"
                  }
                ]
              },
              original_text: sourceSubmissionId === 32 ? freeText : null,
              source_file: null
            },
            processing_job: {
              id: 51,
              project_workspace_id: projectId,
              source_submission_id: sourceSubmissionId,
              status: "completed",
              source_type: "manual_source_entry",
              processor_name: "structured_manual_row_v1",
              created_at: "2025-07-12T10:00:00Z",
              started_at: "2025-07-12T10:00:01Z",
              finished_at: "2025-07-12T10:00:02Z",
              error_message: null,
              diagnostics: { processor: "structured_manual_row_v1" },
              candidate_count: 1,
              review_batch_id: 61
            },
            review_batch: {
              id: 61,
              status: "imported",
              href: `/projects/${projectId}/review-batches/61`
            },
            imported_evidence: [
              {
                id: 21,
                source_label: "Manual Source Entry",
                locator: { kind: "structured_manual" },
                supporting_content: {
                  line_type: "material",
                  name: "PVC pipe"
                },
                annotations: [sourceAnnotation],
                purchase_lines: [
                  {
                    id: 1,
                    status: "active",
                    href: `/projects/${projectId}/purchase-lines/1`,
                    linked_records: [
                      {
                        memory_record_id: 11,
                        record_type: "material",
                        name: "PVC pipe",
                        category_path: "Plumbing / Pipes"
                      }
                    ]
                  }
                ],
                annotation_omitted_count: 0,
                annotation_detected_count: 0
              }
            ],
            empty_state: null
          });
        }

        const entityMemoryMatch = url.match(
          /^\/api\/project-workspaces\/(\d+)\/(materials|services|providers)(?:\?.*)?$/
        );
        if (entityMemoryMatch && method === "GET") {
          const projectId = Number(entityMemoryMatch[1]);
          const entityType = entityMemoryMatch[2];
          const items =
            entityType === "materials"
              ? [
                  {
                    memory_record_id: 1,
                    name: "PVC pipe",
                    category_path: "Plumbing / Pipes",
                    linked_purchase_line_count: 1,
                    source_submission_count: 1
                  }
                ]
              : entityType === "services"
                ? [
                    {
                      memory_record_id: 2,
                      name: "PVC pipe installation",
                      category_path: "Trade services / Pipe installation",
                      linked_purchase_line_count: 1,
                      source_submission_count: 1
                    }
                  ]
                : [
                    {
                      memory_record_id: 3,
                      name: "ABC Trading",
                      category_path: "Providers / General",
                      roles: [
                        "material_supplier",
                        "service_provider",
                        "supply_and_install_provider"
                      ],
                      linked_purchase_line_count: 1,
                      source_submission_count: 1
                    }
                  ];
          return jsonResponse({
            project_workspace: {
              id: projectId,
              project_name: projectNamesById.get(projectId)
            },
            items
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

        if (url === "/api/project-workspaces/1/source-files" && method === "POST") {
          const formData = init?.body as FormData;
          const file = formData.get("files") as File;
          const sourceSubmission = {
            id: 29,
            project_workspace_id: 1,
            submission_type: "source_file",
            submitted_at: "2026-07-10T00:00:00Z",
            entered_by: null
          };
          const sourceFile = {
            id: 39,
            project_workspace_id: 1,
            source_submission_id: sourceSubmission.id,
            original_filename: file.name,
            byte_size: file.size,
            declared_mime_type: file.type,
            uploaded_at: "2026-07-10T00:00:00Z",
            sha256_checksum: "test-checksum",
            storage_path: "source-files/39/original.xlsx"
          };
          const processingJob = {
            id: 49,
            project_workspace_id: 1,
            source_submission_id: sourceSubmission.id,
            source_type: "source_file",
            processor_name: "ai_xlsx_purchase_lines_v1",
            created_at: "2026-07-10T00:00:00Z",
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
              processing_job: {
                ...processingJob,
                status: "review_ready",
                candidate_count: 1,
                review_batch_id: 11
              },
              source_submission: sourceSubmission,
              source_file: {
                id: sourceFile.id,
                original_filename: sourceFile.original_filename,
                byte_size: sourceFile.byte_size,
                declared_mime_type: sourceFile.declared_mime_type,
                uploaded_at: sourceFile.uploaded_at,
                sha256_checksum: sourceFile.sha256_checksum
              },
              review_batch_id: 11
            }
          ]);
          return jsonResponse(
            {
              source_submission: sourceSubmission,
              source_file: sourceFile,
              processing_job: processingJob
            },
            201
          );
        }

        if (url === "/api/project-workspaces/1/review-batches/11" && method === "GET") {
          return jsonResponse({
            review_batch: {
              id: 11,
              project_workspace_id: 1,
              source_submission_id: 29,
              status: "review_pending"
            },
            candidates: [
              {
                ...buildCandidate(30, "PVC pipe", "material", "Plumbing", "Pipes"),
                review_batch_id: 11,
                source_submission_id: 29,
                source_file: {
                  id: 39,
                  original_filename: "purchase-log.xlsx",
                  byte_size: 8,
                  declared_mime_type:
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                  uploaded_at: "2026-07-10T00:00:00Z",
                  sha256_checksum: "test-checksum"
                },
                proposed_payload: {
                  ...buildCandidate(30, "PVC pipe", "material", "Plumbing", "Pipes")
                    .proposed_payload,
                  evidence: {
                    source_submission_id: 29,
                    source_file_id: 39,
                    worksheet: "Purchases",
                    region_id: "purchases",
                    primary_body_row: 31,
                    locators: [
                      { row: 31, role: "body" },
                      { row: 32, role: "body" }
                    ]
                  }
                }
              }
            ],
            duplicate_groups: [],
            duplicate_conflicts: [],
            taxonomy_decisions: []
          });
        }

        if (url === "/api/project-workspaces/1/review-batches/12" && method === "GET") {
          return jsonResponse({
            review_batch: {
              id: 12,
              project_workspace_id: 1,
              source_submission_id: 32,
              status: "review_pending"
            },
            candidates: [buildBundledCandidate(acceptedBatch12GateIds)],
            duplicate_groups: [],
            duplicate_conflicts: [],
            taxonomy_decisions: []
          });
        }

        const batch12GateAcceptMatch = url.match(
          /^\/api\/project-workspaces\/1\/review-batches\/12\/taxonomy-gates\/(\d+)\/accept$/
        );
        if (batch12GateAcceptMatch && method === "POST") {
          acceptedBatch12GateIds.add(Number(batch12GateAcceptMatch[1]));
          return jsonResponse({
            review_batch: {
              id: 12,
              project_workspace_id: 1,
              source_submission_id: 32,
              status: "review_in_progress"
            },
            candidates: [buildBundledCandidate(acceptedBatch12GateIds)],
            duplicate_groups: [],
            duplicate_conflicts: [],
            taxonomy_decisions: []
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

        if (url === "/api/project-workspaces/1/review-batches/61" && method === "GET") {
          return jsonResponse({
            review_batch: {
              id: 61,
              project_workspace_id: 1,
              source_submission_id: 31,
              status: "imported"
            },
            candidates: [buildCandidate(20, "PVC pipe", "material", "Plumbing", "Pipes")],
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

        const taxonomyGateDraftMatch = url.match(
          /^\/api\/project-workspaces\/1\/review-batches\/10\/taxonomy-gates\/(\d+)\/reviewer-draft$/
        );
        if (taxonomyGateDraftMatch && method === "PUT") {
          const body = JSON.parse(String(init?.body));
          const candidates = [
            buildCandidate(20, "PVC pipe", "material", "Mechanical", "Pipe Materials"),
            buildCandidate(21, "PVC elbow", "material", "Mechanical", "Pipe Materials")
          ].map((candidate) => ({
            ...candidate,
            taxonomy_gates: candidate.taxonomy_gates.map((gate) => ({
              ...gate,
              reviewer_draft_category_path: `${body.top_level_category} / ${body.subcategory}`,
              selected_proposal: "reviewer_draft",
              selected_category_path: `${body.top_level_category} / ${body.subcategory}`
            }))
          }));
          return jsonResponse({
            review_batch: {
              review_batch: {
                id: 10,
                project_workspace_id: 1,
                source_submission_id: 30,
                status: "review_pending"
              },
              candidates,
              duplicate_groups: [],
              duplicate_conflicts: [],
              taxonomy_decisions: []
            },
            affected_count: body.apply_to_similar ? 1 : 0
          });
        }

        if (
          url === "/api/project-workspaces/1/review-batches/10/taxonomy-gates/920/accept" &&
          method === "POST"
        ) {
          const candidate = buildCandidate(
            20,
            "PVC pipe",
            "material",
            "Mechanical",
            "Pipe Materials"
          );
          return jsonResponse({
            review_batch: {
              id: 10,
              project_workspace_id: 1,
              source_submission_id: 30,
              status: "review_in_progress"
            },
            candidates: [
              {
                ...candidate,
                taxonomy_gates: candidate.taxonomy_gates.map((gate) => ({
                  ...gate,
                  status: "accepted",
                  accepted_category_path: "Mechanical / Pipe Materials",
                  resolved_category_path: "Mechanical / Pipe Materials",
                  accepted_source: "ai_suggestion",
                  decision: "approved",
                  taxonomy_decision_id: 77
                }))
              }
            ],
            duplicate_groups: [],
            duplicate_conflicts: [],
            taxonomy_decisions: []
          });
        }

        if (
          url === "/api/project-workspaces/1/review-batches/10/taxonomy-mappings" &&
          method === "POST"
        ) {
          const body = JSON.parse(String(init?.body));
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
                  top_level_category: body.top_level_category,
                  subcategory: body.subcategory,
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
                  top_level_category: body.top_level_category,
                  subcategory: body.subcategory,
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
              line_type: "material",
              linked_concepts: [
                {
                  memory_record_id: 1,
                  concept_type: "material",
                  name: "PVC pipe",
                  category_path: "Plumbing / Pipes"
                }
              ],
              provider_state: "external",
              provider_name: "ABC Trading",
              provider_category_path: "Providers / General",
              provider_roles: ["material_supplier"],
              quantity: "20",
              unit: "pcs",
              unit_state: "known",
              price: "1500",
              currency: "PHP",
              price_state: "known",
              purchase_date: "2025-07-12",
              date_state: "known",
              has_evidence: true,
              evidence_count: 1,
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
    await user.type(screen.getByLabelText("Contractor Assigned"), "Quinlan Construction");
    await user.type(screen.getByLabelText("Floor area"), "420 sqm");
    await user.type(screen.getByLabelText("Trade scopes"), "HVAC, Electrical");
    await user.type(screen.getByLabelText("Client or owner"), "Ortigas Holdings");
    await user.type(screen.getByLabelText("Notes"), "Completed fit-out purchasing records.");
    await user.click(screen.getByRole("button", { name: "Create Project Workspace" }));

    const createCall = vi
      .mocked(fetch)
      .mock.calls.find(
        ([input, init]) => input.toString() === "/api/project-workspaces" && init?.method === "POST"
      );
    expect(JSON.parse(String(createCall?.[1]?.body)).contractor_assigned).toBe(
      "Quinlan Construction"
    );

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

  test("reviewer browses sibling memory tabs and filters Provider roles", async () => {
    const user = userEvent.setup();
    render(<App />);
    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );

    await user.click(screen.getByRole("tab", { name: "Materials" }));
    expect(await screen.findByRole("heading", { name: "Materials" })).toBeInTheDocument();
    expect(screen.getByText("PVC pipe")).toBeInTheDocument();
    expect(screen.getByText("Plumbing / Pipes")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Providers" }));
    expect(await screen.findByRole("heading", { name: "Providers" })).toBeInTheDocument();
    await user.click(screen.getByLabelText("Service provider"));
    expect(screen.getByText("ABC Trading")).toBeInTheDocument();
    expect(screen.getByText("Supply & install")).toBeInTheDocument();
    expect(
      vi.mocked(fetch).mock.calls.some(([input]) =>
        input.toString().includes("/providers?roles=service_provider")
      )
    ).toBe(true);
  });

  test("bundled Purchase Line displays both linked concepts and category paths", async () => {
    purchaseLinesByProject.set(1, [
      {
        id: 1,
        line_type: "bundled",
        linked_concepts: [
          {
            memory_record_id: 1,
            concept_type: "material",
            name: "PVC pipe",
            category_path: "Plumbing / Pipes"
          },
          {
            memory_record_id: 2,
            concept_type: "service",
            name: "PVC pipe installation",
            category_path: "Trade services / Pipe installation"
          }
        ],
        provider_state: "external",
        provider_name: "ABC Trading",
        provider_category_path: "Providers / General",
        provider_roles: [
          "material_supplier",
          "service_provider",
          "supply_and_install_provider"
        ],
        quantity: "20",
        unit: "pcs",
        unit_state: "known",
        price: "1500",
        currency: "PHP",
        price_state: "known",
        purchase_date: "2025-07-12",
        date_state: "known",
        has_evidence: true,
        evidence_count: 1,
        source_label: "Manual Source Entry"
      }
    ]);
    const user = userEvent.setup();
    render(<App />);
    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );

    expect(await screen.findByText("PVC pipe")).toBeInTheDocument();
    expect(screen.getByText("PVC pipe installation")).toBeInTheDocument();
    expect(screen.getByText("Plumbing / Pipes")).toBeInTheDocument();
    expect(screen.getByText("Trade services / Pipe installation")).toBeInTheDocument();
  });

  test("reviewer opens read-only Purchase Line Detail from accessible list links", async () => {
    purchaseLinesByProject.set(1, [
      {
        id: 1,
        line_type: "material",
        linked_concepts: [
          {
            memory_record_id: 11,
            concept_type: "material",
            name: "PVC pipe",
            category_path: "Plumbing / Pipes"
          }
        ],
        provider_state: "external",
        provider_name: "ABC Trading",
        provider_category_path: "Providers / General",
        provider_roles: ["material_supplier"],
        quantity: "20",
        unit: "pcs",
        unit_state: "known",
        price: "1500",
        currency: "PHP",
        price_state: "known",
        purchase_date: "2025-07-12",
        date_state: "known",
        has_evidence: true,
        evidence_count: 1,
        source_label: "Manual Source Entry"
      }
    ]);
    const user = userEvent.setup();
    render(<App />);
    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );

    expect(screen.getByText("1 evidence — Manual Source Entry")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "PVC pipe" })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "View details" }));

    expect(window.location.pathname).toBe("/projects/1/purchase-lines/1");
    expect(
      await screen.findByRole("heading", { name: "Purchase Line Detail" })
    ).toBeInTheDocument();
    expect(screen.getByText("ABC Trading")).toBeInTheDocument();
    expect(screen.getAllByText("Delivery included").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Delivery included", { selector: "mark" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Purchase line · PVC pipe" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Material · PVC pipe" })).toBeInTheDocument();
    expect(screen.getByText("Warranty terms")).toBeInTheDocument();
    expect(screen.getByText("Delivery terms")).toBeInTheDocument();
    expect(screen.getAllByText("structured_payload.annotations[0].text").length).toBeGreaterThan(1);
    expect(screen.getByText("No reviewed changes yet")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit|archive|restore/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Manual Source Entry" })).toHaveAttribute(
      "href",
      "/projects/1/sources/31"
    );
  });

  test("reviewer follows Purchase Line evidence into Source Submission Detail", async () => {
    purchaseLinesByProject.set(1, [
      {
        id: 1,
        line_type: "material",
        linked_concepts: [
          {
            memory_record_id: 11,
            concept_type: "material",
            name: "PVC pipe",
            category_path: "Plumbing / Pipes"
          }
        ],
        provider_state: "unknown",
        provider_name: null,
        provider_category_path: null,
        provider_roles: [],
        quantity: "20",
        unit: "pcs",
        unit_state: "known",
        price: "1500",
        currency: "PHP",
        price_state: "known",
        purchase_date: null,
        date_state: "unknown",
        has_evidence: true,
        evidence_count: 1,
        source_label: "Manual Source Entry"
      }
    ]);
    const user = userEvent.setup();
    render(<App />);
    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );
    await user.click(screen.getByRole("link", { name: "View details" }));
    await user.click(await screen.findByRole("link", { name: "Manual Source Entry" }));

    expect(window.location.pathname).toBe("/projects/1/sources/31");
    expect(
      await screen.findByRole("heading", { name: "Source Submission Detail" })
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Immutable source" })).toBeInTheDocument();
    expect(screen.getByText("structured_manual_row_v1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review Batch #61" })).toHaveAttribute(
      "href",
      "/projects/1/review-batches/61"
    );
    expect(screen.getByRole("heading", { name: "Imported evidence" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Purchase Line #1" })).toHaveAttribute(
      "href",
      "/projects/1/purchase-lines/1"
    );
    expect(screen.getAllByText("Delivery included").length).toBeGreaterThan(0);
  });

  test("reviewer opens the linked Review Batch from Source Submission Detail", async () => {
    window.history.pushState({}, "", "/projects/1/sources/31");
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: "Review Batch #61" }));

    expect(window.location.pathname).toBe("/projects/1/review-batches/61");
    expect(await screen.findByRole("heading", { name: "Review Batch #61" })).toBeInTheDocument();
  });

  test("Review Batch survives refresh through its stable URL", async () => {
    window.history.pushState({}, "", "/projects/1/review-batches/61");
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Review Batch #61" })).toBeInTheDocument();
    expect(
      vi.mocked(fetch).mock.calls.some(
        ([input]) => input.toString() === "/api/project-workspaces/1/review-batches/61"
      )
    ).toBe(true);
  });

  test("Purchase Line Detail survives refresh and Browser Back restores the list", async () => {
    window.history.pushState({}, "", "/projects/1/purchase-lines/1");
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Purchase Line Detail" })
    ).toBeInTheDocument();
    expect(screen.getByText("PVC pipe")).toBeInTheDocument();
    expect(
      vi.mocked(fetch).mock.calls.some(
        ([input]) => input.toString() === "/api/project-workspaces/1/purchase-lines/1"
      )
    ).toBe(true);

    window.history.pushState({}, "", "/projects/1/purchase-lines");
    window.dispatchEvent(new PopStateEvent("popstate"));

    expect(
      await screen.findByRole("heading", { name: "Purchase Lines" })
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe("/projects/1/purchase-lines");
  });

  test("Browser Back restores the actual Purchase Lines list scroll position", async () => {
    purchaseLinesByProject.set(1, [
      {
        id: 1,
        line_type: "material",
        linked_concepts: [
          {
            memory_record_id: 11,
            concept_type: "material",
            name: "PVC pipe",
            category_path: "Plumbing / Pipes"
          }
        ],
        provider_state: "unknown",
        provider_name: null,
        provider_category_path: null,
        provider_roles: [],
        quantity: "20",
        unit: "pcs",
        unit_state: "known",
        price: "1500",
        currency: "PHP",
        price_state: "known",
        purchase_date: null,
        date_state: "unknown",
        has_evidence: true,
        evidence_count: 1,
        source_label: "Manual Source Entry"
      }
    ]);
    let scrollY = 0;
    let listWasRenderedWhenScrollRestored = false;
    const scrollTo = vi.fn(() => {
      listWasRenderedWhenScrollRestored =
        screen.queryByRole("heading", { name: "Purchase Lines" }) !== null;
    });
    Object.defineProperty(window, "scrollY", { configurable: true, get: () => scrollY });
    Object.defineProperty(window, "scrollTo", { configurable: true, value: scrollTo });
    const user = userEvent.setup();
    render(<App />);
    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );
    scrollY = 640;
    await user.click(screen.getByRole("link", { name: "View details" }));
    expect(await screen.findByRole("heading", { name: "Purchase Line Detail" })).toBeInTheDocument();
    scrollY = 0;

    window.history.back();

    await waitFor(() => expect(window.location.pathname).toBe("/projects/1/purchase-lines"));
    expect(scrollTo).toHaveBeenCalledWith({ behavior: "auto", top: 640 });
    expect(listWasRenderedWhenScrollRestored).toBe(true);
  });

  test("free-text source inspection scrolls the exact highlighted span into view", async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView
    });
    window.history.pushState({}, "", "/projects/1/sources/32");

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Source Submission Detail" })
    ).toBeInTheDocument();
    expect(screen.getByText("Delivery included", { selector: "mark" })).toBeInTheDocument();
    await waitFor(() => expect(scrollIntoView).toHaveBeenCalledWith({ block: "center" }));
  });

  test("bundled candidate detail separates Linked Concepts, Provider, and Purchase Details", async () => {
    processingJobsByProject.set(1, [
      {
        processing_job: {
          id: 52,
          project_workspace_id: 1,
          source_submission_id: 32,
          status: "review_ready",
          source_type: "manual_source_entry",
          processor_name: "ai_manual_free_form_v1",
          created_at: "2026-07-13T00:00:00Z",
          started_at: "2026-07-13T00:00:01Z",
          finished_at: "2026-07-13T00:00:02Z",
          error_message: null,
          diagnostics: null,
          candidate_count: 1,
          review_batch_id: 12
        },
        source_submission: {
          id: 32,
          submission_type: "manual_source_entry",
          submitted_at: "2026-07-13T00:00:00Z"
        },
        source_file: null,
        review_batch_id: 12
      }
    ]);
    const user = userEvent.setup();
    render(<App />);
    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );
    await user.click(screen.getByRole("tab", { name: "Upload / Review" }));
    await user.click(await screen.findByRole("button", { name: "Open Review Batch" }));
    await user.click((await screen.findAllByRole("button", { name: "Details" }))[0]);

    const detail = await screen.findByRole("dialog", { name: "Candidate Detail" });
    expect(within(detail).getByRole("heading", { name: "Linked Concepts" })).toBeInTheDocument();
    expect(within(detail).getByText("PVC pipe installation")).toBeInTheDocument();
    expect(within(detail).getByRole("heading", { name: "Provider" })).toBeInTheDocument();
    expect(within(detail).getByLabelText("Provider State")).toHaveValue("external");
    expect(within(detail).getByRole("heading", { name: "Purchase Details" })).toBeInTheDocument();
    expect(within(detail).getByText("PHP 1500")).toBeInTheDocument();
    expect(within(detail).getAllByText(/Matched existing memory/)).toHaveLength(2);
    expect(within(detail).queryByLabelText("Service top-level category")).not.toBeInTheDocument();
    expect(within(detail).queryByLabelText("Service subcategory")).not.toBeInTheDocument();
    expect(within(detail).queryByLabelText("Provider top-level category")).not.toBeInTheDocument();
    expect(within(detail).queryByLabelText("Provider subcategory")).not.toBeInTheDocument();
    expect(within(detail).queryByRole("button", { name: "Change Taxonomy" })).not.toBeInTheDocument();
    expect(within(detail).getByText("AI suggestion: Trade services / Pipe installation")).toBeInTheDocument();
    expect(within(detail).getByText("Taxonomy Status").parentElement).toHaveTextContent(
      "Needs decision"
    );
    expect(within(detail).getAllByText("Needs decision")).toHaveLength(4);
    await user.selectOptions(within(detail).getByLabelText("Provider State"), "unknown");
    expect(within(detail).getByText("Provider is a data gap.")).toBeInTheDocument();
    expect(within(detail).queryByLabelText("Provider name")).not.toBeInTheDocument();

    await user.click(within(detail).getByLabelText("Link Service"));
    expect(within(detail).queryByLabelText("Service name")).not.toBeInTheDocument();

    await user.click(within(detail).getAllByRole("button", { name: "Accept selected category" })[0]);
    expect(
      vi.mocked(fetch).mock.calls.find(([input]) =>
        input.toString().includes("/review-batches/12/taxonomy-gates/902/accept")
      )
    ).toBeDefined();
  });

  test("bundled candidate taxonomy status becomes Accepted only after every active gate is accepted", async () => {
    processingJobsByProject.set(1, [
      {
        processing_job: {
          id: 52,
          project_workspace_id: 1,
          source_submission_id: 32,
          status: "review_ready",
          source_type: "manual_source_entry",
          processor_name: "ai_manual_free_form_v1",
          created_at: "2026-07-13T00:00:00Z",
          started_at: "2026-07-13T00:00:01Z",
          finished_at: "2026-07-13T00:00:02Z",
          error_message: null,
          diagnostics: null,
          candidate_count: 1,
          review_batch_id: 12
        },
        source_submission: {
          id: 32,
          submission_type: "manual_source_entry",
          submitted_at: "2026-07-13T00:00:00Z"
        },
        source_file: null,
        review_batch_id: 12
      }
    ]);
    const user = userEvent.setup();
    render(<App />);
    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );
    await user.click(screen.getByRole("tab", { name: "Upload / Review" }));
    await user.click(await screen.findByRole("button", { name: "Open Review Batch" }));
    await user.click((await screen.findAllByRole("button", { name: "Details" }))[0]);

    const detail = await screen.findByRole("dialog", { name: "Candidate Detail" });
    const taxonomyStatus = within(detail).getByText("Taxonomy Status").parentElement;
    expect(taxonomyStatus).toHaveTextContent("Needs decision");

    await user.click(within(detail).getAllByRole("button", { name: "Accept selected category" })[0]);
    expect(taxonomyStatus).toHaveTextContent("Needs decision");
    await user.click(within(detail).getAllByRole("button", { name: "Accept selected category" })[0]);
    expect(taxonomyStatus).toHaveTextContent("Needs decision");
    await user.click(within(detail).getByRole("button", { name: "Accept selected category" }));

    expect(taxonomyStatus).toHaveTextContent("Accepted");
    expect(
      within(detail).queryByRole("button", { name: "Accept selected category" })
    ).not.toBeInTheDocument();
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

  test("reviewer explicitly uploads one XLSX file with visible processing guidance", async () => {
    const user = userEvent.setup();

    render(<App />);

    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );
    await user.click(screen.getByRole("tab", { name: "Upload / Review" }));

    expect(
      screen.getByText(/Upload one saved `.xlsx` file\. Habi reads values from visible worksheet cells/)
    ).toBeInTheDocument();
    const file = new File(["workbook"], "purchase-log.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    });
    await user.upload(screen.getByLabelText("Excel workbook"), file);
    expect(screen.getByText(/purchase-log\.xlsx/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Upload and process" }));

    const queue = await screen.findByRole("region", { name: "Processing Job queue" });
    expect(await within(queue).findByText("purchase-log.xlsx")).toBeInTheDocument();
    const uploadCall = vi
      .mocked(fetch)
      .mock.calls.find(([input, init]) =>
        input.toString().endsWith("/api/project-workspaces/1/source-files") &&
        init?.method === "POST"
    );
    expect(uploadCall?.[1]?.body).toBeInstanceOf(FormData);
    expect(new Headers(uploadCall?.[1]?.headers).has("Content-Type")).toBe(false);
  });

  test("XLSX upload rejects unsupported and over-25-MiB files before submission", async () => {
    const user = userEvent.setup({ applyAccept: false });

    render(<App />);
    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );
    await user.click(screen.getByRole("tab", { name: "Upload / Review" }));
    const input = screen.getByLabelText("Excel workbook");

    await user.upload(input, new File(["csv"], "purchase-log.csv", { type: "text/csv" }));
    expect(screen.getByText("Only .xlsx source files are supported.")).toBeInTheDocument();

    const oversized = new File(["xlsx"], "purchase-log.xlsx");
    Object.defineProperty(oversized, "size", { value: 25 * 1024 * 1024 + 1 });
    await user.upload(input, oversized);
    expect(
      screen.getByText("The selected workbook exceeds the 25 MiB upload limit.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload and process" })).toBeDisabled();
    expect(
      vi
        .mocked(fetch)
        .mock.calls.some(([request]) => request.toString().endsWith("/source-files"))
    ).toBe(false);
  });

  test("reviewer sees verified spreadsheet rows in Candidate Detail", async () => {
    const user = userEvent.setup();

    render(<App />);
    const selector = await screen.findByRole("navigation", {
      name: "Project Workspace selector"
    });
    await user.click(
      within(selector).getByRole("button", { name: "Arnaiz Residence Renovation" })
    );
    await user.click(screen.getByRole("tab", { name: "Upload / Review" }));
    await user.upload(
      screen.getByLabelText("Excel workbook"),
      new File(["workbook"], "purchase-log.xlsx", {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      })
    );
    await user.click(screen.getByRole("button", { name: "Upload and process" }));
    await user.click(await screen.findByRole("button", { name: "Open Review Batch" }));
    await user.click(screen.getAllByRole("button", { name: "Details" })[0]);

    const detail = await screen.findByRole("dialog", { name: "Candidate Detail" });
    expect(detail).toHaveTextContent("purchase-log.xlsx - Purchases - rows 31-32");
    expect(within(detail).getByLabelText("Primary evidence row")).toHaveTextContent("31");
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

  test("reviewer saves a pending taxonomy draft with optional scoped propagation", async () => {
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
    await user.click(within(detail).getByRole("button", { name: "Adjust category" }));

    const taxonomy = await screen.findByRole("dialog", { name: "Edit Taxonomy Gate" });
    const applyToSimilar = within(taxonomy).getByLabelText(
      "Apply reviewer draft to similar (1 gates)"
    );
    expect(applyToSimilar).not.toBeChecked();
    await user.selectOptions(
      within(taxonomy).getByRole("combobox", { name: "Existing Taxonomy Path" }),
      "Electrical / Wiring"
    );
    expect(within(taxonomy).getByLabelText("Top-Level Category")).toHaveValue("Electrical");
    expect(within(taxonomy).getByLabelText("Subcategory")).toHaveValue("Wiring");
    await user.click(applyToSimilar);
    await user.click(within(taxonomy).getByRole("button", { name: "Save reviewer draft" }));

    expect(
      await screen.findByText("Reviewer draft saved and copied to 1 similar gates.")
    ).toBeInTheDocument();
    await user.click(within(detail).getByRole("button", { name: "Close" }));
    expect(screen.getByRole("checkbox", { name: "Include PVC elbow" })).not.toBeChecked();
    const draftCall = fetchSpy.mock.calls.find(([input]) =>
      input.toString().includes("/taxonomy-gates/920/reviewer-draft")
    );
    expect(JSON.parse(String(draftCall?.[1]?.body))).toEqual({
      top_level_category: "Electrical",
      subcategory: "Wiring",
      apply_to_similar: true
    });
  });

  test("accepted taxonomy gate shows accepted source and Edit", async () => {
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

    await user.click(screen.getAllByRole("button", { name: "Details" })[0]);
    const detail = await screen.findByRole("dialog", { name: "Candidate Detail" });
    await user.click(within(detail).getByRole("button", { name: "Accept selected category" }));

    expect(await screen.findByText("Accepted: Mechanical / Pipe Materials")).toBeInTheDocument();
    expect(screen.getByText("Accepted from AI suggestion")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Accept selected category" })).not.toBeInTheDocument();
    expect(within(detail).getByText("Taxonomy Status").parentElement).toHaveTextContent(
      "Accepted"
    );
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
    expect(within(detail).getByText("Taxonomy Status").parentElement).toHaveTextContent(
      "Needs decision"
    );
    expect(within(detail).getByText("Linked Concepts")).toBeInTheDocument();
    expect(within(detail).getByText("Purchase Details")).toBeInTheDocument();
    expect(within(detail).getAllByText("PVC elbow").length).toBeGreaterThan(1);
    expect(within(detail).getByText("AI Confidence").parentElement).toHaveTextContent("84%");
    expect(
      within(detail).getByText(
        "Annotation extraction limit reached — 20 of 21 source-grounded annotation proposals were retained. Review the source and add any omitted qualifiers that matter."
      )
    ).toBeInTheDocument();
    expect(within(detail).getByText("AI suggested")).toBeInTheDocument();
    await user.selectOptions(
      within(detail).getByLabelText("Annotation type 1"),
      "condition_or_exclusion"
    );
    expect(within(detail).getByText("Changed from Delivery terms")).toBeInTheDocument();
    await user.click(within(detail).getByRole("button", { name: "Add annotation" }));
    await user.type(within(detail).getByLabelText("Source quote 2"), "Delivery included");
    expect(
      within(detail).getAllByText("Source locator: Characters 0–17")
    ).toHaveLength(2);
    expect(within(detail).queryByText("Reviewer-added annotation")).not.toBeInTheDocument();
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
    await user.click(screen.getByRole("button", { name: "Add annotation" }));
    await user.type(screen.getByLabelText("Annotation text 1"), "Delivery included");
    await user.selectOptions(screen.getByLabelText("Annotation type 1"), "delivery_terms");
    await user.selectOptions(screen.getByLabelText("Annotation target 1"), "purchase_line");
    expect(screen.queryByLabelText("Remarks or terms")).not.toBeInTheDocument();
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
    expect(within(selectedWorkspace).getAllByText(/Manual Source Entry/).length).toBeGreaterThan(0);
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
    const technicalDetails = within(queue).getByText("Technical details").closest("details");
    expect(technicalDetails).not.toHaveAttribute("open");
    expect(within(queue).queryByText("Unclear thing")).not.toBeInTheDocument();
  });
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

function buildBundledCandidate(acceptedGateIds: ReadonlySet<number>) {
  const gate = (
    id: number,
    subjectType: "material" | "service" | "provider",
    subjectName: string,
    categoryPath: string
  ) => {
    const accepted = acceptedGateIds.has(id);
    return {
      id,
      active: true,
      subject_type: subjectType,
      subject_name: subjectName,
      status: accepted ? "accepted" : "needs_decision",
      reason: accepted ? null : "candidate_acceptance_required",
      suggested_category_path: categoryPath,
      original_ai_category_path: categoryPath,
      reviewer_draft_category_path: null,
      selected_proposal: "ai_suggestion",
      selected_category_path: categoryPath,
      resolved_category_path: accepted ? categoryPath : null,
      accepted_category_path: accepted ? categoryPath : null,
      accepted_source: accepted ? "ai_suggestion" : null,
      decision: accepted ? "approved" : null,
      taxonomy_decision_id: accepted ? id + 100 : null,
      prior_rejection: null,
      decision_history: []
    };
  };

  return {
    id: 42,
    project_workspace_id: 1,
    review_batch_id: 12,
    source_submission_id: 32,
    status: "pending_review",
    proposed_payload: {
      linked_concepts: [
        {
          concept_type: "material",
          name: "PVC pipe",
          category_suggestion: {
            top_level_category: "Plumbing",
            subcategory: "Pipes"
          }
        },
        {
          concept_type: "service",
          name: "PVC pipe installation",
          category_suggestion: {
            top_level_category: "Trade services",
            subcategory: "Pipe installation"
          }
        }
      ],
      provider_state: "external",
      provider_name: "ABC Trading",
      provider_category_suggestion: {
        top_level_category: "Providers",
        subcategory: "General"
      },
      quantity: "20",
      unit: "pcs",
      price: "1500",
      currency: "PHP",
      purchase_date: "2025-07-12"
    },
    decision: null,
    merged_into_candidate_id: null,
    reviewed_payload: null,
    source_file: null,
    taxonomy_gate: null,
    taxonomy_gates: [
      gate(902, "material", "PVC pipe", "Plumbing / Pipes"),
      gate(903, "service", "PVC pipe installation", "Trade services / Pipe installation"),
      gate(904, "provider", "ABC Trading", "Providers / General")
    ],
    existing_memory_matches: [
      {
        subject_type: "material",
        subject_name: "PVC pipe",
        category_path: "Plumbing / Pipes"
      },
      {
        subject_type: "provider",
        subject_name: "ABC Trading",
        category_path: "Providers / General"
      }
    ],
    taxonomy_default: null
  };
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
      confidence: 0.84,
      annotation_omitted_count: 1,
      annotation_detected_count: 21,
      annotation_proposals: [
        {
          proposal_id: `ai:${id}:0`,
          text: "Delivery included",
          annotation_type: "delivery_terms",
          target: "purchase_line",
          source_excerpt: "Delivery included",
          source_locator: { kind: "text_span", start: 0, end: 17 },
          provenance: "ai_suggested"
        }
      ],
      category_suggestion: {
        top_level_category: topLevelCategory,
        subcategory
      }
    },
    decision: null,
    merged_into_candidate_id: null,
    reviewed_payload: null,
    source_grounding: {
      kind: "free_form_text",
      original_text: "Delivery included in the quoted price.",
      options: []
    },
    taxonomy_gate: null,
    taxonomy_gates: [
      {
        id: 900 + id,
        active: true,
        subject_type: lineType,
        subject_name: name,
        status: "needs_decision",
        reason: "candidate_acceptance_required",
        suggested_category_path: `${topLevelCategory} / ${subcategory}`,
        original_ai_category_path: `${topLevelCategory} / ${subcategory}`,
        reviewer_draft_category_path: null,
        selected_proposal: "ai_suggestion",
        selected_category_path: `${topLevelCategory} / ${subcategory}`,
        resolved_category_path: null,
        accepted_category_path: null,
        accepted_source: null,
        decision: null,
        taxonomy_decision_id: null,
        prior_rejection: null,
        decision_history: []
      }
    ],
    taxonomy_default: null
  };
}
