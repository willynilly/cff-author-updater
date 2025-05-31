# CFF Author Updater

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

This GitHub Action adds contributors to the `authors:` section of your `CITATION.cff` file by analyzing pull requests and adding new contributors as authors. Contributors include: commit authors, commit co-authors, pull request reviewers, commenters on issues linked to the pull request, and comments on the pull request itself. You can customize which kinds of contributors can become authors. The action also enriches contributor metadata using GitHub and ORCID.

🛑 **Note:** This action does not modify your repository directly. It posts a comment on the pull request that includes a block with your `CITATION.cff` file updated with new authors from that pull request. This comment also includes a detailed list of each new author's contributions (with links) that qualified them for authorship.

---

## 🔧 Features

- Updates `authors:` in `CITATION.cff` with contributors from PRs
- Customizable inclusive authorship. Allows a variety of contributors to become authors, including commit authors, commit co-authors, PR reviewers, linked issue authors, and linked issue commenters.
- Enriches metadata using GitHub profiles and ORCID lookups
- Skips duplicate authors using multiple identity checks
- Posts a pull request comment with the proposed CFF content, which can be manually copied to update the `CITATION.cff`. The comment also contains a detailed breakdown of each new author's qualifying contributions, grouped by category (commits, PR comments, reviews, issues, etc.), with clickable links to each contribution. It also contains warnings and logging information to help provide context for authorship detection and processing.
- Optionally invalidates pull request when a new author is missing from the `CITATION.cff`.
- Outputs updated `CITATION.cff` file and detailed contributions in a JSON file for other workflow steps to use.

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

      - name: Run cff-author-updater
        uses: willynilly/cff-author-updater@v2.0.0
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          base_branch: main
          head_branch: ${{ github.head_ref }}
          cff_path: CITATION.cff
          post_pr_comment: true
          authorship_for_pr_commits: true
          authorship_for_pr_reviews: true
          authorship_for_pr_issues: true
          authorship_for_pr_issue_comments: true
          authorship_for_pr_comments: true
          missing_author_invalidates_pr: true
          duplicate_author_invalidates_pr: true
          invalid_cff_invalidates_pr: true
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
| `authorship_for_pr_commits`  | Include commit authors and co-authors as authors                     | ❌ No    | `true`                 |
| `authorship_for_pr_reviews`  | Include users who reviewed the PR as authors                                   | ❌ No    | `true`                 |
| `authorship_for_pr_issues`   | Include authors of issues linked to the PR as authors                           | ❌ No    | `true`                 |
| `authorship_for_pr_issue_comments` | Include users who commented on linked issues as authors                 | ❌ No    | `true`                 |
| `authorship_for_pr_comments`  | Include users who commented directly on the PR as authors                      | ❌ No    | `true`                 |
| `missing_author_invalidates_pr`  | Invalidate the pull request if a new author is missing from the CFF file                       | ❌ No    | `true`                 |
| `duplicate_author_invalidates_pr`  | Invalidate the pull request if there is a duplicate author in the CFF file                       | ❌ No    | `true`                 |
| `invalid_cff_invalidates_pr`  | Invalidate the pull request if cffconvert fails to validate the CFF file                       | ❌ No    | `true`                 |
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
| `updated_cff`  | Full content of the updated CFF file             |
| `warnings`     | Skipped or incomplete author entries             |
| `orcid_logs`   | Logs of ORCID match attempts                     |

---

## 📦 Requirements

To use this action in your repository:

- ✅ A `CITATION.cff` file must exist at the root of your repository, or you must specify a custom path using the `cff_path` input.
- ✅ Python is automatically set up by the composite action (uses `setup-python@v5`, Python 3.13).
- ✅ You must pass GitHub’s built-in `${{ secrets.GITHUB_TOKEN }}` to the `github_token` input.
- ✅ You must reference this action in your workflow as:

  ```yaml
  uses: willynilly/cff-author-updater@v2.0.0
  ```

- ✅ For reproducibility, it is recommended to use version tags like `@v2.0.0`.

---

## 🧠 Contributor Classification and Identity Resolution

Contributors are grouped and processed according to their origin and identity metadata:

### 1. GitHub Users

When a contributor is associated with a GitHub account:

- **Individuals** (`type == "User"`):
  - Mapped to CFF `person`
  - Fields used: `given-names`, `family-names`, `alias`, `email`, `orcid`

- **Organizations** (`type == "Organization"`):
  - Mapped to CFF `entity`
  - Fields used: `name`, `alias`, `email` (if provided by GitHub)

> ORCID enrichment is only applied to individuals (`type: person`). The Github user profile URL is used for the `alias`

---

### 2. Non-GitHub Contributors

If a commit or co-author entry lacks a GitHub account (i.e. appears as a raw name/email):

- These are **initially treated as `entities`**.
- If both a name and email are present, and the contributor matches an existing `person`, they are identified as that person.
- If a name has only a single part (e.g. no `family-names`), the contributor is **retained as an `entity`**, and a warning is posted with the commit SHA.
- If only an email is provided (no name), the contributor is skipped with a warning.
- ORCID search is attempted to enrich metadata when a name is full enough (two parts).

#### Fields:
- `person`: `given-names`, `family-names`, `email`, `orcid`
- `entity`: `name`, `email` (if available), `alias` (optional)

> ⚠️ Contributors with missing `family-names` or emails are preserved as `entity` entries and clearly marked in warnings.

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
| Non-GitHub (raw commit)    | *N/A*         | ✅ Yes         | ❌ No              | ❌ No                    | —                | ❌ **Skipped**, warning: name required for CFF entity       |
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
