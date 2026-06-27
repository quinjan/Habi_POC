# AI Extraction Uses Full ISO Dates Only

AI Extraction will populate a candidate `purchase_date` only when the source text supports a full ISO `YYYY-MM-DD` date. Partial or ambiguous dates should be left missing so review and import can represent the date as unknown rather than inventing precision or adding partial-date semantics in the first AI slice.
