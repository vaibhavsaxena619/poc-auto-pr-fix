pipeline {
    agent any

    options {
        disableConcurrentBuilds()
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Compile') {
            steps {
                script {
                    try {
                        bat 'javac src\\*.java'
                    } catch (e) {
                        echo 'Compilation failed'
                        currentBuild.result = 'UNSTABLE'
                    }
                }
            }
        }

        stage('Capture Errors') {
            when {
                expression { currentBuild.result == 'UNSTABLE' }
            }
            steps {
                bat 'javac src\\*.java 2> compile_errors.txt'
            }
        }

        stage('Auto Fix via LLM') {
            when {
                expression { currentBuild.result == 'UNSTABLE' }
            }
            steps {
                bat 'python llm_fix.py compile_errors.txt'
            }
        }

        stage('Recompile After Fix') {
            when {
                expression { currentBuild.result == 'UNSTABLE' }
            }
            steps {
                bat 'javac *.java'
            }
        }

        stage('Commit & Push Fixes') {
            when {
                expression { currentBuild.result == 'UNSTABLE' }
            }
            steps {
                bat '''
                git add .
                git commit -m "ci: auto-fix compilation errors"
                git push origin HEAD
                '''
            }
        }
    }

    post {
        success {
            echo 'Pipeline completed successfully'
        }
        failure {
            echo 'Pipeline failed – manual action required'
        }
        unstable {
            echo 'Auto-fix applied'
        }
    }
}
