# CFF Author Updater

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

This GitHub Action adds contributors to the `authors:` section of your `CITATION.cff` file by analyzing pull requests and adding new contributors as authors. Contributors include: commit authors, commit co-authors, pull request reviewers, commenters on issues linked to the pull request, and comments on the pull request itself. You can customize which kinds of contributors can become authors. The action also enriches contributor metadata using GitHub and ORCID.

🛑 **Note:** This action does not modify your repository directly. It posts a comment on the pull request that includes a block with your `CITATION.cff` file updated with new authors from that pull request. This comment also includes a detailed list of each new author's contributions (with links) that qualified them for authorship.

---

## 🔧 Features

- Updates `authors` in CFF files (e.g. `CITATION.cff`) with contributors from PRs. Currently uses CFF version 1.2.0.
- Customizable inclusive authorship. Allows a variety of contributors to become authors, including commit authors, commit co-authors, PR reviewers, linked issue authors, and linked issue commenters.
- Enriches metadata using GitHub profiles and ORCID lookups
- Skips duplicate authors using multiple identity checks, with optional manual contributor overrides via PR comments (skip/unskip commands)
- Posts a pull request comment with the proposed CFF content, which can be manually copied to update the `CITATION.cff`. The comment also contains a detailed breakdown of each new author's qualifying contributions, grouped by category (commits, PR comments, reviews, issues, etc.), with clickable links to each contribution. It also contains warnings and logging information to help provide context for authorship detection and processing.
- Options for invalidating pull request when a new author is missing from the `CITATION.cff`, when there are duplicate authors, or when `cffconvert` fails to validate `CITATION.cff`.
- Outputs updated `CITATION.cff` file, detailed contributions in a JSON file, validation metadata, and logs for other workflow steps to use.

---

## 🚀 Usage

### Example Workflow

```yaml
name: Review CFF Authors on Pull Request

on:
  pull_request_target:
    branches: ["main"]

permissions:
  contents: read
  pull-requests: write  # Needed for posting PR comments

jobs:
  contributor-check:
    runs-on: ubuntu-latest

    steps:
      - name: Check out PR code safely
        uses: actions/checkout@v3
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          repository: ${{ github.event.pull_request.head.repo.full_name }}
          fetch-depth: 0
      
      - name: Install Python
        uses: actions/setup-python@v5
        with:
          python-version: ">=3.13.3" # required for cff-author-updater
          cache: 'pip' # optional for cff-author-updater

      - name: Run cff-author-updater
        uses: willynilly/cff-author-updater@v2.4.0
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          base_branch: main
          head_branch: ${{ github.head_ref }}
          cff_path: CITATION.cff
          post_pr_comment: true
          show_error_messages_in_pr_comment: true
          show_warning_messages_in_pr_comment: true
          show_info_messages_in_pr_comment: true
          authorship_for_pr_commits: true
          authorship_for_pr_reviews: true
          authorship_for_pr_issues: true
          authorship_for_pr_issue_comments: true
          authorship_for_pr_comments: true
          missing_author_invalidates_pr: true
          duplicate_author_invalidates_pr: true
          invalid_cff_invalidates_pr: true
          can_skip_authorship: true
          bot_blacklist: github-actions[bot]
```

---

## 🔗 Inputs

| Name                          | Description                                                      | Required | Default                |
|-------------------------------|------------------------------------------------------------------|----------|------------------------|
| `github_token`               | GitHub token used for API requests                              | ✅ Yes   | —                      |
| `base_branch`                 | Base branch of the PR                                            | ✅ Yes   | —                      |
| `head_branch`                 | Source branch of the PR                                          | ✅ Yes   | —                      |
| `cff_path`                    | Path to your `CITATION.cff` file                                 | ❌ No    | `CITATION.cff`         |
| `post_pr_comment`                | Whether to comment the updated CFF file on the PR                | ❌ No    | `true`                 |                 |
| `show_error_messages_in_pr_comment`                | Whether to show error messages in PR comment                | ❌ No    | `true`                 |                 |
| `show_warning_messages_in_pr_comment`                | Whether to show warning messages in PR comment                | ❌ No    | `true`                 |                 |
| `show_info_messages_in_pr_comment`                | Whether to show info messages in PR comment                | ❌ No    | `true`                 |                 |
| `authorship_for_pr_commits`  | Include commit authors and co-authors as authors                     | ❌ No    | `true`                 |
| `authorship_for_pr_reviews`  | Include users who reviewed the PR as authors                                   | ❌ No    | `true`                 |
| `authorship_for_pr_issues`   | Include authors of issues linked to the PR as authors                           | ❌ No    | `true`                 |
| `authorship_for_pr_issue_comments` | Include users who commented on linked issues as authors                 | ❌ No    | `true`                 |
| `authorship_for_pr_comments`  | Include users who commented directly on the PR as authors                      | ❌ No    | `true`                 |
| `missing_author_invalidates_pr`  | Invalidate the pull request if a new author is missing from the CFF file                       | ❌ No    | `true`                 |
| `duplicate_author_invalidates_pr`  | Invalidate the pull request if there is a duplicate author in the CFF file                       | ❌ No    | `true`                 |
| `invalid_cff_invalidates_pr`  | Invalidate the pull request if cffconvert fails to validate the CFF file                       | ❌ No    | `true`                 |
| `can_skip_authorship`  | Whether manually skipping and unskipping authorship is enabled or not                       | ❌ No    | `true`                 |
| `bot_blacklist`              | Comma-separated GitHub usernames to exclude from authorship      | ❌ No    | `github-actions[bot]`  |

