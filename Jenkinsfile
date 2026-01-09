pipeline {
    agent any

    tools {
        jdk 'JDK21'        // change if your Jenkins JDK name differs
        python 'Python3'   // change if your Python tool name differs
    }

    environment {
        GIT_CREDENTIALS = 'github-pat'
        REPO_URL = 'https://github.com/vaibhavsaxena619/poc-auto-pr-fix.git'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: '*/main']],
                    userRemoteConfigs: [[
                        url: env.REPO_URL,
                        credentialsId: env.GIT_CREDENTIALS
                    ]]
                ])
            }
        }

        stage('Configure Git') {
            steps {
                bat '''
                git config user.name "vaibhavsaxena619"
                git config user.email "vaibhav.saxena619@gmail.com"
                '''
            }
        }

        stage('Compile (Capture Errors Only)') {
            steps {
                bat '''
                echo Compiling Java files (errors will be captured)...
                javac src\\*.java 2> compile_errors.txt
                exit 0
                '''
            }
        }

        stage('Auto Fix via LLM') {
            steps {
                bat '''
                echo Sending errors to LLM for fixing...
                python llm_fix.py compile_errors.txt
                exit 0
                '''
            }
        }

        stage('Commit & Push Fixes') {
            steps {
                bat '''
                git add src
                git commit -m "Auto-fix via LLM (no validation)" || echo "Nothing to commit"
                git push origin HEAD:main
                '''
            }
        }
    }

    post {
        always {
            echo '✅ LLM fix applied and pushed. No rebuild performed.'
        }
    }
}
