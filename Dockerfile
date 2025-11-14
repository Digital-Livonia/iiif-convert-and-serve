FROM debian:stable-slim

LABEL org.opencontainers.image.authors="ruven@users.sourceforge.net"
LABEL url "https://iipimage.sourceforge.io"
LABEL author "Ruven <ruven@users.sourceforge.net>"
EXPOSE 80 9000

# Install build dependencies
RUN apt-get update && \
apt-get install --no-install-recommends -y \
	lbzip2 \
	libfcgi-dev \
	libopenjp2-7-dev \
	libtiff-dev \
	libjpeg-dev \
	zlib1g-dev \
	libfcgi-dev \
	libwebp-dev \
	libpng-dev \
	pkg-config \
	g++ \
	make \
	libpng-dev \
	libwebp-dev \
	libavif-dev \
	libmemcached-dev \
	lighttpd \
	uwsgi \
	uwsgi-plugin-python3 \
	libvips-tools \
	python3-pip \
	python3-flask \
	python3-boto3


# Get latest source code
WORKDIR /usr/local/src/
ADD https://downloads.sourceforge.net/iipimage/IIP%20Server/iipsrv-1.3/iipsrv-1.3.tar.bz2 iipsrv-1.3.tar.bz2 

# Configure and compile
WORKDIR /usr/local/src/
RUN tar xf iipsrv-1.3.tar.bz2 && \
    cd iipsrv-1.3 && \
    ./configure && \
    make && \
    cp src/iipsrv.fcgi /usr/local/sbin/iipsrv


# Copy configuration and run files
COPY iipsrv.conf /etc/lighttpd/conf-enabled/iipsrv.conf
COPY convert.py convert.ini run /usr/local/bin/

# Install pyvips
RUN python3 -m pip install pyvips tifftools --break-system-packages

# Execute startup script
ENTRYPOINT /usr/local/bin/run