**Note:** When `invalid_cff_invalidates_pr` is enabled, the pull request will be invalidated (workflow will fail) if `cffconvert` reports any validation errors on the CFF file.  
Typical reasons for `cffconvert` validation failure include:
- Duplicate authors (e.g. same ORCID, same author block)
- Invalid or missing required fields (violating Citation File Format spec)
- Incorrect field formats (e.g. malformed ORCID URL)

Any `cffconvert` errors will also appear in the pull request comment under the **Warnings** section.

The `invalid_cff_invalidates_pr` flag enforces the official CFF format standard (as validated by `cffconvert`).  
The `missing_author_invalidates_pr` and `duplicate_author_invalidates_pr` flags provide **additional semantic validation** beyond the CFF format. They use the **Deduplication Strategy** described below.

---

## 📤 Outputs

| Name           | Description                                      |
|----------------|--------------------------------------------------|
| `new_authors`  | New authors and qualifying contributions in JSON |
| `original_cff`  | Full original CFF content in YAML             |
| `original_cff_is_valid_cff`  | Whether the original CFF file has valid CFF according to cffconvert ('true' or 'false')       |
| `updated_cff`  | Full updated CFF content in YAML. If no changes, this will be the same as the original CFF file.             |
| `updated_cff_is_valid_cff`  | Whether the updated CFF file has valid CFF according to cffconvert ('true' or 'false')             |
| `updated_cff_has_error`  | Whether the updated CFF file has an error ('true' or 'false'). An error invalidates the pull request.             |
| `updated_cff_has_warning`  | Whether the updated CFF file has an error ('true' or 'false'). A warning does not invalidate the pull request.             |
| `error_log`   | Log that contains errors about the CFF author update process.             |
| `warning_log` | Log that contains warnings about the CFF author update process.             |
| `info_log`    | Log that contains general information about the CFF author update process.                     |
| `debug_log`    | Log that contains debug information about the CFF author update process.                     |

**Note:** The `debug_log` is empty unless the GitHub environmental variable `ACTIONS_STEP_DEBUG` has been set to `true`. This occurs automatically, when you enable debugging from the GitHub website.  

---

## 📦 Requirements

To use this action in your repository:

- ✅ A `CITATION.cff` file must exist at the root of your repository, or you must specify a custom path using the `cff_path` input.
- ✅ Python version 3.13 or higher needs to be configured in your workflow (e.g., using `setup-python@v5`). See the **Example Workflow** above.
- ✅ You must pass GitHub’s built-in `${{ secrets.GITHUB_TOKEN }}` to the `github_token` input.
- ✅ You must reference this action in your workflow as:

  ```yaml
  uses: willynilly/cff-author-updater@v2.4.0
  ```

- ✅ For reproducibility, it is recommended to use version tags like `@v2.4.0`.

---

## 🧠 Contributor Classification and Identity Resolution

Contributors are grouped and processed according to their origin and identity metadata:

### 1. GitHub Users

When a contributor is associated with a GitHub account:

- **Individuals** (`type == "User"`):
  - Mapped to CFF `person` if `given-names` and `family-names` is available.
  - Otherwise, mapped to CFF `entity` using CFF `name`.
  - CFF Fields used: `given-names` (from GitHub or ORCID profiles if available), `family-names` (from GitHub or ORCID profiles if available), `alias` (is GitHub user profile URL), `email` (from GitHub profile if available), `orcid` (from GitHub profile or ORCID email search if available)

