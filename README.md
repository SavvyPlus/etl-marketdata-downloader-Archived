# Intro
This project contains the lambda code and infrastructure to build a codepipeline for processing ASX files.

# Structure
```
.
├── cloudformation
│   ├── clean-test-files.cfn.yaml
│   ├── config
│   │   ├── prod-market-data-downloader-stack-configuration.json
│   │   └── test-market-data-downloader-stack-configuration.json
│   └── lambda.cfn.yaml
├── data-downloader
│   ├── buildspec.yaml
│   ├── data_downloader.py
│   └── requirements.txt
├── data-harvester
│   ├── buildspec.yaml
│   ├── data_harvester.py
│   └── requirements.txt
├── market-data-downloader.cfn.yaml
├── market-data-downloader-clean-test-files
│   ├── buildspec.yaml
│   ├── market_data_downloader_clean_test_files.py
│   └── requirements.txt
├── market-data-downloader-create-folders
│   ├── buildspec.yaml
│   ├── market_data_downloader_create_folders.py
│   └── requirements.txt
└── README.md
```

The project contains a directory for the harvester lambda `data-harvester` and a directory for the downloader lambda `data-downloader`
Each directory contains the lambda python code and the corresponding requirements file.  The `buildspec.yaml` file is used by AWS CodeBuild to build the lambda with it's dependencies for deploying into the AWS Lambda infrastructure.

# Cloudformation
The main cloudformation file `market-data-downloader.cfn.yaml` defines the MarketDataDownloader stack.  This file creates the
common AWS IAM permissions for the lambdas, defines general parameters, defines the build steps to build the lambdas and specifies an AWS CodePipeline with various stages.

## Sections
The `market-data-downloader.cfn.yaml` file is split into sections; `Parameters`, `Metadata`, `Resources` and `Outputs`

### Parameters
These are used to configure the cloudformation stack and can be used to parameterise or override defaults in the cloudformation template that deploys the lambdas.

### Resources
These are the resources that cloudformation will create when executing this stack. In this stack, the resources include Roles with permissions, CodeBuild definitions for the lambdas, SNS topics for communication and the CodePipeline.

### CodeBuild Resource
```
CodeBuildDownloaderLambda:
  Type: AWS::CodeBuild::Project
  DependsOn: CloudFormationRole
  Properties:
    Artifacts:
      Type: CODEPIPELINE
    Environment:
      ComputeType: BUILD_GENERAL1_SMALL
      Image: aws/codebuild/python:3.5.2
      Type: LINUX_CONTAINER
    Name: 'CodeBuildDownloaderLambda'
    ServiceRole: !GetAtt CodeBuildRole.Arn
    Source:
      Type: CODEPIPELINE
      BuildSpec: 'data-downloader/buildspec.yaml'
    TimeoutInMinutes: 5 # must be between 5 minutes and 8 hours
    Cache:
      Location: 'foamdino-etl-build-cache'
      Type: S3
```
This is an example of one of the CodeBuild resources that is part of the stack.  In this we specify the version of the lambda container linux we want to use to build and we specify the `buildspec` file that should be executed to create the output.

### buildspec
```
version: 0.2

phases:
  install:
    commands:
      - pip install --upgrade pip
      - pip install -r data-downloader/requirements.txt -t data-downloader

artifacts:
  base-directory: data-downloader
  files:
    - '**/*'
  type: zip

cache:
  paths:
    - /root/.cache/pip
```
This is the corresponding `buildspec.yaml` for the CodeBuild step.  There can be many commands executed as part of various phases: https://docs.aws.amazon.com/codebuild/latest/userguide/build-spec-ref.html in this case though we just need to ensure that the dependencies are installed, so we use the `requirements.txt` file and `pip` to achieve this.

## CodePipeline
The core part of this cloudformation template is the `CodePipeline` definition.  This definition describes the CodePipeline and the stages that it is built from.

### Stage 1: GitHubSource
```
Name: GitHubSource
  Actions:
    - Name: TemplateSource
      ActionTypeId:
        Category: Source
        Owner: ThirdParty
        Version: 1
        Provider: GitHub
      Configuration:
        Owner: !Ref 'GitHubOwner'
        Repo: !Ref 'GitHubRepo'
        Branch: !Ref 'GitHubBranch'
        OAuthToken: !Ref 'GitHubToken'
      OutputArtifacts:
        - Name: SourceCode
      RunOrder: 1
```
This stage connects to the specified git repository and branch and downloads the source code.  The output of this stage is given the name `SourceCode` and this is then available to the following stages in the pipeline.

### Stage 2: BuildMarketdataDownloaderLambdas
```
- Name: BuildMarketdataDownloaderLambdas
  Actions:
    - Name: BuildDownloaderLambda
      ActionTypeId:
        Category: Build
        Owner: AWS
        Provider: CodeBuild
        Version: 1
      Configuration:
        ProjectName: !Ref CodeBuildDownloaderLambda
      InputArtifacts:
        - Name: SourceCode
      OutputArtifacts:
        - Name: BuildDownloaderLambdaOutput
```
This stage uses the output of the previous stage; `SourceCode` as the input for the task, which in this case is to run a `CodeBuild` task.  This task references the previously defined codebuild step and after execution the output of this is called `BuildDownloaderLambdaOutput`, which can be used in later stages of the pipeline.

