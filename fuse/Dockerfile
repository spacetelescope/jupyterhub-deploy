FROM golang:1.13.15-alpine3.12 as builder

ENV CGO_ENABLED=0

COPY tls-ca-bundle.pem  /tmp/cert.pem
RUN mv /etc/ssl/cert.pem /etc/ssl/cert.pem.org  && \
    mv /tmp/cert.pem  /etc/ssl
    
WORKDIR /build

RUN apk add -U git  && \
    git config --global http.sslCAInfo /etc/ssl/cert.pem
RUN git clone https://github.com/kahing/goofys.git . && \
    go build -ldflags "-X main.Version=`git rev-parse HEAD`"

RUN apk add -U build-base autoconf automake libxml2-dev fuse-dev curl-dev
RUN git clone https://github.com/s3fs-fuse/s3fs-fuse.git && \
    cd s3fs-fuse/  && \
    ./autogen.sh && \
    ./configure && \
    make && \
    make install  && \
    cp /usr/local/bin/s3fs /build

FROM alpine:3.12
COPY tls-ca-bundle.pem  /tmp/cert.pem
RUN mv /etc/ssl/cert.pem /etc/ssl/cert.pem.org  && \
    mv /tmp/cert.pem  /etc/ssl

RUN apk add fuse curl libxml2 libstdc++

COPY --from=builder /build/goofys .
COPY --from=builder /build/s3fs .

CMD [./goofys]  # dump help,  overridden by daemonset to run goofys or s3fs and mount

