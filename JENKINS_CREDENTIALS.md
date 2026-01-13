# Jenkins Credentials Setup Guide

This document explains how to configure Jenkins credentials for the CI/CD pipeline.

## Required Credentials

### 1. Gemini API Key
**Credential Type:** Secret text  
**Credential ID:** `GEMINI_API_KEY_CREDENTIAL`  
**Purpose:** Powers Gemini AI code review and build error analysis

**Setup Steps:**
1. Go to Jenkins → Manage Jenkins → Manage Credentials
2. Click "Add Credentials"
3. Kind: Secret text
4. Secret: [Your Gemini API Key from https://aistudio.google.com/app/apikey]
5. ID: `GEMINI_API_KEY_CREDENTIAL`
6. Description: "Gemini API Key for code review and error analysis"
7. Click Create

### 2. GitHub Personal Access Token (PAT)
**Credential Type:** Username with password  
**Credential ID:** `GITHUB_PAT_CREDENTIAL`  
**Purpose:** Authenticates with GitHub API for PR comments and branch operations

**Setup Steps:**
1. Generate PAT at https://github.com/settings/tokens with these scopes:
   - `repo` (full control of private repositories)
   - `workflow` (manage GitHub Actions)
   - `read:user` (read user profile)

2. In Jenkins → Manage Jenkins → Manage Credentials
3. Click "Add Credentials"
4. Kind: Username with password
5. Username: Your GitHub username
6. Password: [Your GitHub PAT]
7. ID: `GITHUB_PAT_CREDENTIAL`
8. Description: "GitHub Personal Access Token"
9. Click Create

## Verification

### Check Gemini API Key
```groovy
withCredentials([string(credentialsId: 'GEMINI_API_KEY_CREDENTIAL', variable: 'GEMINI_API_KEY')]) {
    sh 'echo "Key length: ${#GEMINI_API_KEY}"'
}
```

### Check GitHub PAT
```groovy
withCredentials([usernamePassword(credentialsId: 'GITHUB_PAT_CREDENTIAL', 
                                 usernameVariable: 'GITHUB_USER', 
                                 passwordVariable: 'GITHUB_PAT')]) {
    sh 'echo "GitHub user: $GITHUB_USER"'
}
```

## Environment Variables

The pipeline automatically injects these credentials as environment variables:

- `GEMINI_API_KEY` - Used by Python scripts (pr_review.py, build_fix.py)
- `GITHUB_USERNAME` - GitHub account username
- `GITHUB_PAT` - Token for GitHub API authentication

## Troubleshooting

### "Credentials not found" Error
- Verify credential IDs match exactly: `GEMINI_API_KEY_CREDENTIAL` and `GITHUB_PAT_CREDENTIAL`
- Check Jenkins → Manage Credentials → System to confirm credentials exist
- Ensure job has permission to use these credentials

### "Invalid credentials" Error
- Verify Gemini API key is valid at https://aistudio.google.com/app/apikey
- Verify GitHub PAT is not expired: https://github.com/settings/tokens
- Check scopes on GitHub PAT include `repo` and `workflow`

### PR Comments Not Posting
- Verify GitHub PAT has `repo` scope
- Check repository name and PR number are correct
- Look for rate limiting errors (GitHub API limits)

## Security Best Practices

1. **Never commit credentials** to source control
2. **Rotate API keys regularly** (especially Gemini keys)
3. **Use minimal scopes** on GitHub PAT (only what's needed)
4. **Store credentials in Jenkins Vault** for sensitive deployments
5. **Audit credentials access** in Jenkins Manage Credentials section

## References

- Gemini API: https://aistudio.google.com/app/apikey
- GitHub PAT: https://github.com/settings/tokens
- Jenkins Credentials: https://www.jenkins.io/doc/book/security/managing-credentials/
