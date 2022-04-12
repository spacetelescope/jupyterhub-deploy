FROM golang:1.13.15-alpine3.12 as builder

WORKDIR /build
ENV CGO_ENABLED=0
COPY tls-ca-bundle.pem  /tmp/cert.pem
RUN mv /etc/ssl/cert.pem /etc/ssl/cert.pem.org  && \
    mv /tmp/cert.pem  /etc/ssl
RUN apk add -U git
RUN git clone https://github.com/kahing/goofys.git . && \
    go build -ldflags "-X main.Version=`git rev-parse HEAD`"

FROM alpine:3.12
COPY tls-ca-bundle.pem  /tmp/cert.pem
RUN mv /etc/ssl/cert.pem /etc/ssl/cert.pem.org  && \
    mv /tmp/cert.pem  /etc/ssl
WORKDIR /otomato
COPY --from=builder /build/goofys .
CMD [./goofys]
