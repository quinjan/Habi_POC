# Separate Frontend And Backend With API Contracts

The Habi POC will use a separate frontend and backend that communicate only through explicit API contracts. The frontend remains a light review and search interface, while the backend owns project memory rules, source submission, processing jobs, file/artifact access, AI calls, database writes, retrieval, import semantics, and validation.

This preserves a strong boundary around the parts that prove the POC: parsing varied sources with AI, enforcing human-reviewed import, preserving evidence, and returning accurate project-scoped search responses. The UI can stay lightweight without gaining direct database access or duplicating business rules.
