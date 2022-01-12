ARG REPOSITORY
FROM $REPOSITORY/ncbi-blast:latest
ENV DEBIAN_FRONTEND="noninteractive"

# install requirements
RUN apt clean
RUN apt-get update \
 && apt-get install -y build-essential git libtool-bin autopoint autotools-dev autoconf pkg-config \
    libncurses5-dev libncursesw5-dev gettext software-properties-common curl cpio python3 python3-pip vim

# add files
ADD . /app

# compile and install blast
WORKDIR /app

# install app requirements
RUN pip3 install -r requirements.txt

# start container
ENTRYPOINT ["python3", "app.py"]
EXPOSE 9090/tcp