### Stage 3: TestStage
This stage is broken into 3 pieces: `CreateLambdasAndDependencies`, `ApproveTestStack`, `DeleteTestStack`.
```
- Name: CreateLambdasAndDependencies
  ActionTypeId:
    Category: Deploy
    Owner: AWS
    Provider: CloudFormation
    Version: '1'
  InputArtifacts:
    - Name: SourceCode
    - Name: BuildDownloaderLambdaOutput
    - Name: BuildHarvesterLambdaOutput
    - Name: BuildMarketdataDownloaderCreateFoldersLambdaOutput
  Configuration:
    ActionMode: REPLACE_ON_FAILURE
    RoleArn: !GetAtt [CFNRole, Arn]
    StackName: !Ref TestStackName
    Capabilities: CAPABILITY_NAMED_IAM
    TemplateConfiguration: !Sub "SourceCode::cloudformation/config/${TestStackConfig}"
    TemplatePath: "SourceCode::cloudformation/lambda.cfn.yaml"
    ParameterOverrides: !Sub |
      {
        "SourceLocation" : { "Fn::GetArtifactAtt" : ["SourceCode", "URL"] },
        "DownloaderLocation" : { "Fn::GetArtifactAtt" : ["BuildDownloaderLambdaOutput", "URL"] },
        "DownloaderKey" : { "Fn::GetArtifactAtt" : ["BuildDownloaderLambdaOutput", "ObjectKey"] },
        "HarvesterLocation" : { "Fn::GetArtifactAtt" : ["BuildHarvesterLambdaOutput", "URL"] },
        "HarvesterKey" : { "Fn::GetArtifactAtt" : ["BuildHarvesterLambdaOutput", "ObjectKey"] },
        "MarketdataDownloaderCreateFoldersLocation" : { "Fn::GetArtifactAtt" : ["BuildMarketdataDownloaderCreateFoldersLambdaOutput", "URL"] },
        "MarketdataDownloaderCreateFoldersKey" : { "Fn::GetArtifactAtt" : ["BuildMarketdataDownloaderCreateFoldersLambdaOutput", "ObjectKey"] }
      }
  RunOrder: '1'
```
The first stage in the pipeline runs a cloudformation task, but instead of the cloudformation stack being defined inline, this task references another cloudformation template `lambda.cfn.yaml` which is responsible for deploying the lambdas built earlier in the codepipeline and the dependencies that these lambdas rely on.  To access the source code retrieved from git earlier and the built lambdas, this cloudformation stack needs to have the references to these artifacts passed to it.  This is achieved via the `InputArtifacts` section and the `ParameterOverrides` section.

```
- Name: ApproveTestStack
  ActionTypeId:
    Category: Approval
    Owner: AWS
    Provider: Manual
    Version: '1'
  Configuration:
    NotificationArn: !Ref CodePipelineSNSTopic
    CustomData: !Sub 'Do you want to create a changeset against the production stack and delete the test stack?'
  RunOrder: '2'
```
To progress to deploying to production, a user has to manually approve that the code running in the test stack is good.  The approval is done via clicking a button in the code pipeline and entering a comment.  This prevents the scenario of accidentally deploying broken code as the developer can check that the code behaves as expected by uploading files into the test S3 buckets and seeing them being processed correctly.

The next stage deletes any test files that were added to the test buckets etc.
```
- Name: CleanupTestFiles
  ActionTypeId:
    Category: Deploy
    Owner: AWS
    Provider: CloudFormation
    Version: '1'
  InputArtifacts:
    - Name: SourceCode
    - Name: BuildMarketdataDownloaderDeleteTestFilesLambdaOutput
  Configuration:
    ActionMode: REPLACE_ON_FAILURE
    RoleArn: !GetAtt [CFNRole, Arn]
    StackName: !Ref CleanupStackName
    Capabilities: CAPABILITY_NAMED_IAM
    TemplateConfiguration: !Sub "SourceCode::cloudformation/config/${TestStackConfig}"
    TemplatePath: "SourceCode::cloudformation/clean-test-files-lambda.cfn.yaml"
    ParameterOverrides: !Sub |
      {
        "SourceLocation" : { "Fn::GetArtifactAtt" : ["SourceCode", "URL"] },
        "MarketdataDownloaderDeleteTestFilesLocation" : { "Fn::GetArtifactAtt" : ["BuildMarketdataDownloaderDeleteTestFilesLambdaOutput", "URL"] },
        "MarketdataDownloaderDeleteTestFilesKey" : { "Fn::GetArtifactAtt" : ["BuildMarketdataDownloaderDeleteTestFilesLambdaOutput", "ObjectKey"] }
      }
  RunOrder: '3'
```
Next the test stack is deleted.
```
Name: DeleteTestStack
  ActionTypeId:
    Category: Deploy
    Owner: AWS
    Provider: CloudFormation
    Version: '1'
  Configuration:
    ActionMode: DELETE_ONLY
    RoleArn: !GetAtt [CFNRole, Arn]
    StackName: !Ref TestStackName
  RunOrder: '4'
```
After a user has approved the deployment, the test stack is deleted before the prod stack is created.

#### Note: Deleting S3 buckets
If during testing, a file was uploaded to a testing S3 bucket and was not removed before the `ApproveTestStack` is clicked, then the `DeleteTestStack` will fail to execute and the deployment will not progress to production.

### Stage 4: ProdStage
The `ProdStage` is similar to the `TestStage`, except it creates a changeset that it applies to the currently running production stack.  This changeset captures all the differences in code and infrastructure between versions and allows the user to rollback to a prior version and know that it has reverted both the code and any infrastructure changes.

#### Note: Change Sets
Unlike the `TestStage`, changes to the `ProdStage` are applied via an aws changeset https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-changesets.html this is because the `TestStage` is recreated from scratch each time, unlike the `ProdStage` which needs to have changes captured in a fashion that allows them to be rolled back safely should they be incomplete or incorrect.
