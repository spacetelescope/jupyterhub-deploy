FROM golang:1.13.15-alpine3.12 as builder

ENV CGO_ENABLED=0

WORKDIR /build

# Configure STScI cert generally
COPY tls-ca-bundle.pem  /tmp/cert.pem
RUN mv /etc/ssl/cert.pem /etc/ssl/cert.pem.org  && \
    mv /tmp/cert.pem  /etc/ssl
    
# Install git and configure STScI cert for git
RUN apk add -U git  && \
    git config --global http.sslCAInfo /etc/ssl/cert.pem

# Build goofys
RUN git clone https://github.com/kahing/goofys.git . && \
    go build -ldflags "-X main.Version=`git rev-parse HEAD`"

# Build s3fs-fuse
RUN apk add --no-cache -U build-base autoconf automake libxml2-dev fuse-dev curl-dev
RUN git clone https://github.com/s3fs-fuse/s3fs-fuse.git && \
    cd s3fs-fuse/  && \
    ./autogen.sh && \
    ./configure && \
    make && \
    make install  && \
    cp /usr/local/bin/s3fs /build

# -------------------------------------------------------------------

FROM alpine:3.12

COPY tls-ca-bundle.pem  /tmp/cert.pem
RUN mv /etc/ssl/cert.pem /etc/ssl/cert.pem.org  && \
    mv /tmp/cert.pem  /etc/ssl

RUN apk add --no-cache -U fuse curl libxml2 libstdc++ mailcap tini

COPY --from=builder /build/goofys .
COPY --from=builder /build/s3fs .

CMD [./goofys]  # dump help,  overridden by daemonset to run goofys or s3fs and mount

ENTRYPOINT ["/sbin/tini", "--"]

