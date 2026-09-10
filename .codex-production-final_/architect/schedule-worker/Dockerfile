FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY *.go ./
RUN apk add --no-cache git \
    && GOPROXY=${GOPROXY:-https://proxy.golang.org,direct} go mod tidy \
    && CGO_ENABLED=0 go build -o /out/schedule-worker .

FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata wget
WORKDIR /data
COPY --from=build /out/schedule-worker /usr/local/bin/schedule-worker
EXPOSE 8110
ENTRYPOINT ["/usr/local/bin/schedule-worker"]
