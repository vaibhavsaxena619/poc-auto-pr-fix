pipeline {
    agent any

    environment {
        VENV_DIR = 'venv'
    }

    stages {

        stage('Checkout') {
            steps {
                git url: 'https://github.com/vaibhavsaxena619/poc-auto-pr-fix.git', branch: 'main'
            }
        }

        stage('Python Version') {
            steps {
                bat 'python --version'
            }
        }

        stage('Setup Virtual Environment') {
            steps {
                bat """
                    python -m venv %VENV_DIR%
                    %VENV_DIR%\\Scripts\\pip.exe install --upgrade pip
                    if exist requirements.txt (
                        %VENV_DIR%\\Scripts\\pip.exe install -r requirements.txt
                    )
                """
            }
        }

        stage('Run Python Script') {
            steps {
                bat """
                    %VENV_DIR%\\Scripts\\python.exe my_script.py
                """
            }
        }

    }

    post {
        always {
            echo 'Cleaning up virtual environment...'
            bat "rmdir /S /Q %VENV_DIR%"
        }

        success {
            echo 'Python script ran successfully!'
        }

        failure {
            echo 'Python script failed. Check logs for errors.'
        }
    }
}
