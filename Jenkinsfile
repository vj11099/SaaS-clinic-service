pipeline {
    agent any

    environment {
        ENV_FILE = credentials('env-file')
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
                sh 'docker compose build'
            }
        }

        stage('Deploy') {
           steps {
                sh '''
                    cp ${ENV_FILE} ./SaaS-clinic-service/.env
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
