# LightRAG Integration Spec for Shishka OS

**Task:** 2e0cb037 — LightRAG evaluation для agent knowledge retrieval
**Branch:** `research/lightrag-eval`
**Date:** 2026-04-06
**Status:** Research / PoC

---

## 1. Executive Summary

LightRAG — это graph-based RAG система от HKU, которая извлекает **сущности и связи** из документов, строит граф знаний и использует его для ответов на запросы. В отличие от стандартного vector-only RAG, LightRAG даёт более точные ответы на вопросы о связях между концепциями.

**Вердикт:** LightRAG подходит для Shishka OS как knowledge retrieval layer. Запускаем как Docker-микросервис с REST API, используем Ollama для инференса.

---

## 2. Архитектурная схема

```
┌─────────────────────────────────────────────────────┐
│                   Shishka OS                        │
│                                                     │
│  ┌──────────┐   ┌──────────────┐   ┌─────────────┐ │
│  │ MCP      │   │ Post-commit  │   │ Task Track  │ │
│  │ Servers  │   │ Hook         │   │ (Next.js)   │ │
│  └────┬─────┘   └──────┬───────┘   └──────┬──────┘ │
│       │                │                   │        │
│       │    ┌───────────▼───────────────────▼──┐     │
│       │    │      LightRAG REST API           │     │
│       └───►│      http://localhost:9621       │     │
│            │                                  │     │
│            │  /query          — поиск по КГ   │     │
│            │  /documents/scan — индексация     │     │
│            │  /documents/upload — загрузка     │     │
│            │  /api/chat      — Ollama-compat  │     │
│            └──────────┬───────────────────────┘     │
│                       │                             │
│            ┌──────────▼───────────────┐             │
│            │     Ollama (local)       │             │
│            │  LLM:   gemma4:27b      │             │
│            │  Embed: bge-m3          │             │
│            │  http://localhost:11434  │             │
│            └──────────────────────────┘             │
│                                                     │
│  Storage (local files, zero-dependency):            │
│  ┌────────────┐ ┌──────────────┐ ┌───────────────┐ │
│  │ JSON KV    │ │ NanoVectorDB │ │ NetworkX      │ │
│  │ (cache,    │ │ (embeddings) │ │ (knowledge    │ │
│  │  chunks)   │ │              │ │  graph, .gml) │ │
│  └────────────┘ └──────────────┘ └───────────────┘ │
└─────────────────────────────────────────────────────┘
```

---

## 3. Ответы на ключевые вопросы

### 3.1 Стек: Python-микросервис vs TypeScript-порт

**Решение: Docker-микросервис (Python)**

- TypeScript-портов LightRAG **не существует**. Проект — чистый Python.
- LightRAG предоставляет полноценный **REST API** (FastAPI) + **Ollama-совместимые эндпоинты** (`/api/chat`, `/api/generate`).
- Готовый Docker-образ: `ghcr.io/hkuds/lightrag:latest`.
- Наш TypeScript-код (MCP серверы, Task Track) вызывает LightRAG через HTTP — нулевая связность.

**Почему не порт:**
- Алгоритм entity extraction + graph merging сложен (~3000 LOC ядра).
- Python-экосистема (NetworkX, NanoVectorDB, tiktoken) не имеет прямых аналогов в Node.js.
- REST API полностью покрывает наши потребности.

### 3.2 Инференс: Ollama + Gemma 4

**Решение: Ollama — first-class supported**

LightRAG имеет встроенные драйверы для Ollama (`lightrag/llm/ollama.py`).

Конфигурация через `.env`:
```bash
LLM_BINDING=ollama
LLM_BINDING_HOST=http://host.docker.internal:11434
LLM_MODEL=gemma4:27b
OLLAMA_LLM_NUM_CTX=32768

EMBEDDING_BINDING=ollama
EMBEDDING_BINDING_HOST=http://host.docker.internal:11434
EMBEDDING_MODEL=bge-m3:latest
EMBEDDING_DIM=1024
```

**Важные ограничения:**
- Для качественного entity extraction рекомендуется модель **32B+ параметров** с контекстом **32K+ токенов**.
- Gemma 4 27B подходит, но нужно выставить `num_ctx=32768` (Ollama по умолчанию даёт 8192).
- Для embeddings используем `bge-m3` (1024 dim) — лучший open-source multilingual embedding.

**Приватность:** Все данные остаются локально. Нет вызовов к внешним API.

### 3.3 Интеграция с docs/: Post-commit хуки

**Решение: Post-commit hook → curl scan endpoint**

LightRAG не имеет встроенного file watcher, но предоставляет эндпоинт `/documents/scan`, который сканирует `INPUT_DIR` на новые файлы.

Схема автоиндексации:
```
docs/*.md  →  git commit  →  post-commit hook  →  curl /documents/scan
```

