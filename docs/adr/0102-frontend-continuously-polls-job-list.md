# Frontend Continuously Polls Job List

The frontend will continuously poll the selected Project Workspace Processing Job list in the first async source-processing UI. Even though the POC is single-user, continuous polling keeps the job/review queue fresh when the separate worker command advances jobs outside the request that originally submitted the source.
