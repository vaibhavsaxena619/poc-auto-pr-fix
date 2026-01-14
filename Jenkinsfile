pipeline {
    agent any
    
    tools {
        git 'Default'
    }
    
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

        // PR TO MASTER: Compile + Auto-fix + Code Review
        stage('PR to Master Build & Review') {
            when {
                allOf {
                    changeRequest()
                    expression { env.CHANGE_TARGET == 'master' }
                }
            }
            stages {
                stage('Compile & Auto-Fix') {
                    steps {
                        script {
                            echo "PR #${env.CHANGE_ID} to master by ${env.CHANGE_AUTHOR}"
                            try {
                                sh '''
                                    mkdir -p build/classes
                                    javac -d build/classes src/App.java
                                    echo "✓ Compilation successful"
                                '''
                                env.COMPILATION_SUCCESS = 'true'
                            } catch (Exception e) {
                                echo "✗ Compilation failed - Attempting GPT-5 auto-fix..."
                                env.COMPILATION_SUCCESS = 'false'
                                
                                withCredentials([
                                    string(credentialsId: 'AZURE_OPENAI_API_KEY_CREDENTIAL', variable: 'AZURE_OPENAI_API_KEY'),
                                    string(credentialsId: 'AZURE_OPENAI_ENDPOINT_CREDENTIAL', variable: 'AZURE_OPENAI_ENDPOINT'),
                                    usernamePassword(credentialsId: 'GITHUB_PAT_CREDENTIAL',
                                                   usernameVariable: 'GITHUB_USERNAME',
                                                   passwordVariable: 'GITHUB_PAT')
                                ]) {
                                    sh '''
                                        echo "Sending compilation error to GPT-5 for analysis..."
                                        pip install openai requests --quiet
                                        python build_fix.py src/App.java
                                    '''
                                }
                                
                                // Retry compilation after fix
                                sh '''
                                    javac -d build/classes src/App.java
                                    if [ $? -eq 0 ]; then
                                        echo "✓ GPT-5 auto-fix successful - compilation now passes"
                                        exit 0
                                    else
                                        echo "✗ Auto-fix failed - compilation still failing"
                                        exit 1
                                    fi
                                '''
                            }
                        }
                    }
                }

                stage('Code Review & Approval') {
                    steps {
                        script {
                            withCredentials([
                                string(credentialsId: 'AZURE_OPENAI_API_KEY_CREDENTIAL', variable: 'AZURE_OPENAI_API_KEY'),
                                string(credentialsId: 'AZURE_OPENAI_ENDPOINT_CREDENTIAL', variable: 'AZURE_OPENAI_ENDPOINT'),
                                usernamePassword(credentialsId: 'GITHUB_PAT_CREDENTIAL',
                                               usernameVariable: 'GITHUB_USERNAME',
                                               passwordVariable: 'GITHUB_PAT')
                            ]) {
                                sh '''
                                    pip install openai requests --quiet
                                    git fetch origin --prune --quiet
                                    python pr_review.py ${CHANGE_ID} master ${CHANGE_BRANCH}
                                '''
                            }
                            echo "Code review completed for PR #${env.CHANGE_ID}"
                        }
                    }
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
                            sh '''
                                mkdir -p build/classes
                                javac -d build/classes src/App.java
                                if [ $? -ne 0 ]; then exit 1; fi
                                echo "Compilation successful"
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
                                        sh '''
                                            echo "Sending error to Azure OpenAI for analysis..."
                                            pip install openai --quiet
                                            python build_fix.py src/App.java
                                        '''
                                    }
                                    echo "Retrying compilation after fixes..."
                                    sh '''
                                        javac -d build/classes src/App.java
                                        if [ $? -eq 0 ]; then
                                            echo "Recovery successful - compilation passed"
                                            exit 0
                                        else
                                            echo "Recovery failed - compilation still failing"
                                            exit 1
                                        fi
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
                            sh '''
                                cd build/classes
                                jar cfe ../App.jar App *.class
                                cd ../..
                                if [ -f build/App.jar ]; then echo "JAR created successfully"; fi
                            '''
                        }
                    }
                }

                stage('Test') {
                    steps {
                        script {
                            sh '''
                                echo "Running tests..."
                                java -cp build/classes App
                                if [ $? -ne 0 ]; then exit 1; fi
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

        // FEATURE BRANCHES: SKIPPED - Nothing happens
        stage('Other Branches') {
            when {
                not {
                    anyOf {
                        branch 'master'
                    }
                }
            }
            steps {
                script {
                    echo "⊘ Branch ${BRANCH_NAME}: No build triggered (only master builds are processed)"
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
                    echo "✓ SUCCESS: PR #${env.CHANGE_ID} - Build complete, code review posted"
                } else if (env.BRANCH_NAME == 'master') {
                    echo "✓ SUCCESS: Master branch production build complete"
                }
            }
        }
        failure {
            script {
                if (env.CHANGE_ID) {
                    echo "✗ FAILED: PR #${env.CHANGE_ID} - Build or review failed"
                } else if (env.BRANCH_NAME == 'master') {
                    echo "✗ FAILED: Master branch build failed after recovery attempt"
                }
            }
        }
    }
}