- **Organizations** (`type == "Organization"`):
  - Mapped to CFF `entity`
  - CFF Fields used: `name` (from GitHub or ORCID profiles if available), `alias` (is GitHub user profile URL), `email` (from GitHub profile if available)


> GitHub enrichment currently only consists of adding the following metadata from the GitHub user profile: name, email, bio, and blog (i.e., website). The bio and blog are not currently mapped to CFF fields. However, they are used to extract missing ORCID information.  

> ORCID enrichment currently only consists of adding an ORCID and, if available, a name, to a CFF author if it cannot find one from the GitHub profile metadata. It is only applied to individuals GitHub contributors (`type: person`) that are new authors. Moreover, it requires one of several mechanisms to acquire the ORCID, and subsequently the author name associated with that ORCID:

1. The GitHub account has been linked to their ORCID account. The GitHub action scrapes the ORCID from a badge on their user profile page.
2. GitHub user profile has an ORCID listed as their website/blog, or they list it in their bio. The GitHub action uses the GitHub API to extract it from this user profile data.
3. GitHub user has shared their public email and then this email is used to search for a corresponding ORCID account using the ORCID API. Most ORCID users do not make their email addresses public, so this method rarely is used. 

---

### 2. Non-GitHub Contributors

If a commit or co-author entry lacks a GitHub account (i.e. appears as a raw name/email):

- These are **initially treated as `entities`**.
- However, if the contributor matches an existing `person` in the CFF through the **deduplication strategy**, they are identified as that person.
- If a name has only a single part (e.g. no `family-names`), the contributor is **retained as an `entity`**.
- If only an email is provided (i.e., no name), and a name cannot be found on an ORCID profile associated with that email, then the contributor is skipped.
- ORCID enrichment currently only consists of adding an ORCID and a missing author name. It is only applied to git commiters that have an email address, and whose ORCID profile has made that email address public. Most ORCID accounts do not make their email addresses public on their profiles, so this enrichment rarely occurs.

#### CFF Fields:
- `person`: `given-names` (from git commit name or ORCID profile if available), `family-names` (from git commit name or ORCID profile is available), `email` (from git commit email if available), `orcid` (from git commit email and ORCID email search if available)
- `entity`: `name`, `email` (from git commit email if available)

> ⚠️ Contributors with missing `given-names`, `family-names` or `email` are preserved as `entity` entries.

---

### 📋 Contributor Metadata Handling Table

**Definitions:**
- **Full name**: A name containing both given and family parts (e.g. `"Jane Doe"`)
- **Partial name**: A name with only one part (e.g. `"Jane"`)

| Contributor Type            | Example Name | Email Present | Name Present      | GitHub Username Present | Example Username | Action                                                     |
|----------------------------|---------------|---------------|--------------------|--------------------------|------------------|------------------------------------------------------------|
| GitHub User (individual)   | Jane Doe      | ✅ Yes         | ✅ Full            | ✅ Yes                   | `jdoe`           | Added as `person`                                          |
| GitHub User (organization) | CERN          | ❌ No          | ✅ Yes             | ✅ Yes                   | `cern-official`  | Added as `entity`                                          |
| Non-GitHub (raw commit)    | Jane Doe      | ✅ Yes         | ✅ Full            | ❌ No                    | —                | Added as `person`                                          |
| Non-GitHub (raw commit)    | Jane          | ✅ Yes         | ✅ Partial         | ❌ No                    | —                | Added as `entity` with warning                             |
| Non-GitHub (raw commit)    | *N/A*        | ✅ Yes         | ❌ No, and not found on Orcid profile through public email              | ❌ No                    | —                | ❌ **Skipped**, warning: name required for CFF entity       |
| Non-GitHub (raw commit)    | Jane Doe        | ✅ Yes         | ❌ No, but ✅ Full name found on ORCID profile through public email              | ❌ No                    | —                | Added as `person`       |
| Non-GitHub (raw commit)    | Jane        | ✅ Yes         | ❌ No, but ✅ Partial name found on ORCID profile through public email              | ❌ No                    | —                | Added as `entity` with warning       |
| Non-GitHub (raw commit)    | Jane Doe      | ❌ No          | ✅ Full            | ❌ No                    | —                | Added as `entity` with warning if needed                   |
| Non-GitHub (raw commit)    | *N/A*         | ❌ No          | ❌ No              | ❌ No                    | —                | ❌ **Skipped**, warning: name and email both missing        |

