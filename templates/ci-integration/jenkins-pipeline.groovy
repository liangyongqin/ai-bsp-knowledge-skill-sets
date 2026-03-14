// templates/ci-integration/jenkins-pipeline.groovy
// Reference Jenkins pipeline for BSP Knowledge Skill Sets CI/CD integration.
// Adapt to your internal LAVA / CI setup.
//
// This file is a TEMPLATE — do not execute it directly.
// See docs/ci-integration.md (Phase 4, M4.3) for the full integration guide.

pipeline {
    agent any

    environment {
        PYTHON = 'python3.11'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install dependencies') {
            steps {
                sh "${PYTHON} -m pip install -r requirements.txt"
            }
        }

        stage('Initialise knowledge graph') {
            steps {
                sh "${PYTHON} knowledge-graph/schema/init_db.py"
            }
        }

        stage('Build base graph') {
            steps {
                sh "${PYTHON} scripts/build_base_graph.py"
            }
        }

        stage('Start MCP server') {
            steps {
                sh "nohup ${PYTHON} mcp/server.py &"
                sleep(time: 3, unit: 'SECONDS')
            }
        }

        stage('Run eval suite') {
            steps {
                sh "${PYTHON} -m pytest evals/run_evals.py --tb=short -q"
            }
            post {
                always {
                    archiveArtifacts artifacts: 'evals/scorecards/**', allowEmptyArchive: true
                }
            }
        }
    }

    post {
        failure {
            echo 'Eval regression failed — review scorecards for accuracy drift.'
        }
    }
}
