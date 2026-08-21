# Liara Docs Chatbot

An embeddable documentation assistant for Liara Cloud services, with a
streaming chat API, documentation indexer, and JavaScript widget.

## Demo

Try the hosted demo:

**[Open the Liara Docs Chatbot demo](https://lostact.github.io/liara-chatbot/)**

The widget bundle is also available directly at:

**[Download widget.js](https://lostact.github.io/liara-chatbot/widget.js)**

The demo is published by [GitHub Actions](.github/workflows/build-widget.yml)
to GitHub Pages. Its Liara API URL is injected during the workflow from the
`DEMO_API_URL` repository variable and is not committed to the repository.

## Local development

1. Copy `.env.example` to `.env` and provide the required values.
2. Start the local services:

   ```bash
   make dev
   ```

3. Build the widget:

   ```bash
   cd widget
   npm ci
   npm run build
   ```

4. Open [`demo/local-test.html`](demo/local-test.html) for the localhost test
   page.

## Deployment

The API and indexer are designed to run as separate containers on Liara.
Production configuration is supplied through Liara environment variables.
The GitHub Actions workflow builds and publishes the widget demo whenever
changes reach the `main` branch.
