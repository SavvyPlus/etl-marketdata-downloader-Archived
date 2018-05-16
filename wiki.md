# Introduction:
This wiki page describes the standard model of CloudFormation for our cloud applications. It involves synchronizing GitHub repository to the CloudFormation, building lambdas, deploying lambdas and conducting different stages in CloudPipeline.

# Structure:
```	.
	├── cloudformation
	│   ├── clean-test-files-lambda.cfn.yaml
	│   ├── config
	│   │   ├── prod-market-xxx-stack-configuration.json
	│   │   └── test-market-xxx-stack-configuration.json
	│   └── lambda.cfn.yaml
	├── xxx
	│   ├── buildspec.yaml
	│   ├── data_downloader.py
	│   └── requirements.txt
	├── xxx-clean-test-files
	│   ├── buildspec.yaml
	│   ├── xxx_clean_test_files.py
	│   └── requirements.txt
	├── xxx-create-folders
	│   ├── buildspec.yaml
	│   ├── xxx_create_folders.py
	│   └── requirements.txt
	├── xxx-create-database
	│   ├── buildspec.yaml
	│   ├── xxx_create_database.py
	│   └── requirements.txt
	├── README.md
	└── xxx.cfn.yaml
```
`xxx-create-folders`, `xxx-create-database` and `xxx-clean-test-files` exist to work within the pipeline and they are called support lambdas. `xxx` is the core lambda that is actually doing the business processing and it is called business lambda.

# Main CloudFormation Template:
This section explains the two main CloudFormation templates: `xxx.cfn.yaml` and `cloudformation/lambda.cfn.yaml`.

## xxx.cfn.yaml:
`xxx.cfn.yaml` is the main CloudFormation configuration file which defines the overall CloudFormation stack. This file creates the common AWS IAM permissions for the lambdas, defines general parameters, defines the build steps to build the lambdas and specifies an AWS CodePipeline with various stages. It consists of sections: Parameters, Metadata, Resources, Roles etc.

### Parameters:
These are configuration parameters with default values and they are accessible within the xxx.cfn.yaml. For example, "ArtifactBucket" defines the name of S3 bucket for storing pipeline artifacts. When creating the stack using the CloudFormation console, we can change these values.

### Metadata(AWS::CloudFormation::Interface):
It defines how parameters are grouped and sorted in the AWS CloudFormation console.

### Resources:
These are the resources that CloudFormation will create when executing this stack.

#### Roles:
All the roles needed for creating and executing this stack.

#### SNSTopic:
It is used to send CodePipeline notification, which notifies the developer to decide whether to approve the test stack and create the production stack. The emails is referred from the parameters above.

#### CodeBuild:
It defines how the lambda code should be built and complied, including the OS version, compiler and dependencies.

#### Source:
```
Type: CODEPIPELINE
BuildSpec: 'market-data-downloader-clean-test-files/buildspec.yaml'
```
The `buildspec.yaml` defines how the lambda will be built


#### Pipeline:
It is the whole procedure of creating this stack.

* Fetch source file:
	The pipeline fetches everything in a git repository including source code and YAML files etc. The output of this stage is given the name SourceCode and this is then available to the following stages in the pipeline.
* Build lambda:
	This stage uses the output (SourceCode) of the previous stage to compile the lambda code. And it references the previously defined CodeBuild step (e.g.Configuration: ProjectName: !Ref CodeBuildDownloaderLambda) and after execution the output of this is called BuildYYYLambdaOutput (YYY is the name of the corresponding lambda function), which is a package of compiled code and can be used in later stages of the pipeline.
* TestStage:
	* CreateLambdasAndDependencies:

		It execute another CloudFormation template lambda.cfn.yaml which is responsible for deploying the lambdas built earlier in the CodePipeline and the dependencies that these lambdas rely on. In other words, this stage uses lambda.cfn.yaml to create the test stack (deploy all the lambdas and SNS, CloudWatchEvent...) and the deployment details are stored in lambda.cfn.yaml. Therefore, this stage should pass the location of artifacts (built lambda packages) to the Parameters section in lambda.cfn.yaml, which is achieved via the InputArtifacts section and the ParameterOverrides section.

	* ApproveTestStack:

    This stage sends a SNS notification to the developer. To progress to deploying to production, the developer has to click a button in the CodePipeline console to approve that the code running in the test stack is good.

		This prevents the scenario of accidentally deploying broken code as the developer can check that the code behaves as expected by, for example, uploading files into the test S3 buckets and seeing them being processed correctly.

	* CleanupTestFiles:

		After the developer approve in the last stage, this stage deletes any test files that were added to the test buckets etc. The methodology of this stage is similar to the CreateLambdasAndDependencies. The difference is that this stage uses `clean-test-files-lambda.cfn.yaml`

  * DeleteCleanupStack:

    asdada

  * DeleteTestStack:

	Finally, the test stack is deleted.

    Note: Deleting S3 buckets
    If during testing, a file was uploaded to a testing S3 bucket and was not removed before the ApproveTestStack is clicked, then the DeleteTestStack will fail to execute and the deployment will not progress to production.

* ProdStage:
  The ProdStage is similar to the TestStage, except it creates a changeset that it applies to the currently running production stack. This changeset captures all the differences in code and infrastructure between versions and allows the user to rollback to a prior version and know that it has reverted both the code and any infrastructure changes.

	* CreateChangeSet:
	Similar to CreateLambdasAndDependencies in TestStage, except it creates a ChangeSet that it applies to the currently running production stack. This ChangesSet captures all the differences in code and infrastructure between versions and allows the user to rollback to a prior version and know that it has reverted both the code and any infrastructure changes.

	* ApproveChangeSet:
	It is similar to ApproveTestStack in TestStage and notify the developer to manually approve the changes.

	* ExecuteChangeSet:
	It execute the ChangeSet once the developer manually approves the changes.

###Outputs (ArtifactBucket):
It defines a S3 bucket holding all the OutputArtifacts of any pipeline stage.

##cloudformation/lambda.cfn.yaml:
This CloudFormation template is invoked by the CodePipeline in `xxx.cfn.yaml`.
###Parameters:
These are the S3 bucket paths of the built lambda and the paths are passed from `xxx.cfn.yaml`.
###Resources:
These resources are used to define SQS, SNS, Permission and deploy lambdas.
###Outputs:
The identities of some components (e.g. The ARN of every lambda)

#A little story:
* The whole procedure is about a master (`xxx.cfn.yaml`) assigning a task of repairing an old house (a running production stack) to a worker (`lambda.cfn.yaml`).
* The master needs to buy some raw materials (fetch source file) and turn these materials into mortar (build lambda using CodeBuild).
* Afterwards, the master tells the worker where the mortar is (pass artifacts to `lambda.cfn.yaml`) and ask him to build a prototype(the test stack).
* The worker knows how to do his job(the details in lambda.cfn.yaml).
* Once the worker finishes the prototype, he asks (SNS notification) the master to come to the construction site (CodePipeline console) and the master decides
* whether to approve the prototype (ApproveTestStack).
* Once the master approves, the prototype will be destroyed by a terminator called "clean-test-files".
* Then, the master asks the worker to capture the difference between the prototype and the old house and then repair the old house by applying the difference (executing ChangeSet). Mission completed!

Note:
	When there is no old house (existing production stack), repairing an old house becomes building a house (creating a production stack).

#Conclusion:
	In general, there is a top level cloudformation template that creates the codepipeline that is then used to run the lower level template that deploys the built lambdas

Note:
# Partition
The partition lambda is for partitioning the data in Athena for downloaders that push their data to Athena.
