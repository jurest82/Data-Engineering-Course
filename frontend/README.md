# README

- [README](#readme)
  - [Summary](#summary)
  - [Setup](#setup)
    - [Development container](#development-container)
    - [Environment variables](#environment-variables)
    - [Dependencies](#dependencies)
    - [Deployment](#deployment)
    - [Remove](#remove)
  - [Glossary](#glossary)
    - [AWS environment variables: `../.envs/aws.env`](#aws-environment-variables-envsawsenv)
    - [Serverless Framework environment variables: `../.envs/sls.env`](#serverless-framework-environment-variables-envsslsenv)
    - [Service environment variables: `.envs/config.env`](#service-environment-variables-envsconfigenv)

---

## Summary

`Data Engineering Course Frontend` is the chat UI for the Bedrock AgentCore agent described in the root `README.md`: a static site (vanilla HTML/CSS/JS, no build tooling) served from S3 through CloudFront, that talks to the `ChatStream` Lambda (`backend/serverless/bedrock`) over a WebSocket.

---

## Setup

### Development container

This steps are tailored to work with Visual Studio Code, but you are free to chose a different IDE and make necessary adjustments to the setup.

1. Install `ms-vscode-remote.remote-containers` extension. If you don't know how to do that follow this steps: <https://code.visualstudio.com/docs/editor/extension-gallery#_install-an-extension>
2. Open this project's folder in Visual Studio Code. The extension will detect a container configuration and will ask you if you want to reopen the project un the container. Accept.

### Environment variables

At `.envs` folder, you'll need to create env files with the variables described [here](#glossary).

### Dependencies

`serverless` user must be created using `IAM` at `AWS Organization account`, and it's credentials configured in `../.envs/aws.env`.

### Deployment

There's a single stack, `serverless/site`, deployed with its own `deploy.sh` instead of a bare `serverless deploy` -- it resolves the chat WebSocket URL from SSM, generates `dist/config.js` with it, syncs `dist/` to the site's S3 bucket, and invalidates the CloudFront cache, all in one step:

```sh
cd serverless/site && ./deploy.sh [stage]
```

This stack must be deployed **after** `backend/serverless/bedrock` (it needs that stack's `ChatWebSocketUrl` SSM parameter already published).

### Remove

You must use `Serverless Framework` remove command as primary option: <https://www.serverless.com/framework/docs/providers/aws/cli-reference/remove/>

```sh
cd serverless/site && serverless remove
```

If `remove` command fails for whatever reason, you'll need to investigate the reason using `AWS Console` at your browser, solve the issue and then re-attempt the `remove` command.

---

## Glossary

### AWS environment variables: `../.envs/aws.env`

- `AWS_ACCESS_KEY_ID`: _Access Key_ used to deploy Cloud Formation stack to AWS cloud. The owner of the _Access Key_ need to have sufficient IAM permissions to perform the deployment process.
- `AWS_SECRET_ACCESS_KEY`: _Secret Access Key_ that matches the _Access Key_
- `AWS_DEFAULT_REGION`: Region where you intend to deploy the stack
- `AWS_DEFAULT_OUTPUT`: Default response format for AWS CLI commands

### Serverless Framework environment variables: `../.envs/sls.env`

- `SERVERLESS_ACCESS_KEY`: Serverless _Secret API Key_. Needed to deploy stack information to Serverless cloud.

### Service environment variables: `.envs/config.env`

- `DEVELOPER`: Same username as you corporate email without domain part. It's used to guarantee some unique resource names at deploy
