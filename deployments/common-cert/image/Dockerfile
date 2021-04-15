ARG ROOT_CONTAINER=ubuntu:21.04
ARG BASE_CONTAINER=$ROOT_CONTAINER
FROM $BASE_CONTAINER

# ------------------------------------------------------------------------
# SSL/TLS cert setup for STScI AWS firewalling

USER root

RUN mkdir -p /etc/ssl/certs && \
    mkdir -p /etc/pki/ca-trust/extracted/pem
COPY tls-ca-bundle.pem /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem
#RUN ls /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem

RUN echo "export REQUESTS_CA_BUNDLE=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem" >> ~/.bashrc
RUN echo "export CURL_CA_BUNDLE=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem" >> ~/.bashrc
