FROM python:3.10-alpine3.16

# Configure STScI cert generally
COPY tls-ca-bundle.pem  /tmp/cert.pem
RUN mv /etc/ssl/cert.pem /etc/ssl/cert.pem.org  && \
    mv /tmp/cert.pem  /etc/ssl

COPY jh-intermediates.pem /etc/ssl/jh-intermediates.pem

RUN SSL_CERT_FILE=/etc/ssl/cert.pem apk add ca-certificates && \
    update-ca-certificates && \
    apk update && \
    apk upgrade 
    
# Install git and configure STScI cert for git
RUN apk add --no-cache -U git  && \
    git config --global http.sslVerify true && \
    git config --global http.sslCAInfo /etc/ssl/cert.pem && \
    pip config set global.cert /etc/ssl/cert.pem

RUN apk add --no-cache -U tini nfs-utils sudo coreutils
RUN pip install --no-cache pyyaml filelock requests certifi

ENV REQUESTS_CA_BUNDLE=/etc/ssl/cert.pem
ENV CURL_CA_BUNDLE=/etc/ssl/cert.pem

RUN adduser -u 1000 -G users -D -H efs-quota
RUN echo "efs-quota ALL=NOPASSWD:/usr/bin/du,/bin/ls" >> /etc/sudoers

RUN mkdir /efs-quota  # && chown -R efs-quota:users /efs-quota
RUN mkdir -p /efs/quota-control  /efs/users
COPY efs_quota_monitor.py /efs-quota/efs_quota_monitor.py

USER efs-quota
WORKDIR /efs-quota

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["python", "/efs-quota/efs_quota_monitor.py"]   # see helm deployments for actual commands