> Warnings for skipped or downgraded contributors include the commit SHA for traceability.

---

### Deduplication Strategy

Before adding a contributor, the following identifiers are checked against existing CFF `authors:` **in this order**:

1. **ORCID:** If both authors have an ORCID and they match, they are considered the same.
2. **Email:** If both authors have an email and they match, they are considered the same.
3. **GitHub user profile URL as `alias`:** If both authors have an `alias` that is a GitHub user profile URL and they match, they are considered the same.
4. **Full name:** If both authors have a full name (for persons: `given-names` + `family-names`; for entities: `name`) and they match (case-insensitive, whitespace-insensitive), they are considered the same author.


### 🔍 Deduplication Algorithm Summary

| Priority | Matching Field | Behavior |
|----------|----------------|----------|
| 1️⃣ | ORCID | If both have ORCID and it matches → same author |
| 2️⃣ | GitHub `alias` (GitHub profile URL) | If both have alias and it matches → same author |
| 3️⃣ | Email | If both have email and it matches → same author |
| 4️⃣ | Full Name (given-names + family-names, or entity `name`) | If full names match → same author |

## ✋ Manual Overrides: Skip / Unskip Contributors for Authorship

In some cases, the GitHub Action may detect a contributor identity that is incorrect, duplicated, or that the maintainers do not wish to include as an author in the `CITATION.cff` file.

To handle these cases, **maintainers can post PR comments with `skip-authorship` or `unskip-authorship` commands** to manually override contributor processing for that pull request.

### Supported Commands

You can skip or unskip contributors for authorship by writing a comment with one of these commands:

| Command                              | Example |
|--------------------------------------|---------|
| `skip-authorship-by-github-username`      | `skip-authorship-by-github-username someuser` |
| `unskip-authorship-by-github-username`    | `unskip-authorship-by-github-username someuser` |
| `skip-authorship-by-email`                | `skip-authorship-by-email user@example.com` |
| `unskip-authorship-by-email`              | `unskip-authorship-by-email user@example.com` |
| `skip-authorship-by-name`                 | `skip-authorship-by-name John Doe` |
| `unskip-authorship-by-name`               | `unskip-authorship-by-name John Doe` |
| `skip-authorship-by-orcid`                | `skip-authorship-by-orcid https://orcid.org/0000-0000-0000-0000` |
| `unskip-authorship-by-orcid`              | `unskip-authorship-by-orcid https://orcid.org/0000-0000-0000-0000` |


### How manual overrides work

- The Action scans **all PR comments**, ordered chronologically.
- The most recent command for each contributor field wins.
- If a contributor is currently skipped for authorship, the Action will:
  - **Exclude them** from recommended CFF updates
  - **Exclude them** from "missing author" checks

  ⚠️ Important: Skipping a contributor does NOT remove them from the CFF file if they were already present, and does NOT prevent a user from manually adding them to the CFF file in this pull request.
  Skipped contributors are still included in duplicate author checks if present in the CFF file.
  The skip command only prevents the Action from recommending or requiring their addition as a new author.

- You can **change your mind** at any time by posting an `unskip-authorship` command.
- Deleting a comment with a skip command works as if you never wrote that comment.
- Deleting a comment with an unskip command works as if you never wrote that comment. 
- You will need to manually restart the workflow or post another commit to the pull request for newly posted commands to take effect. Posting a pull request comment does not currently trigger the GitHub Action.
- These commands only apply to new contributors on head branch (e.g., the forked branch you are trying to merge) of the pull request. They do not apply to old authors on the base branch (i.e. the branch into which the pull request merges).

### Example of changing your mind with commands. 

Here a contributor is skipped by email and then unskipped by email.

```markdown
skip-authorship-by-email user@example.com
```

```markdown
unskip-authorship-by-email user@example.com
```

Note: You do not need to delete old comments — the Action will always apply the most recent command for each contributor field.


## 🛠 Developer Notes

To run pytest tests, you must create a `.env` in the project folder
that contains `developer.env`. If you don't have a `.env`, you
can rename `developer.env` to `.env`.

## 📝 License

Licensed under the [Apache 2.0 License](LICENSE).

## References
Druskat, S., Spaaks, J. H., Chue Hong, N., Haines, R., Baker, J., Bliven, S.,
Willighagen, E., Pérez-Suárez, D., & Konovalov, A. (2021). Citation File Format
(Version 1.2.0) [Computer software]. <https://doi.org/10.5281/zenodo.5171937>

