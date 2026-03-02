pipeline {
    agent any

    environment {
        ENV_FILE = credentials('saas_clinic_api_keys')
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

//        stage('Test') {
//            steps {
//                sh '''
//                    docker build -t ${IMAGE_NAME}:test .
//                    docker run --rm \
//                        -e DATABASE_URL=${DATABASE_URL} \
//                        -e SECRET_KEY=${SECRET_KEY} \
//                        -e FERNET_KEY=${FERNET_KEY} \
//                        -e DEBUG=False \
//                        ${IMAGE_NAME}:test \
//                        python manage.py test --noinput
//                '''
//            }
//        }

        stage('Build') {
            steps {
                sh '''
                    cp $ENV_FILE .env
                    docker compose build
                '''
            }
        }

        stage('Deploy') {
            steps {
                sh '''
                    cp $ENV_FILE .env
                    docker compose down
                    docker compose up -d
                '''
            }
        }
    }

    post {
        success {
            echo 'Deployed successfully'
        }
        failure {
            echo 'Pipeline failed — app was not redeployed'
        }
    }
}
