pipeline {
    agent any
    
    environment {
        BRANCH_NAME = "${env.GIT_BRANCH?.replace('origin/', '') ?: 'unknown'}"
        IS_PR = "${env.CHANGE_ID != null}"
        PR_NUMBER = "${env.CHANGE_ID ?: 'none'}"
        PR_SOURCE_BRANCH = "${env.CHANGE_BRANCH ?: 'unknown'}"
        PR_TARGET_BRANCH = "${env.CHANGE_TARGET ?: 'unknown'}"
        BUILD_TRIGGER = "${env.BUILD_CAUSE ?: 'unknown'}"
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
                script {
                    echo "Building branch: ${BRANCH_NAME}"
                    echo "Is PR: ${IS_PR}"
                    echo "PR Number: ${PR_NUMBER}"
                    echo "Build Trigger: ${BUILD_TRIGGER}"
                }
            }
        }

        // PR WORKFLOW: Code Review
        stage('Pull Request Review') {
            when {
                changeRequest()
            }
            steps {
                echo "=== PR DETECTED ==="
                echo "PR Number: ${env.CHANGE_ID}"
                echo "PR Title: ${env.CHANGE_TITLE}"
                echo "PR Author: ${env.CHANGE_AUTHOR}"
                echo "Source Branch: ${env.CHANGE_BRANCH}"
                echo "Target Branch: ${env.CHANGE_TARGET}"
                echo "PR URL: ${env.CHANGE_URL}"
                
                script {
                    echo "Starting Gemini code review for PR #${env.CHANGE_ID}"
                    echo "Analyzing changes: ${env.CHANGE_BRANCH} -> ${env.CHANGE_TARGET}"
                    
                    try {
                        withCredentials([
                            string(credentialsId: 'GEMINI_API_KEY', variable: 'GEMINI_API_KEY'),
                            usernamePassword(credentialsId: 'github-pat', 
                                           usernameVariable: 'GITHUB_USERNAME', 
                                           passwordVariable: 'GITHUB_PAT')
                        ]) {
                            // Install dependencies
                            bat '''
                                echo Installing Python dependencies for PR review...
                                pip install google-genai requests pathlib
                            '''
                            
                            // Fetch all branches to ensure we have the diff
                            bat '''
                                echo Fetching latest changes from repository...
                                git fetch origin --prune
                                git fetch origin +refs/heads/*:refs/remotes/origin/*
                            '''
                            
                            // Run Gemini code review
                            def reviewResult = bat(script: '''
                                echo Running Gemini code review analysis...
                                echo PR Details: #%CHANGE_ID% (%CHANGE_BRANCH% -> %CHANGE_TARGET%)
                                python pr_review.py %CHANGE_ID% %CHANGE_TARGET% %CHANGE_BRANCH% code_review
                            ''', returnStatus: true)
                            
                            if (reviewResult == 0) {
                                echo "✅ Gemini code review completed and posted to PR #${env.CHANGE_ID}"
                                echo "Review comment has been added with @${env.CHANGE_AUTHOR} tag"
                            } else {
                                echo "⚠️ Code review had issues but continuing build..."
                                // Try to post an error comment
                                bat '''
                                    echo Code review encountered technical issues. Manual review recommended.
                                    python pr_review.py %CHANGE_ID% %CHANGE_TARGET% %CHANGE_BRANCH% error_fallback
                                '''
                            }
                        }
                    } catch (Exception e) {
                        echo "❌ PR review failed: ${e.message}"
                        echo "Attempting merge conflict analysis..."
                        
                        // Fallback: try merge conflict analysis
                        try {
                            withCredentials([
                                string(credentialsId: 'GEMINI_API_KEY', variable: 'GEMINI_API_KEY'),
                                usernamePassword(credentialsId: 'github-pat', 
                                               usernameVariable: 'GITHUB_USERNAME', 
                                               passwordVariable: 'GITHUB_PAT')
                            ]) {
                                bat '''
                                    echo Running merge conflict analysis...
                                    python pr_review.py %CHANGE_ID% %CHANGE_TARGET% %CHANGE_BRANCH% merge_conflict
                                '''
                            }
                            echo "Merge conflict analysis posted to PR"
                        } catch (Exception e2) {
                            echo "All review attempts failed: ${e2.message}"
                            // Post a simple manual review request
                            echo "Posting manual review request to PR..."
                        }
                    }
                }
            }
        }

        // MAIN BRANCH WORKFLOW: Compile -> Fix -> Push back
        stage('Main Branch - Compile & Auto-Fix') {
            when {
                anyOf {
                    branch 'main'
                    environment name: 'BRANCH_NAME', value: 'main'
                }
            }
            stages {
                stage('Initial Compilation') {
                    steps {
                        script {
                            bat '''
                                if not exist build mkdir build
                                del /Q build\\compile_errors.txt 2>NUL

                                echo [MAIN BRANCH] Compiling Java code...
                                javac src\\App.java 2> build\\compile_errors.txt
                                exit /B 0
                            '''
                        }
                    }
                }

                stage('Auto-Fix via Gemini') {
                    when {
                        expression {
                            return fileExists('build\\compile_errors.txt') &&
                                   readFile('build\\compile_errors.txt').trim().length() > 0
                        }
                    }
                    steps {
                        echo "🔧 [MAIN BRANCH] Compilation failed. Sending errors to Gemini for auto-fix..."
                        script {
                            try {
                                withCredentials([
                                    string(credentialsId: 'GEMINI_API_KEY', variable: 'GEMINI_API_KEY'),
                                    usernamePassword(credentialsId: 'github-pat', 
                                                   usernameVariable: 'GITHUB_USERNAME', 
                                                   passwordVariable: 'GITHUB_PAT')
                                ]) {
                                    // Run the auto-fix with better error handling
                                    def result = bat(script: '''
                                        echo Installing dependencies...
                                        pip install google-genai
                                        
                                        echo Running Gemini auto-fix...
                                        python llm_fix.py build\\compile_errors.txt
                                        echo Auto-fix process completed.
                                    ''', returnStatus: true)
                                    
                                    if (result == 0) {
                                        echo "SUCCESS: Gemini auto-fix completed successfully"
                                    } else {
                                        echo "WARNING: Auto-fix process had issues but may have still applied fixes"
                                        echo "Continuing to verify if code compiles..."
                                    }
                                }
                            } catch (Exception e) {
                                echo "ERROR: Failed to execute auto-fix: ${e.message}"
                                echo "Please check your Jenkins credentials and Gemini API key"
                                // Don't fail the build here - let verification stage determine success
                                echo "Continuing to verification stage to check if manual fixes are needed..."
                            }
                        }
                    }
                }

                stage('Verify Fixed Code') {
                    steps {
                        script {
                            echo "✅ [MAIN BRANCH] Verifying the auto-fixed code compiles correctly..."
                            bat '''
                                javac src\\App.java
                                if %ERRORLEVEL% EQU 0 (
                                    echo ✅ Code compilation successful after auto-fix!
                                ) else (
                                    echo ❌ Code still has compilation errors after auto-fix
                                    exit /B 1
                                )
                            '''
                        }
                    }
                }
            }
        }

        // MASTER BRANCH WORKFLOW: Nightly Production Build
        stage('Master Branch - Nightly Build') {
            when {
                allOf {
                    anyOf {
                        branch 'master'
                        environment name: 'BRANCH_NAME', value: 'master'
                    }
                    expression { return env.IS_PR != 'true' }
                }
            }
            stages {
                stage('Pre-Build Setup') {
                    steps {
                        script {
                            echo "Starting nightly build for master branch..."
                            // Create build log directory
                            bat '''
                                if not exist build mkdir build
                                if not exist build\\logs mkdir build\\logs
                                echo Nightly build started at %date% %time% > build\\logs\\nightly_build.log
                            '''
                        }
                    }
                }
                
                stage('Production Compilation') {
                    steps {
                        script {
                            echo "Running production build..."
                            def compileResult = bat(script: '''
                                echo Compiling for production... >> build\\logs\\nightly_build.log
                                if not exist build\\classes mkdir build\\classes
                                
                                javac -d build\\classes src\\App.java 2>> build\\logs\\nightly_build.log
                                if %ERRORLEVEL% NEQ 0 (
                                    echo Compilation failed at %date% %time% >> build\\logs\\nightly_build.log
                                    exit /B 1
                                ) else (
                                    echo Compilation successful at %date% %time% >> build\\logs\\nightly_build.log
                                )
                            ''', returnStatus: true)
                            
                            if (compileResult != 0) {
                                echo "Production build compilation failed - triggering fix process"
                                error("Production compilation failed")
                            }
                        }
                    }
                    post {
                        failure {
                            script {
                                echo "Compilation failed - analyzing with Gemini..."
                                try {
                                    withCredentials([
                                        string(credentialsId: 'GEMINI_API_KEY', variable: 'GEMINI_API_KEY'),
                                        usernamePassword(credentialsId: 'github-pat', 
                                                       usernameVariable: 'GITHUB_USERNAME', 
                                                       passwordVariable: 'GITHUB_PAT')
                                    ]) {
                                        bat '''
                                            echo Running nightly build fix analysis...
                                            python nightly_fix.py build\\logs\\nightly_build.log "Compilation failure during nightly build"
                                        '''
                                    }
                                } catch (Exception e) {
                                    echo "Failed to run build fix analysis: ${e.message}"
                                }
                            }
                        }
                    }
                }
                
                stage('Create Production JAR') {
                    steps {
                        script {
                            bat '''
                                echo Creating JAR file... >> build\\logs\\nightly_build.log
                                cd build\\classes
                                jar cfe ..\\App.jar App *.class
                                cd ..\\..
                                
                                if exist build\\App.jar (
                                    echo JAR creation successful at %date% %time% >> build\\logs\\nightly_build.log
                                ) else (
                                    echo JAR creation failed at %date% %time% >> build\\logs\\nightly_build.log
                                    exit /B 1
                                )
                            '''
                        }
                    }
                }
                
                stage('Production Tests') {
                    steps {
                        script {
                            echo "Running production tests..."
                            def testResult = bat(script: '''
                                echo Running production tests... >> build\\logs\\nightly_build.log
                                java -cp build\\classes App >> build\\logs\\nightly_build.log 2>&1
                                if %ERRORLEVEL% NEQ 0 (
                                    echo Tests failed at %date% %time% >> build\\logs\\nightly_build.log
                                    exit /B 1
                                ) else (
                                    echo Tests passed at %date% %time% >> build\\logs\\nightly_build.log
                                )
                            ''', returnStatus: true)
                            
                            if (testResult != 0) {
                                echo "Production tests failed - triggering fix process"
                                error("Production tests failed")
                            }
                        }
                    }
                    post {
                        failure {
                            script {
                                echo "Tests failed - analyzing with Gemini..."
                                try {
                                    withCredentials([
                                        string(credentialsId: 'GEMINI_API_KEY', variable: 'GEMINI_API_KEY'),
                                        usernamePassword(credentialsId: 'github-pat', 
                                                       usernameVariable: 'GITHUB_USERNAME', 
                                                       passwordVariable: 'GITHUB_PAT')
                                    ]) {
                                        bat '''
                                            echo Running test failure analysis...
                                            python nightly_fix.py build\\logs\\nightly_build.log "Test execution failure during nightly build"
                                        '''
                                    }
                                } catch (Exception e) {
                                    echo "Failed to run test fix analysis: ${e.message}"
                                }
                            }
                        }
                    }
                }
                
                stage('Archive & Deploy') {
                    steps {
                        script {
                            echo "Archiving production artifacts..."
                            archiveArtifacts artifacts: 'build/App.jar,build/logs/nightly_build.log', allowEmptyArchive: false
                            
                            bat '''
                                echo Build completed successfully at %date% %time% >> build\\logs\\nightly_build.log
                                echo Artifacts archived >> build\\logs\\nightly_build.log
                            '''
                        }
                    }
                }
            }
        }

        // FEATURE BRANCHES: Basic compilation check
        stage('Feature Branch - Basic Check') {
            when {
                not {
                    anyOf {
                        branch 'main'
                        branch 'master'
                        environment name: 'BRANCH_NAME', value: 'main'
                        environment name: 'BRANCH_NAME', value: 'master'
                    }
                }
            }
            steps {
                script {
                    echo "🔍 [FEATURE BRANCH] Running basic compilation check..."
                    bat '''
                        echo Feature branch detected: %BRANCH_NAME%
                        javac src\\App.java
                        echo ✅ Feature branch compilation successful!
                    '''
                }
            }
        }
    }

    post {
        always {
            script {
                echo "COMPLETED: Pipeline finished for branch: ${BRANCH_NAME}"
                if (env.CHANGE_ID) {
                    echo "PR #${env.CHANGE_ID} processing completed"
                }
            }
        }
        success {
            script {
                if (env.CHANGE_ID) {
                    echo "SUCCESS: [PR #${env.CHANGE_ID}] Code review completed - ready for merge"
                } else if (env.BRANCH_NAME == 'main') {
                    echo "SUCCESS: [MAIN BRANCH] Build succeeded - Code auto-fixed and ready for merge"
                } else if (env.BRANCH_NAME == 'master') {
                    echo "SUCCESS: [MASTER BRANCH] Nightly build succeeded - Production ready"
                } else {
                    echo "SUCCESS: [FEATURE BRANCH] Basic compilation check passed"
                }
            }
        }
        failure {
            script {
                if (env.CHANGE_ID) {
                    echo "FAILED: [PR #${env.CHANGE_ID}] Review process encountered issues"
                    echo "TIP: Check PR comments for Gemini analysis and recommendations"
                } else if (env.BRANCH_NAME == 'main') {
                    echo "FAILED: [MAIN BRANCH] Build failed"
                    echo "TIP: Check if auto-fix was applied before manual intervention"
                    // Check if the Java file compiles now even though build failed
                    def compileCheck = bat(script: 'javac src\\App.java', returnStatus: true)
                    if (compileCheck == 0) {
                        echo "NOTE: Java code actually compiles successfully now!"
                        echo "The failure might have been due to git push issues, not compilation"
                    } else {
                        echo "CONFIRM: Compilation still failing - manual review needed"
                    }
                } else if (env.BRANCH_NAME == 'master') {
                    echo "FAILED: [MASTER BRANCH] Nightly build failed"
                    echo "TIP: Check PR comments for automated fix analysis"
                    echo "NEXT: Build will be re-triggered after applying fixes"
                } else {
                    echo "FAILED: [FEATURE BRANCH] Compilation check failed"
                    echo "TIP: Please fix compilation errors before creating pull request"
                }
            }
        }
    }
}
