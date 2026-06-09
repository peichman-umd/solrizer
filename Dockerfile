FROM python:3.12.6-slim

EXPOSE 5000

ENV FLASK_DEBUG=0

WORKDIR /opt/solrizer

RUN apt-get update && apt-get install -y git && apt-get clean

COPY src pyproject.toml /opt/solrizer/

RUN pip install -e ".[redis]"

VOLUME /var/cache/solrizer

ENTRYPOINT [ "solrizer" ]
