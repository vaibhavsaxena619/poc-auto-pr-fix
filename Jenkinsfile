pipeline {
    agent any

    environment {
        JAVA_HOME = tool 'JDK21'
        PATH = "${env.JAVA_HOME}\\bin;${env.PATH}"
    }

    options {
        //timestamps()
        disableConcurrentBuilds()
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Compile (Initial)') {
            steps {
                bat '''
                javac src\\*.java 2> compile_errors.txt
                exit 0
                '''
            }
        }

        stage('Auto Fix via LLM') {
            steps {
                bat '''
                python llm_fix.py compile_errors.txt
                '''
            }
        }

        stage('Recompile After Fix') {
            steps {
                bat '''
                javac src\\*.java
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
            echo '✅ Pipeline completed successfully'
        }
        failure {
            echo '❌ Pipeline failed – manual action required'
        }
    }
}
