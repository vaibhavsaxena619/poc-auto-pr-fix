pipeline {
    agent any

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Compile (Initial)') {
            steps {
                script {
                    bat '''
                        if not exist build mkdir build
                        del /Q build\\compile_errors.txt 2>NUL

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
                echo "Compilation failed. Sending errors to Gemini..."
                script {
                    try {
                        withCredentials([string(credentialsId: 'Gemini_API_key', variable: 'GEMINI_API_KEY')]) {
                            bat '''
                                python llm_fix.py build\\compile_errors.txt
                            '''
                        }
                    } catch (Exception e) {
                        echo "Failed to find credential 'Gemini_API_key': ${e.message}"
                        echo "Please check your Jenkins credentials and update the credentialsId"
                        throw e
                    }
                }
            }
        }

        stage('Compile (After Fix)') {
            steps {
                bat '''
                    javac src\\App.java
                '''
            }
        }
    }

    post {
        success {
            echo "✅ Build succeeded (auto-fix applied if needed)"
        }
        failure {
            echo "❌ Build failed even after Gemini auto-fix"
        }
    }
}
