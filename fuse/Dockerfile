#FROM golang:1.13.15-alpine3.12 as builder

FROM ubuntu:22.04 as builder

RUN apt update && apt install golang git build-essential -y

ENV CGO_ENABLED=0

WORKDIR /build

# Configure STScI cert generally
COPY tls-ca-bundle.pem  /tmp/cert.pem
#RUN mv /etc/ssl/cert.pem /etc/ssl/cert.pem.org  && \
RUN mv /tmp/cert.pem  /etc/ssl
    
# Install git and configure STScI cert for git
#RUN apk add -U git  && \
RUN git config --global http.sslCAInfo /etc/ssl/cert.pem

# Build goofys
RUN git clone https://github.com/kahing/goofys.git . && \
    #git checkout 08534b2  && \
    go build -ldflags "-X main.Version=`git rev-parse HEAD`"

# Build s3fs-fuse 
#RUN apk add --no-cache -U build-base autoconf automake libxml2-dev fuse-dev curl-dev
RUN apt install -y autoconf automake libxml2-dev libfuse-dev libcurl4-openssl-dev pkg-config libssl-dev
RUN git clone  https://github.com/s3fs-fuse/s3fs-fuse.git && \
    cd s3fs-fuse  && \
    #git checkout v1.91 && \
    ./autogen.sh && \
    ./configure && \
    make && \
    make install  && \
    cp /usr/local/bin/s3fs /build
COPY s3-fuse-mount.sh s3-fuse-mount.sh
RUN chmod +x s3-fuse-mount.sh

# -------------------------------------------------------------------

FROM ubuntu:22.04

COPY tls-ca-bundle.pem  /tmp/cert.pem
#RUN mv /etc/ssl/cert.pem /etc/ssl/cert.pem.org  && \
RUN mv /tmp/cert.pem  /etc/ssl

#RUN apk add --no-cache -U fuse curl libxml2 libstdc++ mailcap tini
RUN apt update && apt -y install fuse curl libxml2 libstdc++6 mailcap tini
COPY --from=builder /build/goofys .
COPY --from=builder /build/s3fs .

CMD [./goofys]  # dump help,  overridden by daemonset to run goofys or s3fs and mount

ENTRYPOINT ["/sbin/tini", "--"]

