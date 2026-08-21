You are a senior AI systems architect. Create a production-ready `DESIGN.md` for the project described below.

The document should make clear technical decisions, explain their trade-offs, and provide enough implementation detail for an engineering team to build, deploy, and maintain the system. You are responsible for deciding the architecture and implementation details that are not explicitly specified.

Keep the DESING.md file as simple and short as possible, avoid including flowcharts and write them in a seperate file.

# Project Overview

Liara provides many cloud services and maintains a large amount of technical documentation. A significant portion of its support tickets is caused by users not reading the documentation, not finding the correct information, or having difficulty understanding it.

We want to create an LLM-powered chatbot that answers users’ questions using Liara’s official documentation. The chatbot should provide accurate, practical, and source-backed answers while minimizing hallucinations.

# Official Documentation Sources

Use the following official sources:

- Liara documentation: https://docs.liara.ir/
- Liara documentation source code GitHub repository: https://github.com/liara-cloud/docs

The design should explain how content from these sources is discovered, synchronized, processed, deduplicated, indexed, updated, and cited.

# General Approach

The proposed high-level workflow is:

1. Starting from the documentation homepage, discover and extract all documentation and store it in a database.
2. Synchronize the documentation periodically, on demand, and when appropriate through source-change events.
3. Split the documentation into useful chunks, generate embeddings, and store the vectors and related metadata for semantic search.
4. Create an LLM pipeline that examines the user’s query and conversation context and decides whether to:
   - Answer using existing reliable context.
   - Search the documentation.
   - Retrieve additional pages or sections.
   - Ask a clarifying question.
   - Perform a multi-step process.
   - Use an external web search API if the answer is unavailable in Liara’s documentation.
   - State that there is insufficient information or recommend contacting support.
5. Generate grounded answers with appropriate citations and links to the original documentation.

Official Liara sources must be prioritized. Information obtained from external sources must be clearly identified as external.

Use AI agents where they add practical value, but prefer deterministic workflows when they are simpler, safer, more reliable, or less expensive.

# Required Technologies

Use the following technology choices:

- Python for the backend
- FastAPI or a similarly appropriate Python API framework
- LangChain for the LLM pipeline
- LangGraph where it is useful for agent workflows
- OpenRouter for both LLM and embedding-model access
- A standalone JavaScript chat widget
- Docker and Docker Compose
- Liara as the production deployment platform

The JavaScript widget must be embeddable on different websites using a simple `<script>` tag.

You may select any additional databases, vector-search technologies, crawlers, queues, caches, schedulers, monitoring tools, and supporting libraries. Explain important choices and trade-offs in `DESIGN.md`.

# Dockerized Architecture

Use separate Docker containers for at least the following components:

1. **Database**
   - Stores documentation, chunks, vectors, metadata, indexing state, and any other persistent application data.
   - Must support the retrieval strategy selected in the design.

2. **Chatbot pipeline and API**
   - Handles user requests, conversation context, agent behavior, retrieval decisions, answer generation, citations, personalization, and the public chatbot API.
   - Communicates with the indexing engine through its API.

3. **Indexing engine and API**
   - Handles documentation synchronization, extraction, cleaning, chunking, embedding generation, indexing, and search.
   - Is used both for periodic or manually triggered indexing and for searching and returning relevant results to the chatbot service.
   - a single container for all of the tasks described above and not seperate ones for tasks, indexing and api.

The design must define clear responsibilities and communication boundaries between containers. It should also explain how indexing workloads are prevented from negatively affecting user-facing chatbot performance.

Include a suitable local Docker Compose setup and a production deployment approach for Liara.

# Evaluation Criteria

The proposed design must explicitly optimize for and address all of the following criteria.

## 1. Answer Quality and Accuracy — 80 points

- Accurate and relevant answers
- Complete and practical answers
- Ability to find the appropriate information
- Reduction of incorrect and fabricated answers
- Appropriate citations
- Good performance for both simple and complex questions

## 2. UI Design and User Experience — 55 points

- High-quality, easy-to-use interface
- Good conversational experience
- Proper presentation of code, links, and technical information
- Good experience across continued and multi-turn conversations
- Responsive design
- Attention to UX details

## 3. Agentic Capabilities and Personalization — 50 points

- Correct understanding of user intent
- Asking follow-up questions when necessary
- Preserving conversation context
- Personalizing answers
- Suggesting appropriate next steps
- Performing multi-step processes
- Creative and practical use of agentic capabilities

## 4. Security, Reliability, and Monitoring — 50 points

- Rate limiting
- Secure API key and secret management
- Proper error and failure handling
- Control of token usage and unnecessary requests
- Logging and monitoring
- Scalable and maintainable architecture

The design should also consider relevant AI, web, API, data, container, and supply-chain security risks.

## 5. Deployment on Liara Infrastructure — 40 points

- Successful operation on Liara infrastructure
- High-quality deployment process
- Appropriate configuration
- Production readiness

## 6. Cost Optimization — 25 points

- Appropriate model and service selection
- Token-usage control
- Reduction of unnecessary requests
- Caching where useful
- Awareness of infrastructure costs
- A suitable balance among answer quality, latency, and cost

# Required Design Topics

The resulting `DESIGN.md` should cover at least:

- Goals, non-goals, assumptions, and requirements
- Recommended architecture and component responsibilities
- Docker container and service boundaries
- Documentation crawling and GitHub synchronization
- Content extraction, cleaning, deduplication, and versioning
- Chunking, embedding, indexing, and retrieval
- Database and data model
- Agent and chatbot workflow
- Grounding, citations, confidence assessment, and hallucination prevention
- Persian, English, and mixed-language query handling
- Conversation memory and personalization
- External web-search fallback
- Backend and inter-service APIs
- JavaScript widget architecture and UX
- Background jobs and scheduling
- Security and abuse prevention
- Reliability and failure handling
- Logging, monitoring, and alerting
- Evaluation and testing
- Cost and token optimization
- Docker-based local development
- Production deployment on Liara
- Scalability and maintainability
- Implementation phases and milestones
- Risks and mitigations
- Acceptance criteria
- A traceability matrix mapping the design to all evaluation criteria and point values

Include appropriate architecture diagrams, workflow diagrams, data models, API examples, project structure, deployment plans, and other implementation artifacts you consider useful.

# Output Requirements

- Return only the complete contents of `DESIGN.md`.
- Make clear recommendations instead of only listing alternatives.
- Explain important decisions and trade-offs.
- Distinguish MVP requirements from later improvements.
- State assumptions and open questions rather than silently inventing requirements.
- Keep the architecture practical and avoid unnecessary agentic or infrastructure complexity.
- Prioritize answer quality, security, reliability, user experience, maintainability, production readiness, and cost efficiency.
