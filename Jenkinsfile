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
                expression { return env.IS_PR == 'true' }
            }
            steps {
                echo "Conducting Gemini code review for PR #${PR_NUMBER}: ${PR_SOURCE_BRANCH} -> ${PR_TARGET_BRANCH}"
                script {
                    try {
                        withCredentials([
                            string(credentialsId: 'GEMINI_API_KEY', variable: 'GEMINI_API_KEY'),
                            usernamePassword(credentialsId: 'github-pat', 
                                           usernameVariable: 'GITHUB_USERNAME', 
                                           passwordVariable: 'GITHUB_PAT')
                        ]) {
                            bat '''
                                echo Installing dependencies for PR review...
                                pip install google-genai requests
                                
                                echo Fetching PR changes...
                                git fetch origin
                                
                                echo Running Gemini code review...
                                python pr_review.py %PR_NUMBER% %PR_TARGET_BRANCH% %PR_SOURCE_BRANCH% code_review
                            '''
                        }
                    } catch (Exception e) {
                        echo "PR review failed: ${e.message}"
                        // Don't fail the build - let merge attempt proceed
                        script {
                            withCredentials([
                                string(credentialsId: 'GEMINI_API_KEY', variable: 'GEMINI_API_KEY'),
                                usernamePassword(credentialsId: 'github-pat', 
                                               usernameVariable: 'GITHUB_USERNAME', 
                                               passwordVariable: 'GITHUB_PAT')
                            ]) {
                                bat '''
                                    echo Analyzing merge conflict...
                                    python pr_review.py %PR_NUMBER% %PR_TARGET_BRANCH% %PR_SOURCE_BRANCH% merge_conflict
                                '''
                            }
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
                if (env.IS_PR == 'true') {
                    echo "PR #${PR_NUMBER} processing completed"
                }
            }
        }
        success {
            script {
                if (env.IS_PR == 'true') {
                    echo "SUCCESS: [PR #${PR_NUMBER}] Code review completed - ready for merge"
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
                if (env.IS_PR == 'true') {
                    echo "FAILED: [PR #${PR_NUMBER}] Review process encountered issues"
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
