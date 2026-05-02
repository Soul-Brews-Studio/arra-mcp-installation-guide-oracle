# arra-oracle-v3 — installation & dev targets

REPO := Soul-Brews-Studio/arra-oracle-v3
PORT := 47778
LOCAL := $(HOME)/Code/github.com/$(REPO)

.PHONY: install run health dev test fix-branch status ollama

# Install via bunx (recommended)
install:
	bunx --bun arra-oracle@github:$(REPO) --help

# Run MCP/HTTP server via bunx
run:
	bunx --bun arra-oracle@github:$(REPO) --port $(PORT)

# Health check
health:
	curl -s http://localhost:$(PORT)/api/health | jq .

# Local dev (from cloned repo)
dev:
	cd $(LOCAL) && bun install && bun run src/server.ts

# Run tests
test:
	cd $(LOCAL) && bun test

# Switch to fix branch
fix-branch:
	cd $(LOCAL) && git checkout fix/vector-retrieval-bugs

# Git status of incubated repo
status:
	cd $(LOCAL) && git status && git branch --show-current

# Check ollama is alive (Layer 0)
ollama:
	@curl -s http://localhost:11434/api/tags | jq '.models[].name' 2>/dev/null || echo "❌ Ollama not running"
