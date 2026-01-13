#!/bin/bash
# Jenkins PR Detection Test Script

echo "=== JENKINS PR DETECTION TEST ==="
echo "Current working directory: $(pwd)"
echo "Git branch: $(git branch --show-current)"
echo "Git remote: $(git remote -v)"

echo ""
echo "=== ENVIRONMENT VARIABLES ==="
echo "JENKINS_URL: ${JENKINS_URL:-'Not Set'}"
echo "BUILD_NUMBER: ${BUILD_NUMBER:-'Not Set'}"
echo "GIT_BRANCH: ${GIT_BRANCH:-'Not Set'}"
echo "CHANGE_ID: ${CHANGE_ID:-'Not Set'}"
echo "CHANGE_BRANCH: ${CHANGE_BRANCH:-'Not Set'}"
echo "CHANGE_TARGET: ${CHANGE_TARGET:-'Not Set'}"
echo "CHANGE_AUTHOR: ${CHANGE_AUTHOR:-'Not Set'}"
echo "CHANGE_TITLE: ${CHANGE_TITLE:-'Not Set'}"
echo "CHANGE_URL: ${CHANGE_URL:-'Not Set'}"

echo ""
echo "=== BRANCH DETECTION LOGIC TEST ==="
if [ -n "${CHANGE_ID}" ]; then
    echo "✅ PR DETECTED: PR #${CHANGE_ID}"
    echo "   Source: ${CHANGE_BRANCH}"
    echo "   Target: ${CHANGE_TARGET}"
    echo "   Author: ${CHANGE_AUTHOR}"
else
    echo "❌ NO PR DETECTED"
    echo "   Current branch: ${GIT_BRANCH}"
    echo "   This appears to be a regular branch build"
fi

echo ""
echo "=== JENKINS JOB CONFIGURATION SUGGESTIONS ==="
echo "1. Job Type: Multibranch Pipeline"
echo "2. Branch Sources: GitHub"
echo "3. Repository URL: https://github.com/vaibhavsaxena619/poc-auto-pr-fix.git"
echo "4. Scan Repository Triggers: ✅ Periodically if not otherwise run"
echo "5. Property Strategy: All branches get the same properties"
echo "6. Build Configuration: by Jenkinsfile"

echo ""
echo "=== REQUIRED JENKINS PLUGINS ==="
echo "- GitHub Branch Source Plugin"
echo "- Pipeline: Multibranch Plugin"
echo "- GitHub Integration Plugin"

echo ""
echo "=== TEST COMPLETE ==="