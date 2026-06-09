# EDTF to Date Range Translation

This page documents by example the conversions between EDTF date and Solr 
[DateRange] values that the Solrizer [dates indexer] performs.

This Markdown file is used directly by the 
[unit tests](../tests/indexers/test_dates.py) for the dates indexer. To 
read this Markdown data, the unit tests use the [markdown-to-data] package.
All the tables that have both an `EDTF` and `Solr DateRange` column are 
consider as data sources. Each row in the table is converted to a tuple 
that is passed to the unit test to check that the `EDTF` value gets 
converted to the expected `Solr DateRange`.

Extra columns are ignored by the unit test.

## Supported

| EDTF                    | Solr DateRange               |
|-------------------------|------------------------------|
| `1605-11-05`            | `1605-11-05`                 |
| `2000-11`               | `2000-11`                    |
| `1984`                  | `1984`                       |
| `2000-11-01/2014-12-01` | `[2000-11-01 TO 2014-12-01]` |
| `2004-06/2006-08`       | `[2004-06 TO 2006-08]`       |
| `1964/2008`             | `[1964 TO 2008]`             |
| `2014/2014-12-01`       | `[2014 TO 2014-12-01]`       |
| `../1985-04-12`         | `[* TO 1985-04-12]`          |
| `../1985-04`            | `[* TO 1985-04]`             |
| `../1985`               | `[* TO 1985]`                |
| `1985-04-12/..`         | `[1985-04-12 TO *]`          |
| `1985-04/..`            | `[1985-04 TO *]`             |
| `1985/..`               | `[1985 TO *]`                |
| `-0009`                 | `-0009`                      |

### Date and Time

Normalized to UTC, with the "Z" notation for the time zone.

| EDTF                        | Solr DateRange         |
|-----------------------------|------------------------|
| `2024-11-18T11:49:32-05:00` | `2024-11-18T16:49:32Z` |

### Seasons (Without Hemisphere)

