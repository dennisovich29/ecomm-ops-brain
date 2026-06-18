# Docker Commands Cheat Sheet

## 🚀 Quick Start

### Production Build
```bash
# Build and run all services
docker compose up --build

# Run in detached mode
docker compose up -d

# View logs
docker compose logs -f backend
docker compose logs -f frontend
```

### Development Mode (Hot Reload)
```bash
# Use dev override with volume mounts
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Or with make
make dev
```

---

## 🏗️ Build Architecture

### Backend (Python + uv)
**Multi-stage build:**
1. **Builder stage**: Installs dependencies with `uv` into isolated venv
2. **Runtime stage**: Minimal Python image with only venv + app code

**Benefits:**
- ✅ Faster builds with layer caching
- ✅ Smaller final image (~200MB vs ~800MB)
- ✅ Reproducible builds with uv's lock file support

### Frontend (Next.js + pnpm)
**Multi-stage build:**
1. **Deps stage**: Install node_modules with pnpm
2. **Builder stage**: Build Next.js with standalone output
3. **Runner stage**: Minimal Node image with only built artifacts

**Benefits:**
- ✅ 80% smaller image size (standalone output)
- ✅ Faster cold starts
- ✅ Efficient layer caching with pnpm

---

## 📦 Individual Services

### Build single service
```bash
docker compose build backend
docker compose build frontend
```

### Rebuild without cache
```bash
docker compose build --no-cache backend
```

### Run single service
```bash
docker compose up backend
docker compose up postgres redis qdrant
```

---

## 🧹 Cleanup

```bash
# Stop all services
docker compose down

# Stop and remove volumes (⚠️ deletes data)
docker compose down -v

# Remove dangling images
docker image prune -f

# Remove build cache
docker builder prune -f
```

---

## 🔍 Debugging

### Shell into running container
```bash
docker compose exec backend sh
docker compose exec frontend sh
```

### View service logs
```bash
docker compose logs backend --tail=100 -f
docker compose logs frontend --tail=100 -f
```

### Inspect container
```bash
docker compose ps
docker compose top backend
```

---

## 🌍 Environment Variables

Backend reads from `.env` via `env_file` directive.

Frontend requires build-time variables:
- `NEXT_PUBLIC_API_URL` - Backend API URL
- `NEXT_PUBLIC_WS_URL` - WebSocket URL

---

## ⚡ Performance Tips

1. **Use BuildKit** (enabled by default in Docker 23+)
   ```bash
   export DOCKER_BUILDKIT=1
   ```

2. **Parallel builds**
   ```bash
   docker compose build --parallel
   ```

3. **Prune regularly**
   ```bash
   docker system prune -a --volumes
   ```

---

## 🎯 Makefile Shortcuts

```bash
make build       # Build all images
make up          # Start all services
make dev         # Start with hot reload
make down        # Stop all services
make logs        # Tail all logs
make clean       # Remove containers + volumes
```
