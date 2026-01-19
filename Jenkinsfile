pipeline {
    agent any
    
    tools {
        git 'Default'
    }
    
    parameters {
        booleanParam(name: 'TRIGGER_RELEASE_BUILD', defaultValue: false, description: 'Set to true to trigger Release branch build')
    }
    
    environment {
        BRANCH_NAME = "${env.GIT_BRANCH?.replace('origin/', '') ?: 'unknown'}"
        AZURE_OPENAI_API_VERSION = "2024-12-01-preview"
        AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-5"
        
        // === SECURITY & SAFETY FEATURE FLAGS ===
        ENABLE_AUTO_FIX = "${env.ENABLE_AUTO_FIX ?: 'true'}"
        ENABLE_OPENAI_CALLS = "${env.ENABLE_OPENAI_CALLS ?: 'true'}"
        READ_ONLY_MODE = "${env.READ_ONLY_MODE ?: 'false'}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    echo "Branch: ${BRANCH_NAME}"
                    if (env.CHANGE_ID) {
                        echo "PR #${env.CHANGE_ID} to ${env.CHANGE_TARGET}"
                    }
                }
            }
        }

        // ==========================================
        // DEV_POC_V1 WORKFLOW: No automatic builds
        // ==========================================
        stage('Dev_Poc_V1 - No Build') {
            when {
                allOf {
                    branch 'Dev_Poc_V1'
                    expression { return env.CHANGE_ID == null }
                }
            }
            steps {
                script {
                    echo "✓ Dev_Poc_V1 branch detected"
                    echo "⊘ No automatic builds on Dev_Poc_V1 - Push changes without compilation"
                    echo "ℹ To trigger builds, create a PR to Release or manually trigger Release branch build"
                }
            }
        }

        // ==========================================
        // PULL REQUEST WORKFLOW: Code review without build
        // ==========================================
        stage('Pull Request - Code Review Only') {
            when {
                allOf {
                    changeRequest()
                }
            }
            steps {
                script {
                    echo "PR #${env.CHANGE_ID} to ${env.CHANGE_TARGET} detected"
                    echo "Analyzing code changes without compilation..."
                    
                    withCredentials([
                        string(credentialsId: 'AZURE_OPENAI_API_KEY', variable: 'AZURE_OPENAI_API_KEY'),
                        string(credentialsId: 'AZURE_OPENAI_ENDPOINT', variable: 'AZURE_OPENAI_ENDPOINT'),
                        usernamePassword(credentialsId: 'GITHUB_PAT',
                                       usernameVariable: 'GITHUB_USERNAME',
                                       passwordVariable: 'GITHUB_PAT')
                    ]) {
                        sh '''
                            pip3 install openai requests --quiet --break-system-packages
                            git fetch origin --prune --quiet
                            export ENABLE_OPENAI_CALLS="${ENABLE_OPENAI_CALLS}"
                            export READ_ONLY_MODE="${READ_ONLY_MODE}"
                            python3 pr_review.py ${CHANGE_ID} ${CHANGE_TARGET} ${CHANGE_BRANCH}
                            
                            echo "=========================================="
                            echo "Code review completed for PR #${CHANGE_ID}"
                            echo "Comment posted with:"
                            echo "  - Possible mistakes and improvements"
                            echo "  - Code quality suggestions"
                            echo "  - Best practices recommendations"
                            echo "=========================================="
                        '''
                    }
                }
            }
        }

        // ==========================================
        // RELEASE BRANCH: Manual trigger with build & auto-fix
        // ==========================================
        stage('Release - Manual Build & Fix') {
            when {
                allOf {
                    branch 'Release'
                    expression { return env.CHANGE_ID == null }
                    expression { return params.TRIGGER_RELEASE_BUILD == true }
                }
            }
            stages {
                stage('Release - Compile') {
                    steps {
                        script {
                            echo "Release Branch: Building production release..."
                            try {
                                sh '''
                                    mkdir -p build/classes
                                    javac -d build/classes src/App.java
                                    echo "✓ Compilation successful"
                                '''
                                env.COMPILATION_SUCCESS = 'true'
                                env.COMPILATION_ERROR = ''
                            } catch (Exception e) {
                                echo "✗ Compilation failed - Attempting GPT-5 auto-fix..."
                                env.COMPILATION_SUCCESS = 'false'
                                env.COMPILATION_ERROR = e.message
                            }
                        }
                    }
                }

                stage('Release - Auto-Fix (if needed)') {
                    when {
                        expression { env.COMPILATION_SUCCESS == 'false' }
                    }
                    steps {
                        script {
                            echo "Invoking Azure OpenAI GPT-5 for automatic error fixing..."
                            try {
                                withCredentials([
                                    string(credentialsId: 'AZURE_OPENAI_API_KEY', variable: 'AZURE_OPENAI_API_KEY'),
                                    string(credentialsId: 'AZURE_OPENAI_ENDPOINT', variable: 'AZURE_OPENAI_ENDPOINT'),
                                    usernamePassword(credentialsId: 'GITHUB_PAT',
                                                   usernameVariable: 'GITHUB_USERNAME',
                                                   passwordVariable: 'GITHUB_PAT')
                                ]) {
                                    sh '''
                                        pip3 install openai requests --quiet --break-system-packages
                                        export ENABLE_AUTO_FIX="${ENABLE_AUTO_FIX}"
                                        export ENABLE_OPENAI_CALLS="${ENABLE_OPENAI_CALLS}"
                                        export READ_ONLY_MODE="${READ_ONLY_MODE}"
                                        python3 build_fix.py src/App.java
                                    '''
                                }
                                env.AUTO_FIX_SUCCESS = 'true'
                            } catch (Exception e) {
                                echo "✗ Auto-fix failed with error: ${e.message}"
                                env.AUTO_FIX_SUCCESS = 'false'
                                env.AUTO_FIX_ERROR = e.message
                                error("Auto-fix execution failed")
                            }
                        }
                    }
                }

                stage('Release - Verify Fix') {
                    when {
                        expression { env.AUTO_FIX_SUCCESS == 'true' }
                    }
                    steps {
                        script {
                            try {
                                sh '''
                                    echo "Verifying auto-fix by recompiling..."
                                    javac -d build/classes src/App.java
                                    if [ $? -eq 0 ]; then
                                        echo "✓ Auto-fix successful - compilation now passes"
                                    else
                                        echo "✗ Auto-fix did not resolve all issues"
                                        exit 1
                                    fi
                                '''
                                env.FIX_VERIFICATION_SUCCESS = 'true'
                            } catch (Exception e) {
                                echo "✗ Verification failed: ${e.message}"
                                env.FIX_VERIFICATION_SUCCESS = 'false'
                                error("Fix verification failed")
                            }
                        }
                    }
                }

                stage('Release - Create JAR') {
                    when {
                        expression { env.FIX_VERIFICATION_SUCCESS == 'true' || env.COMPILATION_SUCCESS == 'true' }
                    }
                    steps {
                        script {
                            sh '''
                                cd build/classes
                                jar cfe ../App.jar App *.class
                                cd ../..
                                if [ -f build/App.jar ]; then 
                                    echo "✓ JAR created successfully"
                                fi
                            '''
                        }
                    }
                }

                stage('Release - Run Tests') {
                    when {
                        expression { env.FIX_VERIFICATION_SUCCESS == 'true' || env.COMPILATION_SUCCESS == 'true' }
                    }
                    steps {
                        script {
                            sh '''
                                echo "Running tests..."
                                java -cp build/classes App
                                if [ $? -eq 0 ]; then 
                                    echo "✓ Tests passed"
                                fi
                            '''
                        }
                    }
                }

                stage('Release - Archive Artifacts') {
                    when {
                        expression { env.FIX_VERIFICATION_SUCCESS == 'true' || env.COMPILATION_SUCCESS == 'true' }
                    }
                    steps {
                        script {
                            archiveArtifacts artifacts: 'build/App.jar,build/classes/**', allowEmptyArchive: false
                            echo "✓ Build artifacts archived"
                        }
                    }
                }

                stage('Release - Post Build Summary to PR') {
                    when {
                        expression { env.CHANGE_ID != null }
                    }
                    steps {
                        script {
                            withCredentials([
                                usernamePassword(credentialsId: 'GITHUB_PAT',
                                               usernameVariable: 'GITHUB_USERNAME',
                                               passwordVariable: 'GITHUB_PAT')
                            ]) {
                                sh '''
                                    pip3 install requests --quiet --break-system-packages
                                    python3 << 'EOF'
import os
import requests
import json
from datetime import datetime

# Build summary details
compilation_success = os.getenv('COMPILATION_SUCCESS', 'unknown')
auto_fix_success = os.getenv('AUTO_FIX_SUCCESS', 'unknown')
fix_verification = os.getenv('FIX_VERIFICATION_SUCCESS', 'unknown')

# Prepare comment
summary = f"""## 🔧 Release Build Summary

**Timestamp:** {datetime.now().isoformat()}

### Build Status
- **Initial Compilation:** {'✓ Success' if compilation_success == 'true' else '✗ Failed'}
- **Auto-Fix Applied:** {'✓ Yes' if auto_fix_success == 'true' else '✗ No' if auto_fix_success == 'false' else '⊘ N/A'}
- **Fix Verification:** {'✓ Passed' if fix_verification == 'true' else '✗ Failed' if fix_verification == 'false' else '⊘ N/A'}

### Artifacts Generated
- JAR file: `build/App.jar`
- Compiled classes: `build/classes/`

---
*Generated by Release Build Pipeline*
"""

# Post to GitHub PR
pr_number = os.getenv('CHANGE_ID')
if pr_number:
    repo = "vaibhavsaxena619/poc-auto-pr-fix"
    token = os.getenv('GITHUB_PAT')
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    data = {"body": summary}
    
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 201:
        print("✓ Build summary posted to PR")
    else:
        print(f"✗ Failed to post summary: {response.status_code}")
EOF
                                '''
                            }
                        }
                    }
                }
            }
        }

        // ==========================================
        // RELEASE BRANCH: Manual Trigger Required
        // ==========================================
        stage('Release - Manual Trigger Required') {
            when {
                allOf {
                    branch 'Release'
                    expression { return env.CHANGE_ID == null }
                    expression { return params.TRIGGER_RELEASE_BUILD != true }
                }
            }
            steps {
                script {
                    echo "ℹ Release branch detected"
                    echo "⊘ Automatic builds are disabled for Release branch"
                    echo "ℹ To trigger a production build:"
                    echo "   1. Go to Jenkins job: poc-java-pr-workflow"
                    echo "   2. Click 'Build with Parameters'"
                    echo "   3. Set TRIGGER_RELEASE_BUILD to TRUE"
                    echo "   4. Click 'Build'"
                }
            }
        }

        // ==========================================
        // OTHER BRANCHES: Skipped
        // ==========================================
        stage('Other Branches - Skipped') {
            when {
                allOf {
                    not {
                        anyOf {
                            branch 'Dev_Poc_V1'
                            branch 'Release'
                        }
                    }
                    expression { return env.CHANGE_ID == null }
                }
            }
            steps {
                script {
                    echo "⊘ Branch '${BRANCH_NAME}': No action (only Dev_Poc_V1 and Release branches are processed)"
                }
            }
        }
    }

    post {
        always {
            script {
                echo "=========================================="
                echo "Pipeline completed for: ${BRANCH_NAME}"
                echo "=========================================="
            }
        }
        success {
            script {
                if (env.CHANGE_ID) {
                    echo "✓ SUCCESS: PR #${env.CHANGE_ID} - Code review posted"
                } else if (env.BRANCH_NAME == 'Release') {
                    echo "✓ SUCCESS: Release build completed"
                } else if (env.BRANCH_NAME == 'Dev_Poc_V1') {
                    echo "ℹ Dev_Poc_V1: No build triggered (as expected)"
                }
            }
        }
        failure {
            script {
                if (env.CHANGE_ID) {
                    echo "✗ FAILED: PR #${env.CHANGE_ID} - Review process failed"
                } else if (env.BRANCH_NAME == 'Release') {
                    echo "✗ FAILED: Release build failed (even after auto-fix attempt)"
                }
            }
        }
    }
}
