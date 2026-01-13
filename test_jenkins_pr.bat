@echo off
REM Jenkins PR Detection Test Script for Windows

echo === JENKINS PR DETECTION TEST ===
echo Current working directory: %CD%
echo Git branch: 
git branch --show-current

echo.
echo === ENVIRONMENT VARIABLES ===
echo JENKINS_URL: %JENKINS_URL%
echo BUILD_NUMBER: %BUILD_NUMBER%
echo GIT_BRANCH: %GIT_BRANCH%
echo CHANGE_ID: %CHANGE_ID%
echo CHANGE_BRANCH: %CHANGE_BRANCH%
echo CHANGE_TARGET: %CHANGE_TARGET%
echo CHANGE_AUTHOR: %CHANGE_AUTHOR%
echo CHANGE_TITLE: %CHANGE_TITLE%
echo CHANGE_URL: %CHANGE_URL%

echo.
echo === BRANCH DETECTION LOGIC TEST ===
if defined CHANGE_ID (
    echo ✅ PR DETECTED: PR #%CHANGE_ID%
    echo    Source: %CHANGE_BRANCH%
    echo    Target: %CHANGE_TARGET%  
    echo    Author: %CHANGE_AUTHOR%
) else (
    echo ❌ NO PR DETECTED
    echo    Current branch: %GIT_BRANCH%
    echo    This appears to be a regular branch build
)

echo.
echo === JENKINS MULTIBRANCH CONFIGURATION CHECK ===
echo 1. Go to Jenkins → New Item → Multibranch Pipeline
echo 2. Branch Sources → Add Source → GitHub
echo 3. Repository HTTPS URL: https://github.com/vaibhavsaxena619/poc-auto-pr-fix.git
echo 4. Credentials: Select your GitHub PAT
echo 5. Behaviors → Add → Discover pull requests from origin
echo    - Strategy: Merging the pull request with the current target branch revision
echo 6. Scan Repository Triggers → Periodically if not otherwise run: 1 minute

echo.
echo === WEBHOOK CONFIGURATION ===
echo GitHub Webhook URL: http://YOUR_JENKINS_URL/github-webhook/
echo Content Type: application/json
echo Events: Pull requests, Pushes, Pull request reviews

echo.
echo === TROUBLESHOOTING STEPS ===
echo 1. Check Jenkins logs for webhook reception
echo 2. Verify GitHub webhook delivery (Settings → Webhooks → Recent Deliveries)
echo 3. Ensure Jenkins GitHub plugin is installed and configured
echo 4. Check Jenkins multibranch scan logs
echo 5. Verify GitHub PAT has proper permissions (repo, admin:repo_hook)

echo.
echo === TEST COMPLETE ===