**Post-commit hook** (`.git/hooks/post-commit`):
```bash
#!/bin/bash
# Проверяем, были ли изменены файлы в docs/
CHANGED_DOCS=$(git diff-tree --no-commit-id --name-only -r HEAD | grep '^docs/')

if [ -n "$CHANGED_DOCS" ]; then
    echo "[LightRAG] Detected docs changes, triggering re-index..."
    # Копируем изменённые файлы в input-директорию LightRAG
    for f in $CHANGED_DOCS; do
        cp "$f" ./data/lightrag-inputs/ 2>/dev/null
    done
    # Запускаем сканирование
    curl -s -X POST http://localhost:9621/documents/scan \
         -H "Content-Type: application/json" \
         > /dev/null 2>&1 &
    echo "[LightRAG] Re-index triggered for: $CHANGED_DOCS"
fi
```

**Альтернатива:** Использовать наш Claude Code hook (`post-commit` в `.claude/settings.json`) для того же эффекта.

### 3.4 Хранение: Граф и векторы

**Решение: Локальные файлы (для PoC), PostgreSQL (для прода)**

| Компонент | PoC (локально) | Production |
|-----------|---------------|------------|
| KV Storage | `JsonKVStorage` (JSON-файлы) | `PGKVStorage` (PostgreSQL) |
| Vectors | `NanoVectorDBStorage` (файлы) | `PGVectorStorage` (pgvector) |
| Graph | `NetworkXStorage` (.graphml) | `PGGraphStorage` (Apache AGE) |
| Doc Status | `JsonDocStatusStorage` | `PGDocStatusStorage` |

**Neo4j НЕ нужен.** Для PoC достаточно локальных файлов. Для production PostgreSQL с расширениями `pgvector` + `Apache AGE` покрывает все 4 типа хранилища одной БД (уже используем Supabase/PostgreSQL в Task Track).

Объём данных: наши docs/ — это десятки markdown-файлов. NetworkX справится в памяти без проблем.

---

## 4. Retrieval Modes

LightRAG поддерживает 6 режимов поиска:

| Режим | Описание | Когда использовать |
|-------|----------|-------------------|
| `naive` | Классический vector search по чанкам | Простые вопросы, поиск конкретного текста |
| `local` | Поиск по ближайшим сущностям в графе | "Что такое X?", "Какие свойства Y?" |
| `global` | Поиск по связям и темам | "Как X связан с Y?", обзорные вопросы |
| `hybrid` | `local` + `global` | Основной режим для наших агентов |
| `mix` | `hybrid` + `naive` | Максимальная полнота, с reranker |
| `bypass` | Прямой вызов LLM без RAG | Follow-up вопросы |

**Рекомендация для Shishka:** использовать `hybrid` по умолчанию, `mix` для MCP knowledge search.

---

## 5. Proof of Concept

### 5.1 Docker Compose (добавить в корень Shishka)

```yaml
# docker-compose.lightrag.yml
version: "3.8"

services:
  lightrag:
    image: ghcr.io/hkuds/lightrag:latest
    container_name: shishka-lightrag
    ports:
      - "9621:9621"
    volumes:
      - ./data/rag_storage:/app/data/rag_storage
      - ./data/lightrag-inputs:/app/data/inputs
      - ./lightrag.env:/app/.env
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9621/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### 5.2 Конфигурация (`lightrag.env`)

```bash
# === LLM (Ollama + Gemma 4) ===
LLM_BINDING=ollama
LLM_BINDING_HOST=http://host.docker.internal:11434
LLM_MODEL=gemma4:27b
OLLAMA_LLM_NUM_CTX=32768

# === Embeddings (Ollama + BGE-M3) ===
EMBEDDING_BINDING=ollama
EMBEDDING_BINDING_HOST=http://host.docker.internal:11434
EMBEDDING_MODEL=bge-m3:latest
EMBEDDING_DIM=1024

# === Storage (local files for PoC) ===
LIGHTRAG_KV_STORAGE=JsonKVStorage
LIGHTRAG_DOC_STATUS_STORAGE=JsonDocStatusStorage
LIGHTRAG_GRAPH_STORAGE=NetworkXStorage
LIGHTRAG_VECTOR_STORAGE=NanoVectorDBStorage

# === Performance ===
MAX_ASYNC=4
MAX_PARALLEL_INSERT=2
EMBEDDING_FUNC_MAX_ASYNC=8

# === API ===
HOST=0.0.0.0
PORT=9621
# API_KEY=your-secret-key  # раскомментировать для production
```

### 5.3 Скрипт инициализации и тестирования

```bash
#!/bin/bash
# scripts/lightrag-poc.sh — Quick PoC для LightRAG в Shishka OS

set -e

echo "=== LightRAG PoC for Shishka OS ==="

# 1. Подготовка
mkdir -p data/lightrag-inputs data/rag_storage

