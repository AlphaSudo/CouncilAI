import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  use: {
    baseURL: "http://127.0.0.1:8001",
    channel: "msedge",
    headless: true,
    trace: "retain-on-failure",
  },
  reporter: [
    ["list"],
    ["json", { outputFile: "test-results/browser-results.json" }],
  ],
  webServer: {
    command: "..\\..\\.venv\\Scripts\\python.exe ..\\..\\scripts\\qa_server.py",
    url: "http://127.0.0.1:8001/api/health",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
