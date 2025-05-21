
# Update CFF Authors from Pull Request Contributions

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

This GitHub Action adds contributors to the `authors:` section of your `CITATION.cff` file by analyzing pull requests. It gathers information from commit authors, co-authors, PR reviewers, commenters, and linked issues to build a richer set of contributors. It also enriches contributor metadata using GitHub and ORCID.

🛑 **Note:** This action does not modify your repository directly. It posts a comment on the pull request suggesting updates to your `CITATION.cff` file.

---

## 🔧 Features

- Updates `authors:` in `CITATION.cff` with contributors from PRs
- Parses commit authors, co-authors, PR reviewers, and commenters
- Detects users who opened or commented on linked issues
- Enriches metadata using GitHub profiles and ORCID lookups
- Skips duplicate authors using multiple identity checks
- Posts a pull request comment with the proposed CFF content

---

## 🚀 Usage

### Example Workflow

```yaml
name: Contributor Check on PR

on:
  pull_request:
    branches: ["main"]

jobs:
  contributor-check:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write

    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0

      - name: Run update-cff-authors
        uses: ./.github/actions/update-cff-authors
        with:
          base_branch: main
          head_branch: ${{ github.head_ref }}
          cff_path: CITATION.cff
          post_comment: true
          include_coauthors: true
          authorship_for_pr_commits: true
          authorship_for_pr_reviews: true
          authorship_for_pr_issues: true
          authorship_for_pr_issue_comments: true
          authorship_for_pr_comment: true
```

---

## 🔗 Inputs

| Name                          | Description                                                      | Required | Default        |
|-------------------------------|------------------------------------------------------------------|----------|----------------|
| `base_branch`                 | Base branch of the PR                                            | ✅ Yes   | —              |
| `head_branch`                 | Source branch of the PR                                          | ✅ Yes   | —              |
| `cff_path`                    | Path to your `CITATION.cff` file                                 | ❌ No    | `CITATION.cff` |
| `post_comment`                | Whether to comment the updated CFF file on the PR                | ❌ No    | `true`         |
| `include_coauthors`          | Include co-authors from commit messages                          | ❌ No    | `true`         |
| `authorship_for_pr_commits`  | Add commit authors and co-authors to authors                     | ❌ No    | `true`         |
| `authorship_for_pr_reviews`  | Add users who reviewed the PR                                    | ❌ No    | `true`         |
| `authorship_for_pr_issues`   | Add authors of issues linked to the PR                           | ❌ No    | `true`         |
| `authorship_for_pr_issue_comments` | Add users who commented on linked issues                  | ❌ No    | `true`         |
| `authorship_for_pr_comment`  | Add users who commented directly on the PR                       | ❌ No    | `true`         |

---

## 📤 Outputs

| Name           | Description                                      |
|----------------|--------------------------------------------------|
| `new_users`    | Comma-separated list of added author identifiers |
| `updated_cff`  | Full content of the updated CFF file             |
| `warnings`     | Skipped or incomplete author entries             |
| `orcid_logs`   | Logs of ORCID match attempts                     |

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

> ORCID enrichment is only applied to individuals (`type: person`).

---

### 2. Non-GitHub Contributors

If a commit or co-author entry lacks a GitHub account (i.e. appears as a raw name/email):

- These are **initially treated as `entities`**.
- If the name + email match an existing CFF `person`, the contributor is promoted to `person`.
- ORCID search is attempted to enrich metadata.

#### Fields:
- `person`: `given-names`, `family-names`, `email`, `orcid`
- `entity`: `name`, `email`, `alias` (optional)

---

### Deduplication Strategy

Before adding a contributor, the following identifiers are checked against existing CFF `authors:`:

1. ORCID
2. Email address
3. GitHub alias (if available)
4. Full name (`given-names` + `family-names`)
5. Entity name

Only contributors with **no matching identity** are added.

---


---

## 📦 Requirements

To use this action in your repository:

- ✅ A `CITATION.cff` file must exist at the root of your repository, or you must specify a custom path using the `cff_path` input.
- ✅ Python must be available (the action installs dependencies using `pip`).
- ✅ No additional secrets or tokens are required — this action uses GitHub's built-in `${{ secrets.GITHUB_TOKEN }}`.
- ✅ You must give the workflow appropriate permissions:
  ```yaml
  permissions:
    contents: read
    pull-requests: write
  ```
- ✅ The action must be checked into your repository at `.github/actions/update-cff-authors/`.


## 📝 License

Licensed under the [Apache 2.0 License](LICENSE).
