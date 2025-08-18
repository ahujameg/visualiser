FROM python:3.10 AS base

RUN apt-get update \
  && apt-get install -y jove \ 
  --no-install-recommends \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV DJANGO_SETTINGS_MODULE=visualiser.settings

RUN git clone -b master https://github.com/ahujameg/visualiser.git apps

WORKDIR /apps

# Debian/Ubuntu base image
RUN apt-get update && \
  apt-get install -y --no-install-recommends \
  r-base r-base-dev build-essential \
  libcurl4-openssl-dev libssl-dev libxml2-dev libgit2-dev \
  libicu-dev libharfbuzz-dev libfribidi-dev && \
  rm -rf /var/lib/apt/lists/*

RUN R -e "install.packages(c( \
  'Rcpp',\
  'ontologyIndex','ontologySimilarity',\
  'tidyverse','umap','ggrepel','flexclust','proxy','Matrix','plyr','future','future.apply'\
  ),\
  repos='https://cloud.r-project.org',\
  Ncpus = parallel::detectCores())"

RUN pip install -r requirements.txt

RUN sed -i "/SECRET_KEY/s/^SECRET_KEY.*\\$/SECRET_KEY = \"`python manage.py shell -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`\"/" visualiser/settings.py

EXPOSE 7000

CMD ["gunicorn", "--bind", "0.0.0.0:7000", "--workers", "6", "--timeout", "0", "--graceful-timeout", "0", "--max-requests", "500", "--max-requests-jitter", "100", "config.wsgi:application"]

