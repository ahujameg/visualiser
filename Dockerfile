FROM python:3.10 AS base

WORKDIR /apps

FROM base AS runtime

ENV DJANGO_SETTINGS_MODULE=visualiser.settings \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt install_r_packages.R ./

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        r-base \
        r-base-dev \
        build-essential \
        gfortran \
        cmake \
        libcurl4-openssl-dev \
        libssl-dev \
        libxml2-dev \
        libgit2-dev \
        libglpk-dev \
        libgmp3-dev \
        libfontconfig1-dev \
        libfreetype6-dev \
        libharfbuzz-dev \
        libfribidi-dev \
        libpng-dev \
        libtiff-dev \
        libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt
RUN Rscript install_r_packages.R

COPY . /apps/

CMD ["gunicorn", "--bind", ":7000", "--workers", "1", "--timeout", "36000", "--graceful-timeout", "36000", "--max-requests", "200", "--max-requests-jitter", "50", "config.wsgi:application"]
