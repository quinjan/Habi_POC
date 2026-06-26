# Create Review Batches Only When Candidates Exist

Free-form Manual Source Entry processing will create a Review Batch only when processing produces one or more Extracted Candidates. Empty or unusable free-form extraction is represented by the Processing Job terminal status `no_candidates_found`, keeping Review Batches reserved for actual candidate review work rather than empty processing outcomes.
