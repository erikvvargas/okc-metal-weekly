# ADR-0001: Use Google Sheets as the Initial Data Store

**Status:** Accepted (historical)  
**Decision date:** Retrospective documentation, October 2026  
**Applies to:** v0.4.0 and earlier  
**Decision owners:** Project maintainer

## Context

OKC Metal Weekly was developed to generate Instagram carousel posts featuring upcoming heavy music shows and new releases.

The initial workflow required a simple way to manually curate and edit event and release data without building a separate administration interface.

The application had a small dataset, a limited number of editors, and a batch-oriented publishing process.

The primary engineering priorities were:

- Rapid development and iteration.
- Minimal infrastructure and hosting costs.
- Easy manual data entry and correction.
- Compatibility with Python and pandas.
- A workflow that could run locally or through GitHub Actions.

## Decision

Use Google Sheets as the initial system of record for event and release information.

Maintain two worksheets, `Shows` and `Releases`, accessed through the Google Sheets API using `gspread` and a read-only service account.

Transform worksheet records into pandas DataFrames for filtering, grouping, and slide generation.

Retain local CSV files as an alternative data source for development and fallback execution.

## Alternatives considered

### PostgreSQL

**Advantages**
- Relational integrity and unique constraints.
- Structured querying and normalized data models.
- Better foundation for source provenance, deduplication, and historical analysis.

**Disadvantages**
- Additional database setup and administration.
- A separate editing interface would be needed for convenient manual curation.
- Greater initial implementation complexity.

### Local CSV files

**Advantages**
- Minimal dependencies.
- Easy integration with pandas.
- Straightforward version control for non-sensitive data.

**Disadvantages**
- Less convenient for editing from multiple devices.
- No built-in relational integrity.
- More cumbersome manual updates than a spreadsheet interface.

## Consequences

### Positive

- The application could be developed without provisioning a database.
- Event and release data remained easy to inspect and modify.
- Google Sheets integrated directly with the Python processing pipeline.
- GitHub Actions could generate posts without a permanently running server.
- Development effort could focus on publication quality and automation.

### Negative

- Artists, venues, and events lacked stable relational identifiers.
- Data quality depended heavily on manual review.
- Duplicate and inconsistent records were difficult to detect systematically.
- Source provenance was not consistently captured.
- Historical edits and publication inputs were not tracked by the application.
- The spreadsheet schema could change without formal migrations.

## Future considerations

As the project grows into a more complete data engineering platform, PostgreSQL will become the preferred system of record.

A future ADR will document that migration decision, including schema design, migration strategy, operational costs, and compatibility with the existing generator.

Google Sheets may remain available as an ingestion source or lightweight editorial interface during the transition.

## References

- [Historical v0.4 architecture](../architecture/v0.4-google-sheets.md)
- [Project changelog](../../CHANGELOG.md)
- [v0.4.0 release](https://github.com/erikvvargas/okc-metal-weekly/releases/tag/v0.4.0)
