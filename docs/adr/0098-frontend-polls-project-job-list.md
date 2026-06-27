# Frontend Polls Project Job List

The frontend will poll the selected Project Workspace Processing Job list rather than polling each job detail endpoint individually. A single project-scoped polling request keeps multiple outstanding job state coherent, avoids N-per-job request patterns, and still allows the existing job detail endpoint to support focused inspection or deep links.
