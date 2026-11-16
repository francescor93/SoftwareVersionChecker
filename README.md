# SoftwareVersionChecker

SoftwareVersionChecker is a Python script that collects the installed versions of a server software stack and updates a matching table in a Confluence page.

The script checks Apache, PHP, MariaDB, Node.js, NPM, and Python, then records the check time. It finds the first table in the configured Confluence page and updates the cells in the column identified by `SERVER_NAME`. The first column of the table must contain the software names used by the script: `Apache`, `PHP`, `MariaDB`, `Node.js`, `NPM`, `Python`, and `Last Check`.

## Requirements

- Python 3 and pip
- A Confluence account and API token with permission to view and edit the target page
- The software whose versions you want to check, installed and available to the script

Version detection runs shell commands and uses utilities such as `grep`, `awk`, `cut`, `tr`, and `head`. Make sure these commands are available in the environment where the script runs, especially on Windows.

## Installation

Clone or download the repository, then install the Python dependencies:

```shell
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set the values for your Confluence instance and target table.

## Configuration

The script loads `.env` from the repository folder. Configure the following variables:

| Variable | Description |
| --- | --- |
| `MODE` | Selects the credential set to use: `CLASSIC` or `SCOPED`. |
| `CONF_USER` | Confluence account email or username used for authentication. |
| `CONF_CLASSIC_BASE_URL` | Base URL for the Confluence instance when `MODE=CLASSIC`. |
| `CONF_CLASSIC_TOKEN` | API token for `MODE=CLASSIC`. |
| `CONF_SCOPED_BASE_URL` | Base URL for the Confluence instance when `MODE=SCOPED`. |
| `CONF_SCOPED_TOKEN` | API token for `MODE=SCOPED`. |
| `CONF_PAGE_ID` | ID of the Confluence page containing the table to update. |
| `SERVER_NAME` | Exact header of the table column to update. |
| `HTTP_TIMEOUT` | HTTP request timeout in seconds. |
| `MAX_RETRIES` | Number of retries after the initial attempt. |
| `RETRY_DELAY` | Base delay between retry attempts, in seconds. |
| `RETRY_JITTER` | Maximum additional random delay, in seconds. |

Set the base URL to the root of your Confluence instance; the script appends `/wiki/rest/api` to it. Only the URL and token corresponding to the selected `MODE` are required. The table must have a header row using `<th>` cells, and its first table must contain a column whose header exactly matches `SERVER_NAME`.

Keep `.env` private: it contains credentials and should not be committed or shared.

## Usage

Run the script from the repository folder:

```shell
python update_versions_confluence.py
```

The script logs progress and errors to the console and to `software_versions.log` in the repository folder. It retries version conflicts, rate limits, server errors, and network timeouts up to `MAX_RETRIES` times after the first attempt. It exits with status `0` on success and `1` if the update fails.

The script is suitable for scheduled execution, provided the environment has access to the required software commands and the configured Confluence page.

## Contributing

If you would like to contribute, open an issue to discuss your idea or submit a pull request with your changes.

This project is provided "as is", without any guarantee that it is free of bugs. It is an independent project and is not affiliated with Atlassian or any of the software vendors mentioned above.
