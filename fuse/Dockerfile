FROM ubuntu:22.04 as builder

RUN apt update && apt install golang git build-essential -y

ENV CGO_ENABLED=0

WORKDIR /build

# Configure STScI cert generally
COPY tls-ca-bundle.pem  /tmp/cert.pem
RUN mv /tmp/cert.pem  /etc/ssl
    
# Install git and configure STScI cert for git
RUN git config --global http.sslCAInfo /etc/ssl/cert.pem

# Build goofys
RUN git clone https://github.com/kahing/goofys.git . && \
    git checkout 829d8e5  && \
    go build -ldflags "-X main.Version=`git rev-parse HEAD`"

# Build s3fs-fuse 
RUN apt install -y autoconf automake libxml2-dev libfuse-dev libcurl4-openssl-dev pkg-config libssl-dev

RUN git clone  https://github.com/s3fs-fuse/s3fs-fuse.git && \
    cd s3fs-fuse  && \
    git checkout v1.91 && \
    ./autogen.sh && \
    ./configure && \
    make && \
    make install  && \
    cp /usr/local/bin/s3fs /build

# -------------------------------------------------------------------

FROM ubuntu:22.04

COPY tls-ca-bundle.pem  /tmp/cert.pem
RUN mv /tmp/cert.pem  /etc/ssl

RUN apt update && apt -y install fuse curl libxml2 libstdc++6 mailcap tini
COPY --from=builder /build/goofys .
COPY --from=builder /build/s3fs .

CMD [./goofys]  # dump help,  overridden by daemonset to run goofys or s3fs and mount

ENTRYPOINT ["/sbin/tini", "--"]