Assumes the Northern Hemisphere. See the
[Seasons (With Hemisphere)](#seasons-with-hemisphere) for a note about 
year-wrapping and winter.

| EDTF      | Solr DateRange               | Season |
|-----------|------------------------------|--------|
| `2001-21` | `[2001-03-01 TO 2001-05-31]` | spring |
| `2001-22` | `[2001-06-01 TO 2001-08-31]` | summer |
| `2001-23` | `[2001-09-01 TO 2001-11-30]` | autumn |
| `2001-24` | `[2001-12-01 TO 2001-12-31]` | winter |

### Seasons (With Hemisphere)

Note about year-wrapping (taken from a comment in 
[edtf.appsettings]):

> winter in the northern hemisphere wraps the end of the year, so
> Winter 2010 could wrap into 2011.
> 
> For simplicity, we assume it falls at the end of the year, esp since the
> spec says that sort order goes spring > summer > autumn > winter

#### Northern Hemisphere

| EDTF      | Solr DateRange               | Season |
|-----------|------------------------------|--------|
| `2001-25` | `[2001-03-01 TO 2001-05-31]` | spring |
| `2001-26` | `[2001-06-01 TO 2001-08-31]` | summer |
| `2001-27` | `[2001-09-01 TO 2001-11-30]` | autumn |
| `2001-28` | `[2001-12-01 TO 2001-12-31]` | winter |

#### Southern Hemisphere

| EDTF      | Solr DateRange               | Season |
|-----------|------------------------------|--------|
| `2001-29` | `[2001-09-01 TO 2001-11-30]` | spring |
| `2001-30` | `[2001-12-01 TO 2001-12-31]` | summer |
| `2001-31` | `[2001-03-01 TO 2001-05-31]` | autumn |
| `2001-32` | `[2001-06-01 TO 2001-08-31]` | winter |

### Other Year Subdivisions

#### Quarters (3-month blocks)

| EDTF      | Solr DateRange               |
|-----------|------------------------------|
| `2001-33` | `[2001-01-01 TO 2001-03-31]` |
| `2001-34` | `[2001-04-01 TO 2001-06-30]` |
| `2001-35` | `[2001-07-01 TO 2001-09-30]` |
| `2001-36` | `[2001-10-01 TO 2001-12-31]` |

#### Quadrimesters (4-month blocks)

| EDTF      | Solr DateRange               |
|-----------|------------------------------|
| `2001-37` | `[2001-01-01 TO 2001-04-30]` |
| `2001-38` | `[2001-05-01 TO 2001-08-31]` |
| `2001-39` | `[2001-09-01 TO 2001-12-31]` |

#### Semesters  (6-month blocks)

| EDTF      | Solr DateRange               |
|-----------|------------------------------|
| `2001-40` | `[2001-01-01 TO 2001-06-30]` |
| `2001-41` | `[2001-07-01 TO 2001-12-31]` |

### Unspecified Digits

| EDTF         | Solr DateRange               |
|--------------|------------------------------|
| `1992-09-XX` | `[1992-09-01 TO 1992-09-30]` |
| `1992-XX`    | `[1992-01-01 TO 1992-12-31]` |
| `199X`       | `[1990-01-01 TO 1999-12-31]` |
| `19XX`       | `[1900-01-01 TO 1999-12-31]` |
| `1XXX`       | `[1000-01-01 TO 1999-12-31]` |
| `XXXX`       | `[0000-01-01 TO 9999-12-31]` |

### Exponential Years

These are supported, as long as they are between -9999 and 9999.

| EDTF    | Solr DateRange                 |
|---------|--------------------------------|
| `Y1E3`  | `[1000-01-01 TO 1000-12-31]`   |
| `Y5E2`  | `[0500-01-01 TO 0500-12-31]`   |
| `Y6E1`  | `[0060-01-01 TO 0060-12-31]`   |
| `Y-1E3` | `[-1000-01-01 TO -1000-12-31]` |
| `Y-5E2` | `[-500-01-01 TO -500-12-31]`   |
| `Y-6E1` | `[-060-01-01 TO -060-12-31]`   |

### Qualified Dates

| EDTF    | Solr DateRange | Uncertain? | Approximate? | Uncertain and Approximate? | Precision | Range Size |
|---------|----------------|------------|--------------|----------------------------|-----------|------------|
| `2024?` | `2024`         | True       |              |                            | 4         | 366        |
| `2024~` | `2024`         |            | x            |                            | 4         | 366        |
| `2024%` | `2024`         |            |              | x                          | 4         | 366        |

### Qualified Intervals

| EDTF          | Solr DateRange   | Uncertain? | Approximate? | Uncertain and Approximate? | Precision | Range Size |
|---------------|------------------|------------|--------------|----------------------------|-----------|------------|
| `2024?/2025`  | `[2024 TO 2025]` | x          |              |                            | 4         | 731        |
| `2024~/2025`  | `[2024 TO 2025]` |            | x            |                            | 4         | 731        |
| `2024%/2025`  | `[2024 TO 2025]` |            |              | x                          | 4         | 731        |
| `2024?/2025?` | `[2024 TO 2025]` | x          |              |                            | 4         | 731        |
| `2024~/2025~` | `[2024 TO 2025]` |            | x            |                            | 4         | 731        |
| `2024%/2025%` | `[2024 TO 2025]` |            |              | x                          | 4         | 731        |
| `2024/2025?`  | `[2024 TO 2025]` | x          |              |                            | 4         | 731        |
| `2024/2025~`  | `[2024 TO 2025]` |            | x            |                            | 4         | 731        |
| `2024/2025%`  | `[2024 TO 2025]` |            |              | x                          | 4         | 731        |
| `2024?/2025~` | `[2024 TO 2025]` | x          | x            |                            | 4         | 731        |
| `2024~/2025?` | `[2024 TO 2025]` | x          | x            |                            | 4         | 731        |
| `2024?/2025%` | `[2024 TO 2025]` | x          |              | x                          | 4         | 731        |
| `2024~/2025%` | `[2024 TO 2025]` |            | x            | x                          | 4         | 731        |

### Qualified Individual Components

| EDTF               | Solr DateRange         | Uncertain? | Approximate? | Uncertain and Approximate? | Precision | Range Size |
|--------------------|------------------------|------------|--------------|----------------------------|-----------|------------|
| `~1945/1959`       | `[1945-01-01 TO 1959]` |            | x            |                            | 4         | 5478       |
| `1945/~1959`       | `[1945 TO 1959-12-31]` |            | x            |                            | 4         | 5478       |
| `1945-~06/1959`    | `[1945-06-01 TO 1959]` |            | x            |                            | 4         | 5327       |
| `1945/1959~-06`    | `[1945 TO 1959-06-30]` |            | x            |                            | 4         | 5294       |
| `1945-06~-15/1959` | `[1945-06-15 TO 1959]` |            | x            |                            | 4         | 5313       |
| `1945/1959-06-~15` | `[1945 TO 1959-06-15]` |            | x            |                            | 4         | 5279       |


## Precisions

| EDTF                    | Precision |
|-------------------------|-----------|
| `2026-03-12`            | 6         |
| `2026-03`               | 5         |
| `2026`                  | 4         |
| `202X`                  | 3         |
| `20XX`                  | 2         |
| `2XXX`                  | 1         |
| `2026-03-01/2026-03-10` | 6         |
| `2026-04/2026-04`       | 5         |
| `2026/2028`             | 4         |
| `198X/199X`             | 3         |
| `19XX/20XX`             | 2         |
| `1XXX/2XXX`             | 1         |
| `2026-03/2026-03-10`    | 5         |
| `2026/2026-03-10`       | 4         |
| `202X/2026-03-10`       | 3         |
| `20XX/2026-03-10`       | 2         |
| `2XXX/2026-03-10`       | 1         |
| `1990-01-01/1999-02-01` | 6         |
| `1990-01-01/1999-02`    | 5         |
| `1990-01-01/1999`       | 4         |
| `1990-01-01/199X`       | 3         |
| `1990-01-01/19XX`       | 2         |
| `1990-01-01/1XXX`       | 1         |
| `2026-03-12/`           | 6         |
| `2026-03/`              | 5         |
| `2026/`                 | 4         |
| `[2026-03-12..]`        | 6         |
| `[2026-03..]`           | 5         |
| `[2026..]`              | 4         |
| `/2026-03-12`           | 6         |
| `/2026-03`              | 5         |
| `/2026`                 | 4         |
| `[..2026-03-12]`        | 6         |
| `[..2026-03]`           | 5         |
| `[..2026]`              | 4         |

## Not Supported

These values, while valid EDTF, cannot be converted to Solr DateRange 
values and are thus not supported by Solrizer:

### Long Year

Years with more than 4 digits. For example:

  * `Y21000`
  * `Y-18000`

### Exponential Years ≥ 1E4

When the exponent is greater than 3. For example:

  * `Y1E5`
  * `Y-2E6`

## Not Implemented

Conversion of these types of EDTF values is not yet implemented. Any 
translation would likely be just a "good-enough" approximation.

### One of a Set

e.g., `[2001,2002,2005]`

### Multiple Dates

e.g., `{1966,1979,1983}`

[DateRange]: https://solr.apache.org/guide/solr/9_6/indexing-guide/date-formatting-math.html
[dates indexer]: https://umd-lib.github.io/solrizer/solrizer/indexers/dates.html
[markdown-to-data]: https://pypi.org/project/markdown-to-data/
[edtf.appsettings]: https://github.com/ixc/python-edtf/blob/main/edtf/appsettings.py#L15-L28
