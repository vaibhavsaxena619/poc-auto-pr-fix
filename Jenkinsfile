pipeline {
    agent any

    environment {
        JAVA_HOME = tool 'JDK21'        // Adjust to your Java installation name in Jenkins
        PATH = "${env.JAVA_HOME}\\bin;${env.PATH}"
        LLM_ENDPOINT = "http://localhost:11434/api/generate"
    }

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
                    // Run javac and capture errors to file
                    bat '''
                    setlocal enabledelayedexpansion
                    javac src\\*.java 2> compile_errors.txt
                    if errorlevel 1 (
                        echo Compilation failed
                        exit 0
                    )
                    '''
                }
            }
        }

        stage('Auto Fix via LLM') {
            steps {
                // Call Python script to fix errors
                bat 'python llm_fix.py compile_errors.txt'
            }
        }

        stage('Recompile After Fix') {
            steps {
                bat '''
                javac src\\*.java
                if errorlevel 1 (
                    echo Compilation still has errors
                    exit 1
                )
                '''
            }
        }

        stage('Commit & Push Fixes') {
            steps {
                bat '''
                git status
                git add .
                git diff-index --quiet HEAD || (
                    git commit -m "ci: auto-fix compilation errors"
                    git push origin HEAD
                )
                '''
            }
        }
    }

    post {
        success {
            echo 'Pipeline completed successfully!'
        }
        failure {
            echo 'Pipeline failed – manual action required.'
        }
        unstable {
            echo 'Auto-fix applied, check changes.'
        }
    }
}