# 2. Проверяем Ollama
echo "Checking Ollama..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "ERROR: Ollama not running. Start it first: ollama serve"
    exit 1
fi

# 3. Проверяем модели
echo "Checking required models..."
ollama pull bge-m3:latest 2>/dev/null || true
# gemma4:27b — пользователь должен скачать заранее

# 4. Копируем тестовые docs
echo "Preparing test documents..."
if [ -d "docs" ]; then
    cp docs/*.md data/lightrag-inputs/ 2>/dev/null || true
fi
# Создаём тестовый документ если docs/ пуст
cat > data/lightrag-inputs/test-knowledge.md << 'DOCEOF'
# Shishka OS Architecture

Shishka OS is a restaurant management platform consisting of several modules:

## Modules
- **Task Track**: Next.js web app for kitchen task management, built with Supabase
- **Antigravity**: Data pipeline for Syrve POS integration (n8n workflows)
- **Book Organizer**: PDF processing and Google Drive integration
- **MCP Servers**: shishka-chef (recipe/BOM management) and shishka-finance (expense tracking)

## Tech Stack
- Frontend: Next.js, React, TypeScript, Tailwind CSS, shadcn/ui
- Backend: Supabase (PostgreSQL), MCP protocol
- AI: Claude (via Anthropic API), local Ollama models
- Deployment: Docker, Vercel
DOCEOF

# 5. Запускаем LightRAG
echo "Starting LightRAG..."
docker compose -f docker-compose.lightrag.yml up -d

echo "Waiting for LightRAG to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:9621/health > /dev/null 2>&1; then
        echo "LightRAG is ready!"
        break
    fi
    sleep 2
done

# 6. Индексируем документы
echo "Triggering document scan..."
curl -s -X POST http://localhost:9621/documents/scan \
     -H "Content-Type: application/json"

echo ""
echo "Waiting for indexing (30s)..."
sleep 30

# 7. Тестовые запросы
echo ""
echo "=== Test Query: hybrid mode ==="
curl -s -X POST http://localhost:9621/query \
     -H "Content-Type: application/json" \
     -d '{
       "query": "What modules does Shishka OS have and how are they connected?",
       "mode": "hybrid",
       "only_need_context": false
     }' | python3 -m json.tool 2>/dev/null || echo "(raw output above)"

echo ""
echo "=== Test Query: local mode ==="
curl -s -X POST http://localhost:9621/query \
     -H "Content-Type: application/json" \
     -d '{
       "query": "What is Task Track built with?",
       "mode": "local"
     }' | python3 -m json.tool 2>/dev/null || echo "(raw output above)"

echo ""
echo "=== PoC Complete ==="
echo "Web UI: http://localhost:9621"
echo "API Docs: http://localhost:9621/docs"
```

### 5.4 MCP-интеграция (будущий шаг)

Для подключения LightRAG к нашим MCP-серверам — простой wrapper:

```typescript
// Пример: вызов LightRAG из MCP-сервера
async function queryKnowledge(question: string, mode = "hybrid") {
  const response = await fetch("http://localhost:9621/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query: question, mode }),
  });
  return response.json();
}
```

---

## 6. Roadmap интеграции

| Фаза | Описание | Effort |
|------|----------|--------|
| **Phase 1** | Docker PoC: поднять LightRAG + Ollama, проиндексировать тестовый doc | 2-3 часа |
| **Phase 2** | Post-commit hook: автоиндексация docs/ при коммитах | 1 час |
| **Phase 3** | MCP tool `search_knowledge` в shishka-chef: запросы к LightRAG | 3-4 часа |
| **Phase 4** | Web UI для просмотра графа знаний (LightRAG built-in) | 0 (есть из коробки) |
| **Phase 5** | Production: миграция на PostgreSQL (pgvector + AGE) | 4-6 часов |

---

## 7. Риски и митигации

| Риск | Вероятность | Митигация |
|------|------------|-----------|
| Gemma 4 27B слабо извлекает entities | Средняя | Тестируем на реальных docs; fallback на llama3.3:70b или Gemini API |
| Высокое потребление RAM (Ollama + LightRAG) | Высокая | На Mac M-серии: 16GB min, 32GB рекомендуется. Используем quantized модели |
| Медленная индексация больших документов | Низкая | Наши docs — десятки файлов, не тысячи. NanoVectorDB справится |
| NetworkX не масштабируется | Низкая (для нас) | При росте до 10K+ сущностей мигрируем на PostgreSQL+AGE |

---

## 8. Ссылки

- [LightRAG GitHub](https://github.com/HKUDS/LightRAG)
- [LightRAG Paper](https://arxiv.org/abs/2410.05779)
- [Docker Image](https://ghcr.io/hkuds/lightrag)
- [API Docs](http://localhost:9621/docs) (после запуска)
