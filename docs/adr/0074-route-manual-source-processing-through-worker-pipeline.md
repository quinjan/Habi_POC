# Route Manual Source Processing Through Worker Pipeline

All Manual Source Entry Processing Jobs will go through the same background worker pipeline rather than keeping structured rows synchronous and only queuing free-form text. Even when structured rows could complete immediately, the shared pipeline keeps source processing behavior consistent and leaves room for later AI Extraction and AI-suggested category paths to run behind the same Processing Job lifecycle.
