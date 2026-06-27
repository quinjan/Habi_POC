# Add Project Processing Job List Endpoint

The async Manual Source Entry workflow will include a Project Workspace Processing Job list endpoint so the frontend can show multiple outstanding and completed jobs for the selected project. The list should return project-scoped jobs with source summaries, statuses, candidate counts, optional Review Batch IDs, and timestamps so reviewers can browse review-ready batches independently while other jobs remain queued, processing, failed, or no-candidates-found.
