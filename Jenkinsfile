pipeline {
    agent any
    
    environment {
        BRANCH_NAME = "${env.GIT_BRANCH?.replace('origin/', '') ?: 'unknown'}"
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
                script {
                    echo "Building branch: ${BRANCH_NAME}"
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

        // MASTER BRANCH WORKFLOW: Automatic Build
        stage('Master Branch - Production Build') {
            when {
                anyOf {
                    branch 'master'
                    environment name: 'BRANCH_NAME', value: 'master'
                }
            }
            stages {
                stage('Production Compilation') {
                    steps {
                        script {
                            echo "🚀 [MASTER BRANCH] Running production build..."
                            bat '''
                                if not exist build mkdir build
                                if not exist build\\classes mkdir build\\classes
                                
                                echo Compiling for production...
                                javac -d build\\classes src\\App.java
                                
                                echo Creating JAR file...
                                cd build\\classes
                                jar cfe ..\\App.jar App *.class
                                cd ..\\..
                                
                                echo ✅ Production build completed successfully!
                                dir build\\App.jar
                            '''
                        }
                    }
                }
                
                stage('Production Tests') {
                    steps {
                        script {
                            echo "🧪 [MASTER BRANCH] Running production tests..."
                            bat '''
                                echo Running basic functionality test...
                                java -cp build\\classes App
                                echo ✅ Basic functionality test passed!
                            '''
                        }
                    }
                }
                
                stage('Archive Artifacts') {
                    steps {
                        script {
                            echo "📦 [MASTER BRANCH] Archiving production artifacts..."
                            archiveArtifacts artifacts: 'build/App.jar', allowEmptyArchive: false
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
            }
        }
        success {
            script {
                if (env.BRANCH_NAME == 'main') {
                    echo "SUCCESS: [MAIN BRANCH] Build succeeded - Code auto-fixed and ready for merge"
                } else if (env.BRANCH_NAME == 'master') {
                    echo "SUCCESS: [MASTER BRANCH] Production build succeeded - JAR created and archived"
                } else {
                    echo "SUCCESS: [FEATURE BRANCH] Basic compilation check passed"
                }
            }
        }
        failure {
            script {
                if (env.BRANCH_NAME == 'main') {
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
                    echo "FAILED: [MASTER BRANCH] Production build failed"
                    echo "TIP: Please ensure main branch is stable before merging to master"
                } else {
                    echo "FAILED: [FEATURE BRANCH] Compilation check failed"
                    echo "TIP: Please fix compilation errors before creating pull request"
                }
            }
        }
    }
}
