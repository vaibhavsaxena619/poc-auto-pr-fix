pipeline {
    agent any
    
    environment {
        BRANCH_NAME = "${env.GIT_BRANCH?.replace('origin/', '') ?: 'unknown'}"
        AZURE_OPENAI_API_VERSION = "2024-12-01-preview"
        AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-5"
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

        // PR WORKFLOW: Gemini Code Review (Master PRs only)
        stage('Code Review') {
            when {
                allOf {
                    changeRequest()
                    expression { env.CHANGE_TARGET == 'master' }
                }
            }
            steps {
                echo "PR #${env.CHANGE_ID} to master by ${env.CHANGE_AUTHOR}"
                script {
                    try {
                        withCredentials([
                            string(credentialsId: 'AZURE_OPENAI_API_KEY_CREDENTIAL', variable: 'AZURE_OPENAI_API_KEY'),
                            string(credentialsId: 'AZURE_OPENAI_ENDPOINT_CREDENTIAL', variable: 'AZURE_OPENAI_ENDPOINT'),
                            usernamePassword(credentialsId: 'GITHUB_PAT_CREDENTIAL', 
                                           usernameVariable: 'GITHUB_USERNAME', 
                                           passwordVariable: 'GITHUB_PAT')
                        ]) {
                            bat '''
                                pip install openai requests --quiet
                                git fetch origin --prune --quiet
                                python pr_review.py %CHANGE_ID% master %CHANGE_BRANCH%
                            '''
                        }
                        echo "Code review posted to PR #${env.CHANGE_ID}"
                    } catch (Exception e) {
                        echo "Code review failed: ${e.message}"
                        currentBuild.result = 'FAILURE'
                    }
                }
            }
        }

        // MAIN BRANCH WORKFLOW: Compile only (no auto-fix, no push)
        stage('Main Branch Build') {
            when {
                anyOf {
                    branch 'main'
                    environment name: 'BRANCH_NAME', value: 'main'
                }
            }
            steps {
                script {
                    echo "Main branch: Compiling Java code..."
                    bat '''
                        if not exist build mkdir build
                        javac src/App.java
                        if %ERRORLEVEL% NEQ 0 (
                            echo Compilation failed on main branch
                            exit /B 1
                        )
                        echo Compilation successful
                    '''
                }
            }
        }

        // MASTER BRANCH WORKFLOW: Production build with error recovery
        stage('Master Branch Build') {
            when {
                allOf {
                    anyOf {
                        branch 'master'
                        environment name: 'BRANCH_NAME', value: 'master'
                    }
                    expression { return env.CHANGE_ID == null }
                }
            }
            stages {
                stage('Compile') {
                    steps {
                        script {
                            echo "Master: Production compilation..."
                            bat '''
                                if not exist build mkdir build
                                if not exist build/classes mkdir build/classes
                                javac -d build/classes src/App.java
                                if %ERRORLEVEL% NEQ 0 exit /B 1
                                echo Compilation successful
                            '''
                        }
                    }
                    post {
                        failure {
                            script {
                                echo "Compilation failed - attempting recovery via Azure OpenAI..."
                                try {
                                    withCredentials([
                                        string(credentialsId: 'AZURE_OPENAI_API_KEY_CREDENTIAL', variable: 'AZURE_OPENAI_API_KEY'),
                                        string(credentialsId: 'AZURE_OPENAI_ENDPOINT_CREDENTIAL', variable: 'AZURE_OPENAI_ENDPOINT'),
                                        usernamePassword(credentialsId: 'GITHUB_PAT_CREDENTIAL',
                                                       usernameVariable: 'GITHUB_USERNAME',
                                                       passwordVariable: 'GITHUB_PAT')
                                    ]) {
                                        bat '''
                                            echo Sending error to Azure OpenAI for analysis...
                                            pip install openai --quiet
                                            python build_fix.py src/App.java
                                        '''
                                    }
                                    echo "Retrying compilation after fixes..."
                                    bat '''
                                        javac -d build/classes src/App.java
                                        if %ERRORLEVEL% EQU 0 (
                                            echo Recovery successful - compilation passed
                                            exit /B 0
                                        ) else (
                                            echo Recovery failed - compilation still failing
                                            exit /B 1
                                        )
                                    '''
                                } catch (Exception e) {
                                    echo "Recovery failed: ${e.message}"
                                    currentBuild.result = 'FAILURE'
                                    error("Build recovery failed")
                                }
                            }
                        }
                    }
                }

                stage('Create JAR') {
                    steps {
                        script {
                            bat '''
                                cd build/classes
                                jar cfe ../App.jar App *.class
                                cd ../..
                                if exist build/App.jar echo JAR created successfully
                            '''
                        }
                    }
                }

                stage('Test') {
                    steps {
                        script {
                            bat '''
                                echo Running tests...
                                java -cp build/classes App
                                if %ERRORLEVEL% NEQ 0 exit /B 1
                            '''
                        }
                    }
                }

                stage('Archive') {
                    steps {
                        script {
                            archiveArtifacts artifacts: 'build/App.jar,build/classes/**', allowEmptyArchive: false
                            echo "Build artifacts archived"
                        }
                    }
                }
            }
        }

        // FEATURE BRANCHES: Basic compilation check
        stage('Feature Branch Build') {
            when {
                not {
                    anyOf {
                        branch 'main'
                        branch 'master'
                    }
                }
            }
            steps {
                script {
                    echo "Feature branch: Running compilation check..."
                    bat '''
                        javac src/App.java
                        if %ERRORLEVEL% NEQ 0 exit /B 1
                        echo Compilation successful
                    '''
                }
            }
        }
    }

    post {
        always {
            script {
                echo "Pipeline completed for: ${BRANCH_NAME}"
            }
        }
        success {
            script {
                if (env.CHANGE_ID) {
                    echo "SUCCESS: PR #${env.CHANGE_ID} code review completed"
                } else if (env.BRANCH_NAME == 'main') {
                    echo "SUCCESS: Main branch compiled successfully"
                } else if (env.BRANCH_NAME == 'master') {
                    echo "SUCCESS: Master branch production build complete"
                } else {
                    echo "SUCCESS: Feature branch compilation check passed"
                }
            }
        }
        failure {
            script {
                if (env.CHANGE_ID) {
                    echo "FAILED: PR #${env.CHANGE_ID} review failed"
                } else if (env.BRANCH_NAME == 'main') {
                    echo "FAILED: Main branch compilation failed"
                } else if (env.BRANCH_NAME == 'master') {
                    echo "FAILED: Master branch build failed after recovery attempt"
                } else {
                    echo "FAILED: Feature branch compilation failed"
                }
            }
        }
    }
}
