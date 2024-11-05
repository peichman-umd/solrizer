# solrizer

RDF to Solr document converter microservice

## Development Setup

Requires Python 3.12

```zsh
git clone git@github.com:umd-lib/solrizer.git
cd solrizer
python -m venv --prompt "solrizer-py$(cat .python-version)" .venv
source .venv/bin/activate
pip install -e '.[dev,test]'
```

Create a `.env` file with the following contents:

```
FLASK_DEBUG=1
SOLRIZER_FCREPO_ENDPOINT={URL of fcrepo instance}
SOLRIZER_FCREPO_JWT_TOKEN={authentication token}
SOLRIZER_IIIF_IDENTIFIER_PREFIX=fcrepo:
SOLRIZER_IIIF_MANIFESTS_URL_PATTERN={URI template for IIIF manifests}
SOLRIZER_IIIF_THUMBNAIL_URL_PATTERN={URI template for IIIF thumbnail images}
SOLRIZER_INDEXERS={"__default__":["content_model","discoverability","page_sequence","iiif_links","dates","facets","extracted_text"],"Page":["content_model"]}
```

In the IIIF URI templates, use `{+id}` as the placeholder for the IIIF 
identifier of the resource being indexed.

### Running

```zsh
flask --app solrizer.web run
```

The application will be available at <http://localhost:5000>

### Tests

```zsh
pytest
```

With coverage information:

```zsh
pytest --cov src --cov-report term-missing tests
```

### API Documentation

```zsh
pdoc solrizer
```

API documentation generated by [pdoc](https://pdoc.dev/)
will be available at <http://localhost:8080/>.

To serve the documentation on an alternate port:

```zsh
pdoc -p 8888 solrizer
```

Now the documentation will be at <http://localhost:8888/>.

### Docker Image

Build the image:

```zsh
docker build -t docker.lib.umd.edu/solrizer .
```

Run, using the `.env` file set up earlier:

```zsh
docker run --rm -it -p 5000:5000 --env-file .env docker.lib.umd.edu/solrizer
```

## License

See the [LICENSE](LICENSE.md) file for license rights and
limitations (Apache 2.0).
