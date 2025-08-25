# https://developers.home-assistant.io/docs/add-ons/configuration#add-on-dockerfile
ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python.
ARG TEMPIO_VERSION=BUILD_ARCH
RUN \
    apk add --no-cache python3 py3-pip

## Download the Chambers code.
#RUN \
#    wget https://github.com/chrisgilldc/chambers/archive/refs/tags/0.1.0-alpha7.zip &&\
#    unzip 0.1.0-alpha7.zip

# Copy the chambers package.
#COPY chambers /
RUN ls -al

ADD . /chambers

# Install
RUN \
    pip install --break-system-packages ./chambers

# Copy root filesystem
#COPY rootfs /
COPY run.sh /
RUN chmod 555 /run.sh

CMD [ "/run.sh" ]