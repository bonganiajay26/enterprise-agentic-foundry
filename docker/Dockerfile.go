# Multi-stage Go production Dockerfile
# Produces a minimal scratch image (< 20MB)

# ─── Stage 1: Build ───────────────────────────────────────────────────
FROM golang:1.22-alpine AS builder
WORKDIR /app

# Install CA certs and timezone data for scratch image
RUN apk add --no-cache ca-certificates tzdata

# Dependency caching
COPY go.mod go.sum ./
RUN go mod download && go mod verify

# Build static binary
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build \
    -ldflags="-w -s -X main.version=$(cat VERSION 2>/dev/null || echo dev) -X main.buildTime=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    -trimpath \
    -o /server \
    ./cmd/server

# ─── Stage 2: Production (scratch) ───────────────────────────────────
FROM scratch AS runner

# Copy essentials from builder
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo
COPY --from=builder /server /server

# Non-root UID (numeric, scratch has no useradd)
USER 65532:65532

LABEL org.opencontainers.image.title="Go Application" \
      org.opencontainers.image.vendor="Your Org" \
      org.opencontainers.image.licenses="Apache-2.0"

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["/server", "health"]

ENTRYPOINT ["/server"]
