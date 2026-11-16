# SoftwareVersionChecker

SoftwareVersionChecker is a Python script that collects the installed versions of a server software stack and updates a matching table in a Confluence page.

The script checks Apache, PHP, MariaDB, Node.js, NPM, and Python, then records the check time. It finds the first table in the configured Confluence page and updates the cells in the column identified by `SERVER_NAME`. The first column of the table must contain the software names used by the script: `Apache`, `PHP`, `MariaDB`, `Node.js`, `NPM`, `Python`, and `Last Check`.

## Requirements

- Python 3 and pip
- A Confluence Cloud site, plus an account and an API token with permission to view and edit the target page. The script uses the `/wiki/rest/api` REST path of Confluence Cloud; other editions have not been tested.
- The software whose versions you want to check, installed and available to the script

Version detection runs shell commands and uses utilities such as `grep`, `awk`, `cut`, `tr`, and `head`. Make sure these commands are available in the environment where the script runs, especially on Windows.

## Installation

Clone or download the repository, then install the Python dependencies:

```shell
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set the values for your Confluence instance and target table.  
The first table on the target page must have a header row using `<th>` cells, including a column whose header exactly matches `SERVER_NAME` (see below).

## Configuration

The script loads `.env` from the repository folder. Configure the following variables:

| Variable | Description |
| --- | --- |
| `MODE` | Selects the credential set to use: `CLASSIC` or `SCOPED`. |
| `CONF_USER` | Email address of the Confluence account that owns the API token. |
| `CONF_CLASSIC_BASE_URL` | Site URL used when `MODE=CLASSIC`, e.g. `https://your-site.atlassian.net`. |
| `CONF_CLASSIC_TOKEN` | Unscoped API token, used when `MODE=CLASSIC`. |
| `CONF_SCOPED_BASE_URL` | API gateway URL used when `MODE=SCOPED`: `https://api.atlassian.com/ex/confluence/<cloudId>` (see below). |
| `CONF_SCOPED_TOKEN` | Scoped API token, used when `MODE=SCOPED`. |
| `CONF_PAGE_ID` | ID of the Confluence page containing the table to update. |
| `SERVER_NAME` | Exact header of the table column to update. |
| `HTTP_TIMEOUT` | Optional. HTTP request timeout in seconds. Default: `30`. |
| `MAX_RETRIES` | Optional. Number of retries after the initial attempt. Default: `5`. |
| `RETRY_DELAY` | Optional. Base delay between retry attempts, in seconds. Default: `60`. |
| `RETRY_JITTER` | Optional. Maximum additional random delay, in seconds. Default: `10`. |

Only the URL and token corresponding to the selected `MODE` are required.

### Authentication modes

Both modes use HTTP Basic authentication with `CONF_USER` and the token. They differ in the base URL and in how the token is restricted. In both cases the script appends `/wiki/rest/api/...` to the base URL, so do not include `/wiki` in it.

**`CLASSIC`**: an unscoped API token, which has the same permissions as the account that created it. Set `CONF_CLASSIC_BASE_URL` to your site URL, for example `https://your-site.atlassian.net`.

**`SCOPED`**: an API token limited to specific scopes. Requests must go through the Atlassian API gateway, so `CONF_SCOPED_BASE_URL` must be `https://api.atlassian.com/ex/confluence/<cloudId>`, not your site URL. You can look up your `cloudId` at `https://your-site.atlassian.net/_edge/tenant_info`.

Scopes the script has been tested with in `SCOPED` mode:

- `read:content-details:confluence`
- `read:content.metadata:confluence`
- `read:space:confluence`
- `write:content:confluence`

The classic scopes `read:confluence-content.all`, `read:confluence-space.summary` and `write:confluence-content` were not sufficient in testing: Confluence answered `401 Unauthorized; scope does not match`. Scopes only limit what the token can do; the account still needs permission to view and edit the page.

Keep `.env` private: it contains credentials and should not be committed or shared.

## Usage

Run the script from the repository folder:

```shell
python update_versions_confluence.py
```

The script logs progress and errors to the console and to `software_versions.log` in the repository folder. If a version cannot be detected, its cell is set to `N/A` and the raw command output is written to the log.

Every update attempt re-reads the page from Confluence before writing, so when several servers update the same page at the same time, a server that hits a version conflict simply retries on top of the other server's changes. Version conflicts, rate limits, server errors and network timeouts are retried up to `MAX_RETRIES` times after the first attempt, waiting `RETRY_DELAY` seconds plus a random delay of up to `RETRY_JITTER` seconds between attempts. Other errors (authentication, missing table or column) fail immediately. The script exits with status `0` on success and `1` if the update fails.

### Scheduling

The script is suitable for scheduled execution. Example crontab entry, daily at midnight:

```shell
0 0 * * * /usr/bin/python3 /path/to/SoftwareVersionChecker/update_versions_confluence.py
```

Notes for scheduled runs:

- Cron runs with a minimal `PATH`. If `php`, `node`, `npm` or `mysql` are not in standard locations (for example when installed through a version manager), set `PATH` at the top of the crontab.
- On Linux, Apache's version is read with `sudo apache2 -v`. The user running the script must be able to run it without a password prompt, otherwise detection fails and the cell shows `N/A`. Example sudoers rule, to be edited with `visudo` (check the binary path with `which apache2`): `scriptuser ALL=(root) NOPASSWD: /usr/sbin/apache2 -v`

## Contributing

If you would like to contribute, open an issue to discuss your idea or submit a pull request with your changes.

This project is provided "as is", without any guarantee that it is free of bugs. It is an independent project and is not affiliated with Atlassian or any of the software vendors mentioned above.

## License

Released under the [MIT License](LICENSE).
