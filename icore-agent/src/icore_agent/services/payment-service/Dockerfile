FROM golang:1.22-alpine AS builder

WORKDIR /src

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy
ARG GOPROXY=https://proxy.golang.org,direct
ARG GOSUMDB=sum.golang.org
ARG GONOPROXY
ARG GONOSUMDB

ENV GOPROXY=${GOPROXY} \
    GOSUMDB=${GOSUMDB} \
    GONOPROXY=${GONOPROXY} \
    GONOSUMDB=${GONOSUMDB}

COPY lib-go/go.mod lib-go/go.sum ./lib-go/
COPY payment-service/go.mod payment-service/go.sum ./payment-service/
WORKDIR /src/payment-service
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download
WORKDIR /src
COPY lib-go ./lib-go
COPY payment-service ./payment-service
WORKDIR /src/payment-service
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux go build -o /out/payment-service ./cmd/payment-service

FROM alpine:3.20
RUN adduser -D -H -u 10001 appuser
USER appuser
COPY --from=builder /out/payment-service /usr/local/bin/payment-service
COPY payment-service/config /etc/icore/payment-service
EXPOSE 8080
ENTRYPOINT ["payment-service"]
