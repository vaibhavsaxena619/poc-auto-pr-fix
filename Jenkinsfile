pipeline {
    agent any

    environment {
        // Optional: Python virtual environment folder
        VENV_DIR = 'venv'
    }

    stages {

        stage('Checkout') {
            steps {
                // Checkout your repo
                git url: 'https://github.com/vaibhavsaxena619/poc-auto-pr-fix.git', branch: 'main'
            }
        }

        stage('Python Version') {
            steps {
                // Check Python version
                sh 'python3 --version'
            }
        }

        stage('Setup Virtual Environment') {
            steps {
                // Create and activate venv, install requirements
                sh """
                    python3 -m venv ${VENV_DIR}
                    source ${VENV_DIR}/bin/activate
                    pip install --upgrade pip
                    if [ -f requirements.txt ]; then
                        pip install -r requirements.txt
                    fi
                """
            }
        }

        stage('Run Python Script') {
            steps {
                // Run your main Python script inside venv
                sh """
                    source ${VENV_DIR}/bin/activate
                    python my_script.py
                """
            }
        }

    }

    post {
        always {
            echo 'Cleaning up virtual environment...'
            sh "rm -rf ${VENV_DIR}"
        }

        success {
            echo 'Python script ran successfully!'
        }

        failure {
            echo 'Python script failed. Check logs for errors.'
        }
    }
}
